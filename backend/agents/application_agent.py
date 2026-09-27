import json

from agents.task_agent import task_agent
from database import get_connection


APPLICATION_SELECT = """
    SELECT applications.*, programs.university, programs.program,
           programs.country, leads.name AS student_name
    FROM applications
    JOIN programs ON programs.id = applications.program_id
    JOIN leads ON leads.id = applications.lead_id
"""


class ApplicationAgent:
    STATUSES = {
        "preparing",
        "ready",
        "submitted",
        "under_review",
        "offer_received",
        "rejected",
        "withdrawn",
    }

    TRANSITIONS = {
        "preparing": {"ready", "withdrawn"},
        "ready": {"submitted", "withdrawn"},
        "submitted": {"under_review", "withdrawn"},
        "under_review": {"offer_received", "rejected", "withdrawn"},
        "offer_received": set(),
        "rejected": set(),
        "withdrawn": set(),
    }

    @staticmethod
    def _log(conn, action: str, details: str):
        conn.execute(
            """
            INSERT INTO agent_logs (agent, action, details)
            VALUES ('application_agent', ?, ?)
            """,
            (action, details),
        )

    @staticmethod
    def _history(
        conn,
        application_id: int,
        action: str,
        from_status: str | None = None,
        to_status: str | None = None,
        details: str | None = None,
    ):
        conn.execute(
            """
            INSERT INTO application_history (
                application_id, action, from_status, to_status, details
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (application_id, action, from_status, to_status, details),
        )

    @staticmethod
    def _fetch_application(conn, application_id: int, include_history: bool = True):
        row = conn.execute(
            APPLICATION_SELECT + " WHERE applications.id = ?",
            (application_id,),
        ).fetchone()
        if row is None:
            return None

        application = dict(row)
        if include_history:
            history = conn.execute(
                """
                SELECT id, action, from_status, to_status, details, created_at
                FROM application_history
                WHERE application_id = ?
                ORDER BY id
                """,
                (application_id,),
            ).fetchall()
            application["history"] = [dict(item) for item in history]
        return application

    def create_application(
        self,
        lead_id: int,
        university: str,
        program: str,
        notes: str | None = None,
    ):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        lead = conn.execute(
            "SELECT id FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if lead is None:
            conn.close()
            return {"error": "lead_not_found"}

        catalog_program = conn.execute(
            """
            SELECT id, university, program
            FROM programs
            WHERE LOWER(university) = LOWER(?)
              AND LOWER(program) = LOWER(?)
            """,
            (university.strip(), program.strip()),
        ).fetchone()
        if catalog_program is None:
            conn.close()
            return {"error": "program_not_found"}

        existing = conn.execute(
            """
            SELECT id FROM applications
            WHERE lead_id = ? AND program_id = ?
            """,
            (lead_id, catalog_program["id"]),
        ).fetchone()
        if existing is not None:
            self._log(
                conn,
                "duplicate_application_prevented",
                f"Application ID: {existing['id']}; Lead ID: {lead_id}; Program ID: {catalog_program['id']}",
            )
            conn.commit()
            application = self._fetch_application(conn, existing["id"])
            conn.close()
            return {
                "created": False,
                "duplicate": True,
                "application": application,
            }

        initial_notes = (notes or "").strip()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO applications (lead_id, program_id, notes)
            VALUES (?, ?, ?)
            """,
            (lead_id, catalog_program["id"], initial_notes),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                """
                SELECT id FROM applications
                WHERE lead_id = ? AND program_id = ?
                """,
                (lead_id, catalog_program["id"]),
            ).fetchone()
            self._log(
                conn,
                "duplicate_application_prevented",
                f"Application ID: {existing['id']}; Lead ID: {lead_id}; Program ID: {catalog_program['id']}",
            )
            conn.commit()
            application = self._fetch_application(conn, existing["id"])
            conn.close()
            return {
                "created": False,
                "duplicate": True,
                "application": application,
            }

        application_id = cursor.lastrowid
        self._history(
            conn,
            application_id,
            "application_created",
            to_status="preparing",
            details=initial_notes or None,
        )
        self._log(
            conn,
            "application_created",
            f"Application ID: {application_id}; Lead ID: {lead_id}; Program ID: {catalog_program['id']}",
        )
        conn.commit()
        application = self._fetch_application(conn, application_id)
        conn.close()
        return {
            "created": True,
            "duplicate": False,
            "application": application,
        }

    @staticmethod
    def get_applications_for_lead(lead_id: int):
        conn = get_connection()
        lead = conn.execute(
            "SELECT id FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if lead is None:
            conn.close()
            return None

        rows = conn.execute(
            APPLICATION_SELECT + " WHERE applications.lead_id = ? ORDER BY applications.created_at, applications.id",
            (lead_id,),
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_application(application_id: int):
        conn = get_connection()
        application = ApplicationAgent._fetch_application(conn, application_id)
        conn.close()
        return application

    @staticmethod
    def get_all_applications(
        lead_id: int | None = None,
        status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ):
        conditions = []
        parameters = []
        if lead_id is not None:
            conditions.append("applications.lead_id = ?")
            parameters.append(lead_id)
        if status is not None:
            conditions.append("applications.status = ?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        conn = get_connection()
        total = conn.execute(
            "SELECT COUNT(*) FROM applications" + where,
            parameters,
        ).fetchone()[0]
        rows = conn.execute(
            APPLICATION_SELECT
            + where
            + " ORDER BY applications.updated_at DESC, applications.id DESC LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
        conn.close()
        return {"applications": [dict(row) for row in rows], "total": total}

    @staticmethod
    def _document_readiness(conn, lead_id: int, program_id: int):
        program = conn.execute(
            "SELECT documents_needed FROM programs WHERE id = ?",
            (program_id,),
        ).fetchone()
        required_documents = []
        for item in (program["documents_needed"] or "").split(","):
            document_type = item.strip()
            if document_type and document_type.casefold() not in {
                existing.casefold() for existing in required_documents
            }:
                required_documents.append(document_type)

        rows = conn.execute(
            """
            SELECT document_type, status, result
            FROM documents
            WHERE lead_id = ?
            ORDER BY uploaded_at DESC, id DESC
            """,
            (lead_id,),
        ).fetchall()
        latest_by_type = {}
        for row in rows:
            document_type = (row["document_type"] or "").strip().casefold()
            if document_type:
                latest_by_type.setdefault(document_type, row)

        missing_documents = []
        problematic_documents = []
        for required in required_documents:
            record = latest_by_type.get(required.casefold())
            if record is None:
                missing_documents.append(required)
            elif (record["status"] or "").strip().casefold() != "ok":
                problematic_documents.append(
                    {
                        "document_type": required,
                        "status": record["status"],
                        "details": record["result"],
                    }
                )

        return {
            "ready": not missing_documents and not problematic_documents,
            "required_documents": required_documents,
            "missing_documents": missing_documents,
            "problematic_documents": problematic_documents,
        }

    def update_status(self, application_id: int, requested_status: str):
        new_status = requested_status.strip().lower()
        if new_status not in self.STATUSES:
            return {
                "error": "invalid_status",
                "allowed_statuses": sorted(self.STATUSES),
            }

        conn = get_connection()
        application = conn.execute(
            "SELECT id, lead_id, program_id, status FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if application is None:
            conn.close()
            return {"error": "application_not_found"}

        current_status = application["status"]
        if new_status == current_status:
            result = self._fetch_application(conn, application_id)
            conn.close()
            return {"updated": False, "application": result}

        allowed = self.TRANSITIONS[current_status]
        if new_status not in allowed:
            self._log(
                conn,
                "status_transition_rejected",
                f"Application ID: {application_id}; {current_status} -> {new_status}",
            )
            conn.commit()
            conn.close()
            return {
                "error": "invalid_transition",
                "current_status": current_status,
                "requested_status": new_status,
                "allowed_transitions": sorted(allowed),
            }

        if new_status == "ready":
            readiness = self._document_readiness(
                conn,
                application["lead_id"],
                application["program_id"],
            )
            self._log(
                conn,
                "readiness_checked",
                f"Application ID: {application_id}; result: {json.dumps(readiness, sort_keys=True)}",
            )
            if not readiness["ready"]:
                details = json.dumps(readiness, sort_keys=True)
                self._history(
                    conn,
                    application_id,
                    "readiness_blocked",
                    from_status=current_status,
                    to_status=new_status,
                    details=details,
                )
                self._log(
                    conn,
                    "blocked_readiness_attempt",
                    f"Application ID: {application_id}; {details}",
                )
                conn.commit()
                conn.close()
                return {
                    "error": "documents_not_ready",
                    "message": "Required documents must be valid before the application can be marked ready.",
                    "readiness": readiness,
                }

        conn.execute(
            """
            UPDATE applications
            SET status = ?,
                submitted_at = CASE
                    WHEN ? = 'submitted' THEN COALESCE(submitted_at, CURRENT_TIMESTAMP)
                    ELSE submitted_at
                END,
                decision_at = CASE
                    WHEN ? IN ('offer_received', 'rejected')
                        THEN COALESCE(decision_at, CURRENT_TIMESTAMP)
                    ELSE decision_at
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, new_status, new_status, application_id),
        )
        self._history(
            conn,
            application_id,
            "status_changed",
            from_status=current_status,
            to_status=new_status,
        )
        self._log(
            conn,
            "status_changed",
            f"Application ID: {application_id}; {current_status} -> {new_status}",
        )
        if new_status == "submitted":
            self._log(
                conn,
                "application_submitted",
                f"Application ID: {application_id}; Lead ID: {application['lead_id']}",
            )
            task_agent.complete_submission_tasks(conn, application_id)
        if new_status in {"offer_received", "rejected"}:
            self._log(
                conn,
                "decision_recorded",
                f"Application ID: {application_id}; explicitly recorded outcome: {new_status}",
            )

        conn.commit()
        saved = self._fetch_application(conn, application_id)
        conn.close()
        return {"updated": True, "application": saved}

    def add_note(self, application_id: int, note: str):
        clean_note = note.strip()
        if not clean_note:
            return {"error": "empty_note"}

        conn = get_connection()
        application = conn.execute(
            "SELECT notes, status FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if application is None:
            conn.close()
            return {"error": "application_not_found"}

        updated_notes = (
            f"{application['notes']}\n{clean_note}"
            if application["notes"]
            else clean_note
        )
        conn.execute(
            """
            UPDATE applications
            SET notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (updated_notes, application_id),
        )
        self._history(
            conn,
            application_id,
            "notes_added",
            from_status=application["status"],
            to_status=application["status"],
            details=clean_note,
        )
        self._log(
            conn,
            "notes_added",
            f"Application ID: {application_id}; note appended",
        )
        conn.commit()
        saved = self._fetch_application(conn, application_id)
        conn.close()
        return {"updated": True, "application": saved}


application_agent = ApplicationAgent()
