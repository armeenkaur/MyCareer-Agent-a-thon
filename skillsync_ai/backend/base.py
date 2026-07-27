from __future__ import annotations

import json
from typing import Any
from ..agents.evidence_curator import AGENT_NAME as EVIDENCE_AGENT, CURATOR_VERSION, curate_evidence
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from ..core.logging_setup import get_logger
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class BackendBase:
    def __init__(self, data: Any, database: Database) -> None:
        self.data = data
        self.db = database
        self.db.clear_runtime_cache()
        self.db.seed_from_workbooks(data)
        self.competencies = [row["skill"] for row in data.competencies]

    # Authentication and phase gates

    def employee(self, employee_code: str) -> dict[str, Any]:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM employees WHERE employee_code=?", (employee_code,)).fetchone()
        if not row:
            raise BackendError("Employee not found.", "not_found", 404)
        return dict(row)


    def _assert_employee_scope(self, user: dict[str, Any], employee_code: str) -> None:
        if employee_code not in {row["employee_code"] for row in self.scoped_employees(user)}:
            raise BackendError("Employee is outside your reporting scope.", "forbidden", 403)


    def _validate_ratings(self, ratings: dict[str, str], complete: bool) -> None:
        unknown = set(ratings) - set(self.competencies)
        invalid = {key: value for key, value in ratings.items() if value not in PROFICIENCY_ORDER}
        if unknown or invalid:
            raise BackendError("Ratings contain unknown competencies or proficiency levels.")
        if complete and set(ratings) != set(self.competencies):
            raise BackendError("All seven competency ratings are required before submission.")


    def _validate_career_recommendation(self, employee_code: str, recommendation: str) -> None:
        allowed = {row["id"] for row in self.data.manager_career_move_options(self.employee(employee_code))}
        if recommendation not in allowed:
            raise BackendError(
                "Select a valid career move recommendation before submission.",
                "career_recommendation_required",
                400,
            )

    @staticmethod

    def _course_contract(
        course: dict[str, Any], competency: str, current_level: str, target_level: str
    ) -> dict[str, Any]:
        """Expose catalog fields using the stable frontend vocabulary."""
        return {
            **course,
            "provider": course.get("author") or "LinkedIn Learning",
            "source_type": "LinkedIn Learning",
            "competency": competency,
            "supported_proficiency_movement": {
                "from": current_level,
                "to": target_level,
            },
        }


    def _cached_evidence(self, employee_code: str, competency: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT evidence_json FROM curated_evidence WHERE employee_code=? AND competency=?",
                (employee_code, competency),
            ).fetchone()
        if not row:
            return None
        payload = self.db.decode_json(row["evidence_json"], None)
        if not isinstance(payload, dict):
            return None
        # Bust stale curator output so RD always sees competency-scoped evidence.
        if payload.get("curator_version") != CURATOR_VERSION:
            return None
        return payload


    def _save_evidence(self, employee_code: str, competency: str, payload: dict[str, Any]) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO curated_evidence(employee_code,competency,evidence_json,generated_at) VALUES(?,?,?,?)
                ON CONFLICT(employee_code,competency) DO UPDATE SET evidence_json=excluded.evidence_json,generated_at=excluded.generated_at
                """,
                (employee_code, competency, json.dumps(payload), utc_now()),
            )


    def _audit(
        self, employee_code: str, agent: str, competency: str, input_summary: str,
        output: dict[str, Any], status: str,
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO agent_audit(employee_code,agent,competency,input_summary,output_json,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (employee_code, agent, competency, input_summary[:1000], json.dumps(output, default=str), status, utc_now()),
            )
