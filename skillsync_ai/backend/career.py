from __future__ import annotations

from typing import Any
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from ..core.logging_setup import get_logger
from ..core.utils import display_designation, is_kam_title, role_level_key, slug
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class CareerMixin:
    def career_state(self, employee_code: str) -> dict[str, Any]:
        employee = self.employee(employee_code)
        with self.db.connect() as connection:
            choice = connection.execute("SELECT * FROM career_choices WHERE employee_code=?", (employee_code,)).fetchone()
        role = self._current_role(employee)
        grade = str(employee.get("grade") or "").strip()
        paths = self._career_paths(employee)
        journey = self._career_journey(employee, paths)
        insights = self._career_insights(employee_code, employee, role, grade, paths)
        skill_summary = self._skill_summary(employee_code)
        return {
            "unlocked": self.lattice_unlocked(employee_code),
            "current": role,
            "current_label": self._current_role_label(role, grade),
            "grade": grade,
            "designation": display_designation(
                employee.get("designation") or "",
                employee.get("role_name") or employee.get("role") or "",
                short=False,
            ),
            "paths": paths,
            "journey": journey,
            "insights": insights,
            "skill_summary": skill_summary,
            "choice": dict(choice) if choice else None,
        }


    def _skill_summary(self, employee_code: str) -> dict[str, Any]:
        """Compare final RD profile to current-role ideal: strengths vs improve list."""
        actual = self.final_profile(employee_code)
        if not actual:
            return {
                "has_profile": False,
                "ideal_met": False,
                "good_at": [],
                "improve": [],
            }
        ideal = self.data.ideal_for_employee(employee_code)
        good_at: list[str] = []
        improve: list[str] = []
        for competency in self.competencies:
            current = PROFICIENCY_VALUE.get(actual.get(competency) or "", 0)
            target = PROFICIENCY_VALUE.get(ideal.get(competency) or "", 0)
            if not target:
                continue
            if current >= target:
                good_at.append(competency)
            else:
                improve.append(competency)
        return {
            "has_profile": True,
            "ideal_met": len(improve) == 0,
            "good_at": good_at,
            "improve": improve,
        }


    def _current_role_label(self, role: str, grade: str) -> str:
        prefix = "BD" if role == "BDM" else role
        return f"{prefix} {grade}".strip() if grade else prefix


    def _career_journey(self, employee: dict[str, Any], paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
        role = self._current_role(employee)
        grade = str(employee.get("grade") or "").strip()
        nodes = [
            {
                "id": "current",
                "label": self._current_role_label(role, grade),
                "short_label": self._current_role_label(role, grade),
                "tier": "start",
                "enabled": True,
                "state": "current",
                "selectable": False,
            }
        ]
        for path in paths:
            nodes.append(
                {
                    "id": path["id"],
                    "label": path["label"],
                    "short_label": path["id"].upper(),
                    "tier": "eligible" if path["enabled"] else "future",
                    "enabled": bool(path["enabled"]),
                    "state": path["state"],
                    "selectable": bool(path["enabled"]),
                    "target_key": path.get("target_key") or "",
                }
            )
        return nodes


    def _career_insights(
        self,
        employee_code: str,
        employee: dict[str, Any],
        role: str,
        grade: str,
        paths: list[dict[str, Any]],
    ) -> dict[str, Any]:
        label = self._current_role_label(role, grade)
        enabled = [path for path in paths if path["enabled"]]
        locked = [path for path in paths if not path["enabled"]]
        next_path = enabled[0] if enabled else None
        growth = (
            f"{len(enabled)} eligible path{'s' if len(enabled) != 1 else ''} from your current position as {label}."
            if enabled
            else f"No eligible next roles from {label} in this portal. Focus on mastering your current role."
        )
        key_competency = "Complete RD validation to unlock competency-based path guidance."
        eligibility_pct = None
        eligibility_label = next_path["label"] if next_path else "Path readiness"
        profile = self.final_profile(employee_code)
        if next_path and profile:
            ideal = self.data.ideal_for_role_key(next_path["target_key"])
            scores = []
            weakest = None
            weakest_gap = 0
            for competency in self.competencies:
                current = profile.get(competency)
                target = ideal.get(competency)
                cur_v = PROFICIENCY_VALUE.get(current or "", 0)
                tgt_v = PROFICIENCY_VALUE.get(target or "", 0)
                if not tgt_v:
                    continue
                scores.append(min(1.0, cur_v / tgt_v))
                gap = tgt_v - cur_v
                if gap > weakest_gap:
                    weakest_gap = gap
                    weakest = competency
            if scores:
                eligibility_pct = int(round((sum(scores) / len(scores)) * 100))
            if weakest and weakest_gap > 0:
                key_competency = f"Strengthen {weakest} to improve readiness for {next_path['label']}."
            elif weakest_gap == 0:
                key_competency = f"Competency profile already aligns with {next_path['label']} ideals."
        elif next_path:
            key_competency = f"Build capabilities for {next_path['label']} after your RD profile is finalized."

        tips = []
        if not enabled:
            tips.append("No greened career moves for your grade in Probable Career Paths — focus on current-role excellence.")
        else:
            tips.append(
                f"Eligible moves (green): {', '.join(path['label'] for path in enabled)}."
            )
        if locked:
            tips.append(
                f"Grey / locked futures: {', '.join(path['label'] for path in locked)}."
            )
        tips.append("Complete all seven assessments before locking an aspiration.")
        if next_path:
            tips.append(f"Locking {next_path['label']} starts your personalized learning journey for that path.")

        return {
            "growth": growth,
            "key_competency": key_competency,
            "tips": tips,
            "eligible_count": len(enabled),
            "locked_count": len(locked),
            "eligibility_pct": eligibility_pct,
            "eligibility_label": eligibility_label,
            "next_path_id": next_path["id"] if next_path else None,
        }

    @staticmethod

    def _current_role(employee: dict[str, Any]) -> str:
        return (
            "KAM"
            if is_kam_title(
                employee.get("role_name", ""),
                employee.get("role", ""),
                employee.get("designation", ""),
            )
            else "BDM"
        )


    def _career_paths(self, employee: dict[str, Any]) -> list[dict[str, Any]]:
        """Probable Career Paths Table 2 — Yes = coloured/enabled, Grey/Locked = locked.

        BDFE and Category always appear on the lattice and are always locked (not selectable).
        """
        role = self._current_role(employee)
        grade = str(employee.get("grade") or "").strip()
        locked_sides = [
            {
                "id": "bdfe",
                "label": "Business Development Fieldforce Effectiveness",
                "target_key": "",
                "enabled": False,
                "state": "locked_future",
            },
            {
                "id": "category",
                "label": "Category",
                "target_key": "",
                "enabled": False,
                "state": "locked_future",
            },
        ]
        if role == "BDM":
            kam_key = "KAM (RL4)" if grade == "RL4" else "KAM (RL2-3)"
            zm_enabled = grade in {"RL3", "RL4"}
            return [
                {
                    "id": "kam",
                    "label": "Key Account Manager",
                    "target_key": kam_key,
                    "enabled": True,
                    "state": "available",
                },
                {
                    "id": "zm",
                    "label": "Zonal Manager",
                    "target_key": "ZM (RL4-5)",
                    "enabled": zm_enabled,
                    "state": "available" if zm_enabled else "locked_future",
                },
                {
                    "id": "rd",
                    "label": "Regional Director",
                    "target_key": "RD (RL7-8)",
                    "enabled": False,
                    "state": "locked_future",
                },
                *locked_sides,
            ]
        zm_enabled = grade in {"RL3", "RL4"}
        return [
            {
                "id": "zm",
                "label": "Zonal Manager",
                "target_key": "ZM (RL4-5)",
                "enabled": zm_enabled,
                "state": "available" if zm_enabled else "locked_future",
            },
            {
                "id": "rd",
                "label": "Regional Director",
                "target_key": "RD (RL7-8)",
                "enabled": False,
                "state": "locked_future",
            },
            *locked_sides,
        ]


    def choose_career(self, user: dict[str, Any], aspiration_role: str) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        employee_code = user["employee_code"]
        if not self.lattice_unlocked(employee_code):
            raise BackendError("Complete both voice roleplay sessions before choosing an aspiration.", "lattice_locked", 409)
        existing = self.career_state(employee_code)["choice"]
        if existing:
            raise BackendError("Career aspiration is locked. Admin reset required.", "career_locked", 409)
        path = next((row for row in self._career_paths(self.employee(employee_code)) if row["id"] == aspiration_role and row["enabled"]), None)
        if not path:
            raise BackendError("Career path is not available for this role and grade.")
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO career_choices(employee_code,aspiration_role,target_key,locked_at) VALUES(?,?,?,?)",
                (employee_code, aspiration_role, path["target_key"], utc_now()),
            )
        if not self.recommendations(employee_code)["ready"]:
            self.generate_recommendations(employee_code)
        return self.career_state(employee_code)


    def reset_career(self, admin: dict[str, Any], employee_code: str) -> None:
        if admin["role"] != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM career_choices WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM learning_selections WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM external_learning WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM course_progress WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM other_source_recommendations WHERE employee_code=?", (employee_code,))


    def reset_learning(self, admin: dict[str, Any], employee_code: str) -> dict[str, Any]:
        """Unlock Select Your Courses for an employee without clearing aspiration."""
        if admin["role"] != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        employee = self.employee(employee_code)
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM learning_selections WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM external_learning WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM course_progress WHERE employee_code=?", (employee_code,))
        return {
            "status": "reset",
            "employee_code": employee["employee_code"],
            "learning_locked": False,
        }


    def final_profile(self, employee_code: str) -> dict[str, str] | None:
        assessment = self.assessment(employee_code, "rd")
        return assessment["ratings"] if assessment and assessment["status"] == "submitted" else None

