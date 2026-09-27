from datetime import date, datetime, time, timedelta, timezone

from database import get_connection


TASK_SELECT = """
    SELECT tasks.*, leads.name AS student_name,
           applications.program_id,
           programs.university AS university,
           programs.program AS program
    FROM tasks
    JOIN leads ON leads.id = tasks.lead_id
    LEFT JOIN applications ON applications.id = tasks.application_id
    LEFT JOIN programs ON programs.id = applications.program_id
"""


class TaskAgent:
    STATUSES = {"pending", "completed", "cancelled"}
    PRIORITIES = {"low", "normal", "high", "urgent"}

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @classmethod
    def _normalize_due_at(cls, value: str) -> str | None:
        if not value or not value.strip():
            return None

        normalized = value.strip()
        try:
            parsed = datetime.fromisoformat(
                normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
            )
        except ValueError:
            parsed = None

        if parsed is None:
            for date_format in ("%d %b %Y", "%d %B %Y", "%d/%m/%Y"):
                try:
                    parsed_date = datetime.strptime(normalized, date_format).date()
                    parsed = datetime.combine(parsed_date, time(23, 59, 59))
                    break
                except ValueError:
                    continue

        if parsed is None:
            return None

        if len(normalized) == 10 and parsed.time() == time.min:
            parsed = datetime.combine(parsed.date(), time(23, 59, 59))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.isoformat(timespec="seconds")

    @staticmethod
    def _catalog_deadline(value: str | None) -> str | None:
        if not value or not value.strip():
            return None

        normalized = value.strip()
        parsed_date = None
        for date_format in ("%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                parsed_date = datetime.strptime(normalized, date_format).date()
                break
            except ValueError:
                continue

        if parsed_date is None:
            return None
        return datetime.combine(parsed_date, time(23, 59, 59)).isoformat(timespec="seconds")

    @classmethod
    def _serialize(cls, row, now: datetime | None = None):
        task = dict(row)
        current_time = now or cls._now()
        try:
            due_at = datetime.fromisoformat(task["due_at"])
            if due_at.tzinfo is not None:
                due_at = due_at.astimezone(timezone.utc).replace(tzinfo=None)
            task["is_overdue"] = task["status"] == "pending" and due_at < current_time
        except (TypeError, ValueError):
            task["is_overdue"] = False
        return task

    @staticmethod
    def _log(conn, action: str, details: str):
        conn.execute(
            """
            INSERT INTO agent_logs (agent, action, details)
            VALUES ('task_agent', ?, ?)
            """,
            (action, details),
        )

    @classmethod
    def _fetch_task(cls, conn, task_id: int):
        row = conn.execute(
            TASK_SELECT + " WHERE tasks.id = ?",
            (task_id,),
        ).fetchone()
        return cls._serialize(row) if row else None

    @classmethod
    def _insert_task(
        cls,
        conn,
        *,
        lead_id: int,
        application_id: int | None,
        title: str,
        description: str | None,
        task_type: str,
        due_at: str,
        priority: str,
        automatic_key: str | None = None,
        automatic: bool = False,
    ):
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO tasks (
                lead_id, application_id, title, description, task_type,
                due_at, status, priority, automatic_key
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                lead_id,
                application_id,
                title,
                description,
                task_type,
                due_at,
                priority,
                automatic_key,
            ),
        )
        if cursor.rowcount == 0:
            existing = conn.execute(
                "SELECT id FROM tasks WHERE automatic_key = ?",
                (automatic_key,),
            ).fetchone()
            if automatic:
                cls._log(
                    conn,
                    "duplicate_generation_skipped",
                    f"Automatic task ID: {existing['id']}; key: {automatic_key}",
                )
            return existing["id"], False

        task_id = cursor.lastrowid
        cls._log(
            conn,
            "task_created",
            f"Task ID: {task_id}; Lead ID: {lead_id}; application: {application_id}",
        )
        if automatic:
            cls._log(
                conn,
                "automatic_deadline_task_generated",
                f"Task ID: {task_id}; Application ID: {application_id}; due: {due_at}",
            )
        return task_id, True

    def create_task(
        self,
        lead_id: int,
        title: str,
        task_type: str,
        due_at: str,
        description: str | None = None,
        application_id: int | None = None,
        priority: str = "normal",
    ):
        clean_title = title.strip()
        clean_type = task_type.strip()
        clean_priority = priority.strip().lower()
        normalized_due_at = self._normalize_due_at(due_at)
        if not clean_title:
            return {"error": "title_required"}
        if not clean_type:
            return {"error": "task_type_required"}
        if not normalized_due_at:
            return {"error": "invalid_due_at"}
        if clean_priority not in self.PRIORITIES:
            return {
                "error": "invalid_priority",
                "allowed_priorities": sorted(self.PRIORITIES),
            }

        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        lead = conn.execute(
            "SELECT id FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if lead is None:
            conn.close()
            return {"error": "lead_not_found"}

        if application_id is not None:
            application = conn.execute(
                "SELECT lead_id FROM applications WHERE id = ?",
                (application_id,),
            ).fetchone()
            if application is None:
                conn.close()
                return {"error": "application_not_found"}
            if application["lead_id"] != lead_id:
                conn.close()
                return {"error": "application_lead_mismatch"}

        task_id, created = self._insert_task(
            conn,
            lead_id=lead_id,
            application_id=application_id,
            title=clean_title,
            description=description.strip() if description and description.strip() else None,
            task_type=clean_type,
            due_at=normalized_due_at,
            priority=clean_priority,
        )
        conn.commit()
        task = self._fetch_task(conn, task_id)
        conn.close()
        return {"created": created, "task": task}

    def generate_application_deadline_task(self, application_id: int):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        application = conn.execute(
            """
            SELECT applications.id, applications.lead_id, applications.status,
                   programs.university, programs.program, programs.deadline
            FROM applications
            JOIN programs ON programs.id = applications.program_id
            WHERE applications.id = ?
            """,
            (application_id,),
        ).fetchone()
        if application is None:
            conn.close()
            return {"error": "application_not_found"}

        if application["status"] not in {"preparing", "ready"}:
            conn.close()
            return {
                "generated": False,
                "reason": "application_not_open_for_submission",
                "application_id": application_id,
            }

        due_at = self._catalog_deadline(application["deadline"])
        if due_at is None:
            self._log(
                conn,
                "verified_deadline_unavailable",
                f"Application ID: {application_id}; catalog deadline: {application['deadline']}",
            )
            conn.commit()
            conn.close()
            return {
                "generated": False,
                "reason": "no_verified_deadline_available",
                "application_id": application_id,
            }

        automatic_key = f"application-deadline:{application_id}"
        task_id, created = self._insert_task(
            conn,
            lead_id=application["lead_id"],
            application_id=application_id,
            title=f"Submit {application['university']} application",
            description=(
                f"Submit {application['program']} by the catalog deadline "
                f"{application['deadline']}."
            ),
            task_type="application_submission",
            due_at=due_at,
            priority="normal",
            automatic_key=automatic_key,
            automatic=True,
        )
        conn.commit()
        task = self._fetch_task(conn, task_id)
        conn.close()
        return {"generated": created, "duplicate": not created, "task": task}

    @classmethod
    def _list_by_query(cls, query: str, parameters: tuple):
        conn = get_connection()
        rows = conn.execute(
            TASK_SELECT + query,
            parameters,
        ).fetchall()
        now = cls._now()
        tasks = [cls._serialize(row, now) for row in rows]
        conn.close()
        return tasks

    def list_tasks_for_lead(self, lead_id: int):
        conn = get_connection()
        lead = conn.execute(
            "SELECT id FROM leads WHERE id = ?",
            (lead_id,),
        ).fetchone()
        if lead is None:
            conn.close()
            return None
        rows = conn.execute(
            TASK_SELECT
            + " WHERE tasks.lead_id = ? ORDER BY tasks.due_at, tasks.id",
            (lead_id,),
        ).fetchall()
        now = self._now()
        tasks = [self._serialize(row, now) for row in rows]
        conn.close()
        return tasks

    def list_tasks_for_application(self, application_id: int):
        conn = get_connection()
        application = conn.execute(
            "SELECT id FROM applications WHERE id = ?",
            (application_id,),
        ).fetchone()
        if application is None:
            conn.close()
            return None
        rows = conn.execute(
            TASK_SELECT
            + " WHERE tasks.application_id = ? ORDER BY tasks.due_at, tasks.id",
            (application_id,),
        ).fetchall()
        now = self._now()
        tasks = [self._serialize(row, now) for row in rows]
        conn.close()
        return tasks

    def list_all_tasks(
        self,
        status: str | None = None,
        lead_id: int | None = None,
        limit: int = 500,
        offset: int = 0,
    ):
        conditions = []
        parameters = []
        if status is not None:
            conditions.append("tasks.status = ?")
            parameters.append(status)
        if lead_id is not None:
            conditions.append("tasks.lead_id = ?")
            parameters.append(lead_id)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        conn = get_connection()
        rows = conn.execute(
            TASK_SELECT
            + where
            + " ORDER BY CASE WHEN tasks.status = 'pending' THEN 0 ELSE 1 END, tasks.due_at, tasks.id LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
        now = self._now()
        tasks = [self._serialize(row, now) for row in rows]
        conn.close()
        return tasks

    def get_overdue_tasks(self):
        conn = get_connection()
        now = self._now()
        rows = conn.execute(
            TASK_SELECT
            + " WHERE tasks.status = 'pending' AND tasks.due_at < ? ORDER BY tasks.due_at, tasks.id",
            (now.isoformat(timespec="seconds"),),
        ).fetchall()
        tasks = [self._serialize(row, now) for row in rows]
        self._log(conn, "overdue_scan_performed", f"Overdue pending tasks: {len(tasks)}")
        conn.commit()
        conn.close()
        return tasks

    def get_upcoming_tasks(self, days: int = 7):
        if days < 0:
            return {"error": "days_must_be_nonnegative"}

        now = self._now()
        upper_bound = now + timedelta(days=days)
        tasks = self._list_by_query(
            """
            WHERE tasks.status = 'pending'
              AND tasks.due_at >= ?
              AND tasks.due_at <= ?
            ORDER BY tasks.due_at, tasks.id
            """,
            (
                now.isoformat(timespec="seconds"),
                upper_bound.isoformat(timespec="seconds"),
            ),
        )
        conn = get_connection()
        self._log(
            conn,
            "upcoming_scan_performed",
            f"Days: {days}; upcoming pending tasks: {len(tasks)}",
        )
        conn.commit()
        conn.close()
        return tasks

    def complete_task(self, task_id: int):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        task = conn.execute(
            "SELECT id, status FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None:
            conn.close()
            return {"error": "task_not_found"}
        if task["status"] == "cancelled":
            conn.close()
            return {"error": "task_cancelled"}
        if task["status"] == "completed":
            result = self._fetch_task(conn, task_id)
            conn.close()
            return {"completed": False, "task": result}

        conn.execute(
            """
            UPDATE tasks
            SET status = 'completed',
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
            """,
            (task_id,),
        )
        self._log(conn, "task_completed", f"Task ID: {task_id}")
        conn.commit()
        result = self._fetch_task(conn, task_id)
        conn.close()
        return {"completed": True, "task": result}

    def cancel_task(self, task_id: int):
        conn = get_connection()
        conn.execute("BEGIN IMMEDIATE")
        task = conn.execute(
            "SELECT id, status FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None:
            conn.close()
            return {"error": "task_not_found"}
        if task["status"] == "completed":
            conn.close()
            return {"error": "task_completed"}
        if task["status"] == "cancelled":
            result = self._fetch_task(conn, task_id)
            conn.close()
            return {"cancelled": False, "task": result}

        conn.execute(
            """
            UPDATE tasks
            SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND status = 'pending'
            """,
            (task_id,),
        )
        self._log(conn, "task_cancelled", f"Task ID: {task_id}")
        conn.commit()
        result = self._fetch_task(conn, task_id)
        conn.close()
        return {"cancelled": True, "task": result}

    @staticmethod
    def complete_submission_tasks(conn, application_id: int):
        cursor = conn.execute(
            """
            UPDATE tasks
            SET status = 'completed',
                completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE application_id = ?
              AND task_type = 'application_submission'
              AND status = 'pending'
            """,
            (application_id,),
        )
        completed_count = cursor.rowcount
        if completed_count:
            TaskAgent._log(
                conn,
                "application_submission_task_auto_completed",
                f"Application ID: {application_id}; tasks completed: {completed_count}",
            )
        return completed_count


task_agent = TaskAgent()
