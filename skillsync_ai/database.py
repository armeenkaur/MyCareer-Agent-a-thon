from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator


ROLES = {"admin", "zm", "rd", "employee"}
ROLE_PRIORITY = ("admin", "zm", "rd", "employee")
PHASES = ("zm", "rd", "employee")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
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
            connection.executescript(
                """
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
                    role TEXT NOT NULL CHECK(role IN ('admin','zm','rd','employee')),
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
                    phase TEXT PRIMARY KEY CHECK(phase IN ('zm','rd','employee')),
                    status TEXT NOT NULL CHECK(status IN ('closed','open','complete')) DEFAULT 'closed',
                    opened_at TEXT,
                    closed_at TEXT,
                    opened_by TEXT,
                    override_used INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_code TEXT NOT NULL REFERENCES employees(employee_code),
                    assessor_role TEXT NOT NULL CHECK(assessor_role IN ('zm','rd')),
                    assessor_login_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('draft','submitted')) DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    submitted_at TEXT,
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
                """
            )
            for phase in PHASES:
                connection.execute("INSERT OR IGNORE INTO phases(phase, status) VALUES (?, 'closed')", (phase,))
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

    def clear_runtime_cache(self) -> None:
        """Clear restart-scoped sessions. Keep curated RD evidence on disk."""
        with self.transaction() as connection:
            connection.execute("DELETE FROM sessions")

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

    def _upsert_user(
        self,
        connection: sqlite3.Connection,
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
    def _row(row: sqlite3.Row | None) -> dict[str, Any]:
        return dict(row) if row else {}

    @staticmethod
    def decode_json(value: str | None, default: Any) -> Any:
        try:
            return json.loads(value or "")
        except json.JSONDecodeError:
            return default
