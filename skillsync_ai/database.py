from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from typing import Any, Iterator
import os
from urllib.parse import unquote, urlparse

from .db_conn import CompatConnection, connect_mysql, connect_sqlite


ROLES = {"admin", "zm", "rd", "employee", "lteam"}
ROLE_PRIORITY = ("admin", "lteam", "zm", "rd", "employee")
KUDOS_PRESET = "Kudos, you're learning curve is going good."
PHASE_FREE_ROLES = frozenset({"admin", "lteam"})
PHASES = ("zm", "rd", "employee", "feedback")
FEEDBACK_QUESTION = (
    "Looking at this employee's assigned learning journey over the past quarter: "
    "Have they started the recommended path? Have you observed any change in on-the-job "
    "behaviour (skills, habits, or impact), or do things look the same as before the journey "
    "was assigned? Please share concrete examples where you can."
)
MENTORCLOUD_URL = "https://makemytrip.mentorcloud.com/"
LTEAM_ACCOUNTS = (
    {"login_id": "MMT2351", "display_name": "Abhishek Logani", "password": "Abhishek"},
    {"login_id": "MMT12568", "display_name": "Ajeeta Yadav", "password": "Ajeeta"},
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


IST = timezone(timedelta(hours=5, minutes=30))


def ist_today() -> str:
    """Current calendar date in Asia/Kolkata (IST), YYYY-MM-DD."""
    return datetime.now(IST).date().isoformat()


def generated_password(display_name: str) -> str:
    first_name = str(display_name or "").strip().split()[0] if str(display_name or "").strip() else "User"
    return first_name[:1].upper() + first_name[1:].lower()


def _password_hash(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return salt.hex(), digest.hex()


def _password_matches(password: str, salt_hex: str, expected_hex: str) -> bool:
    _, actual = _password_hash(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(actual, expected_hex)


class Database:
    """Persistent store. MySQL when MYSQL_* / DATABASE_URL set; else SQLite file."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        engine: str | None = None,
        mysql: dict[str, Any] | None = None,
    ) -> None:
        # Explicit MySQL
        if engine == "mysql" or mysql is not None:
            cfg = mysql or mysql_config_from_env()
            if not cfg:
                raise RuntimeError("MySQL requested but MYSQL_* / DATABASE_URL not configured.")
            self.engine = "mysql"
            self.mysql = cfg
            self.path = None
            self.migrate()
            return
        # Explicit SQLite path (unit tests / local file)
        if path is not None or engine == "sqlite":
            from .core.config import DATABASE_PATH

            self.engine = "sqlite"
            self.mysql = None
            self.path = Path(path if path is not None else DATABASE_PATH)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.migrate()
            return
        # Auto: env MySQL else SQLite file
        cfg = mysql_config_from_env()
        if cfg:
            self.engine = "mysql"
            self.mysql = cfg
            self.path = None
            self.migrate()
            return
        from .core.config import DATABASE_PATH

        self.engine = "sqlite"
        self.mysql = None
        self.path = Path(DATABASE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @classmethod
    def open(cls) -> Database:
        """Production entry: MySQL if configured, otherwise local SQLite."""
        cfg = mysql_config_from_env()
        if cfg:
            return cls(engine="mysql", mysql=cfg)
        return cls(engine="sqlite")

    def connect(self) -> CompatConnection:
        if self.engine == "mysql":
            assert self.mysql is not None
            return connect_mysql(self.mysql)
        assert self.path is not None
        return connect_sqlite(str(self.path))

    @contextmanager
    def transaction(self) -> Iterator[CompatConnection]:
        connection = self.connect()
        try:
            if self.engine == "sqlite":
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connect() as connection:
            if self.engine == "mysql":
                self._migrate_mysql(connection)
            else:
                self._migrate_sqlite(connection)

    def _migrate_mysql(self, connection: CompatConnection) -> None:
        connection.executescript(MYSQL_SCHEMA)
        self._migrate_assessment_career_recommendation_note(connection)
        for phase in PHASES:
            connection.execute(
                "INSERT OR IGNORE INTO phases(phase, status) VALUES (?, 'closed')",
                (phase,),
            )

    def _migrate_sqlite(self, connection: CompatConnection) -> None:
        connection.executescript(SQLITE_SCHEMA)
        self._migrate_phases_feedback(connection)
        self._migrate_users_lteam(connection)
        self._migrate_employee_mentors(connection)
        self._migrate_voice_roleplay_sessions(connection)
        self._migrate_assessment_career_recommendation(connection)
        self._migrate_assessment_career_recommendation_note(connection)
        self._migrate_leaderboard_snapshots(connection)
        self._migrate_disclaimer_acks(connection)
        for phase in PHASES:
            connection.execute(
                "INSERT OR IGNORE INTO phases(phase, status) VALUES (?, 'closed')",
                (phase,),
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS course_progress (
                employee_code TEXT NOT NULL REFERENCES employees(employee_code),
                course_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed')) DEFAULT 'not_started',
                progress_pct INTEGER NOT NULL DEFAULT 0 CHECK(progress_pct >= 0 AND progress_pct <= 100),
                launched_at TEXT,
                completed_at TEXT,
                PRIMARY KEY(employee_code, course_id)
            )
            """
        )

    def _migrate_employee_mentors(self, connection: CompatConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_mentors (
                employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
                mentor_login_id TEXT NOT NULL,
                mentor_name TEXT NOT NULL DEFAULT '',
                selected_at TEXT NOT NULL
            )
            """
        )

    def _migrate_disclaimer_acks(self, connection: CompatConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS employee_disclaimer_acks (
                employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
                acknowledged_at TEXT NOT NULL,
                login_id TEXT NOT NULL DEFAULT ''
            )
            """
        )

    def _migrate_assessment_career_recommendation(self, connection: CompatConnection) -> None:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(assessments)").fetchall()}
        if "career_recommendation" not in columns:
            connection.execute(
                "ALTER TABLE assessments ADD COLUMN career_recommendation TEXT NOT NULL DEFAULT ''"
            )

    def _migrate_assessment_career_recommendation_note(self, connection: CompatConnection) -> None:
        if self.engine == "mysql":
            row = connection.execute(
                """
                SELECT COUNT(*) AS c FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'assessments'
                  AND COLUMN_NAME = 'career_recommendation_note'
                """
            ).fetchone()
            count = int((row["c"] if row else 0) or 0)
            if count == 0:
                connection.execute(
                    "ALTER TABLE assessments ADD COLUMN career_recommendation_note VARCHAR(2000) NOT NULL DEFAULT ''"
                )
            return
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(assessments)").fetchall()}
        if "career_recommendation_note" not in columns:
            connection.execute(
                "ALTER TABLE assessments ADD COLUMN career_recommendation_note TEXT NOT NULL DEFAULT ''"
            )

    def _migrate_leaderboard_snapshots(self, connection: CompatConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
                cache_key TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                PRIMARY KEY(cache_key, snapshot_date)
            )
            """
        )

    def _migrate_voice_roleplay_sessions(self, connection: CompatConnection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_roleplay_sessions (
                employee_code TEXT NOT NULL REFERENCES employees(employee_code),
                kind TEXT NOT NULL CHECK(kind IN ('functional','behavioural')),
                status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed','failed'))
                    DEFAULT 'not_started',
                scores_json TEXT NOT NULL DEFAULT '{}',
                error TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(employee_code, kind)
            )
            """
        )

    def _migrate_phases_feedback(self, connection: CompatConnection) -> None:
        """Widen phases CHECK to include feedback; create journey_feedback if missing."""
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS journey_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL REFERENCES employees(employee_code),
                zm_login_id TEXT NOT NULL,
                zm_name TEXT NOT NULL DEFAULT '',
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_journey_feedback_employee
                ON journey_feedback(employee_code, created_at DESC)
            """
        )
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='phases'"
        ).fetchone()
        sql = (row["sql"] if row else "") or ""
        if "'feedback'" in sql:
            return
        connection.executescript(
            """
            CREATE TABLE phases_new (
                phase TEXT PRIMARY KEY CHECK(phase IN ('zm','rd','employee','feedback')),
                status TEXT NOT NULL CHECK(status IN ('closed','open','complete')) DEFAULT 'closed',
                opened_at TEXT,
                closed_at TEXT,
                opened_by TEXT,
                override_used INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO phases_new(phase, status, opened_at, closed_at, opened_by, override_used)
            SELECT phase, status, opened_at, closed_at, opened_by, override_used FROM phases;
            DROP TABLE phases;
            ALTER TABLE phases_new RENAME TO phases;
            """
        )

    def _migrate_users_lteam(self, connection: CompatConnection) -> None:
        """Widen users CHECK for lteam; ensure learning_kudos exists."""
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS learning_kudos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL REFERENCES employees(employee_code),
                from_login_id TEXT NOT NULL,
                from_name TEXT NOT NULL DEFAULT '',
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_learning_kudos_employee
                ON learning_kudos(employee_code, created_at DESC)
            """
        )
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        sql = (row["sql"] if row else "") or ""
        if "'lteam'" in sql:
            return
        connection.executescript(
            """
            PRAGMA foreign_keys = OFF;
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','zm','rd','employee','lteam')),
                display_name TEXT NOT NULL,
                employee_code TEXT,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(login_id, role)
            );
            INSERT INTO users_new(
                id, login_id, role, display_name, employee_code,
                password_salt, password_hash, active, created_at, updated_at
            )
            SELECT id, login_id, role, display_name, employee_code,
                password_salt, password_hash, active, created_at, updated_at
            FROM users;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
            PRAGMA foreign_keys = ON;
            """
        )

    def clear_runtime_cache(self) -> None:
        """Drop auth sessions only. Workflow data stays on disk across restarts."""
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions")

    def ensure_phases_open(self) -> None:
        """Open every phase window (zm/rd/employee/feedback) for local / hackathon use."""
        now = utc_now()
        with self.transaction() as connection:
            for phase in PHASES:
                connection.execute(
                    "INSERT OR IGNORE INTO phases(phase, status, opened_at) VALUES (?, 'open', ?)",
                    (phase, now),
                )
                connection.execute(
                    """
                    UPDATE phases
                    SET status='open',
                        opened_at=COALESCE(opened_at, ?),
                        closed_at=NULL,
                        opened_by=COALESCE(opened_by, 'system'),
                        override_used=1
                    WHERE phase=? AND status!='open'
                    """,
                    (now, phase),
                )

    def seed_from_workbooks(self, data: Any) -> None:
        now = utc_now()
        with self.transaction() as connection:
            for employee in data.employees.values():
                connection.execute(
                    """
                    INSERT INTO employees(
                        employee_code,name,designation,role_name,grade,location,cohort,
                        zm_code,zm_name,rd_code,rd_name,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(employee_code) DO UPDATE SET
                        name=excluded.name, designation=excluded.designation, role_name=excluded.role_name,
                        grade=excluded.grade, location=excluded.location, cohort=excluded.cohort,
                        zm_code=excluded.zm_code, zm_name=excluded.zm_name,
                        rd_code=excluded.rd_code, rd_name=excluded.rd_name, updated_at=excluded.updated_at
                    """,
                    (
                        employee["code"], employee["name"], employee.get("designation", ""),
                        employee.get("role", ""), employee.get("level", ""), employee.get("location", ""),
                        employee.get("cohort", ""), employee.get("manager_code", ""), employee.get("manager", ""),
                        employee.get("rd_code", ""), employee.get("rd", ""), now,
                    ),
                )
                self._upsert_user(connection, employee["code"], "employee", employee["name"], employee["code"])
            for manager in data.manager_accounts():
                self._upsert_user(connection, manager["code"], "zm", manager["name"], None)
            for rd in data.rd_accounts():
                self._upsert_user(connection, rd["code"], "rd", rd["name"], None)
            self._upsert_user(connection, "ADMIN", "admin", "Admin", None)
            # Legacy shared LTeam login → real L-Team members
            connection.execute(
                "UPDATE users SET active=0, updated_at=? WHERE login_id=? AND role=?",
                (now, "LTeam", "lteam"),
            )
            for account in LTEAM_ACCOUNTS:
                self._upsert_user(
                    connection,
                    account["login_id"],
                    "lteam",
                    account["display_name"],
                    None,
                )
                self._force_password(
                    connection,
                    account["login_id"],
                    "lteam",
                    account["password"],
                )

    def _force_password(
        self,
        connection: CompatConnection,
        login_id: str,
        role: str,
        password: str,
    ) -> None:
        salt, password_hash = _password_hash(password)
        connection.execute(
            """
            UPDATE users SET password_salt=?, password_hash=?, updated_at=?
            WHERE login_id=? AND role=?
            """,
            (salt, password_hash, utc_now(), login_id, role),
        )

    def _upsert_user(
        self,
        connection: CompatConnection,
        login_id: str,
        role: str,
        display_name: str,
        employee_code: str | None,
    ) -> None:
        existing = connection.execute(
            "SELECT id FROM users WHERE login_id=? AND role=?", (login_id, role)
        ).fetchone()
        now = utc_now()
        if existing:
            connection.execute(
                "UPDATE users SET display_name=?, employee_code=?, active=1, updated_at=? WHERE id=?",
                (display_name, employee_code, now, existing["id"]),
            )
            return
        sibling = connection.execute(
            "SELECT password_salt,password_hash FROM users WHERE login_id=? AND active=1 LIMIT 1",
            (login_id,),
        ).fetchone()
        if sibling:
            salt, password_hash = sibling["password_salt"], sibling["password_hash"]
        else:
            salt, password_hash = _password_hash(generated_password(display_name))
        connection.execute(
            """
            INSERT INTO users(login_id,role,display_name,employee_code,password_salt,password_hash,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (login_id, role, display_name, employee_code, salt, password_hash, now, now),
        )

    def authenticate(self, login_id: str, role: str, password: str) -> dict[str, Any] | None:
        if role not in ROLES:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE login_id=? AND role=? AND active=1",
                (login_id.strip(), role),
            ).fetchone()
        if not row or not _password_matches(password, row["password_salt"], row["password_hash"]):
            return None
        return self._row(row)

    def authenticate_login(self, login_id: str, password: str) -> list[dict[str, Any]]:
        """Return every active role row for login_id that accepts password."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users WHERE login_id=? AND active=1",
                (login_id.strip(),),
            ).fetchall()
        matched = [
            self._row(row)
            for row in rows
            if _password_matches(password, row["password_salt"], row["password_hash"])
        ]
        order = {role: index for index, role in enumerate(ROLE_PRIORITY)}
        return sorted(matched, key=lambda row: order.get(row["role"], 99))

    def roles_for_login(self, login_id: str) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT role FROM users WHERE login_id=? AND active=1",
                (login_id.strip(),),
            ).fetchall()
        order = {role: index for index, role in enumerate(ROLE_PRIORITY)}
        roles = [row["role"] for row in rows]
        return sorted(roles, key=lambda role: order.get(role, 99))

    def user_by_login_role(self, login_id: str, role: str) -> dict[str, Any] | None:
        if role not in ROLES:
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE login_id=? AND role=? AND active=1",
                (login_id.strip(), role),
            ).fetchone()
        return self._row(row) if row else None

    def change_password(self, login_id: str, role: str, current_password: str, new_password: str) -> None:
        if role not in ROLES:
            raise ValueError("Unknown role.")
        if not str(new_password or "").strip():
            raise ValueError("New password is required.")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE login_id=? AND role=? AND active=1",
                (login_id.strip(), role),
            ).fetchone()
        if not row or not _password_matches(current_password, row["password_salt"], row["password_hash"]):
            raise ValueError("Current password is incorrect.")
        salt, password_hash = _password_hash(new_password)
        now = utc_now()
        with self.transaction() as connection:
            # One person → one password: sync every role row for this login_id.
            connection.execute(
                "UPDATE users SET password_salt=?, password_hash=?, updated_at=? WHERE login_id=? AND active=1",
                (salt, password_hash, now, login_id.strip()),
            )

    def create_session(self, user_id: int, hours: int = 12) -> str:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(hours=hours)
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at < ?", (utc_now(),))
            connection.execute(
                "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (token_hash, user_id, expires.replace(microsecond=0).isoformat(), utc_now()),
            )
        return token

    def session_user(self, token: str) -> dict[str, Any] | None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=? AND s.expires_at>=? AND u.active=1
                """,
                (token_hash, utc_now()),
            ).fetchone()
        return self._row(row) if row else None

    def delete_session(self, token: str) -> None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return dict(row) if row else {}

    @staticmethod
    def decode_json(value: str | None, default: Any) -> Any:
        try:
            return json.loads(value or "")
        except json.JSONDecodeError:
            return default


def mysql_config_from_env() -> dict[str, Any] | None:
    """Parse DATABASE_URL=mysql://... or MYSQL_HOST/USER/PASSWORD/DATABASE."""
    url = (os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL") or "").strip()
    if url.startswith("mysql://") or url.startswith("mysql+pymysql://"):
        parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
        if not parsed.hostname or not parsed.path.strip("/"):
            return None
        return {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or "root"),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.strip("/").split("/")[0],
        }
    host = (os.environ.get("MYSQL_HOST") or "").strip()
    database = (os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQL_DB") or "").strip()
    user = (os.environ.get("MYSQL_USER") or "").strip()
    if not (host and database and user):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("MYSQL_PORT") or 3306),
        "user": user,
        "password": os.environ.get("MYSQL_PASSWORD") or "",
        "database": database,
    }




SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    employee_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    designation TEXT NOT NULL DEFAULT '',
    role_name TEXT NOT NULL DEFAULT '',
    grade TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    cohort TEXT NOT NULL DEFAULT '',
    zm_code TEXT NOT NULL DEFAULT '',
    zm_name TEXT NOT NULL DEFAULT '',
    rd_code TEXT NOT NULL DEFAULT '',
    rd_name TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','zm','rd','employee','lteam')),
    display_name TEXT NOT NULL,
    employee_code TEXT,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(login_id, role)
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phases (
    phase TEXT PRIMARY KEY CHECK(phase IN ('zm','rd','employee','feedback')),
    status TEXT NOT NULL CHECK(status IN ('closed','open','complete')) DEFAULT 'closed',
    opened_at TEXT,
    closed_at TEXT,
    opened_by TEXT,
    override_used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS journey_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    zm_login_id TEXT NOT NULL,
    zm_name TEXT NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_journey_feedback_employee
    ON journey_feedback(employee_code, created_at DESC);
CREATE TABLE IF NOT EXISTS learning_kudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    from_login_id TEXT NOT NULL,
    from_name TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_learning_kudos_employee
    ON learning_kudos(employee_code, created_at DESC);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    assessor_role TEXT NOT NULL CHECK(assessor_role IN ('zm','rd')),
    assessor_login_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('draft','submitted')) DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    submitted_at TEXT,
    career_recommendation TEXT NOT NULL DEFAULT '',
    career_recommendation_note TEXT NOT NULL DEFAULT '',
    UNIQUE(employee_code, assessor_role)
);
CREATE TABLE IF NOT EXISTS assessment_ratings (
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    competency TEXT NOT NULL,
    proficiency TEXT NOT NULL CHECK(proficiency IN ('Beginner','Intermediate','Proficient','Advanced')),
    note TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(assessment_id, competency)
);
CREATE TABLE IF NOT EXISTS curated_evidence (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    competency TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, competency)
);
CREATE TABLE IF NOT EXISTS roleplay_assessments (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    competency TEXT NOT NULL,
    filename TEXT NOT NULL DEFAULT '',
    file_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK(status IN ('not_started','processing','completed','reupload_required','service_unavailable')),
    ai_proficiency TEXT,
    rationale TEXT NOT NULL DEFAULT '',
    ocr_text TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, competency)
);
CREATE TABLE IF NOT EXISTS career_choices (
    employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
    aspiration_role TEXT NOT NULL,
    target_key TEXT NOT NULL,
    locked_at TEXT NOT NULL,
    reset_at TEXT,
    reset_by TEXT
);
CREATE TABLE IF NOT EXISTS course_recommendations (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    target_key TEXT NOT NULL,
    competency TEXT NOT NULL,
    current_level TEXT NOT NULL,
    target_level TEXT NOT NULL,
    candidate_ids_json TEXT NOT NULL,
    courses_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, target_key, competency)
);
CREATE TABLE IF NOT EXISTS learning_selections (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    competency TEXT NOT NULL,
    course_id TEXT NOT NULL,
    selected_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, course_id)
);
CREATE TABLE IF NOT EXISTS external_learning (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    resource_id TEXT NOT NULL,
    competency TEXT NOT NULL,
    resource_json TEXT NOT NULL,
    clicked_at TEXT,
    completed_at TEXT,
    PRIMARY KEY(employee_code, resource_id)
);
CREATE TABLE IF NOT EXISTS other_source_recommendations (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    target_key TEXT NOT NULL,
    competency TEXT NOT NULL,
    picks_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, target_key, competency)
);
CREATE TABLE IF NOT EXISTS linkedin_activity (
    employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
    learning_hours REAL NOT NULL DEFAULT 0,
    completions INTEGER NOT NULL DEFAULT 0,
    synced_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employee_badges (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    badge_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    earned_at TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(employee_code, badge_id)
);
CREATE TABLE IF NOT EXISTS learning_activity_days (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    activity_date TEXT NOT NULL,
    PRIMARY KEY(employee_code, activity_date)
);
CREATE TABLE IF NOT EXISTS course_progress (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    course_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed')) DEFAULT 'not_started',
    progress_pct INTEGER NOT NULL DEFAULT 0 CHECK(progress_pct >= 0 AND progress_pct <= 100),
    launched_at TEXT,
    completed_at TEXT,
    PRIMARY KEY(employee_code, course_id)
);
CREATE TABLE IF NOT EXISTS agent_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code TEXT NOT NULL,
    agent TEXT NOT NULL,
    competency TEXT NOT NULL DEFAULT '',
    input_summary TEXT NOT NULL DEFAULT '',
    output_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employee_mentors (
    employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
    mentor_login_id TEXT NOT NULL,
    mentor_name TEXT NOT NULL DEFAULT '',
    selected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employee_disclaimer_acks (
    employee_code TEXT PRIMARY KEY REFERENCES employees(employee_code),
    acknowledged_at TEXT NOT NULL,
    login_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    cache_key TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY(cache_key, snapshot_date)
);
CREATE TABLE IF NOT EXISTS voice_roleplay_sessions (
    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
    kind TEXT NOT NULL CHECK(kind IN ('functional','behavioural')),
    status TEXT NOT NULL CHECK(status IN ('not_started','in_progress','completed','failed')) DEFAULT 'not_started',
    scores_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(employee_code, kind)
);
"""

MYSQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    employee_code VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    designation VARCHAR(255) NOT NULL DEFAULT '',
    role_name VARCHAR(255) NOT NULL DEFAULT '',
    grade VARCHAR(64) NOT NULL DEFAULT '',
    location VARCHAR(255) NOT NULL DEFAULT '',
    cohort VARCHAR(255) NOT NULL DEFAULT '',
    zm_code VARCHAR(64) NOT NULL DEFAULT '',
    zm_name VARCHAR(255) NOT NULL DEFAULT '',
    rd_code VARCHAR(64) NOT NULL DEFAULT '',
    rd_name VARCHAR(255) NOT NULL DEFAULT '',
    updated_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    login_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    employee_code VARCHAR(64) NULL,
    password_salt VARCHAR(128) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    active TINYINT NOT NULL DEFAULT 1,
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    UNIQUE KEY uq_users_login_role (login_id, role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS sessions (
    token_hash VARCHAR(128) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS phases (
    phase VARCHAR(32) PRIMARY KEY,
    status VARCHAR(32) NOT NULL DEFAULT 'closed',
    opened_at VARCHAR(64) NULL,
    closed_at VARCHAR(64) NULL,
    opened_by VARCHAR(64) NULL,
    override_used TINYINT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS journey_feedback (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_code VARCHAR(64) NOT NULL,
    zm_login_id VARCHAR(64) NOT NULL,
    zm_name VARCHAR(255) NOT NULL DEFAULT '',
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_journey_feedback_employee (employee_code, created_at),
    CONSTRAINT fk_jf_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS learning_kudos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_code VARCHAR(64) NOT NULL,
    from_login_id VARCHAR(64) NOT NULL,
    from_name VARCHAR(255) NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    created_at VARCHAR(64) NOT NULL,
    KEY idx_learning_kudos_employee (employee_code, created_at),
    CONSTRAINT fk_kudos_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_code VARCHAR(64) NOT NULL,
    assessor_role VARCHAR(8) NOT NULL,
    assessor_login_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    created_at VARCHAR(64) NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    submitted_at VARCHAR(64) NULL,
    career_recommendation VARCHAR(64) NOT NULL DEFAULT '',
    career_recommendation_note VARCHAR(2000) NOT NULL DEFAULT '',
    UNIQUE KEY uq_assessment_emp_role (employee_code, assessor_role),
    CONSTRAINT fk_assess_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS assessment_ratings (
    assessment_id INT NOT NULL,
    competency VARCHAR(128) NOT NULL,
    proficiency VARCHAR(32) NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (assessment_id, competency),
    CONSTRAINT fk_ar_assess FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS curated_evidence (
    employee_code VARCHAR(64) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    evidence_json MEDIUMTEXT NOT NULL,
    generated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, competency),
    CONSTRAINT fk_ce_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS roleplay_assessments (
    employee_code VARCHAR(64) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    filename VARCHAR(512) NOT NULL DEFAULT '',
    file_path VARCHAR(1024) NOT NULL DEFAULT '',
    status VARCHAR(64) NOT NULL,
    ai_proficiency VARCHAR(32) NULL,
    rationale TEXT NOT NULL,
    ocr_text MEDIUMTEXT NOT NULL,
    error TEXT NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, competency),
    CONSTRAINT fk_ra_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS career_choices (
    employee_code VARCHAR(64) PRIMARY KEY,
    aspiration_role VARCHAR(64) NOT NULL,
    target_key VARCHAR(128) NOT NULL,
    locked_at VARCHAR(64) NOT NULL,
    reset_at VARCHAR(64) NULL,
    reset_by VARCHAR(64) NULL,
    CONSTRAINT fk_cc_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS course_recommendations (
    employee_code VARCHAR(64) NOT NULL,
    target_key VARCHAR(128) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    current_level VARCHAR(32) NOT NULL,
    target_level VARCHAR(32) NOT NULL,
    candidate_ids_json MEDIUMTEXT NOT NULL,
    courses_json MEDIUMTEXT NOT NULL,
    generated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, target_key, competency),
    CONSTRAINT fk_cr_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS learning_selections (
    employee_code VARCHAR(64) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    course_id VARCHAR(128) NOT NULL,
    selected_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, course_id),
    CONSTRAINT fk_ls_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS external_learning (
    employee_code VARCHAR(64) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    resource_json MEDIUMTEXT NOT NULL,
    clicked_at VARCHAR(64) NULL,
    completed_at VARCHAR(64) NULL,
    PRIMARY KEY (employee_code, resource_id),
    CONSTRAINT fk_el_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS other_source_recommendations (
    employee_code VARCHAR(64) NOT NULL,
    target_key VARCHAR(128) NOT NULL,
    competency VARCHAR(128) NOT NULL,
    picks_json MEDIUMTEXT NOT NULL,
    generated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, target_key, competency),
    CONSTRAINT fk_osr_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS linkedin_activity (
    employee_code VARCHAR(64) PRIMARY KEY,
    learning_hours DOUBLE NOT NULL DEFAULT 0,
    completions INT NOT NULL DEFAULT 0,
    synced_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_la_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS employee_badges (
    employee_code VARCHAR(64) NOT NULL,
    badge_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT '',
    earned_at VARCHAR(64) NOT NULL,
    meta_json TEXT NOT NULL,
    PRIMARY KEY (employee_code, badge_id),
    CONSTRAINT fk_eb_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS learning_activity_days (
    employee_code VARCHAR(64) NOT NULL,
    activity_date VARCHAR(32) NOT NULL,
    PRIMARY KEY (employee_code, activity_date),
    CONSTRAINT fk_lad_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS course_progress (
    employee_code VARCHAR(64) NOT NULL,
    course_id VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'not_started',
    progress_pct INT NOT NULL DEFAULT 0,
    launched_at VARCHAR(64) NULL,
    completed_at VARCHAR(64) NULL,
    PRIMARY KEY (employee_code, course_id),
    CONSTRAINT fk_cp_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS agent_audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_code VARCHAR(64) NOT NULL,
    agent VARCHAR(128) NOT NULL,
    competency VARCHAR(128) NOT NULL DEFAULT '',
    input_summary TEXT NOT NULL,
    output_json MEDIUMTEXT NOT NULL,
    status VARCHAR(64) NOT NULL,
    created_at VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS employee_mentors (
    employee_code VARCHAR(64) PRIMARY KEY,
    mentor_login_id VARCHAR(64) NOT NULL,
    mentor_name VARCHAR(255) NOT NULL DEFAULT '',
    selected_at VARCHAR(64) NOT NULL,
    CONSTRAINT fk_em_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS employee_disclaimer_acks (
    employee_code VARCHAR(64) PRIMARY KEY,
    acknowledged_at VARCHAR(64) NOT NULL,
    login_id VARCHAR(64) NOT NULL DEFAULT '',
    CONSTRAINT fk_eda_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    cache_key VARCHAR(128) NOT NULL,
    snapshot_date VARCHAR(32) NOT NULL,
    payload_json MEDIUMTEXT NOT NULL,
    computed_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (cache_key, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS voice_roleplay_sessions (
    employee_code VARCHAR(64) NOT NULL,
    kind VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'not_started',
    scores_json MEDIUMTEXT NOT NULL,
    error TEXT NOT NULL,
    updated_at VARCHAR(64) NOT NULL,
    PRIMARY KEY (employee_code, kind),
    CONSTRAINT fk_vrs_emp FOREIGN KEY (employee_code) REFERENCES employees(employee_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
