from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from ..core.logging_setup import get_logger
from ..core.utils import display_designation, is_kam_title, role_level_key, slug
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from ..linkedin_learning import sync_learning_activity
from ..state import RuntimeState
from .errors import BackendError
log = get_logger('skillsync.backend')

class AdminMixin:
    def agent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM agent_audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {**dict(row), "output": self.db.decode_json(row["output_json"], {})}
            for row in rows
        ]


    def talent_insights(self) -> dict[str, Any]:
        """Per-competency gap headcount vs current-role ideal (RD final profiles only)."""
        gap_counts = {competency: 0 for competency in self.competencies}
        rated_employees = 0
        employees_with_gaps = 0
        with self.db.connect() as connection:
            codes = [
                row["employee_code"]
                for row in connection.execute(
                    """
                    SELECT employee_code FROM assessments
                    WHERE assessor_role='rd' AND status='submitted'
                    ORDER BY employee_code
                    """
                ).fetchall()
            ]
        for employee_code in codes:
            if employee_code not in self.data.employees:
                continue
            rated_employees += 1
            source = self.data.employees[employee_code]
            current_key = role_level_key(
                source["designation"],
                source["level"],
                source.get("role_name") or source.get("role") or "",
            )
            gaps = self.deterministic_gaps(employee_code, current_key)
            if gaps:
                employees_with_gaps += 1
            for gap in gaps:
                competency = gap["competency"]
                if competency in gap_counts:
                    gap_counts[competency] += 1

        competencies = [
            {
                "competency": competency,
                "gap_count": gap_counts[competency],
                "rated_employees": rated_employees,
                "percentage": int(round((gap_counts[competency] / rated_employees) * 100)) if rated_employees else 0,
            }
            for competency in self.competencies
        ]
        competencies.sort(key=lambda row: (-row["gap_count"], row["competency"]))
        return {
            "rated_employees": rated_employees,
            "employees_with_gaps": employees_with_gaps,
            "competencies": competencies,
        }


    def sync_linkedin(self, admin: dict[str, Any]) -> dict[str, Any]:
        if admin["role"] != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        runtime = RuntimeState()
        result = sync_learning_activity(self.data, runtime)
        if result["status"] == "ok":
            with self.db.transaction() as connection:
                for employee_code, hours in runtime.linkedin_hours.items():
                    connection.execute(
                        """
                        INSERT INTO linkedin_activity(employee_code,learning_hours,completions,synced_at) VALUES(?,?,?,?)
                        ON CONFLICT(employee_code) DO UPDATE SET
                            learning_hours=excluded.learning_hours,completions=excluded.completions,synced_at=excluded.synced_at
                        """,
                        (employee_code, hours, runtime.linkedin_completions.get(employee_code, 0), utc_now()),
                    )
                    if float(hours or 0) > 0 or int(runtime.linkedin_completions.get(employee_code, 0) or 0) > 0:
                        day = utc_now()[:10]
                        connection.execute(
                            """
                            INSERT OR IGNORE INTO learning_activity_days(employee_code, activity_date)
                            VALUES(?, ?)
                            """,
                            (employee_code, day),
                        )
        return result


    def record_learning_day(self, employee_code: str, day: str | None = None) -> None:
        activity_date = (day or utc_now())[:10]
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO learning_activity_days(employee_code, activity_date)
                VALUES(?, ?)
                """,
                (employee_code, activity_date),
            )


    def learning_streak(self, employee_code: str) -> int:
        """Current consecutive learning-day streak ending today or yesterday."""
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT activity_date FROM learning_activity_days
                WHERE employee_code=?
                ORDER BY activity_date DESC
                """,
                (employee_code,),
            ).fetchall()
        if not rows:
            return 0
        days = {row["activity_date"][:10] for row in rows}
        today = datetime.now(timezone.utc).date()
        cursor = today
        if cursor.isoformat() not in days:
            cursor = today - timedelta(days=1)
            if cursor.isoformat() not in days:
                return 0
        streak = 0
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        return streak

    # Helpers
