from database import escalation_dedupe_key, get_connection


ESCALATION_SELECT = """
    SELECT escalations.*, leads.name AS student_name,
           leads.phone AS student_phone,
           conversations.started_at AS conversation_started_at
    FROM escalations
    LEFT JOIN leads ON leads.id = escalations.lead_id
    LEFT JOIN conversations ON conversations.id = escalations.conversation_id
"""


class EscalationAgent:
    STATUSES = {"open", "in_progress", "resolved"}

    @staticmethod
    def _log(conn, action: str, details: str):
        conn.execute(
            """
            INSERT INTO agent_logs (agent, action, details)
            VALUES ('escalation_agent', ?, ?)
            """,
            (action, details),
        )

    @staticmethod
    def _fetch(conn, escalation_id: int):
        row = conn.execute(
            ESCALATION_SELECT + " WHERE escalations.id = ?",
            (escalation_id,),
        ).fetchone()
        return dict(row) if row else None

    def create_escalation(
        self,
        question: str,
        reason: str,
        source_agent: str,
        lead_id: int | None = None,
        conversation_id: int | None = None,
    ):
        if not question or not question.strip():
            return {"error": "question_required"}
        if not reason or not reason.strip():
            return {"error": "reason_required"}
        if not source_agent or not source_agent.strip():
            return {"error": "source_agent_required"}

        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        if lead_id is not None:
            lead = conn.execute(
                "SELECT id FROM leads WHERE id = ?",
                (lead_id,),
            ).fetchone()
            if lead is None:
                conn.close()
                return {"error": "lead_not_found"}

        if conversation_id is not None:
            conversation = conn.execute(
                "SELECT lead_id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if conversation is None:
                conn.close()
                return {"error": "conversation_not_found"}
            if (
                lead_id is not None
                and conversation["lead_id"] is not None
                and conversation["lead_id"] != lead_id
            ):
                conn.close()
                return {"error": "conversation_lead_mismatch"}
            if lead_id is None:
                lead_id = conversation["lead_id"]

        dedupe_key = escalation_dedupe_key(
            lead_id,
            conversation_id,
            question,
        )
        existing = conn.execute(
            """
            SELECT id FROM escalations
            WHERE dedupe_key = ? AND status IN ('open', 'in_progress')
            ORDER BY id
            LIMIT 1
            """,
            (dedupe_key,),
        ).fetchone()
        if existing is not None:
            self._log(
                conn,
                "open_escalation_reused",
                f"Escalation ID: {existing['id']}; source agent: {source_agent}",
            )
            conn.commit()
            escalation = self._fetch(conn, existing["id"])
            conn.close()
            return {
                "created": False,
                "reused": True,
                "escalation": escalation,
            }

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO escalations (
                lead_id, conversation_id, question, reason, source_agent,
                status, dedupe_key
            )
            VALUES (?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                lead_id,
                conversation_id,
                question,
                reason.strip(),
                source_agent.strip(),
                dedupe_key,
            ),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                """
                SELECT id FROM escalations
                WHERE dedupe_key = ? AND status IN ('open', 'in_progress')
                ORDER BY id
                LIMIT 1
                """,
                (dedupe_key,),
            ).fetchone()
            self._log(
                conn,
                "open_escalation_reused",
                f"Escalation ID: {existing['id']}; source agent: {source_agent}",
            )
            conn.commit()
            escalation = self._fetch(conn, existing["id"])
            conn.close()
            return {
                "created": False,
                "reused": True,
                "escalation": escalation,
            }

        escalation_id = cursor.lastrowid
        self._log(
            conn,
            "escalation_created",
            f"Escalation ID: {escalation_id}; Lead ID: {lead_id}; Conversation ID: {conversation_id}; source agent: {source_agent}",
        )
        conn.commit()
        escalation = self._fetch(conn, escalation_id)
        conn.close()
        return {
            "created": True,
            "reused": False,
            "escalation": escalation,
        }

    @classmethod
    def list_escalations(
        cls,
        lead_id: int | None = None,
        status: str | None = None,
    ):
        conditions = []
        parameters = []
        if lead_id is not None:
            conditions.append("escalations.lead_id = ?")
            parameters.append(lead_id)
        if status is not None:
            conditions.append("escalations.status = ?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        conn = get_connection()
        rows = conn.execute(
            ESCALATION_SELECT
            + where
            + " ORDER BY escalations.created_at DESC, escalations.id DESC",
            parameters,
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @classmethod
    def list_open_escalations(cls, lead_id: int | None = None):
        conditions = ["escalations.status IN ('open', 'in_progress')"]
        parameters = []
        if lead_id is not None:
            conditions.append("escalations.lead_id = ?")
            parameters.append(lead_id)
        conn = get_connection()
        rows = conn.execute(
            ESCALATION_SELECT
            + " WHERE "
            + " AND ".join(conditions)
            + " ORDER BY escalations.created_at DESC, escalations.id DESC",
            parameters,
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @classmethod
    def get_escalation(cls, escalation_id: int):
        conn = get_connection()
        escalation = cls._fetch(conn, escalation_id)
        conn.close()
        return escalation

    def start_escalation(self, escalation_id: int):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        escalation = conn.execute(
            "SELECT id, status FROM escalations WHERE id = ?",
            (escalation_id,),
        ).fetchone()
        if escalation is None:
            conn.close()
            return {"error": "escalation_not_found"}
        if escalation["status"] == "resolved":
            conn.close()
            return {"error": "escalation_resolved"}
        if escalation["status"] == "in_progress":
            result = self._fetch(conn, escalation_id)
            conn.close()
            return {"updated": False, "escalation": result}
        if escalation["status"] != "open":
            conn.close()
            return {"error": "invalid_status", "status": escalation["status"]}

        conn.execute(
            "UPDATE escalations SET status = 'in_progress' WHERE id = ?",
            (escalation_id,),
        )
        self._log(conn, "escalation_in_progress", f"Escalation ID: {escalation_id}")
        conn.commit()
        result = self._fetch(conn, escalation_id)
        conn.close()
        return {"updated": True, "escalation": result}

    def resolve_escalation(
        self,
        escalation_id: int,
        staff_response: str,
        actor_id: int | None = None,
    ):
        response = staff_response.strip() if staff_response else ""
        if not response:
            return {"error": "staff_response_required"}

        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT id, status, staff_response, conversation_id FROM escalations WHERE id = ?",
            (escalation_id,),
        ).fetchone()
        if current is None:
            conn.close()
            return {"error": "escalation_not_found"}

        if current["status"] == "resolved":
            if current["staff_response"] == response:
                self._log(
                    conn,
                    "duplicate_delivery_prevented",
                    f"Escalation ID: {escalation_id}; Conversation ID: {current['conversation_id']}",
                )
                conn.commit()
                result = self._fetch(conn, escalation_id)
                conn.close()
                return {
                    "resolved": False,
                    "already_resolved": True,
                    "escalation": result,
                }
            conn.close()
            return {
                "error": "escalation_already_resolved",
                "escalation": self.get_escalation(escalation_id),
            }

        if current["status"] not in {"open", "in_progress"}:
            conn.close()
            return {"error": "invalid_status", "status": current["status"]}

        conn.execute(
            """
            UPDATE escalations
            SET status = 'resolved',
                staff_response = ?,
                resolved_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status IN ('open', 'in_progress')
            """,
            (response, escalation_id),
        )
        message_id = None
        if current["conversation_id"] is not None:
            message_cursor = conn.execute(
                """
                INSERT INTO messages (conversation_id, sender, content)
                VALUES (?, 'staff', ?)
                """,
                (current["conversation_id"], response),
            )
            message_id = message_cursor.lastrowid
            self._log(
                conn,
                "staff_response_delivered_to_conversation",
                f"Escalation ID: {escalation_id}; Conversation ID: {current['conversation_id']}; Message ID: {message_id}",
            )

        self._log(
            conn,
            "escalation_resolved",
            f"Escalation ID: {escalation_id}; Conversation ID: {current['conversation_id']}; Actor ID: {actor_id}",
        )
        conn.commit()
        result = self._fetch(conn, escalation_id)
        conn.close()
        return {
            "resolved": True,
            "delivered_to_conversation": message_id is not None,
            "message_id": message_id,
            "escalation": result,
        }


escalation_agent = EscalationAgent()
