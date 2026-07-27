from __future__ import annotations

from typing import Any
from ..core.logging_setup import get_logger
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class FeedbackMixin:
    def list_journey_feedback(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user["role"] not in {"zm", "rd", "admin"}:
            raise BackendError("Feedback logbook is available to ZM, RD, and Admin.", "forbidden", 403)
        if user["role"] in {"zm", "rd"}:
            self._assert_employee_scope(user, employee_code)
        employee = self.employee(employee_code)
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, employee_code, zm_login_id, zm_name, question, answer, created_at
                FROM journey_feedback
                WHERE employee_code=?
                ORDER BY created_at DESC, id DESC
                """,
                (employee_code,),
            ).fetchall()
        return {
            "employee": employee,
            "question": FEEDBACK_QUESTION,
            "phase_open": self.phase_is_open("feedback"),
            "can_write": user["role"] == "zm" and self.phase_is_open("feedback"),
            "entries": [dict(row) for row in rows],
        }


    def submit_journey_feedback(self, user: dict[str, Any], employee_code: str, answer: str) -> dict[str, Any]:
        if user.get("role") != "zm":
            raise BackendError("Only ZMs can submit journey feedback.", "forbidden", 403)
        if not self.phase_is_open("feedback"):
            raise BackendError("Journey feedback phase is closed.", "phase_closed", 403)
        self._assert_employee_scope(user, employee_code)
        text = str(answer or "").strip()
        if len(text) < 20:
            raise BackendError("Please write a fuller response (at least a few sentences).")
        if len(text) > 4000:
            raise BackendError("Feedback is too long (max 4000 characters).")
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO journey_feedback(
                    employee_code, zm_login_id, zm_name, question, answer, created_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (
                    employee_code,
                    user["login_id"],
                    user.get("display_name") or "",
                    FEEDBACK_QUESTION,
                    text,
                    now,
                ),
            )
        return self.list_journey_feedback(user, employee_code)


    def list_kudos(self, employee_code: str) -> list[dict[str, Any]]:
        code = str(employee_code or "").strip()
        if not code:
            return []
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, employee_code, from_login_id, from_name, message, created_at
                FROM learning_kudos
                WHERE employee_code=?
                ORDER BY created_at DESC, id DESC
                """,
                (code,),
            ).fetchall()
        return [dict(row) for row in rows]


    def send_kudos(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user.get("role") != "lteam":
            raise BackendError("Only L-Team can send kudos.", "forbidden", 403)
        code = str(employee_code or "").strip()
        if not code:
            raise BackendError("employee_code is required.")
        self.employee(code)
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO learning_kudos(employee_code, from_login_id, from_name, message, created_at)
                VALUES(?,?,?,?,?)
                """,
                (code, user["login_id"], user.get("display_name") or "L-Team", KUDOS_PRESET, now),
            )
        return {
            "status": "sent",
            "message": KUDOS_PRESET,
            "employee_code": code,
            "kudos": self.list_kudos(code),
        }

