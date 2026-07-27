from __future__ import annotations

from typing import Any
from ..core.logging_setup import get_logger
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from ..voice_live import ROLEPLAY_BUCKETS, VOICE_KINDS
from .errors import BackendError
log = get_logger('skillsync.backend')

class PhasesMixin:
    def phase(self, phase: str) -> dict[str, Any]:
        if phase not in PHASES:
            raise BackendError("Unknown phase.")
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM phases WHERE phase=?", (phase,)).fetchone()
        result = dict(row)
        result["progress"] = self.phase_progress(phase)
        return result


    def phases(self) -> list[dict[str, Any]]:
        return [self.phase(phase) for phase in PHASES]


    def phase_is_open(self, phase: str) -> bool:
        with self.db.connect() as connection:
            row = connection.execute("SELECT status FROM phases WHERE phase=?", (phase,)).fetchone()
        return bool(row and row["status"] in {"open", "complete"})


    def phase_progress(self, phase: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0])
            if phase == "feedback":
                opened = connection.execute(
                    "SELECT opened_at FROM phases WHERE phase='feedback'"
                ).fetchone()
                opened_at = opened["opened_at"] if opened else None
                if opened_at:
                    completed = int(
                        connection.execute(
                            """
                            SELECT COUNT(DISTINCT employee_code) FROM journey_feedback
                            WHERE created_at >= ?
                            """,
                            (opened_at,),
                        ).fetchone()[0]
                    )
                else:
                    completed = int(
                        connection.execute(
                            "SELECT COUNT(DISTINCT employee_code) FROM journey_feedback"
                        ).fetchone()[0]
                    )
            elif phase in {"zm", "rd"}:
                completed = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM assessments WHERE assessor_role=? AND status='submitted'", (phase,)
                    ).fetchone()[0]
                )
            else:
                completed = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM (
                            SELECT employee_code FROM voice_roleplay_sessions
                            WHERE status='completed'
                            GROUP BY employee_code HAVING COUNT(*)=?
                        )
                        """,
                        (len(VOICE_KINDS),),
                    ).fetchone()[0]
                )
        return {
            "completed": completed,
            "total": total,
            "percentage": round((completed / total) * 100, 1) if total else 0,
            "is_complete": bool(total and completed == total),
        }


    def open_phase(self, admin: dict[str, Any], phase: str, override: bool = False) -> dict[str, Any]:
        if admin.get("role") != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        if phase not in PHASES:
            raise BackendError("Unknown phase.")
        # Feedback is an independent quarterly window — no prior-phase gate, does not close others.
        previous = {"rd": "zm", "employee": "rd"}.get(phase)
        progress = None
        if previous:
            progress = self.phase_progress(previous)
            if not progress["is_complete"] and not override:
                raise BackendError(
                    f"{previous.upper()} phase is not 100% complete. Explicit override required.",
                    "completion_gate",
                    409,
                )
        with self.db.transaction() as connection:
            if previous and progress is not None:
                previous_status = "complete" if progress["is_complete"] else "closed"
                connection.execute(
                    "UPDATE phases SET status=?, closed_at=? WHERE phase=?",
                    (previous_status, utc_now(), previous),
                )
            connection.execute(
                """
                UPDATE phases SET status='open', opened_at=?, closed_at=NULL, opened_by=?, override_used=?
                WHERE phase=?
                """,
                (utc_now(), admin["login_id"], int(override), phase),
            )
        return self.phase(phase)


    def close_phase(self, admin: dict[str, Any], phase: str) -> dict[str, Any]:
        if admin.get("role") != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        with self.db.transaction() as connection:
            connection.execute("UPDATE phases SET status='closed', closed_at=? WHERE phase=?", (utc_now(), phase))
        return self.phase(phase)

    # ZM and RD assessment workflows
