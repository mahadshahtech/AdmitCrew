import json
import re

from fastapi import APIRouter
from pydantic import BaseModel

from agents.coordinator_agent import coordinator_agent
from agents.lead_agent import lead_agent
from agents.university_agent import university_agent
from database import get_connection


router = APIRouter(prefix="/api/chat", tags=["Student Chat"])


class ChatMessage(BaseModel):
    session_id: str
    message: str


# =========================================================
# HELPERS
# =========================================================

def clean_number(value: str) -> float | None:
    cleaned = value.replace("%", "").strip()

    try:
        return float(cleaned)
    except ValueError:
        return None


def get_session(session_id: str):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM chat_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    ).fetchone()

    conn.close()

    if not row:
        return None

    session = dict(row)

    try:
        session["data"] = json.loads(session["data_json"])
    except json.JSONDecodeError:
        session["data"] = {}

    return session


def create_session(session_id: str):
    conn = get_connection()

    # Starting the same session ID again resets that session.
    conn.execute(
        """
        INSERT INTO chat_sessions (
            session_id,
            step,
            data_json,
            lead_id,
            conversation_id
        )
        VALUES (?, 'name', '{}', NULL, NULL)

        ON CONFLICT(session_id)
        DO UPDATE SET
            step = 'name',
            data_json = '{}',
            lead_id = NULL,
            conversation_id = NULL,
            updated_at = CURRENT_TIMESTAMP
        """,
        (session_id,),
    )

    conn.commit()
    conn.close()

    return get_session(session_id)


def update_session(
    session_id: str,
    *,
    step: str | None = None,
    data: dict | None = None,
    lead_id: int | None = None,
    conversation_id: int | None = None,
):
    session = get_session(session_id)

    if not session:
        return None

    new_step = step if step is not None else session["step"]
    new_data = data if data is not None else session["data"]

    new_lead_id = (
        lead_id
        if lead_id is not None
        else session["lead_id"]
    )

    new_conversation_id = (
        conversation_id
        if conversation_id is not None
        else session["conversation_id"]
    )

    conn = get_connection()

    conn.execute(
        """
        UPDATE chat_sessions
        SET
            step = ?,
            data_json = ?,
            lead_id = ?,
            conversation_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE session_id = ?
        """,
        (
            new_step,
            json.dumps(new_data),
            new_lead_id,
            new_conversation_id,
            session_id,
        ),
    )

    conn.commit()
    conn.close()

    return get_session(session_id)


def create_conversation(lead_id: int) -> int:
    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO conversations (lead_id)
        VALUES (?)
        """,
        (lead_id,),
    )

    conversation_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return conversation_id


def save_message(
    conversation_id: int,
    sender: str,
    content: str,
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO messages (
            conversation_id,
            sender,
            content
        )
        VALUES (?, ?, ?)
        """,
        (
            conversation_id,
            sender,
            content,
        ),
    )

    conn.commit()
    conn.close()


def format_coordinator_response(result: dict) -> str:
    coordinator_result = result.get("result", {})

    # Exact university data returned from SQLite
    if (
        coordinator_result.get("answered")
        and coordinator_result.get("data")
    ):
        data = coordinator_result["data"]

        return (
            f"{data['university']} — {data['program']}\n\n"
            f"Country: {data['country']}\n"
            f"Fee per year: {data['fee_per_year']}\n"
            f"Deadline: {data['deadline']}\n"
            f"Minimum marks: {data['min_marks']}%\n"
            f"Minimum IELTS: {data['min_ielts']}\n"
            f"Documents needed: {data['documents_needed']}"
        )

    message = coordinator_result.get("message")

    if message:
        return message

    return (
        "I couldn't process that request right now. "
        "Please try again shortly."
    )


# =========================================================
# START CHAT
# =========================================================

@router.post("/start")
def start_chat(session_id: str):
    create_session(session_id)

    return {
        "session_id": session_id,
        "agent": "lead_agent",
        "message": (
            "Hi! 👋 Welcome to AdmitCrew. "
            "I'll help you get started with your study abroad enquiry. "
            "What's your full name?"
        ),
    }


