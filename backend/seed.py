from database import get_connection


def seed():
    conn = get_connection()

    # =========================================================
    # UNIVERSITY / PROGRAM DATA
    # =========================================================

    programs = [
        # ---------- UK ----------
        (
            "University of Manchester",
            "UK",
            "BSc Computer Science",
            "£32,000",
            "15 Jan 2027",
            75,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Leeds",
            "UK",
            "BSc Business Management",
            "£27,000",
            "31 Jan 2027",
            70,
            6.5,
            "Passport, transcript, IELTS, personal statement",
        ),
        (
            "University of Birmingham",
            "UK",
            "BSc Artificial Intelligence",
            "£30,000",
            "20 Jan 2027",
            75,
            6.5,
            "Passport, transcript, IELTS, personal statement",
        ),
        (
            "University of Nottingham",
            "UK",
            "BSc Data Science",
            "£29,000",
            "25 Jan 2027",
            72,
            6.5,
            "Passport, transcript, IELTS",
        ),

        # ---------- CANADA ----------
        (
            "University of Toronto",
            "Canada",
            "BSc Computer Science",
            "CAD 60,000",
            "15 Jan 2027",
            80,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Alberta",
            "Canada",
            "BSc Computing Science",
            "CAD 35,000",
            "1 Mar 2027",
            75,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Ottawa",
            "Canada",
            "BCom Management",
            "CAD 42,000",
            "1 Feb 2027",
            72,
            6.5,
            "Passport, transcript, IELTS, personal statement",
        ),
        (
            "York University",
            "Canada",
            "BSc Information Technology",
            "CAD 38,000",
            "15 Feb 2027",
            70,
            6.5,
            "Passport, transcript, IELTS",
        ),

        # ---------- GERMANY ----------
        (
            "TU Munich",
            "Germany",
            "BSc Informatics",
            "No tuition (about €150 a term)",
            "15 Jul 2027",
            70,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "RWTH Aachen University",
            "Germany",
            "BSc Computer Engineering",
            "No tuition (about €300 a term)",
            "15 Jul 2027",
            75,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Hamburg",
            "Germany",
            "BSc Computing in Science",
            "No tuition (about €350 a term)",
            "15 Jul 2027",
            70,
            6.0,
            "Passport, transcript, IELTS",
        ),

        # ---------- AUSTRALIA ----------
        (
            "Monash University",
            "Australia",
            "Bachelor of IT",
            "AUD 48,000",
            "30 Nov 2026",
            70,
            6.0,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Sydney",
            "Australia",
            "Bachelor of Computer Science",
            "AUD 52,000",
            "1 Dec 2026",
            75,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "University of Adelaide",
            "Australia",
            "Bachelor of Software Engineering",
            "AUD 50,000",
            "15 Dec 2026",
            72,
            6.5,
            "Passport, transcript, IELTS",
        ),
        (
            "RMIT University",
            "Australia",
            "Bachelor of Information Technology",
            "AUD 44,000",
            "10 Dec 2026",
            70,
            6.0,
            "Passport, transcript, IELTS",
        ),
    ]

    conn.executemany(
        """
        INSERT OR IGNORE INTO programs (
            university,
            country,
            program,
            fee_per_year,
            deadline,
            min_marks,
            min_ielts,
            documents_needed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        programs,
    )

    # =========================================================
    # REQUIRED TEST STUDENTS
    # =========================================================

    leads = [
        (
            "Ali Khan",
            "0301 2345678",
            "UK",
            78,
            6.5,
            None,
            "Today",
        ),
        (
            "Ayesha Noor",
            "0333 9876543",
            "Canada",
            85,
            7.0,
            None,
            "Today",
        ),
        (
            "Hamza Iqbal",
            "0346 2223344",
            "UK",
            69,
            None,
            None,
            "4 days ago",
        ),
    ]

    conn.executemany(
        """
        INSERT OR IGNORE INTO leads (
            name,
            phone,
            preferred_country,
            marks,
            ielts_score,
            budget,
            last_reply_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        leads,
    )

    # =========================================================
    # SAVE EVERYTHING
    # =========================================================

    conn.commit()

    program_count = conn.execute(
        "SELECT COUNT(*) FROM programs"
    ).fetchone()[0]

    lead_count = conn.execute(
        "SELECT COUNT(*) FROM leads"
    ).fetchone()[0]

    conn.close()

    print("AdmitCrew seed completed successfully.")
    print(f"Programs: {program_count}")
    print(f"Test leads: {lead_count}")


if __name__ == "__main__":
    seed()