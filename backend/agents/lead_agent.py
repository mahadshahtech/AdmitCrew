import re

from database import get_connection


class LeadAgent:
    """
    Handles creation and updating of student leads.

    The phone number is the unique identifier so the same student
    cannot accidentally become multiple leads.
    """

    @staticmethod
    def normalize_phone(phone: str) -> str:
        return "".join(char for char in phone if char.isdigit())

    @classmethod
    def validate_full_name(cls, value: str | None, message: str = "") -> str | None:
        if not isinstance(value, str):
            return None
        candidate = " ".join(value.strip().split())
        words = candidate.split()
        if not 2 <= len(words) <= 5:
            return None
        if not re.fullmatch(r"[^\W\d_]+(?:[.'’-][^\W\d_]+)*(?:\s+[^\W\d_]+(?:[.'’-][^\W\d_]+)*){1,4}", candidate, re.UNICODE):
            return None

        normalized_message = message.casefold()
        intent_markers = (
            "want to study", "looking to study", "study computer science",
            "study in", "apply to", "university", "program", "course",
            "tuition", "deadline", "ielts", "marks", "percentage",
        )
        has_name_marker = re.search(
            r"\b(?:my name is|i am|i'm|this is|name is)\b",
            normalized_message,
        ) is not None
        if not has_name_marker and any(marker in normalized_message for marker in intent_markers):
            return None
        if candidate.casefold() in {"computer science", "business management", "data science"}:
            return None
        return candidate

    @classmethod
    def extract_profile_fields(
        cls,
        message: str,
        expected_field: str,
        catalog_countries: list[str],
        suggested_fields: dict | None = None,
    ) -> dict:
        """Extract only validated onboarding fields, using model suggestions as hints."""
        text = message.strip()
        normalized = text.casefold()
        extracted = {}
        suggestions = suggested_fields or {}

        name_match = re.search(
            r"\b(?:my name is|i am|i'm|this is|name is)\s+(.+)",
            text,
            re.IGNORECASE,
        )
        name_candidate = None
        if name_match:
            name_candidate = re.split(
                r"\b(?:from|and|but|i have|i got|my phone|phone is|i want|i plan)\b|[,.;!?]",
                name_match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
        elif expected_field == "name":
            name_candidate = re.split(r"[,.;!?]", text, maxsplit=1)[0]

        suggested_name = suggestions.get("name")
        if suggested_name and str(suggested_name).casefold() in normalized:
            name_candidate = suggested_name
        valid_name = cls.validate_full_name(name_candidate, text)
        if valid_name:
            extracted["name"] = valid_name

        phone_match = re.search(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)", text)
        phone_candidate = phone_match.group(0).strip() if phone_match else suggestions.get("phone")
        if phone_candidate:
            phone_text = str(phone_candidate)
            phone_digits = cls.normalize_phone(phone_text)
            digits_in_message = cls.normalize_phone(text)
            if 10 <= len(phone_digits) <= 15 and (
                phone_digits in digits_in_message
                or expected_field == "phone" and phone_digits == digits_in_message
            ):
                extracted["phone"] = phone_text

        country_candidate = None
        for country in catalog_countries:
            match = re.search(rf"(?<!\w){re.escape(country)}(?!\w)", text, re.IGNORECASE)
            if not match:
                continue
            prefix = text[:match.start()].casefold()
            destination_context = re.search(
                r"\b(?:study|studying|apply|applying|prefer|planning|destination|move)\b",
                prefix,
            ) is not None
            if text.strip().casefold() == country.casefold() and expected_field == "preferred_country":
                destination_context = True
            if destination_context:
                country_candidate = country
                break
        suggested_country = suggestions.get("preferred_country")
        if suggested_country and any(
            str(suggested_country).casefold() == country.casefold()
            and re.search(rf"(?<!\w){re.escape(country)}(?!\w)", text, re.IGNORECASE)
            for country in catalog_countries
        ):
            country_candidate = next(
                country for country in catalog_countries
                if str(suggested_country).casefold() == country.casefold()
            )
        if country_candidate:
            extracted["preferred_country"] = country_candidate

        marks_match = re.search(
            r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:marks?)?"
            r"|(?:marks?|percentage|percent)\s*(?:are|is|of|at|:)?\s*(\d{1,3}(?:\.\d+)?)\s*%?",
            text,
            re.IGNORECASE,
        )
        marks_value = next((group for group in marks_match.groups() if group is not None), None) if marks_match else None
        if marks_value is None and expected_field == "marks" and re.fullmatch(r"\s*\d{1,3}(?:\.\d+)?\s*%?\s*", text):
            marks_value = text.strip().removesuffix("%").strip()
        if marks_value is None and suggestions.get("marks") is not None and re.search(r"%|percent|marks?", normalized):
            marks_value = suggestions["marks"]
        try:
            marks = float(marks_value) if marks_value is not None else None
        except (TypeError, ValueError):
            marks = None
        if marks is not None and 0 <= marks <= 100:
            extracted["marks"] = marks

        not_taken = re.search(
            r"\b(?:not taken|haven't taken|have not taken|no ielts|without ielts|ielts pending)\b",
            normalized,
        ) is not None
        score_match = re.search(
            r"\bielts(?:\s+(?:overall\s+)?(?:score|band))?\s*(?:is|of|:)?\s*(\d(?:\.\d)?)\b"
            r"|(\d(?:\.\d)?)\s*(?:overall\s+)?ielts\b",
            text,
            re.IGNORECASE,
        )
        score_value = next((group for group in score_match.groups() if group is not None), None) if score_match else None
        if score_value is None and expected_field == "ielts_score" and re.fullmatch(r"\s*\d(?:\.\d)?\s*", text):
            score_value = text.strip()
        if score_value is None and suggestions.get("ielts_score") is not None and "ielts" in normalized:
            score_value = suggestions["ielts_score"]
        try:
            ielts_score = float(score_value) if score_value is not None else None
        except (TypeError, ValueError):
            ielts_score = None
        if not_taken and ("ielts" in normalized or expected_field == "ielts_score"):
            extracted["ielts_not_taken"] = True
        elif ielts_score is not None and 0 <= ielts_score <= 9:
            extracted["ielts_score"] = ielts_score
            extracted["ielts_not_taken"] = False

        budget_match = re.search(
            r"\b(?:budget|spend|afford)\s*(?:is|of|around|about|approximately|approx\.)?\s*([^.;!?\n]+)",
            text,
            re.IGNORECASE,
        )
        budget_candidate = budget_match.group(1).strip() if budget_match else None
        if budget_candidate is None and expected_field == "budget":
            budget_candidate = text
        suggested_budget = suggestions.get("budget")
        if suggested_budget and str(suggested_budget).casefold() in normalized:
            budget_candidate = str(suggested_budget)
        if budget_candidate:
            budget_candidate = " ".join(budget_candidate.split()).strip(" ,.")
            budget_lower = budget_candidate.casefold()
            has_amount_or_flexible_response = (
                re.search(r"\d|[$£€]|\b(?:cad|usd|gbp|eur|aud)\b", budget_lower) is not None
                or any(term in budget_lower for term in ("flexible", "not decided", "undecided", "not sure yet"))
            )
            if 2 <= len(budget_candidate) <= 100 and has_amount_or_flexible_response:
                extracted["budget"] = budget_candidate

        return extracted

    @classmethod
    def validate_intake_state(
        cls,
        profile: dict,
        catalog_countries: list[str],
    ) -> dict:
        validated = {}
        name = cls.validate_full_name(profile.get("name"), str(profile.get("name", "")))
        if name:
            validated["name"] = name

        phone = profile.get("phone")
        if isinstance(phone, str):
            digits = cls.normalize_phone(phone)
            if 10 <= len(digits) <= 15:
                validated["phone"] = phone.strip()

        country = profile.get("preferred_country")
        if isinstance(country, str):
            matched_country = next(
                (item for item in catalog_countries if item.casefold() == country.strip().casefold()),
                None,
            )
            if matched_country:
                validated["preferred_country"] = matched_country

        try:
            marks = float(profile["marks"])
            if 0 <= marks <= 100:
                validated["marks"] = marks
        except (KeyError, TypeError, ValueError):
            pass

        try:
            score = float(profile["ielts_score"])
            if 0 <= score <= 9:
                validated["ielts_score"] = score
                validated["ielts_not_taken"] = False
        except (KeyError, TypeError, ValueError):
            if profile.get("ielts_not_taken") is True:
                validated["ielts_not_taken"] = True

        budget = profile.get("budget")
        if isinstance(budget, str):
            budget = " ".join(budget.strip().split())
            normalized_budget = budget.casefold()
            if (
                2 <= len(budget) <= 100
                and (
                    re.search(r"\d|[$£€]|\b(?:cad|usd|gbp|eur|aud)\b", normalized_budget)
                    or any(term in normalized_budget for term in ("flexible", "not decided", "undecided", "not sure yet"))
                )):
                validated["budget"] = budget

        return validated

    def get_all_leads(
        self,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        clean_search = search.strip().casefold() if search else None
        pattern = f"%{clean_search}%" if clean_search else None
        conn = get_connection()
        total = conn.execute(
            """
            SELECT COUNT(*)
            FROM leads
            WHERE ? IS NULL
               OR LOWER(name) LIKE ?
               OR phone LIKE ?
               OR LOWER(COALESCE(preferred_country, '')) LIKE ?
            """,
            (pattern, pattern, pattern, pattern),
        ).fetchone()[0]
        rows = conn.execute(
            """
            SELECT *
            FROM leads
            WHERE ? IS NULL
               OR LOWER(name) LIKE ?
               OR phone LIKE ?
               OR LOWER(COALESCE(preferred_country, '')) LIKE ?
            ORDER BY name COLLATE NOCASE, id
            LIMIT ? OFFSET ?
            """,
            (pattern, pattern, pattern, pattern, limit, offset),
        ).fetchall()
        conn.close()
        return {"leads": [dict(row) for row in rows], "total": total}

    def find_by_phone(self, phone: str):
        normalized_phone = self.normalize_phone(phone)

        conn = get_connection()

        rows = conn.execute("SELECT * FROM leads").fetchall()

        lead = None

        for row in rows:
            if self.normalize_phone(row["phone"]) == normalized_phone:
                lead = dict(row)
                break

        conn.close()

        return lead

    def find_by_id(self, lead_id: int):
        conn = get_connection()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_profile_fields(self, lead_id: int, updates: dict):
        allowed_fields = {
            "name", "preferred_country", "marks", "ielts_score", "budget",
        }
        safe_updates = {
            field: value
            for field, value in updates.items()
            if field in allowed_fields and value is not None
        }
        if not safe_updates:
            return {"error": "no_valid_profile_updates"}

        conn = get_connection()
        lead = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if lead is None:
            conn.close()
            return {"error": "lead_not_found"}

        assignments = ", ".join(f"{field} = ?" for field in safe_updates)
        conn.execute(
            f"UPDATE leads SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*safe_updates.values(), lead_id),
        )
        conn.execute(
            "INSERT INTO agent_logs (agent, action, details) VALUES (?, ?, ?)",
            (
                "lead_agent",
                "updated_student_profile_from_chat",
                f"Lead ID: {lead_id}; fields: {', '.join(sorted(safe_updates))}",
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
        conn.close()
        return {"updated": True, "lead": dict(row), "updated_fields": sorted(safe_updates)}

    def save_lead(
        self,
        name: str,
        phone: str,
        preferred_country: str | None = None,
        marks: float | None = None,
        ielts_score: float | None = None,
        budget: str | None = None,
    ):
        existing = self.find_by_phone(phone)

        conn = get_connection()

        if existing:
            conn.execute(
                """
                UPDATE leads
                SET
                    name = ?,
                    preferred_country = ?,
                    marks = ?,
                    ielts_score = ?,
                    budget = ?,
                    last_reply_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    name,
                    preferred_country,
                    marks,
                    ielts_score,
                    budget,
                    existing["id"],
                ),
            )

            lead_id = existing["id"]
            action = "updated_existing_lead"

        else:
            cursor = conn.execute(
                """
                INSERT INTO leads (
                    name,
                    phone,
                    preferred_country,
                    marks,
                    ielts_score,
                    budget,
                    last_reply_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    name,
                    phone,
                    preferred_country,
                    marks,
                    ielts_score,
                    budget,
                ),
            )

            lead_id = cursor.lastrowid
            action = "created_new_lead"

        conn.execute(
            """
            INSERT INTO agent_logs (agent, action, details)
            VALUES (?, ?, ?)
            """,
            (
                "lead_agent",
                action,
                f"Lead ID: {lead_id}, phone: {phone}",
            ),
        )

        conn.commit()

        saved_lead = conn.execute(
            "SELECT * FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()

        conn.close()

        return {
            "action": action,
            "lead": dict(saved_lead),
        }


lead_agent = LeadAgent()