# =========================================================
# HISTORY
# =========================================================

@router.get("/history")
def get_chat_history(session_id: str):
    session = get_session(session_id)
    if not session:
        return {"error": "Session not found.", "messages": []}

    lead_id = session.get("lead_id")
    if not lead_id:
        return {"messages": []}

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT m.id, m.sender, m.content, m.created_at
        FROM messages m
        JOIN conversations c ON c.id = m.conversation_id
        WHERE c.lead_id = ?
        ORDER BY m.created_at ASC, m.id ASC
        """,
        (lead_id,),
    ).fetchall()
    conn.close()

    messages = [
        {
            "id": str(row["id"]),
            "role": "student" if row["sender"] == "student" else "admitcrew" if row["sender"] == "assistant" else "staff",
            "text": row["content"],
            "agent": row["sender"],
            "timestamp": row["created_at"],
        }
        for row in rows
    ]

    return {"messages": messages}


def handle_student_intake(session_id: str, message: str, session: dict):
    current_data = session["data"]
    countries = sorted({item["country"] for item in university_agent.get_all_programs()})
    profile = lead_agent.validate_intake_state(current_data, countries)

    def next_missing_field(values: dict) -> str | None:
        ordered_fields = ["name", "phone", "preferred_country", "marks", "ielts", "budget"]
        for field in ordered_fields:
            if field == "ielts":
                if "ielts_score" not in values and values.get("ielts_not_taken") is not True:
                    return "ielts_score"
            elif field not in values:
                return field
        return None

    expected_field = next_missing_field(profile) or session["step"]
    extracted = coordinator_agent.extract_intake_fields(
        message=message,
        expected_field=expected_field,
        current_profile=profile,
    )
    profile.update(extracted)
    profile = lead_agent.validate_intake_state(profile, countries)

    if profile.get("phone"):
        existing = lead_agent.find_by_phone(profile["phone"])
        if existing:
            conversation_id = create_conversation(existing["id"])
            saved_profile = lead_agent.validate_intake_state(existing, countries)
            if current_data.get("ielts_not_taken") is True and existing.get("ielts_score") is None:
                saved_profile["ielts_not_taken"] = True
            context = current_data.get("conversation_context", {})
            update_session(
                session_id,
                step="assistant",
                data={**saved_profile, "conversation_context": context},
                lead_id=existing["id"],
                conversation_id=conversation_id,
            )
            save_message(conversation_id, "student", message)
            reply = (
                f"Welcome back, {existing['name']}! I found your existing profile, "
                "so I won't create another student record. You can ask about "
                "verified programs, requirements, or documents."
            )
            save_message(conversation_id, "assistant", reply)
            return {
                "agent": "lead_agent",
                "existing_lead": True,
                "lead": existing,
                "conversation_id": conversation_id,
                "message": reply,
            }

    if next_missing_field(profile) is None:
        lead_result = lead_agent.save_lead(
            name=profile["name"],
            phone=profile["phone"],
            preferred_country=profile["preferred_country"],
            marks=profile["marks"],
            ielts_score=profile.get("ielts_score"),
            budget=profile["budget"],
        )
        lead = lead_result["lead"]
        conversation_id = create_conversation(lead["id"])
        context = current_data.get("conversation_context", {})
        persisted_profile = {
            "name": lead["name"],
            "phone": lead["phone"],
            "preferred_country": lead["preferred_country"],
            "marks": lead["marks"],
            "ielts_score": lead["ielts_score"],
            "ielts_not_taken": profile.get("ielts_not_taken", False),
            "budget": lead["budget"],
            "conversation_context": context,
        }
        update_session(
            session_id,
            step="assistant",
            data=persisted_profile,
            lead_id=lead["id"],
            conversation_id=conversation_id,
        )
        save_message(
            conversation_id,
            "system",
            (
                "Lead intake completed with validated fields. "
                f"Lead ID: {lead['id']}; Preferred country: {lead['preferred_country']}; "
                f"Marks: {lead['marks']}; IELTS: {lead['ielts_score']}; Budget: {lead['budget']}."
            ),
        )
        reply = (
            f"Thanks, {lead['name']}! Your validated profile has been saved. "
            "You can now ask about universities, programs, requirements, or documents."
        )
        save_message(conversation_id, "assistant", reply)
        return {
            "agent": "lead_agent",
            "saved": True,
            "action": lead_result["action"],
            "lead": lead,
            "conversation_id": conversation_id,
            "message": reply,
        }

    field = next_missing_field(profile)
    next_prompts = {
        "name": "What's your full name?",
        "phone": "What's the best phone number to reach you on?",
        "preferred_country": "Which country would you prefer to study in?",
        "marks": "What percentage did you get in your latest studies?",
        "ielts_score": "What is your IELTS overall score? If you haven't taken IELTS, say 'not taken'.",
        "budget": "What's your approximate study budget? A range or 'flexible' is fine.",
    }
    interest_acknowledgement = ""
    if field == "name" and re.search(
        r"\b(?:study|studying|course|program|university|college)\b",
        message,
        re.IGNORECASE,
    ):
        interest_acknowledgement = (
        "Got it — I can help with those study plans. "
    )

    labels = {
        "name": "your name", "phone": "your phone number",
        "preferred_country": "your destination country", "marks": "your marks",
        "ielts_score": "your IELTS status", "budget": "your budget",
    }
    captured = [labels[key] for key in extracted if key in labels]
    acknowledgement = f"I have {', '.join(captured)}. " if captured else ""
    reply = interest_acknowledgement + acknowledgement + next_prompts[field]
    update_session(session_id, step={"ielts_score": "ielts"}.get(field, field), data=profile)
    return {"agent": "lead_agent", "saved": False, "message": reply}


# =========================================================
# SEND MESSAGE
# =========================================================

@router.post("/message")
def _send_message_legacy(data: ChatMessage):
    session = get_session(data.session_id)

    if not session:
        return {
            "error": "Session not found.",
            "message": "Please start a new chat first.",
        }

    step = session["step"]
    student_data = session["data"]
    message = data.message.strip()
    
    if step != "assistant":
        return handle_student_intake(
            session_id=data.session_id,
            message=message,
            session=session,
    )

    # -----------------------------------------------------
    # NAME
    # -----------------------------------------------------

    if step == "name":
        student_data["name"] = message

        update_session(
            data.session_id,
            step="phone",
            data=student_data,
        )

        return {
            "agent": "lead_agent",
            "message": "Nice to meet you! What's your phone number?",
        }

    # -----------------------------------------------------
    # PHONE
    # -----------------------------------------------------

    if step == "phone":
        student_data["phone"] = message

        existing = lead_agent.find_by_phone(message)

        if existing:
            conversation_id = create_conversation(existing["id"])

            update_session(
                data.session_id,
                step="assistant",
                data=student_data,
                lead_id=existing["id"],
                conversation_id=conversation_id,
            )

            save_message(
                conversation_id,
                "student",
                message,
            )

            reply = (
                f"Welcome back, {existing['name']}! 👋 "
                "I found your existing details, so I won't create "
                "another student record. You can now ask me about "
                "universities, programs, requirements, or documents."
            )

            save_message(
                conversation_id,
                "assistant",
                reply,
            )

            return {
                "agent": "lead_agent",
                "existing_lead": True,
                "lead": existing,
                "conversation_id": conversation_id,
                "message": reply,
            }

        update_session(
            data.session_id,
            step="country",
            data=student_data,
        )

        return {
            "agent": "lead_agent",
            "message": "Which country would you prefer to study in?",
        }

    # -----------------------------------------------------
    # COUNTRY
    # -----------------------------------------------------

    if step == "country":
        student_data["preferred_country"] = message

        update_session(
            data.session_id,
            step="marks",
            data=student_data,
        )

        return {
            "agent": "lead_agent",
            "message": (
                "What percentage marks did you get "
                "in your latest studies?"
            ),
        }

    # -----------------------------------------------------
    # MARKS
    # -----------------------------------------------------

    if step == "marks":
        marks = clean_number(message)

        if marks is None or marks < 0 or marks > 100:
            return {
                "agent": "lead_agent",
                "message": (
                    "Please enter your marks as a percentage, "
                    "for example 78%."
                ),
            }

        student_data["marks"] = marks

        update_session(
            data.session_id,
            step="ielts",
            data=student_data,
        )

        return {
            "agent": "lead_agent",
            "message": (
                "What is your IELTS overall score? "
                "If you haven't taken IELTS yet, type 'not taken'."
            ),
        }

    # -----------------------------------------------------
    # IELTS
    # -----------------------------------------------------

    if step == "ielts":
        if message.lower() in {
            "not taken",
            "not taken yet",
            "no",
            "none",
        }:
            student_data["ielts_score"] = None

        else:
            score = clean_number(message)

            if score is None or score < 0 or score > 9:
                return {
                    "agent": "lead_agent",
                    "message": (
                        "Please enter an IELTS score between 0 and 9, "
                        "or type 'not taken'."
                    ),
                }

            student_data["ielts_score"] = score

        update_session(
            data.session_id,
            step="budget",
            data=student_data,
        )

        return {
            "agent": "lead_agent",
            "message": (
                "Finally, what's your approximate study budget?"
            ),
        }

    # -----------------------------------------------------
    # BUDGET / SAVE NEW LEAD
    # -----------------------------------------------------

    if step == "budget":
        student_data["budget"] = message

        result = lead_agent.save_lead(**student_data)
        lead = result["lead"]

        conversation_id = create_conversation(lead["id"])

        update_session(
            data.session_id,
            step="assistant",
            data=student_data,
            lead_id=lead["id"],
            conversation_id=conversation_id,
        )

        intake_summary = (
            f"Lead intake completed. "
            f"Name: {lead['name']}; "
            f"Phone: {lead['phone']}; "
            f"Preferred country: {lead['preferred_country']}; "
            f"Marks: {lead['marks']}; "
            f"IELTS: {lead['ielts_score']}; "
            f"Budget: {lead['budget']}."
        )

        save_message(
            conversation_id,
            "system",
            intake_summary,
        )

        reply = (
            f"Thanks, {lead['name']}! ✅ "
            "Your details have been saved successfully. "
            "You can now ask me about universities, programs, "
            "requirements, or documents."
        )

        save_message(
            conversation_id,
            "assistant",
            reply,
        )

        return {
            "agent": "lead_agent",
            "saved": True,
            "action": result["action"],
            "lead": lead,
            "conversation_id": conversation_id,
            "message": reply,
        }

    # -----------------------------------------------------
    # COORDINATOR / NORMAL STUDENT CHAT
    # -----------------------------------------------------

    if step == "assistant":
        lead_id = session["lead_id"]
        conversation_id = session["conversation_id"]

        if not lead_id or not conversation_id:
            return {
                "error": "Chat session is incomplete.",
                "message": "Please start a new chat.",
            }

        save_message(
            conversation_id,
            "student",
            message,
        )

        conversation_context = session["data"].get("conversation_context", {})
        profile = {k: v for k, v in session["data"].items() if k != "conversation_context"}

        result = coordinator_agent.handle_message(
            message=message,
            lead_id=lead_id,
            conversation_id=conversation_id,
            conversation_context=conversation_context,
            profile=profile,
        )

        reply = format_coordinator_response(result)

        save_message(
            conversation_id,
            "assistant",
            reply,
        )

        # Update session with conversation context from coordinator
        context_update = result.get("context_update")
        if context_update:
            session = get_session(data.session_id)
            if session:
                current_context = session["data"].get("conversation_context", {})
                current_context.update(context_update)
                update_session(data.session_id, data={**session["data"], "conversation_context": current_context})

        coordinator = result.get("coordinator", {})

        return {
            "agent": coordinator.get("agent"),
            "conversation_id": conversation_id,
            "message": reply,
            "details": result,
        }

    return {
        "error": "Unknown chat state.",
        "message": "Please start a new chat.",
    }