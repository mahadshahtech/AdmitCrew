import sqlite3
from hashlib import sha256
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "data" / "admitcrew.db"


def escalation_dedupe_key(
    lead_id: int | None,
    conversation_id: int | None,
    question: str,
) -> str:
    normalized_question = " ".join(question.split()).casefold()
    if lead_id is not None:
        context = f"lead:{lead_id}"
    elif conversation_id is not None:
        context = f"conversation:{conversation_id}"
    else:
        context = "anonymous"
    return sha256(f"{context}\0{normalized_question}".encode("utf-8")).hexdigest()


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database():
    conn = get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            preferred_country TEXT,
            marks REAL,
            ielts_score REAL,
            budget TEXT,
            last_reply_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS staff_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'counselor')),
            is_active INTEGER NOT NULL DEFAULT 1
                CHECK (is_active IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            university TEXT NOT NULL,
            country TEXT NOT NULL,
            program TEXT NOT NULL,
            fee_per_year TEXT NOT NULL,
            deadline TEXT NOT NULL,
            min_marks REAL NOT NULL,
            min_ielts REAL NOT NULL,
            documents_needed TEXT NOT NULL,
            UNIQUE(university, program)
        );


        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lead_id)
                REFERENCES leads(id)
        );


        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
        );


        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            document_type TEXT,
            filename TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            result TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lead_id)
                REFERENCES leads(id)
        );


        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            conversation_id INTEGER,
            question TEXT NOT NULL,
            reason TEXT NOT NULL,
            source_agent TEXT,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'resolved')),
            staff_response TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT,
            dedupe_key TEXT,

            FOREIGN KEY (lead_id)
                REFERENCES leads(id) ON DELETE SET NULL,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id) ON DELETE SET NULL
        );


        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            inactivity_event_key TEXT,
            approved_at TEXT,
            sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lead_id)
                REFERENCES leads(id)
        );


        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            program_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'preparing'
                CHECK (status IN (
                    'preparing', 'ready', 'submitted', 'under_review',
                    'offer_received', 'rejected', 'withdrawn'
                )),
            notes TEXT NOT NULL DEFAULT '',
            submitted_at TEXT,
            decision_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lead_id, program_id),
            FOREIGN KEY (lead_id)
                REFERENCES leads(id) ON DELETE RESTRICT,
            FOREIGN KEY (program_id)
                REFERENCES programs(id) ON DELETE RESTRICT
        );


        CREATE TABLE IF NOT EXISTS application_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            from_status TEXT,
            to_status TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id)
                REFERENCES applications(id) ON DELETE RESTRICT
        );


        CREATE INDEX IF NOT EXISTS idx_applications_lead_created
            ON applications (lead_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_application_history_application
            ON application_history (application_id, created_at);


        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            application_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            task_type TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'completed', 'cancelled')),
            priority TEXT NOT NULL DEFAULT 'normal'
                CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
            completed_at TEXT,
            automatic_key TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id)
                REFERENCES leads(id) ON DELETE RESTRICT,
            FOREIGN KEY (application_id)
                REFERENCES applications(id) ON DELETE RESTRICT
        );


        CREATE INDEX IF NOT EXISTS idx_tasks_lead_due
            ON tasks (lead_id, due_at);

        CREATE INDEX IF NOT EXISTS idx_tasks_application_due
            ON tasks (application_id, due_at);

        CREATE INDEX IF NOT EXISTS idx_tasks_status_due
            ON tasks (status, due_at);


        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );


        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            step TEXT NOT NULL DEFAULT 'name',
            data_json TEXT NOT NULL DEFAULT '{}',
            lead_id INTEGER,
            conversation_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (lead_id)
                REFERENCES leads(id),

            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
        );
        """
    )

    followup_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(followups)").fetchall()
    }

    if "inactivity_event_key" not in followup_columns:
        conn.execute(
            "ALTER TABLE followups ADD COLUMN inactivity_event_key TEXT"
        )

    escalation_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(escalations)").fetchall()
    }
    escalation_migrations = {
        "conversation_id": (
            "ALTER TABLE escalations ADD COLUMN conversation_id "
            "INTEGER REFERENCES conversations(id) ON DELETE SET NULL"
        ),
        "source_agent": "ALTER TABLE escalations ADD COLUMN source_agent TEXT",
        "staff_response": "ALTER TABLE escalations ADD COLUMN staff_response TEXT",
        "resolved_at": "ALTER TABLE escalations ADD COLUMN resolved_at TEXT",
        "dedupe_key": "ALTER TABLE escalations ADD COLUMN dedupe_key TEXT",
    }
    for column, statement in escalation_migrations.items():
        if column not in escalation_columns:
            conn.execute(statement)

    existing_keys = {
        row["dedupe_key"]
        for row in conn.execute(
            """
            SELECT dedupe_key FROM escalations
            WHERE status IN ('open', 'in_progress') AND dedupe_key IS NOT NULL
            """
        ).fetchall()
    }
    legacy_open_escalations = conn.execute(
        """
        SELECT id, lead_id, conversation_id, question
        FROM escalations
        WHERE status IN ('open', 'in_progress')
          AND dedupe_key IS NULL
        ORDER BY id
        """
    ).fetchall()
    for escalation in legacy_open_escalations:
        dedupe_key = escalation_dedupe_key(
            escalation["lead_id"],
            escalation["conversation_id"],
            escalation["question"],
        )
        if dedupe_key not in existing_keys:
            conn.execute(
                "UPDATE escalations SET dedupe_key = ? WHERE id = ?",
                (dedupe_key, escalation["id"]),
            )
            existing_keys.add(dedupe_key)

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_escalations_active_dedupe
        ON escalations (dedupe_key)
        WHERE status IN ('open', 'in_progress') AND dedupe_key IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_escalations_status_created
        ON escalations (status, created_at)
        """
    )

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_followups_inactivity_event
        ON followups (lead_id, inactivity_event_key)
        """
    )

    conn.commit()
    conn.close()

    print(f"AdmitCrew database ready: {DB_PATH}")


if __name__ == "__main__":
    init_database()