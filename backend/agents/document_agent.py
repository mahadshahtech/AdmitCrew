from datetime import date, datetime

from database import get_connection


class DocumentAgent:
    """
    Checks student document information and stores the result.

    Current checks:
    - Passport expiry
    - Name mismatch
    - IELTS document ownership
    - General document status

    Results are stored so staff can review them later.
    """

    @staticmethod
    def normalize_name(name: str) -> str:
        return " ".join(name.lower().strip().split())

    @staticmethod
    def parse_date(value: str):
        formats = [
            "%d %b %Y",
            "%d %B %Y",
            "%Y-%m-%d",
            "%d/%m/%Y",
        ]

        for date_format in formats:
            try:
                return datetime.strptime(
                    value.strip(),
                    date_format,
                ).date()
            except ValueError:
                continue

        return None

    def get_lead(self, lead_id: int):
        conn = get_connection()

        row = conn.execute(
            """
            SELECT *
            FROM leads
            WHERE id = ?
            """,
            (lead_id,),
        ).fetchone()

        conn.close()

        return dict(row) if row else None

    def save_result(
        self,
        lead_id: int,
        document_type: str,
        filename: str,
        status: str,
        result: str,
    ):
        conn = get_connection()

        cursor = conn.execute(
            """
            INSERT INTO documents (
                lead_id,
                document_type,
                filename,
                status,
                result
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                document_type,
                filename,
                status,
                result,
            ),
        )

        document_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO agent_logs (
                agent,
                action,
                details
            )
            VALUES (?, ?, ?)
            """,
            (
                "document_agent",
                "document_checked",
                (
                    f"Document ID: {document_id}; "
                    f"Lead ID: {lead_id}; "
                    f"Type: {document_type}; "
                    f"Status: {status}"
                ),
            ),
        )

        conn.commit()

        saved = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

        conn.close()

        return dict(saved)

    def check_document(
        self,
        lead_id: int,
        document_type: str,
        filename: str,
        document_name: str,
        expiry_date: str | None = None,
        ielts_score: float | None = None,
    ):
        lead = self.get_lead(lead_id)

        if not lead:
            return {
                "checked": False,
                "error": "Student lead not found.",
            }

        problems = []

        expected_name = self.normalize_name(lead["name"])
        actual_name = self.normalize_name(document_name)

        # ---------------------------------------------
        # NAME CHECK
        # ---------------------------------------------

        if expected_name != actual_name:
            problems.append(
                (
                    f"Name mismatch: student record is "
                    f"'{lead['name']}' but document says "
                    f"'{document_name}'."
                )
            )

        # ---------------------------------------------
        # PASSPORT EXPIRY CHECK
        # ---------------------------------------------

        if document_type.lower() == "passport":
            if not expiry_date:
                problems.append(
                    "Passport expiry date is missing."
                )

            else:
                parsed_expiry = self.parse_date(expiry_date)

                if parsed_expiry is None:
                    problems.append(
                        "Passport expiry date could not be read."
                    )

                elif parsed_expiry < date.today():
                    problems.append(
                        (
                            "Passport is expired. "
                            f"Expiry date: {expiry_date}."
                        )
                    )

        # ---------------------------------------------
        # IELTS CHECK
        # ---------------------------------------------

        if document_type.lower() == "ielts":
            if ielts_score is None:
                problems.append(
                    "IELTS score is missing."
                )

            elif ielts_score < 0 or ielts_score > 9:
                problems.append(
                    "IELTS score is outside the valid 0–9 range."
                )

        # ---------------------------------------------
        # FINAL RESULT
        # ---------------------------------------------

        if problems:
            status = "problem"
            result_text = " ".join(problems)

        else:
            status = "ok"
            result_text = (
                f"{document_type} passed the current "
                "AdmitCrew document checks."
            )

        saved_document = self.save_result(
            lead_id=lead_id,
            document_type=document_type,
            filename=filename,
            status=status,
            result=result_text,
        )

        return {
            "checked": True,
            "status": status,
            "problems": problems,
            "document": saved_document,
        }

    def get_documents_for_lead(self, lead_id: int):
        conn = get_connection()

        rows = conn.execute(
            """
            SELECT *
            FROM documents
            WHERE lead_id = ?
            ORDER BY uploaded_at DESC, id DESC
            """,
            (lead_id,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def get_all_documents(self):
        conn = get_connection()

        rows = conn.execute(
            """
            SELECT
                documents.*,
                leads.name AS student_name,
                leads.phone AS student_phone
            FROM documents
            JOIN leads
                ON leads.id = documents.lead_id
            ORDER BY documents.uploaded_at DESC,
                     documents.id DESC
            """
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]


document_agent = DocumentAgent()