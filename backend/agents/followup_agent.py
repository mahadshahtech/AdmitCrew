import re
from datetime import datetime, timedelta, timezone

from database import get_connection


class FollowupAgent:
    INACTIVE_DAYS = 3

    @staticmethod
    def parse_last_reply(value: str | None) -> datetime | None:
        if not value:
            return None

        normalized = value.strip()
        if not normalized:
            return None

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        lowered = normalized.lower()

        if lowered == "today":
            return now
        if lowered == "yesterday":
            return now - timedelta(days=1)

        relative = re.fullmatch(
            r"(\d+)\s+(day|days|week|weeks|hour|hours)\s+ago",
            lowered,
        )
        if relative:
            amount = int(relative.group(1))
            unit = relative.group(2)
            if unit.startswith("week"):
                amount *= 7
            elif unit.startswith("hour"):
                return now - timedelta(hours=amount)
            return now - timedelta(days=amount)

        timestamp = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError:
            return None

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def build_message(name: str) -> str:
        return (
            f"Hi {name}, just checking in on your study-abroad plans. "
            "Let us know if you need any help."
        )

    @staticmethod
    def log_action(conn, action: str, details: str):
        conn.execute(
            """
            INSERT INTO agent_logs (agent, action, details)
            VALUES ('followup_agent', ?, ?)
            """,
            (action, details),
        )

    def run_detection(self):
        conn = get_connection()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=self.INACTIVE_DAYS)
        leads = conn.execute(
            "SELECT id, name, last_reply_at FROM leads WHERE last_reply_at IS NOT NULL"
        ).fetchall()
        created = []
        skipped = 0

        for lead in leads:
            last_reply_at = lead["last_reply_at"]
            parsed_reply_at = self.parse_last_reply(last_reply_at)
            if parsed_reply_at is None:
                skipped += 1
                self.log_action(
                    conn,
                    "invalid_last_reply_skipped",
                    f"Lead ID: {lead['id']}; last_reply_at: {last_reply_at}",
                )
                continue

            if parsed_reply_at > cutoff:
                continue

            event_key = last_reply_at.strip()
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO followups (
                    lead_id, message, status, inactivity_event_key
                )
                VALUES (?, ?, 'pending', ?)
                """,
                (lead["id"], self.build_message(lead["name"]), event_key),
            )

            if cursor.rowcount:
                followup_id = cursor.lastrowid
                self.log_action(
                    conn,
                    "followup_created_pending_approval",
                    f"Follow-up ID: {followup_id}; Lead ID: {lead['id']}; event: {event_key}",
                )
                followup = conn.execute(
                    "SELECT * FROM followups WHERE id = ?",
                    (followup_id,),
                ).fetchone()
                created.append(dict(followup))

        self.log_action(
            conn,
            "followup_detection_completed",
            f"Inactive leads: {len(created)} new reminders; invalid timestamps skipped: {skipped}",
        )
        conn.commit()
        conn.close()

        return {"created": len(created), "followups": created}

    @staticmethod
    def list_followups(status: str):
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT followups.*, leads.name AS student_name,
                   leads.phone AS student_phone
            FROM followups
            JOIN leads ON leads.id = followups.lead_id
            WHERE followups.status = ?
            ORDER BY followups.created_at, followups.id
            """,
            (status,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def approve_followup(self, followup_id: int):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        followup = conn.execute(
            "SELECT * FROM followups WHERE id = ?",
            (followup_id,),
        ).fetchone()

        if followup is None:
            conn.rollback()
            conn.close()
            return None

        if followup["status"] == "sent" or followup["sent_at"] is not None:
            self.log_action(
                conn,
                "followup_approval_repeated",
                f"Follow-up ID: {followup_id}; already sent",
            )
            conn.commit()
            conn.close()
            return {"already_sent": True, "followup": dict(followup)}

        if followup["status"] != "pending":
            conn.rollback()
            conn.close()
            return {"not_pending": True, "followup": dict(followup)}

        conn.execute(
            """
            UPDATE followups
            SET status = 'sent',
                approved_at = COALESCE(approved_at, CURRENT_TIMESTAMP),
                sent_at = COALESCE(sent_at, CURRENT_TIMESTAMP)
            WHERE id = ? AND status = 'pending' AND sent_at IS NULL
            """,
            (followup_id,),
        )
        self.log_action(
            conn,
            "followup_approved_and_sent",
            f"Follow-up ID: {followup_id}; Lead ID: {followup['lead_id']}",
        )
        saved = conn.execute(
            "SELECT * FROM followups WHERE id = ?",
            (followup_id,),
        ).fetchone()
        conn.commit()
        conn.close()
        return {"already_sent": False, "followup": dict(saved)}


followup_agent = FollowupAgent()
