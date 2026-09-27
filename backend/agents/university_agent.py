import re

from database import get_connection
from agents.escalation_agent import escalation_agent


class UniversityAgent:
    """
    Answers university/program questions ONLY from AdmitCrew's database.
    It never invents program information.
    """

    def get_all_programs(self):
        conn = get_connection()

        rows = conn.execute(
            """
            SELECT *
            FROM programs
            ORDER BY country, university, program
            """
        ).fetchall()

        conn.close()
        return [dict(row) for row in rows]

    def search_programs(self, query: str):
        query = query.strip().lower()

        conn = get_connection()

        rows = conn.execute(
            """
            SELECT *
            FROM programs
            WHERE LOWER(university) LIKE ?
               OR LOWER(program) LIKE ?
               OR LOWER(country) LIKE ?
            ORDER BY university, program
            """,
            (
                f"%{query}%",
                f"%{query}%",
                f"%{query}%",
            ),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())

    @staticmethod
    def _amount_and_currency(value: str):
        normalized = value.strip().casefold()
        if "no tuition" in normalized:
            return None, 0.0
        if re.search(r"\bper\s+term\b|\ba\s+term\b|\bper\s+semester\b", normalized):
            return None, None

        currency_match = re.search(r"\b(cad|aud|usd|gbp|eur)\b|([£$€])", normalized)
        amount_match = re.search(r"\d[\d,]*(?:\.\d+)?", normalized)
        if currency_match is None or amount_match is None:
            return None, None
        currency = (currency_match.group(1) or currency_match.group(2) or "").casefold()
        currency = {"£": "gbp", "$": "usd", "€": "eur"}.get(currency, currency)
        try:
            amount = float(amount_match.group(0).replace(",", ""))
        except ValueError:
            return None, None
        return currency, amount

    def parse_catalog_filters(self, message: str) -> dict:
        normalized = self._normalize_text(message)
        programs = self.get_all_programs()
        countries = sorted({item["country"] for item in programs}, key=len, reverse=True)
        country = None
        for candidate in countries:
            match = re.search(rf"(?<!\w){re.escape(candidate.casefold())}(?!\w)", normalized)
            if not match:
                continue
            prefix = normalized[:match.start()]
            if re.search(r"\b(?:from|born in|based in)\s*$", prefix):
                continue
            destination_context = re.search(
                r"\b(?:study|studying|apply|applying|prefer|planning|destination)\b",
                prefix,
            ) is not None
            if destination_context or normalized.strip() == candidate.casefold():
                country = candidate
                break

        stop_words = {
            "which", "what", "where", "can", "could", "should", "i", "we",
            "apply", "applying", "universities", "university", "college",
            "program", "programs", "course", "courses", "for", "in", "the",
            "a", "an", "to", "of", "with", "have", "my", "profile", "based",
            "do", "does", "meet", "meets", "minimum", "requirements", "fee",
            "fees", "tuition", "deadline", "deadlines", "documents", "document",
            "need", "needed", "required", "requirements", "show", "find", "options",
            "options", "suitable", "eligible", "eligible", "admission", "entry",
            "marks", "mark", "ielts", "score", "scores", "and", "or", "in", "uk",
            "suit", "suits", "match", "matches", "could", "would", "might",
            "why", "how", "when", "where", "who", "whom", "whose", "verified",
            "catalog", "catalogue", "list", "listed", "give", "tell", "me",
            "us", "them", "their", "your", "our", "will", "shall", "should",
            "may", "might", "must", "can", "could", "please", "thanks", "thank",
        }
        keyword_candidates = []
        for program in programs:
            program_words = self._normalize_text(program["program"]).split()
            while program_words and program_words[0] in {
                "bsc", "ba", "bcom", "msc", "ma", "mba", "bachelor", "master", "of"
            }:
                program_words.pop(0)
            meaningful_words = [word for word in program_words if word not in {"of", "in", "and"}]
            if len(meaningful_words) >= 2 and all(
                re.search(rf"(?<!\w){re.escape(word)}(?!\w)", normalized)
                for word in meaningful_words
            ):
                keyword_candidates.append(" ".join(meaningful_words))

        if not keyword_candidates:
            words = [
                word for word in normalized.split()
                if word not in stop_words and len(word) > 2 and not word.isdigit()
            ]
            keyword_candidates = [" ".join(words)] if words else []

        keywords = list(dict.fromkeys(keyword_candidates))
        return {"country": country, "keywords": keywords}

    def search_catalog(
        self,
        country: str | None = None,
        keywords: list[str] | None = None,
        marks: float | None = None,
        ielts_score: float | None = None,
        budget: str | None = None,
    ):
        programs = self.get_all_programs()
        selected = []
        budget_currency, budget_amount = self._amount_and_currency(budget or "")
        for program in programs:
            if country and program["country"].casefold() != country.casefold():
                continue
            program_text = self._normalize_text(
                f"{program['university']} {program['program']} {program['country']}"
            )
            keyword_match = True
            for keyword in keywords or []:
                tokens = self._normalize_text(keyword).split()
                if tokens and not all(
                    re.search(rf"(?<!\w){re.escape(token)}(?!\w)", program_text)
                    for token in tokens
                ):
                    keyword_match = False
                    break
            if not keyword_match:
                continue
            if marks is not None and marks < program["min_marks"]:
                continue
            if ielts_score is not None and ielts_score < program["min_ielts"]:
                continue
            if budget_amount is not None:
                program_currency, program_amount = self._amount_and_currency(program["fee_per_year"])
                if program_amount is not None and (
                    program_amount > budget_amount
                    or budget_currency is not None
                    and program_currency is not None
                    and budget_currency != program_currency
                ):
                    continue
            selected.append(program)
        return selected

    def get_program_by_id(self, program_id: int | None):
        if program_id is None:
            return None
        conn = get_connection()
        row = conn.execute("SELECT * FROM programs WHERE id = ?", (program_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def resolve_program_from_message(
        self,
        message: str,
        contextual_program_id: int | None = None,
    ):
        normalized = self._normalize_text(message)
        if contextual_program_id is not None and re.search(
            r"\b(?:this|that|the)\s+(?:program|course|university|application)\b|\b(?:it|those requirements)\b",
            normalized,
        ):
            contextual = self.get_program_by_id(contextual_program_id)
            if contextual:
                return contextual

        programs = self.get_all_programs()
        exact_programs = [
            program for program in programs
            if self._normalize_text(program["program"]) in normalized
        ]
        if len(exact_programs) == 1:
            return exact_programs[0]

        exact_universities = [
            program for program in programs
            if self._normalize_text(program["university"]) in normalized
        ]
        if len(exact_universities) == 1:
            return exact_universities[0]
        if exact_universities:
            query_filters = self.parse_catalog_filters(message)
            narrowed = [
                program for program in exact_universities
                if query_filters["keywords"] and all(
                    all(token in self._normalize_text(program["program"]).split() for token in keyword.split())
                    for keyword in query_filters["keywords"]
                )
            ]
            if len(narrowed) == 1:
                return narrowed[0]

        return None

    def is_catalog_discovery_query(self, message: str) -> bool:
        normalized = self._normalize_text(message)
        discovery_markers = (
            "which universities", "what universities", "which programs",
            "what programs", "program options", "university options",
            "can i apply to", "universities can i apply", "find programs",
            "show programs", "courses in", "programs in",
        )
        if any(marker in normalized for marker in discovery_markers):
            return True
        filters = self.parse_catalog_filters(message)
        mentions_education = any(
            token in normalized.split()
            for token in ("study", "studying", "program", "programs", "course", "courses", "universities")
        )
        return bool(filters["country"] and filters["keywords"] and mentions_education)

    def is_explicit_unknown_university(self, message: str) -> bool:
        normalized = self._normalize_text(message)
        if self.is_catalog_discovery_query(message):
            return False
        if any(
            self._normalize_text(program["university"]) in normalized
            for program in self.get_all_programs()
        ):
            return False
        return bool(
            re.search(r"\b(?:university|college)\b", normalized)
            or re.search(r"\b(?:for|about|at)\s+[a-z][a-z0-9&'-]+(?:\s+[a-z][a-z0-9&'-]+){0,2}(?:'s)?\s+(?:fee|fees|deadline|program|course|university)", normalized)
            or re.search(r"\b(?:fee|fees|deadline|tuition)\s+(?:for|at|of)\s+[a-z][a-z0-9&'-]+", normalized)
        )

    @staticmethod
    def requested_fields(message: str) -> list[str]:
        normalized = message.casefold()
        requested = []
        if re.search(r"\b(?:fee|fees|tuition|cost|price|budget)\b", normalized):
            requested.append("fee")
        if re.search(r"\b(?:deadline|closing date|application date)\b", normalized):
            requested.append("deadline")
        if re.search(r"\b(?:documents?|passport|transcript|personal statement)\b", normalized):
            requested.append("documents")
        if re.search(r"\b(?:minimum|requirements?|marks?|percentage|ielts|score)\b", normalized):
            requested.append("requirements")
        return requested

    def respond_to_program_question(
        self,
        question: str,
        program: dict,
        requested_fields: list[str] | None = None,
        profile: dict | None = None,
        eligibility: bool = False,
    ) -> dict:
        fields = set(requested_fields or self.requested_fields(question))
        selected_profile = profile or {}
        context_update = {
            "last_program_id": program["id"],
            "last_university": program["university"],
            "last_program": program["program"],
        }

        if eligibility:
            marks = selected_profile.get("marks")
            ielts_score = selected_profile.get("ielts_score")
            lines = [
                f"For {program['university']} — {program['program']}, the listed minimums are {program['min_marks']}% marks and IELTS {program['min_ielts']}."
            ]
            outcomes = []
            if marks is None:
                lines.append("I don't have your latest-study percentage recorded, so I can't compare that part yet.")
            else:
                meets_marks = float(marks) >= float(program["min_marks"])
                outcomes.append(meets_marks)
                lines.append(
                    f"Your marks ({float(marks):g}%) {'meet' if meets_marks else 'are below'} the listed minimum of {program['min_marks']}%."
                )
            if ielts_score is None:
                if selected_profile.get("ielts_not_taken"):
                    lines.append(f"You noted that you haven't taken IELTS; this program lists {program['min_ielts']} as its minimum IELTS score.")
                else:
                    lines.append("I don't have an IELTS score recorded, so I can't compare that part yet.")
            else:
                meets_ielts = float(ielts_score) >= float(program["min_ielts"])
                outcomes.append(meets_ielts)
                lines.append(
                    f"Your IELTS score ({float(ielts_score):g}) {'meets' if meets_ielts else 'is below'} the listed minimum of {program['min_ielts']}."
                )
            if outcomes and len(outcomes) == 2 and all(outcomes):
                summary = "You meet the listed marks and IELTS minimums."
            elif any(outcome is False for outcome in outcomes):
                summary = "You do not meet every listed minimum yet."
            else:
                summary = "I need the missing profile details to compare every listed minimum."
            lines.extend([summary, "Meeting these listed minimums is not a guarantee of admission."])
            return {
                "answered": True,
                "source": "admitcrew_program_database",
                "message": " ".join(lines),
                "context_update": context_update,
            }

        if not fields:
            fields = {"fee", "deadline", "requirements", "documents"}
        parts = [f"{program['university']} — {program['program']}."]
        if "fee" in fields:
            parts.append(f"Tuition: {program['fee_per_year']} per year.")
        if "deadline" in fields:
            parts.append(f"Catalog deadline: {program['deadline']}.")
        if "requirements" in fields:
            parts.append(
                f"Listed minimums: {program['min_marks']}% marks and IELTS {program['min_ielts']}."
            )
        if "documents" in fields:
            parts.append(f"Required documents: {program['documents_needed']}.")
        parts.append("These are catalog requirements, not a promise of admission.")
        return {
            "answered": True,
            "source": "admitcrew_program_database",
            "message": " ".join(parts),
            "context_update": context_update,
        }

    def respond_to_catalog_search(
        self,
        query: str,
        filters: dict,
        profile: dict | None = None,
        use_profile: bool = False,
    ) -> dict:
        selected_profile = profile or {}
        marks = selected_profile.get("marks") if use_profile else None
        ielts_score = selected_profile.get("ielts_score") if use_profile else None
        budget = selected_profile.get("budget") if use_profile else None
        programs = self.search_catalog(
            country=filters.get("country"),
            keywords=filters.get("keywords"),
            marks=marks,
            ielts_score=ielts_score,
            budget=budget,
        )
        if not programs:
            search_summary = " and ".join(filters.get("keywords") or []) or "the selected catalog filters"
            location = f" in {filters['country']}" if filters.get("country") else ""
            return {
                "answered": True,
                "source": "admitcrew_program_database",
                "message": f"I couldn't find a verified catalog program matching {search_summary}{location}. You can try another subject or destination; I won't guess at university information.",
                "context_update": {
                    "last_program_id": None,
                    "last_university": None,
                    "last_program": None,
                },
            }

        display_programs = programs[:5]
        lines = [f"I found {len(programs)} verified catalog match{'es' if len(programs) != 1 else ''}:"]
        for item in display_programs:
            lines.append(
                f"{item['university']} — {item['program']} ({item['country']}); "
                f"fee {item['fee_per_year']}/year; deadline {item['deadline']}; "
                f"minimum {item['min_marks']}% and IELTS {item['min_ielts']}."
            )
        if len(programs) > len(display_programs):
            lines.append(f"Showing {len(display_programs)} of {len(programs)} matches.")
        lines.append("Listed minimums are not a guarantee of admission.")
        context = display_programs[0] if len(display_programs) == 1 else None
        return {
            "answered": True,
            "source": "admitcrew_program_database",
            "message": " ".join(lines),
            "programs": display_programs,
            "context_update": {
                "last_program_id": context["id"] if context else None,
                "last_university": context["university"] if context else None,
                "last_program": context["program"] if context else None,
            },
        }

    def get_program(self, university: str, program: str | None = None):
        conn = get_connection()

        if program:
            row = conn.execute(
                """
                SELECT *
                FROM programs
                WHERE LOWER(university) = LOWER(?)
                  AND LOWER(program) = LOWER(?)
                LIMIT 1
                """,
                (university.strip(), program.strip()),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT *
                FROM programs
                WHERE LOWER(university) = LOWER(?)
                LIMIT 1
                """,
                (university.strip(),),
            ).fetchone()

        conn.close()

        return dict(row) if row else None

    def answer_from_program(self, program_data: dict):
        return {
            "university": program_data["university"],
            "country": program_data["country"],
            "program": program_data["program"],
            "fee_per_year": program_data["fee_per_year"],
            "deadline": program_data["deadline"],
            "min_marks": program_data["min_marks"],
            "min_ielts": program_data["min_ielts"],
            "documents_needed": program_data["documents_needed"],
        }

    def create_escalation(
        self,
        question: str,
        reason: str = "Information not available in university database",
        lead_id: int | None = None,
        conversation_id: int | None = None,
    ):
        result = escalation_agent.create_escalation(
            question=question,
            reason=reason,
            source_agent="university_agent",
            lead_id=lead_id,
            conversation_id=conversation_id,
        )
        if result.get("error"):
            return result
        escalation = result["escalation"]
        return {
            "escalation_id": escalation["id"],
            "status": escalation["status"],
            "reason": escalation["reason"],
            "source_agent": escalation["source_agent"],
            "reused": result["reused"],
        }

    def ask_about_program(
        self,
        university: str,
        question: str,
        program: str | None = None,
        lead_id: int | None = None,
        conversation_id: int | None = None,
    ):
        result = self.get_program(university, program)

        if result:
            return {
                "answered": True,
                "source": "admitcrew_program_database",
                "data": self.answer_from_program(result),
            }

        escalation = self.create_escalation(
            question=question,
            lead_id=lead_id,
            conversation_id=conversation_id,
        )

        return {
            "answered": False,
            "escalated": True,
            "message": (
                "I don't have verified information about that program "
                "in our university list. I've passed your question to staff."
            ),
            "escalation": escalation,
        }


university_agent = UniversityAgent()