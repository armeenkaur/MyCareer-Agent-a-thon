from __future__ import annotations

from typing import Any
from ..core.logging_setup import get_logger
from ..data_sources import CAREER_MOVE_LABELS
from ..voice_live import ROLEPLAY_BUCKETS, VOICE_KINDS
from .errors import BackendError
log = get_logger('skillsync.backend')

class EmployeesMixin:
    def scoped_employees(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        role = user["role"]
        with self.db.connect() as connection:
            if role == "zm":
                rows = connection.execute("SELECT * FROM employees WHERE zm_code=? ORDER BY employee_code", (user["login_id"],)).fetchall()
            elif role == "rd":
                rows = connection.execute("SELECT * FROM employees WHERE rd_code=? ORDER BY employee_code", (user["login_id"],)).fetchall()
            elif role == "employee":
                rows = connection.execute("SELECT * FROM employees WHERE employee_code=?", (user["employee_code"],)).fetchall()
            elif role in {"admin", "lteam"}:
                rows = connection.execute("SELECT * FROM employees ORDER BY employee_code").fetchall()
            else:
                rows = []
        return [dict(row) for row in rows]


    def employee_summaries(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        """Role-scoped employee rows with workflow status for frontend tables."""
        feedback_open = self.phase_is_open("feedback")
        output = []
        for employee in self.scoped_employees(user):
            zm = self.assessment(employee["employee_code"], "zm")
            rd = self.assessment(employee["employee_code"], "rd")
            with self.db.connect() as connection:
                roleplay_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM voice_roleplay_sessions WHERE employee_code=? AND status='completed'",
                        (employee["employee_code"],),
                    ).fetchone()[0]
                )
                choice = connection.execute(
                    "SELECT aspiration_role,target_key,locked_at FROM career_choices WHERE employee_code=?",
                    (employee["employee_code"],),
                ).fetchone()
                learning_locked = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM learning_selections WHERE employee_code=?",
                        (employee["employee_code"],),
                    ).fetchone()[0]
                ) > 0 or int(
                    connection.execute(
                        "SELECT COUNT(*) FROM external_learning WHERE employee_code=?",
                        (employee["employee_code"],),
                    ).fetchone()[0]
                ) > 0
                feedback_row = connection.execute(
                    """
                    SELECT COUNT(*) AS feedback_count, MAX(created_at) AS feedback_latest_at
                    FROM journey_feedback WHERE employee_code=?
                    """,
                    (employee["employee_code"],),
                ).fetchone()
            output.append(
                {
                    **employee,
                    "zm_status": zm["status"] if zm else "not_started",
                    "rd_status": rd["status"] if rd else "not_started",
                    "zm_ratings": (zm or {}).get("ratings") or {},
                    "rd_ratings": (rd or {}).get("ratings") or {},
                    "zm_career_recommendation": (
                        (zm or {}).get("career_recommendation") or ""
                    ) if user["role"] == "admin" else "",
                    "rd_career_recommendation": (
                        (rd or {}).get("career_recommendation") or ""
                    ) if user["role"] == "admin" else "",
                    "final_profile_available": bool(rd and rd["status"] == "submitted"),
                    "roleplays_completed": roleplay_count,
                    "roleplays_total": len(VOICE_KINDS),
                    "aspiration": dict(choice) if choice else None,
                    "learning_locked": learning_locked,
                    "feedback_count": int(feedback_row["feedback_count"] or 0) if feedback_row else 0,
                    "feedback_latest_at": feedback_row["feedback_latest_at"] if feedback_row else None,
                    "feedback_phase_open": feedback_open,
                }
            )
        return output


    def profile_for_user(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user["role"] == "employee":
            if user.get("employee_code") != employee_code:
                raise BackendError("You do not have access to this profile.", "forbidden", 403)
        elif user["role"] in {"zm", "rd"}:
            self._assert_employee_scope(user, employee_code)
        profile = self.final_profile(employee_code)
        payload = {
            "employee": self.employee(employee_code),
            "status": "final" if profile else "pending",
            "ratings": profile or {},
            "ideal_ratings": self.data.ideal_for_employee(employee_code),
        }
        if user["role"] == "admin":
            zm = self.assessment(employee_code, "zm")
            rd = self.assessment(employee_code, "rd")
            payload["zm_career_recommendation"] = (zm or {}).get("career_recommendation") or ""
            payload["rd_career_recommendation"] = (rd or {}).get("career_recommendation") or ""
            payload["zm_career_recommendation_label"] = CAREER_MOVE_LABELS.get(
                str(payload["zm_career_recommendation"]), payload["zm_career_recommendation"]
            )
            payload["rd_career_recommendation_label"] = CAREER_MOVE_LABELS.get(
                str(payload["rd_career_recommendation"]), payload["rd_career_recommendation"]
            )
        return payload

