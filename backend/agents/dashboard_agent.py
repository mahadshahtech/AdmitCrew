from datetime import datetime, timedelta, timezone

from database import get_connection


PIPELINE_STATUSES = (
    "preparing",
    "ready",
    "submitted",
    "under_review",
    "offer_received",
    "rejected",
    "withdrawn",
)
ACTIVE_APPLICATION_STATUSES = ("preparing", "ready", "submitted", "under_review")


class DashboardAgent:
    """Read-only dashboard aggregation over AdmitCrew's source-of-truth tables.

    Metrics are defined as follows: active applications are preparing, ready,
    submitted, or under_review; submitted/offers/rejections count their exact
    status. Document problems count the latest check per lead and document type.
    Upcoming tasks are pending and due between now and the requested window.
    Applications needing attention are unique application IDs with a document
    readiness failure (preparing/ready only) or an overdue pending linked task.
    Lead-level escalations are surfaced separately because the schema does not
    link an escalation to a specific application.
    """

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _activity_item(row):
        details = None if row["agent"] == "lead_agent" else row["details"]
        return {
            "id": row["id"],
            "type": "agent_log",
            "agent": row["agent"],
            "action": row["action"],
            "details": details,
            "created_at": row["created_at"],
        }

    @classmethod
    def _latest_documents(cls, conn, lead_ids=None):
        if lead_ids is not None and not lead_ids:
            return {}

        parameters = []
        lead_filter = ""
        if lead_ids is not None:
            placeholders = ", ".join("?" for _ in lead_ids)
            lead_filter = f"AND lead_id IN ({placeholders})"
            parameters.extend(lead_ids)

        rows = conn.execute(
            f"""
            SELECT latest.*, leads.name AS student_name
            FROM (
                SELECT documents.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY lead_id,
                               LOWER(TRIM(COALESCE(document_type, '')))
                           ORDER BY uploaded_at DESC, id DESC
                       ) AS document_rank
                FROM documents
                WHERE document_type IS NOT NULL
                  AND TRIM(document_type) <> ''
                  {lead_filter}
            ) AS latest
            JOIN leads ON leads.id = latest.lead_id
            WHERE latest.document_rank = 1
            ORDER BY latest.uploaded_at DESC, latest.id DESC
            """,
            parameters,
        ).fetchall()

        documents = {}
        for row in rows:
            document = dict(row)
            document.pop("document_rank", None)
            doc_type = document["document_type"].strip().casefold()
            documents.setdefault(document["lead_id"], {})[doc_type] = document
        return documents

    @staticmethod
    def _required_documents(value):
        required = []
        seen = set()
        for item in (value or "").split(","):
            document_type = item.strip()
            key = document_type.casefold()
            if document_type and key not in seen:
                required.append(document_type)
                seen.add(key)
        return required

    @classmethod
    def _application_readiness_issues(cls, conn, latest_documents):
        rows = conn.execute(
            """
            SELECT applications.id, applications.lead_id, applications.status,
                   applications.created_at, programs.university, programs.program,
                   programs.documents_needed, leads.name AS student_name
            FROM applications
            JOIN programs ON programs.id = applications.program_id
            JOIN leads ON leads.id = applications.lead_id
            WHERE applications.status IN ('preparing', 'ready')
            ORDER BY applications.created_at DESC, applications.id DESC
            """
        ).fetchall()

        blocked = []
        blocked_ids = set()
        for row in rows:
            required_documents = cls._required_documents(row["documents_needed"])
            student_documents = latest_documents.get(row["lead_id"], {})
            missing = []
            problematic = []
            for document_type in required_documents:
                document = student_documents.get(document_type.casefold())
                if document is None:
                    missing.append(document_type)
                elif (document["status"] or "").strip().casefold() != "ok":
                    problematic.append(
                        {
                            "document_type": document_type,
                            "status": document["status"],
                            "details": document["result"],
                        }
                    )

            if not missing and not problematic:
                continue
            blocked_ids.add(row["id"])
            descriptions = []
            if missing:
                descriptions.append("Missing: " + ", ".join(missing))
            if problematic:
                descriptions.append(
                    "Not valid: "
                    + ", ".join(
                        f"{item['document_type']} ({item['status'] or 'unverified'})"
                        for item in problematic
                    )
                )
            blocked.append(
                {
                    "type": "application_readiness",
                    "severity": "high",
                    "lead_id": row["lead_id"],
                    "student_name": row["student_name"],
                    "application_id": row["id"],
                    "title": f"Application blocked: {row['university']} {row['program']}",
                    "description": "; ".join(descriptions),
                    "created_at": row["created_at"],
                    "due_at": None,
                    "source_record_id": row["id"],
                    "missing_documents": missing,
                    "problematic_documents": problematic,
                }
            )
        return blocked, blocked_ids

    @classmethod
    def _overdue_tasks(cls, conn, now):
        rows = conn.execute(
            """
            SELECT tasks.*, leads.name AS student_name
            FROM tasks
            JOIN leads ON leads.id = tasks.lead_id
            WHERE tasks.status = 'pending'
              AND julianday(tasks.due_at) < julianday(?)
            ORDER BY julianday(tasks.due_at), tasks.id
            """,
            (now.isoformat(timespec="seconds"),),
        ).fetchall()
        return [dict(row) for row in rows]

    @classmethod
    def _upcoming_task_count(cls, conn, now, days):
        upper_bound = now.replace(microsecond=0) + timedelta(days=days)
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM tasks
            WHERE status = 'pending'
              AND julianday(due_at) >= julianday(?)
              AND julianday(due_at) <= julianday(?)
            """,
            (
                now.isoformat(timespec="seconds"),
                upper_bound.isoformat(timespec="seconds"),
            ),
        ).fetchone()[0]

    @classmethod
    def get_overview(cls, upcoming_days: int = 7):
        conn = get_connection()
        try:
            total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            status_counts = {
                row["status"]: row["count"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM applications GROUP BY status"
                ).fetchall()
            }
            total_applications = sum(status_counts.values())
            latest_documents = cls._latest_documents(conn)
            document_problems = sum(
                1
                for documents in latest_documents.values()
                for document in documents.values()
                if (document["status"] or "").strip().casefold() == "problem"
            )
            now = cls._now()
            overdue_tasks = conn.execute(
                """
                SELECT COUNT(*) FROM tasks
                WHERE status = 'pending'
                  AND julianday(due_at) < julianday(?)
                """,
                (now.isoformat(timespec="seconds"),),
            ).fetchone()[0]
            pipeline_attention, attention_ids = cls._application_readiness_issues(
                conn,
                latest_documents,
            )
            del pipeline_attention
            overdue_application_ids = {
                row[0]
                for row in conn.execute(
                    """
                    SELECT DISTINCT application_id FROM tasks
                    WHERE status = 'pending'
                      AND application_id IS NOT NULL
                      AND julianday(due_at) < julianday(?)
                    """,
                    (now.isoformat(timespec="seconds"),),
                ).fetchall()
            }
            attention_ids.update(overdue_application_ids)

            return {
                "total_leads": total_leads,
                "total_applications": total_applications,
                "active_applications": sum(
                    status_counts.get(status, 0)
                    for status in ACTIVE_APPLICATION_STATUSES
                ),
                "submitted_applications": status_counts.get("submitted", 0),
                "offers_received": status_counts.get("offer_received", 0),
                "rejected_applications": status_counts.get("rejected", 0),
                "applications_needing_attention": len(attention_ids),
                "open_escalations": conn.execute(
                    "SELECT COUNT(*) FROM escalations WHERE status IN ('open', 'in_progress')"
                ).fetchone()[0],
                "pending_followups": conn.execute(
                    "SELECT COUNT(*) FROM followups WHERE status = 'pending'"
                ).fetchone()[0],
                "overdue_tasks": overdue_tasks,
                "upcoming_tasks": cls._upcoming_task_count(conn, now, upcoming_days),
                "document_problems": document_problems,
                "upcoming_days": upcoming_days,
            }
        finally:
            conn.close()

    @classmethod
    def get_pipeline(cls):
        conn = get_connection()
        try:
            counts = {
                row["status"]: row["count"]
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS count FROM applications GROUP BY status"
                ).fetchall()
            }
            pipeline = {status: counts.get(status, 0) for status in PIPELINE_STATUSES}
            return {
                "pipeline": pipeline,
                "total_applications": sum(pipeline.values()),
            }
        finally:
            conn.close()

    @classmethod
    def get_attention(cls, limit: int = 50):
        conn = get_connection()
        try:
            items = []
            now = cls._now()
            latest_documents = cls._latest_documents(conn)

            escalations = conn.execute(
                """
                  SELECT escalations.id, escalations.lead_id, escalations.question,
                      escalations.reason, escalations.status, escalations.created_at,
                      leads.name AS student_name
                  FROM escalations
                  LEFT JOIN leads ON leads.id = escalations.lead_id
                WHERE status IN ('open', 'in_progress')
                """
            ).fetchall()
            for row in escalations:
                items.append(
                    {
                        "type": "escalation",
                        "severity": "high",
                        "lead_id": row["lead_id"],
                        "student_name": row["student_name"],
                        "application_id": None,
                        "title": row["question"],
                        "description": row["reason"],
                        "created_at": row["created_at"],
                        "due_at": None,
                        "source_record_id": row["id"],
                    }
                )

            for row in cls._overdue_tasks(conn, now):
                items.append(
                    {
                        "type": "overdue_task",
                        "severity": row["priority"],
                        "lead_id": row["lead_id"],
                        "student_name": row["student_name"],
                        "application_id": row["application_id"],
                        "title": row["title"],
                        "description": row["description"],
                        "created_at": row["created_at"],
                        "due_at": row["due_at"],
                        "source_record_id": row["id"],
                        "is_overdue": True,
                    }
                )

            for documents in latest_documents.values():
                for document in documents.values():
                    if (document["status"] or "").strip().casefold() != "problem":
                        continue
                    items.append(
                        {
                            "type": "document_problem",
                            "severity": "high",
                            "lead_id": document["lead_id"],
                            "student_name": document["student_name"],
                            "application_id": None,
                            "title": f"Review {document['document_type']}",
                            "description": document["result"],
                            "created_at": document["uploaded_at"],
                            "due_at": None,
                            "source_record_id": document["id"],
                        }
                    )

            followups = conn.execute(
                """
                SELECT followups.id, followups.lead_id, followups.message,
                       followups.created_at, leads.name AS student_name
                FROM followups
                JOIN leads ON leads.id = followups.lead_id
                WHERE followups.status = 'pending'
                """
            ).fetchall()
            for row in followups:
                items.append(
                    {
                        "type": "pending_followup",
                        "severity": "normal",
                        "lead_id": row["lead_id"],
                        "student_name": row["student_name"],
                        "application_id": None,
                        "title": "Review pending follow-up",
                        "description": row["message"],
                        "created_at": row["created_at"],
                        "due_at": None,
                        "source_record_id": row["id"],
                    }
                )

            blocked_applications, _ = cls._application_readiness_issues(
                conn,
                latest_documents,
            )
            items.extend(blocked_applications)

            severity_rank = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

            def order_key(item):
                timestamp = item.get("due_at") or item.get("created_at") or ""
                try:
                    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    if parsed.tzinfo is not None:
                        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                except (TypeError, ValueError):
                    parsed = datetime.max
                return (
                    0 if item.get("is_overdue") else 1,
                    severity_rank.get(item["severity"], 2),
                    parsed,
                    item["type"],
                    item["source_record_id"],
                )

            items.sort(key=order_key)
            return {"items": items[:limit], "total": len(items)}
        finally:
            conn.close()

    @classmethod
    def get_recent_activity(cls, limit: int = 20):
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT id, agent, action, details, created_at
                FROM agent_logs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [cls._activity_item(row) for row in rows]
        finally:
            conn.close()

    @classmethod
    def _student_activity(cls, conn, lead_id: int, entity_ids: dict, limit: int):
        patterns = [f"%Lead ID: {lead_id};%", f"%Lead ID: {lead_id},%"]
        for label, ids in entity_ids.items():
            for record_id in ids:
                patterns.append(f"%{label} ID: {record_id};%")
        if not patterns:
            return []

        conditions = " OR ".join("details LIKE ?" for _ in patterns)
        rows = conn.execute(
            f"""
            SELECT id, agent, action, details, created_at
            FROM agent_logs
            WHERE details IS NOT NULL AND ({conditions})
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (*patterns, limit),
        ).fetchall()
        return [cls._activity_item(row) for row in rows]

    @classmethod
    def get_student_case(cls, lead_id: int, activity_limit: int = 20):
        conn = get_connection()
        try:
            lead = conn.execute(
                "SELECT * FROM leads WHERE id = ?",
                (lead_id,),
            ).fetchone()
            if lead is None:
                return None

            applications = conn.execute(
                """
                SELECT applications.*, programs.university, programs.program,
                       programs.country
                FROM applications
                JOIN programs ON programs.id = applications.program_id
                WHERE applications.lead_id = ?
                ORDER BY applications.created_at DESC, applications.id DESC
                """,
                (lead_id,),
            ).fetchall()
            documents = conn.execute(
                """
                SELECT * FROM documents
                WHERE lead_id = ?
                ORDER BY uploaded_at DESC, id DESC
                """,
                (lead_id,),
            ).fetchall()
            tasks = conn.execute(
                """
                SELECT tasks.*, applications.program_id,
                       programs.university, programs.program
                FROM tasks
                LEFT JOIN applications ON applications.id = tasks.application_id
                LEFT JOIN programs ON programs.id = applications.program_id
                WHERE tasks.lead_id = ?
                ORDER BY tasks.due_at, tasks.id
                """,
                (lead_id,),
            ).fetchall()
            followups = conn.execute(
                "SELECT * FROM followups WHERE lead_id = ? ORDER BY created_at DESC, id DESC",
                (lead_id,),
            ).fetchall()
            escalations = conn.execute(
                "SELECT * FROM escalations WHERE lead_id = ? ORDER BY created_at DESC, id DESC",
                (lead_id,),
            ).fetchall()

            related_ids = {
                "Application": {row["id"] for row in applications},
                "Document": {row["id"] for row in documents},
                "Task": {row["id"] for row in tasks},
                "Follow-up": {row["id"] for row in followups},
                "Escalation": {row["id"] for row in escalations},
            }
            recent_activity = cls._student_activity(
                conn,
                lead_id,
                related_ids,
                activity_limit,
            )
            now = cls._now()
            serialized_tasks = []
            for row in tasks:
                task = dict(row)
                try:
                    due_at = datetime.fromisoformat(task["due_at"])
                    if due_at.tzinfo is not None:
                        due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)
                    task["is_overdue"] = task["status"] == "pending" and due_at < now
                except (TypeError, ValueError):
                    task["is_overdue"] = False
                serialized_tasks.append(task)

            return {
                "lead": dict(lead),
                "applications": [dict(row) for row in applications],
                "documents": [dict(row) for row in documents],
                "tasks": serialized_tasks,
                "followups": [dict(row) for row in followups],
                "escalations": [dict(row) for row in escalations],
                "recent_activity": recent_activity,
            }
        finally:
            conn.close()


dashboard_agent = DashboardAgent()
