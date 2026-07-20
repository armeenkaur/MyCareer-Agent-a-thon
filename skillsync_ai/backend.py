from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
import re
from typing import Any

from .agents.course_recommendation import (
    AGENT_NAME as COURSE_AGENT,
    _fallback_choices,
    _prefilter,
    _rank_all_with_agent,
    curate_other_sources,
    resolve_other_source,
)
from .agents.evidence_curator import AGENT_NAME as EVIDENCE_AGENT, CURATOR_VERSION, curate_evidence
from .agents.roleplay_assessment import AGENT_NAME as ROLEPLAY_AGENT, assess_roleplay
from .core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from .core.logging_setup import get_logger
from .core.utils import display_designation, is_kam_title, role_level_key, slug
from .database import Database, PHASES, utc_now
from .linkedin_learning import sync_learning_activity
from .state import RuntimeState


SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
log = get_logger("skillsync.backend")

BADGE_CATALOG = [
    {"id": "hours_stacked", "title": "Hours Stacked", "rule": "Every 2 LinkedIn learning hours", "icon": "bolt"},
    {"id": "first_mile", "title": "First Mile", "rule": "Complete 1 LinkedIn course", "icon": "flag"},
    {"id": "pathway_pack", "title": "Pathway Pack", "rule": "Complete 3 LinkedIn courses", "icon": "stacks"},
    {"id": "lattice_climber", "title": "Lattice Climber", "rule": "Complete 5 LinkedIn courses", "icon": "moving"},
    {"id": "ten_hour_club", "title": "Ten-Hour Club", "rule": "Reach 10 LinkedIn hours", "icon": "schedule"},
    {"id": "full_circuit", "title": "Full Circuit", "rule": "Finish all locked LinkedIn courses", "icon": "all_inclusive"},
    {"id": "gap_closer", "title": "Gap Closer", "rule": "Close all focus-area gaps", "icon": "verified"},
    {"id": "cohort_crown", "title": "Cohort Crown", "rule": "#1 in your severity band", "icon": "military_tech"},
]


class BackendError(Exception):
    def __init__(self, message: str, code: str = "bad_request", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class MyCareerBackend:
    def __init__(self, data: Any, database: Database) -> None:
        self.data = data
        self.db = database
        self.db.clear_runtime_cache()
        self.db.seed_from_workbooks(data)
        self.competencies = [row["skill"] for row in data.competencies]

    # Authentication and phase gates
    def login(self, login_id: str, role: str, password: str) -> dict[str, Any]:
        user = self.db.authenticate(login_id, role, password)
        if not user:
            raise BackendError("Invalid employee ID, role, or password.", "invalid_credentials", 401)
        if role != "admin" and not self.phase_is_open(role):
            raise BackendError(
                "This phase is not open yet. You will be notified when access becomes available.",
                "phase_closed",
                403,
            )
        token = self.db.create_session(int(user["id"]))
        return {"token": token, "user": self.public_user(user), "phase": self.phase(role) if role != "admin" else None}

    def logout(self, token: str) -> None:
        self.db.delete_session(token)

    def change_password(self, user: dict[str, Any], current_password: str, new_password: str) -> dict[str, str]:
        try:
            self.db.change_password(user["login_id"], user["role"], current_password, new_password)
        except ValueError as exc:
            message = str(exc)
            code = "invalid_credentials" if "incorrect" in message.lower() else "bad_request"
            status = 401 if code == "invalid_credentials" else 400
            raise BackendError(message, code, status) from exc
        return {"status": "ok"}

    def user_for_token(self, token: str, roles: set[str] | None = None) -> dict[str, Any]:
        user = self.db.session_user(token)
        if not user:
            raise BackendError("Authentication required.", "unauthorized", 401)
        if roles and user["role"] not in roles:
            raise BackendError("You do not have access to this resource.", "forbidden", 403)
        return user

    def public_user(self, user: dict[str, Any]) -> dict[str, Any]:
        payload = {key: user.get(key) for key in ("login_id", "role", "display_name", "employee_code")}
        role = user.get("role")
        # Immediate supervisor / skip-level titles (not Darwin employee rows).
        if role == "zm":
            payload["designation"] = "Zonal Manager"
            return payload
        if role == "rd":
            payload["designation"] = "Regional Director"
            return payload
        # Employees: job title from Darwin only — never system role or grade/level.
        if role == "employee" and user.get("employee_code"):
            try:
                employee = self.employee(str(user["employee_code"]))
            except BackendError:
                employee = {}
            designation = str(employee.get("designation") or "").strip()
            role_name = str(employee.get("role_name") or employee.get("role") or "").strip()
            if designation or role_name:
                payload["designation"] = display_designation(designation, role_name, short=True)
        return payload

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
            if phase in {"zm", "rd"}:
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
                            SELECT employee_code FROM roleplay_assessments
                            WHERE status='completed'
                            GROUP BY employee_code HAVING COUNT(*)=?
                        )
                        """,
                        (len(self.competencies),),
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
        previous = {"rd": "zm", "employee": "rd"}.get(phase)
        if previous:
            progress = self.phase_progress(previous)
            if not progress["is_complete"] and not override:
                raise BackendError(
                    f"{previous.upper()} phase is not 100% complete. Explicit override required.",
                    "completion_gate",
                    409,
                )
        with self.db.transaction() as connection:
            if previous:
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
    def scoped_employees(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        role = user["role"]
        with self.db.connect() as connection:
            if role == "zm":
                rows = connection.execute("SELECT * FROM employees WHERE zm_code=? ORDER BY employee_code", (user["login_id"],)).fetchall()
            elif role == "rd":
                rows = connection.execute("SELECT * FROM employees WHERE rd_code=? ORDER BY employee_code", (user["login_id"],)).fetchall()
            elif role == "employee":
                rows = connection.execute("SELECT * FROM employees WHERE employee_code=?", (user["employee_code"],)).fetchall()
            elif role == "admin":
                rows = connection.execute("SELECT * FROM employees ORDER BY employee_code").fetchall()
            else:
                rows = []
        return [dict(row) for row in rows]

    def employee_summaries(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        """Role-scoped employee rows with workflow status for frontend tables."""
        output = []
        for employee in self.scoped_employees(user):
            zm = self.assessment(employee["employee_code"], "zm")
            rd = self.assessment(employee["employee_code"], "rd")
            with self.db.connect() as connection:
                roleplay_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM roleplay_assessments WHERE employee_code=? AND status='completed'",
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
            output.append(
                {
                    **employee,
                    "zm_status": zm["status"] if zm else "not_started",
                    "rd_status": rd["status"] if rd else "not_started",
                    "final_profile_available": bool(rd and rd["status"] == "submitted"),
                    "roleplays_completed": roleplay_count,
                    "roleplays_total": len(self.competencies),
                    "aspiration": dict(choice) if choice else None,
                    "learning_locked": learning_locked,
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
        return {
            "employee": self.employee(employee_code),
            "status": "final" if profile else "pending",
            "ratings": profile or {},
            "ideal_ratings": self.data.ideal_for_employee(employee_code),
        }

    def assessment(self, employee_code: str, role: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM assessments WHERE employee_code=? AND assessor_role=?", (employee_code, role)
            ).fetchone()
            if not row:
                return None
            ratings = connection.execute(
                "SELECT competency,proficiency,note FROM assessment_ratings WHERE assessment_id=? ORDER BY competency",
                (row["id"],),
            ).fetchall()
        result = dict(row)
        result["ratings"] = {rating["competency"]: rating["proficiency"] for rating in ratings}
        result["notes"] = {rating["competency"]: rating["note"] for rating in ratings if rating["note"]}
        return result

    def save_assessment(
        self,
        user: dict[str, Any],
        employee_code: str,
        ratings: dict[str, str],
        notes: dict[str, str] | None = None,
        submit: bool = False,
    ) -> dict[str, Any]:
        role = user["role"]
        if role not in {"zm", "rd"}:
            raise BackendError("ZM or RD access required.", "forbidden", 403)
        if not self.phase_is_open(role):
            raise BackendError("Assessment phase is closed.", "phase_closed", 403)
        self._assert_employee_scope(user, employee_code)
        if role == "rd":
            zm_assessment = self.assessment(employee_code, "zm")
            if not zm_assessment or zm_assessment["status"] != "submitted":
                raise BackendError(
                    "ZM assessment must be submitted before RD validation.",
                    "zm_assessment_required",
                    409,
                )
        self._validate_ratings(ratings, complete=submit)
        existing = self.assessment(employee_code, role)
        if existing and existing["status"] == "submitted":
            raise BackendError("Submitted assessment is locked.", "assessment_locked", 409)
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO assessments(employee_code,assessor_role,assessor_login_id,status,created_at,updated_at,submitted_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(employee_code,assessor_role) DO UPDATE SET
                    assessor_login_id=excluded.assessor_login_id,status=excluded.status,
                    updated_at=excluded.updated_at,submitted_at=excluded.submitted_at
                """,
                (employee_code, role, user["login_id"], "submitted" if submit else "draft", now, now, now if submit else None),
            )
            assessment_id = connection.execute(
                "SELECT id FROM assessments WHERE employee_code=? AND assessor_role=?", (employee_code, role)
            ).fetchone()[0]
            for competency, proficiency in ratings.items():
                connection.execute(
                    """
                    INSERT INTO assessment_ratings(assessment_id,competency,proficiency,note) VALUES(?,?,?,?)
                    ON CONFLICT(assessment_id,competency) DO UPDATE SET proficiency=excluded.proficiency,note=excluded.note
                    """,
                    (assessment_id, competency, proficiency, (notes or {}).get(competency, "")),
                )
        if submit and self.phase_progress(role)["is_complete"]:
            with self.db.transaction() as connection:
                connection.execute("UPDATE phases SET status='complete', closed_at=? WHERE phase=?", (utc_now(), role))
        if submit and role == "rd":
            try:
                self.precompute_recommendations(employee_code)
            except Exception:  # noqa: BLE001
                log.exception("Course precomputation failed employee=%s", employee_code)
        return self.assessment(employee_code, role) or {}

    def rd_validation_context(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user["role"] not in {"rd", "admin"}:
            raise BackendError("RD or Admin access required.", "forbidden", 403)
        if user["role"] == "rd":
            self._assert_employee_scope(user, employee_code)
        zm_assessment = self.assessment(employee_code, "zm")
        if not zm_assessment or zm_assessment["status"] != "submitted":
            raise BackendError(
                "ZM assessment must be submitted before RD validation.",
                "zm_assessment_required",
                409,
            )
        evidence = {}
        rd_assessment = self.assessment(employee_code, "rd")
        # Agent runs only on Start/draft cache miss. View (submitted) never re-curates.
        allow_curate = not (rd_assessment and rd_assessment.get("status") == "submitted")
        for competency in self.competencies:
            cached = self._cached_evidence(employee_code, competency)
            if cached is None and allow_curate:
                cached = curate_evidence(self.data, employee_code, competency)
                self._save_evidence(employee_code, competency, cached)
                self._audit(employee_code, EVIDENCE_AGENT, competency, "Workbook evidence", cached, "ok")
            elif cached is None:
                cached = {
                    "competency": competency,
                    "evidence": [],
                    "empty_message": "No saved evidence for this competency.",
                    "source": "cache",
                    "curator_version": CURATOR_VERSION,
                }
            evidence[competency] = cached
        return {
            "employee": self.employee(employee_code),
            "zm_assessment": zm_assessment,
            "rd_assessment": rd_assessment,
            "evidence": evidence,
            "rubric": self.data.level_definitions,
        }

    # Employee role-play, career, and learning workflows
    def submit_roleplay(
        self,
        user: dict[str, Any],
        competency: str,
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        if not self.phase_is_open("employee"):
            raise BackendError("Employee phase is closed.", "phase_closed", 403)
        if competency not in self.competencies:
            raise BackendError("Unknown competency.")
        if not payload:
            raise BackendError("Screenshot is required.")
        employee_code = user["employee_code"]
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name) or "roleplay.png"
        if Path(safe_name).suffix.lower() not in SCREENSHOT_EXTENSIONS:
            raise BackendError("Screenshot must be PNG, JPG, JPEG, or WEBP.", "unsupported_file_type", 415)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / f"{employee_code}_{slug(competency)}_{safe_name}"
        path.write_bytes(payload)
        result = assess_roleplay(
            competency,
            safe_name,
            payload,
            self.data.level_definitions.get(competency, {}),
            employee_code,
        )
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO roleplay_assessments(
                    employee_code,competency,filename,file_path,status,ai_proficiency,rationale,ocr_text,error,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(employee_code,competency) DO UPDATE SET
                    filename=excluded.filename,file_path=excluded.file_path,status=excluded.status,
                    ai_proficiency=excluded.ai_proficiency,rationale=excluded.rationale,
                    ocr_text=excluded.ocr_text,error=excluded.error,updated_at=excluded.updated_at
                """,
                (
                    employee_code, competency, safe_name, str(path), result["status"], result.get("proficiency"),
                    result.get("rationale", ""), result.get("ocr_text", "")[:8000], result.get("error", ""), utc_now(),
                ),
            )
        self._audit(employee_code, ROLEPLAY_AGENT, competency, f"Screenshot {safe_name}", result, result["status"])
        if result["status"] == "completed" and self.phase_progress("employee")["is_complete"]:
            with self.db.transaction() as connection:
                connection.execute(
                    "UPDATE phases SET status='complete', closed_at=? WHERE phase='employee'",
                    (utc_now(),),
                )
        return {
            "status": result["status"],
            "competency": competency,
            "filename": safe_name,
            "error": result.get("error", ""),
        }

    def roleplays(self, employee_code: str, include_private: bool = False) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            stored = {
                row["competency"]: dict(row)
                for row in connection.execute(
                    "SELECT * FROM roleplay_assessments WHERE employee_code=?", (employee_code,)
                ).fetchall()
            }
        output = []
        for competency in self.competencies:
            stored_row = stored.get(competency, {})
            row = {
                "competency": competency,
                "roleplay_url": self.data.roleplay_links.get(competency, ""),
                "link_available": bool(self.data.roleplay_links.get(competency)),
                "status": stored_row.get("status", "not_started"),
                "error": stored_row.get("error", ""),
                "updated_at": stored_row.get("updated_at"),
            }
            if include_private:
                row.update(
                    {
                        "filename": stored_row.get("filename", ""),
                        "ai_proficiency": stored_row.get("ai_proficiency"),
                        "rationale": stored_row.get("rationale", ""),
                        "ocr_text": stored_row.get("ocr_text", ""),
                        "screenshot_available": bool(stored_row.get("file_path")),
                    }
                )
            output.append(row)
        return output

    def admin_roleplays(
        self, admin: dict[str, Any], employee_code: str, competency: str = ""
    ) -> dict[str, Any]:
        if admin.get("role") != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        employee = self.employee(employee_code)
        rows = self.roleplays(employee_code, include_private=True)
        result: dict[str, Any] = {"employee": employee, "roleplays": rows}
        if not competency:
            return result
        if competency not in self.competencies:
            raise BackendError("Unknown competency.")
        with self.db.connect() as connection:
            stored = connection.execute(
                "SELECT filename,file_path FROM roleplay_assessments WHERE employee_code=? AND competency=?",
                (employee_code, competency),
            ).fetchone()
        if not stored or not stored["file_path"]:
            raise BackendError("Role-play screenshot not found.", "not_found", 404)
        path = Path(stored["file_path"])
        if not path.is_file():
            raise BackendError("Role-play screenshot file is unavailable.", "not_found", 404)
        result["screenshot"] = {
            "competency": competency,
            "filename": stored["filename"],
            "content_type": mimetypes.guess_type(stored["filename"])[0] or "image/png",
            "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
        return result

    def lattice_unlocked(self, employee_code: str) -> bool:
        return all(row["status"] == "completed" for row in self.roleplays(employee_code))

    def career_state(self, employee_code: str) -> dict[str, Any]:
        employee = self.employee(employee_code)
        with self.db.connect() as connection:
            choice = connection.execute("SELECT * FROM career_choices WHERE employee_code=?", (employee_code,)).fetchone()
        role = self._current_role(employee)
        grade = str(employee.get("grade") or "").strip()
        paths = self._career_paths(employee)
        journey = self._career_journey(employee, paths)
        insights = self._career_insights(employee_code, employee, role, grade, paths)
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
            "choice": dict(choice) if choice else None,
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
        """Probable Career Paths Table 2 — Yes = coloured/enabled, Grey/Locked = locked."""
        role = self._current_role(employee)
        grade = str(employee.get("grade") or "").strip()
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
        ]

    def choose_career(self, user: dict[str, Any], aspiration_role: str) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        employee_code = user["employee_code"]
        if not self.lattice_unlocked(employee_code):
            raise BackendError("Complete all seven role plays before choosing an aspiration.", "lattice_locked", 409)
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
        """Unlock Shop Your Courses for an employee without clearing aspiration."""
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

    def deterministic_gaps(self, employee_code: str, target_key: str | None = None) -> list[dict[str, Any]]:
        actual = self.final_profile(employee_code)
        if not actual:
            return []
        ideal = self.data.ideal_for_role_key(target_key) if target_key else self.data.ideal_for_employee(employee_code)
        gaps = []
        for competency in self.competencies:
            current = actual.get(competency)
            target = ideal.get(competency)
            difference = PROFICIENCY_VALUE.get(target, 0) - PROFICIENCY_VALUE.get(current, 0)
            if difference > 0:
                gaps.append({"competency": competency, "current": current, "target": target, "gap_levels": difference})
        return gaps

    def learning_target(self, employee_code: str) -> dict[str, Any]:
        current_key = role_level_key(
            self.data.employees[employee_code]["designation"],
            self.data.employees[employee_code]["level"],
            self.data.employees[employee_code].get("role_name")
            or self.data.employees[employee_code].get("role")
            or "",
        )
        current_gaps = self.deterministic_gaps(employee_code, current_key)
        total = sum(row["gap_levels"] for row in current_gaps)
        if total >= 2:
            return {"mode": "current_role", "target_key": current_key, "gaps": current_gaps, "total_gap_levels": total}
        state = self.career_state(employee_code)
        if not state["choice"]:
            return {"mode": "aspiration_required", "target_key": "", "gaps": [], "total_gap_levels": 0}
        target_key = state["choice"]["target_key"]
        gaps = self.deterministic_gaps(employee_code, target_key)
        return {"mode": "future_role", "target_key": target_key, "gaps": gaps, "total_gap_levels": sum(row["gap_levels"] for row in gaps)}

    def generate_recommendations(self, employee_code: str) -> dict[str, Any]:
        target = self.learning_target(employee_code)
        if target["mode"] == "aspiration_required":
            raise BackendError("Choose a career aspiration before generating future-role courses.", "aspiration_required", 409)
        return self._generate_recommendations_for_target(employee_code, target)

    def precompute_recommendations(self, employee_code: str) -> list[dict[str, Any]]:
        """Generate current-role and every eligible future-path cache after RD submission."""
        generated = []
        for target in self.recommendation_targets(employee_code):
            generated.append(self._generate_recommendations_for_target(employee_code, target))
        return generated

    def recommendation_targets(self, employee_code: str) -> list[dict[str, Any]]:
        employee = self.employee(employee_code)
        source = self.data.employees[employee_code]
        current_key = role_level_key(
            source["designation"],
            source["level"],
            source.get("role_name") or source.get("role") or "",
        )
        candidates = [("current_role", current_key, self._current_role(employee))]
        candidates.extend(
            ("future_role", path["target_key"], path["label"])
            for path in self._career_paths(employee)
            if path["enabled"]
        )
        targets = []
        seen = set()
        for mode, target_key, label in candidates:
            if not target_key or target_key in seen:
                continue
            seen.add(target_key)
            gaps = self.deterministic_gaps(employee_code, target_key)
            targets.append(
                {
                    "mode": mode,
                    "target_key": target_key,
                    "label": label,
                    "gaps": gaps,
                    "total_gap_levels": sum(row["gap_levels"] for row in gaps),
                }
            )
        return targets

    def _generate_recommendations_for_target(
        self, employee_code: str, target: dict[str, Any]
    ) -> dict[str, Any]:
        employee = self.data.employees[employee_code]
        groups = {}
        for gap in target["gaps"]:
            candidates = _prefilter(self.data.courses, gap["competency"], gap["current"], employee)[:15]
            groups[gap["competency"]] = {
                "current": gap["current"],
                "target_roles": [target["target_key"]],
                "target_levels": {target["target_key"]: gap["target"]},
                "candidates": candidates,
            }
        ranked, audit = _rank_all_with_agent(groups, employee, employee_code) if groups else ({}, "no gaps")
        generated = {}
        audits = []
        with self.db.transaction() as connection:
            connection.execute(
                "DELETE FROM course_recommendations WHERE employee_code=? AND target_key=?",
                (employee_code, target["target_key"]),
            )
            for gap in target["gaps"]:
                group = groups[gap["competency"]]
                courses = [
                    self._course_contract(course, gap["competency"], gap["current"], gap["target"])
                    for course in (ranked.get(gap["competency"]) or _fallback_choices(group["candidates"]))[:2]
                ]
                generated[gap["competency"]] = courses
                connection.execute(
                    """
                    INSERT INTO course_recommendations(
                        employee_code,target_key,competency,current_level,target_level,
                        candidate_ids_json,courses_json,generated_at
                    ) VALUES(?,?,?,?,?,?,?,?)
                    """,
                    (
                        employee_code, target["target_key"], gap["competency"], gap["current"], gap["target"],
                        json.dumps([str(row["id"]) for row in group["candidates"]]), json.dumps(courses, default=str), utc_now(),
                    ),
                )
                audits.append(
                    (
                        gap["competency"],
                        f"{len(group['candidates'])} backend-filtered candidates",
                        {"courses": courses, "audit": audit},
                    )
                )
        for competency, input_summary, output in audits:
            self._audit(employee_code, COURSE_AGENT, competency, input_summary, output, "ok")
        other_sources = curate_other_sources(list(groups.keys()), employee_code) if groups else {}
        with self.db.transaction() as connection:
            connection.execute(
                "DELETE FROM other_source_recommendations WHERE employee_code=? AND target_key=?",
                (employee_code, target["target_key"]),
            )
            for competency, picks in other_sources.items():
                connection.execute(
                    """
                    INSERT INTO other_source_recommendations(employee_code,target_key,competency,picks_json,generated_at)
                    VALUES(?,?,?,?,?)
                    """,
                    (employee_code, target["target_key"], competency, json.dumps(picks, default=str), utc_now()),
                )
        return {"target": target, "competencies": generated, "other_sources": other_sources}

    def recommendations(self, employee_code: str) -> dict[str, Any]:
        target = self.learning_target(employee_code)
        if not target["target_key"]:
            return {"target": target, "competencies": {}, "ready": False}
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM course_recommendations WHERE employee_code=? AND target_key=? ORDER BY competency",
                (employee_code, target["target_key"]),
            ).fetchall()
            other_rows = connection.execute(
                "SELECT competency,picks_json FROM other_source_recommendations WHERE employee_code=? AND target_key=?",
                (employee_code, target["target_key"]),
            ).fetchall()
        competencies = {
            row["competency"]: self.db.decode_json(row["courses_json"], []) for row in rows
        }
        other_sources = {
            row["competency"]: self.db.decode_json(row["picks_json"], []) for row in other_rows
        }
        # Always refresh from verified catalog — older LLM picks often 404.
        if competencies:
            other_sources = curate_other_sources(list(competencies.keys()), employee_code)
            with self.db.transaction() as connection:
                for competency, picks in other_sources.items():
                    connection.execute(
                        """
                        INSERT INTO other_source_recommendations(employee_code,target_key,competency,picks_json,generated_at)
                        VALUES(?,?,?,?,?)
                        ON CONFLICT(employee_code,target_key,competency) DO UPDATE SET
                            picks_json=excluded.picks_json, generated_at=excluded.generated_at
                        """,
                        (employee_code, target["target_key"], competency, json.dumps(picks, default=str), utc_now()),
                    )
        return {
            "target": target,
            "competencies": competencies,
            "other_sources": other_sources,
            "ready": bool(rows) or not target["gaps"],
        }

    def checkout(self, user: dict[str, Any], course_ids: list[str], other_sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        employee_code = user["employee_code"]
        existing = self.learning_journey(employee_code)
        if existing.get("locked"):
            if course_ids:
                raise BackendError(
                    "Learning journey is already locked. Course selection cannot be changed.",
                    "journey_locked",
                    409,
                )
            return self.add_other_sources(user, other_sources or [])
        recommendations = self.recommendations(employee_code)
        selected = {str(value) for value in course_ids if not str(value).startswith("other:")}
        valid: dict[str, dict[str, Any]] = {}
        missing = []
        for competency, courses in recommendations["competencies"].items():
            chosen = [course for course in courses if str(course.get("id")) in selected]
            if not chosen:
                missing.append(competency)
            for course in chosen:
                valid[str(course["id"])] = {"competency": competency, "course": course}
        if missing:
            raise BackendError(
                f"Select at least one LinkedIn course for: {', '.join(missing)}.",
                "course_selection_incomplete",
                409,
            )
        extras = []
        for item in other_sources or []:
            if not isinstance(item, dict):
                continue
            resource_id = str(item.get("id") or "").strip()
            competency = str(item.get("competency") or "").strip()
            title = str(item.get("title") or "").strip()
            kind = str(item.get("kind") or "other").strip()
            url = str(item.get("url") or "").strip()
            duration_minutes = item.get("duration_minutes")
            if not resource_id.startswith("other:") or not competency or not title:
                continue
            extras.append(
                {
                    "resource_id": resource_id,
                    "competency": competency,
                    "resource_json": json.dumps(
                        {
                            "id": resource_id,
                            "title": title,
                            "kind": kind,
                            "url": url,
                            "duration_minutes": duration_minutes,
                            "source": "other",
                            "provider": "TEDx Talk" if kind in {"tedx", "ted"} else kind.replace("_", " ").title(),
                        }
                    ),
                }
            )
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM learning_selections WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM external_learning WHERE employee_code=?", (employee_code,))
            connection.execute("DELETE FROM course_progress WHERE employee_code=?", (employee_code,))
            for course_id, row in valid.items():
                connection.execute(
                    "INSERT INTO learning_selections(employee_code,competency,course_id,selected_at) VALUES(?,?,?,?)",
                    (employee_code, row["competency"], course_id, utc_now()),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO course_progress(employee_code,course_id,status,progress_pct,launched_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (employee_code, course_id, "not_started", 0, None, None),
                )
            for extra in extras:
                connection.execute(
                    """
                    INSERT INTO external_learning(employee_code,resource_id,competency,resource_json,clicked_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (employee_code, extra["resource_id"], extra["competency"], extra["resource_json"], None, None),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO course_progress(employee_code,course_id,status,progress_pct,launched_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (employee_code, extra["resource_id"], "not_started", 0, None, None),
                )
        return self.learning_journey(employee_code)

    def add_other_sources(self, user: dict[str, Any], other_sources: list[dict[str, Any]]) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        employee_code = user["employee_code"]
        journey = self.learning_journey(employee_code)
        if not journey.get("locked"):
            raise BackendError("Lock LinkedIn courses before adding other sources.", "journey_not_locked", 409)
        allowed = {str(course.get("competency") or "") for course in journey["courses"]}
        extras = []
        for item in other_sources or []:
            if not isinstance(item, dict):
                continue
            resource_id = str(item.get("id") or "").strip()
            competency = str(item.get("competency") or "").strip()
            title = str(item.get("title") or "").strip()
            kind = str(item.get("kind") or "other").strip()
            url = str(item.get("url") or "").strip()
            duration_minutes = item.get("duration_minutes")
            if not resource_id.startswith("other:") or not competency or not title:
                continue
            if competency not in allowed:
                continue
            extras.append(
                {
                    "resource_id": resource_id,
                    "competency": competency,
                    "resource_json": json.dumps(
                        {
                            "id": resource_id,
                            "title": title,
                            "kind": kind,
                            "url": url,
                            "duration_minutes": duration_minutes,
                            "source": "other",
                            "provider": "TEDx Talk" if kind in {"tedx", "ted"} else kind.replace("_", " ").title(),
                        }
                    ),
                }
            )
        if not extras:
            raise BackendError("No valid other sources to add.", "validation_error", 400)
        with self.db.transaction() as connection:
            for extra in extras:
                connection.execute(
                    """
                    INSERT INTO external_learning(employee_code,resource_id,competency,resource_json,clicked_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(employee_code, resource_id) DO UPDATE SET
                        competency=excluded.competency,
                        resource_json=excluded.resource_json
                    """,
                    (employee_code, extra["resource_id"], extra["competency"], extra["resource_json"], None, None),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO course_progress(employee_code,course_id,status,progress_pct,launched_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (employee_code, extra["resource_id"], "not_started", 0, None, None),
                )
        return self.learning_journey(employee_code)

    def update_course_progress(self, user: dict[str, Any], course_id: str, action: str) -> dict[str, Any]:
        if user["role"] != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        employee_code = user["employee_code"]
        course_id = str(course_id or "").strip()
        action = str(action or "").strip().lower()
        if not course_id:
            raise BackendError("course_id is required.", "validation_error", 400)
        if action not in {"launch", "complete"}:
            raise BackendError("action must be launch or complete.", "validation_error", 400)
        if action == "complete" and not course_id.startswith("other:"):
            raise BackendError(
                "LinkedIn course completion is tracked from LinkedIn Learning — mark complete only for other sources.",
                "linkedin_complete_not_allowed",
                409,
            )
        journey = self.learning_journey(employee_code)
        if not journey.get("locked"):
            raise BackendError("Lock your learning journey before tracking progress.", "journey_not_locked", 409)
        known = {str(course.get("id") or course.get("course_id")) for course in journey["courses"]}
        if course_id not in known:
            raise BackendError("Course is not part of the locked journey.", "course_not_in_journey", 404)
        now = utc_now()
        with self.db.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM course_progress WHERE employee_code=? AND course_id=?",
                (employee_code, course_id),
            ).fetchone()
            if not row:
                connection.execute(
                    """
                    INSERT INTO course_progress(employee_code,course_id,status,progress_pct,launched_at,completed_at)
                    VALUES(?,?,?,?,?,?)
                    """,
                    (employee_code, course_id, "not_started", 0, None, None),
                )
                row = connection.execute(
                    "SELECT * FROM course_progress WHERE employee_code=? AND course_id=?",
                    (employee_code, course_id),
                ).fetchone()
            if action == "launch":
                if row["status"] != "completed":
                    connection.execute(
                        """
                        UPDATE course_progress
                        SET status='in_progress', launched_at=COALESCE(launched_at, ?)
                        WHERE employee_code=? AND course_id=?
                        """,
                        (now, employee_code, course_id),
                    )
                if course_id.startswith("other:"):
                    connection.execute(
                        "UPDATE external_learning SET clicked_at=COALESCE(clicked_at, ?) WHERE employee_code=? AND resource_id=?",
                        (now, employee_code, course_id),
                    )
            else:
                connection.execute(
                    """
                    UPDATE course_progress
                    SET status='completed', progress_pct=100, launched_at=COALESCE(launched_at, ?), completed_at=?
                    WHERE employee_code=? AND course_id=?
                    """,
                    (now, now, employee_code, course_id),
                )
                if course_id.startswith("other:"):
                    connection.execute(
                        "UPDATE external_learning SET completed_at=? WHERE employee_code=? AND resource_id=?",
                        (now, employee_code, course_id),
                    )
        return self.learning_journey(employee_code)

    def learning_journey(self, employee_code: str) -> dict[str, Any]:
        recommendations = self.recommendations(employee_code)
        by_id = {
            str(course["id"]): {**course, "competency": competency}
            for competency, courses in recommendations["competencies"].items()
            for course in courses
        }
        with self.db.connect() as connection:
            selections = connection.execute(
                "SELECT * FROM learning_selections WHERE employee_code=? ORDER BY competency,course_id", (employee_code,)
            ).fetchall()
            external = connection.execute(
                "SELECT * FROM external_learning WHERE employee_code=? ORDER BY competency,resource_id", (employee_code,)
            ).fetchall()
            progress_rows = connection.execute(
                "SELECT * FROM course_progress WHERE employee_code=?", (employee_code,)
            ).fetchall()
            activity = connection.execute(
                "SELECT * FROM linkedin_activity WHERE employee_code=?", (employee_code,)
            ).fetchone()
        progress_by_id = {row["course_id"]: dict(row) for row in progress_rows}
        courses = []
        for row in selections:
            course = {**dict(row), **by_id.get(row["course_id"], {})}
            course["id"] = str(course.get("id") or row["course_id"])
            course["source"] = course.get("source") or "linkedin"
            courses.append(self._with_course_progress(course, progress_by_id.get(row["course_id"])))
        for row in external:
            payload = self.db.decode_json(row["resource_json"], {})
            minutes = payload.get("duration_minutes")
            duration = f"{int(minutes)}m" if minutes not in (None, "") else ""
            url = str(payload.get("url") or "").strip()
            curated = resolve_other_source(str(row["competency"] or ""), str(payload.get("kind") or ""))
            if curated:
                # Prefer verified catalog over stale/hallucinated locked URLs.
                url = str(curated.get("url") or url)
                minutes = curated.get("duration_minutes", minutes)
                duration = f"{int(minutes)}m" if minutes not in (None, "") else duration
                if curated.get("title") and (not payload.get("title") or "http" in str(payload.get("title") or "").lower()):
                    payload = {**payload, "title": curated["title"]}
            course = {
                "id": row["resource_id"],
                "course_id": row["resource_id"],
                "competency": row["competency"],
                "title": payload.get("title") or (curated or {}).get("title") or row["resource_id"],
                "provider": payload.get("provider") or "Other source",
                "duration": duration,
                "duration_minutes": minutes,
                "url": url,
                "source": "other",
                "kind": payload.get("kind") or "other",
            }
            courses.append(self._with_course_progress(course, progress_by_id.get(row["resource_id"])))
        linkedin_courses = [
            course for course in courses
            if not (course.get("source") == "other" or str(course.get("id") or "").startswith("other:"))
        ]
        completed = sum(1 for course in linkedin_courses if course.get("status") == "completed")
        in_progress = sum(1 for course in linkedin_courses if course.get("status") == "in_progress")
        total = len(linkedin_courses)
        return {
            "target": recommendations["target"],
            "courses": courses,
            "locked": bool(courses),
            "progress": {
                "completed": completed,
                "in_progress": in_progress,
                "total": total,
                "percentage": round((completed / total) * 100) if total else 0,
            },
            "linkedin": dict(activity) if activity else {"learning_hours": 0.0, "completions": 0, "synced_at": None},
        }

    @staticmethod
    def _with_course_progress(course: dict[str, Any], progress: dict[str, Any] | None) -> dict[str, Any]:
        status = "not_started"
        progress_pct = 0
        launched_at = None
        completed_at = None
        if progress:
            status = progress.get("status") or "not_started"
            progress_pct = int(progress.get("progress_pct") or 0)
            launched_at = progress.get("launched_at")
            completed_at = progress.get("completed_at")
        return {
            **course,
            "status": status,
            "progress_pct": progress_pct,
            "launched_at": launched_at,
            "completed_at": completed_at,
        }

    # Deterministic confidence and leaderboard
    def confidence(self, employee_code: str) -> dict[str, Any]:
        rd = self.assessment(employee_code, "rd")
        zm = self.assessment(employee_code, "zm")
        if not rd or rd["status"] != "submitted" or not zm or zm["status"] != "submitted":
            return {"status": "pending", "score": None, "competencies": []}
        roleplays = {
            row["competency"]: row for row in self.roleplays(employee_code, include_private=True)
        }
        rows = []
        for competency in self.competencies:
            ai_level = roleplays[competency].get("ai_proficiency")
            if not ai_level:
                rows.append({"competency": competency, "status": "pending"})
                continue
            rd_value = PROFICIENCY_VALUE[rd["ratings"][competency]]
            zm_value = PROFICIENCY_VALUE[zm["ratings"][competency]]
            ai_value = PROFICIENCY_VALUE[ai_level]
            zm_agreement = round((1 - abs(rd_value - zm_value) / 3) * 100, 1)
            ai_agreement = round((1 - abs(rd_value - ai_value) / 3) * 100, 1)
            rows.append(
                {
                    "competency": competency,
                    "status": "complete",
                    "rd_rating": rd["ratings"][competency],
                    "zm_rating": zm["ratings"][competency],
                    "ai_rating": ai_level,
                    "zm_agreement": zm_agreement,
                    "ai_agreement": ai_agreement,
                    "confidence": round((zm_agreement + ai_agreement) / 2, 1),
                }
            )
        completed = [row for row in rows if row["status"] == "complete"]
        if len(completed) != len(self.competencies):
            return {"status": "pending", "score": None, "completed": len(completed), "total": len(self.competencies), "competencies": rows}
        score = round(sum(row["confidence"] for row in completed) / len(completed), 1)
        band = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
        return {"status": "complete", "score": score, "band": band, "competencies": rows}

    def leaderboard(self, user: dict[str, Any]) -> dict[str, Any]:
        """Severity-band cohort leaderboard + badges + manager/RD stats."""
        scoped = self.scoped_employees(user)
        employee_cohort: int | None = None
        viewer_code = ""
        if user["role"] == "employee":
            viewer_code = str(user.get("employee_code") or "")
            if self.final_profile(viewer_code):
                employee_cohort = int(self.learning_target(viewer_code)["total_gap_levels"])
                with self.db.connect() as connection:
                    scoped = [dict(row) for row in connection.execute("SELECT * FROM employees ORDER BY employee_code")]

        rows: list[dict[str, Any]] = []
        with self.db.connect() as connection:
            for employee in scoped:
                code = employee["employee_code"]
                if not self.final_profile(code):
                    continue
                target = self.learning_target(code)
                severity = int(target["total_gap_levels"])
                if employee_cohort is not None and severity != employee_cohort:
                    continue
                focus_areas = len(target.get("gaps") or [])
                activity = connection.execute(
                    "SELECT learning_hours,completions FROM linkedin_activity WHERE employee_code=?",
                    (code,),
                ).fetchone()
                hours = float(activity["learning_hours"]) if activity else 0.0
                completions = int(activity["completions"]) if activity else 0
                linkedin_locked = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM learning_selections WHERE employee_code=?", (code,)
                    ).fetchone()[0]
                )
                linkedin_done = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM course_progress cp
                        JOIN learning_selections ls
                          ON ls.employee_code=cp.employee_code AND ls.course_id=cp.course_id
                        WHERE cp.employee_code=? AND cp.status='completed'
                        """,
                        (code,),
                    ).fetchone()[0]
                )
                full_circuit = bool(linkedin_locked and linkedin_done >= linkedin_locked)
                rows.append(
                    {
                        "employee_code": code,
                        "name": employee["name"],
                        "severity_band": severity,
                        "focus_areas": focus_areas,
                        "gap_cohort": severity,  # back-compat
                        "learning_hours": hours,
                        "completions": completions,
                        "journey_locked": bool(linkedin_locked),
                        "full_circuit": full_circuit,
                    }
                )

        # Rank within each severity band: hours desc, then completions desc; share rank on full tie.
        for cohort in {row["severity_band"] for row in rows}:
            group = sorted(
                (row for row in rows if row["severity_band"] == cohort),
                key=lambda row: (-row["learning_hours"], -row["completions"], row["name"]),
            )
            previous_key = None
            rank = 0
            for index, row in enumerate(group, 1):
                key = (row["learning_hours"], row["completions"])
                if previous_key is None or key != previous_key:
                    rank = index
                    previous_key = key
                row["rank"] = rank

        for row in rows:
            row["badges"] = self._sync_badges_for_row(row)

        rows = sorted(rows, key=lambda row: (row["severity_band"], row["rank"], row["name"]))
        viewer_badges = []
        viewer_row = next((row for row in rows if row["employee_code"] == viewer_code), None)
        if viewer_row:
            viewer_badges = viewer_row["badges"]
        elif viewer_code:
            viewer_badges = self.badges_for(viewer_code)

        viewer_gaps: list[dict[str, Any]] = []
        if viewer_code and self.final_profile(viewer_code):
            for gap in self.learning_target(viewer_code).get("gaps") or []:
                levels = int(gap.get("gap_levels") or 0)
                intensity = "High" if levels >= 3 else "Med" if levels == 2 else "Low"
                viewer_gaps.append(
                    {
                        "competency": gap["competency"],
                        "gap_levels": levels,
                        "intensity": intensity,
                        "current": gap.get("current"),
                        "target": gap.get("target"),
                    }
                )

        stats = None
        if user["role"] in {"zm", "rd", "admin"}:
            stats = self._leaderboard_stats(rows)

        return {
            "leaderboard": rows,
            "viewer": {
                "role": user["role"],
                "employee_code": viewer_code or None,
                "severity_band": employee_cohort,
                "focus_areas": viewer_row["focus_areas"] if viewer_row else None,
                "rank": viewer_row["rank"] if viewer_row else None,
                "learning_hours": viewer_row["learning_hours"] if viewer_row else None,
                "completions": viewer_row["completions"] if viewer_row else None,
                "gaps": viewer_gaps,
            },
            "badges": viewer_badges,
            "badge_catalog": BADGE_CATALOG,
            "stats": stats,
        }

    def badges_for(self, employee_code: str) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT badge_id,title,earned_at,meta_json FROM employee_badges WHERE employee_code=? ORDER BY earned_at",
                (employee_code,),
            ).fetchall()
        return [
            {
                "id": row["badge_id"],
                "title": row["title"],
                "earned_at": row["earned_at"],
                "meta": self.db.decode_json(row["meta_json"], {}),
            }
            for row in rows
        ]

    def _sync_badges_for_row(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        code = row["employee_code"]
        hours = float(row["learning_hours"])
        completions = int(row["completions"])
        earned: list[tuple[str, str, dict[str, Any]]] = []
        stacked = int(hours // 2)
        if stacked >= 1:
            earned.append(
                (
                    "hours_stacked",
                    "Hours Stacked",
                    {"tier": stacked, "hours": hours, "copy": f"+{stacked * 2:.0f}h on LinkedIn — Hours Stacked unlocked"},
                )
            )
        if completions >= 1:
            earned.append(("first_mile", "First Mile", {"completions": completions}))
        if completions >= 3:
            earned.append(("pathway_pack", "Pathway Pack", {"completions": completions}))
        if completions >= 5:
            earned.append(("lattice_climber", "Lattice Climber", {"completions": completions}))
        if hours >= 10:
            earned.append(("ten_hour_club", "Ten-Hour Club", {"hours": hours}))
        if row.get("full_circuit"):
            earned.append(("full_circuit", "Full Circuit", {}))
        if int(row.get("focus_areas") or 0) == 0 and int(row.get("severity_band") or 0) == 0:
            earned.append(("gap_closer", "Gap Closer", {"focus_areas": 0}))
        if int(row.get("rank") or 0) == 1:
            earned.append(("cohort_crown", "Cohort Crown", {"severity_band": row.get("severity_band")}))

        now = utc_now()
        with self.db.transaction() as connection:
            for badge_id, title, meta in earned:
                connection.execute(
                    """
                    INSERT INTO employee_badges(employee_code,badge_id,title,earned_at,meta_json)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(employee_code,badge_id) DO UPDATE SET
                        title=excluded.title,
                        meta_json=excluded.meta_json
                    """,
                    (code, badge_id, title, now, json.dumps(meta, default=str)),
                )
        return self.badges_for(code)

    @staticmethod
    def _leaderboard_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
        team_size = len(rows)
        total_hours = round(sum(row["learning_hours"] for row in rows), 1)
        avg_hours = round(total_hours / team_size, 1) if team_size else 0.0
        locked = sum(1 for row in rows if row.get("journey_locked"))
        focus_dist: dict[int, int] = {}
        for row in rows:
            key = int(row["focus_areas"])
            focus_dist[key] = focus_dist.get(key, 0) + 1
        hours_buckets = {"0–2h": 0, "2–5h": 0, "5–10h": 0, "10h+": 0}
        for row in rows:
            h = float(row["learning_hours"])
            if h < 2:
                hours_buckets["0–2h"] += 1
            elif h < 5:
                hours_buckets["2–5h"] += 1
            elif h < 10:
                hours_buckets["5–10h"] += 1
            else:
                hours_buckets["10h+"] += 1
        badge_dist: dict[str, int] = {}
        for row in rows:
            for badge in row.get("badges") or []:
                key = badge.get("title") or badge.get("id") or "Badge"
                badge_dist[key] = badge_dist.get(key, 0) + 1
        return {
            "team_size": team_size,
            "total_hours": total_hours,
            "avg_hours": avg_hours,
            "journey_locked": locked,
            "journey_locked_pct": int(round((locked / team_size) * 100)) if team_size else 0,
            "focus_area_distribution": [
                {"focus_areas": key, "count": focus_dist[key]} for key in sorted(focus_dist)
            ],
            "hours_buckets": [{"label": label, "count": count} for label, count in hours_buckets.items()],
            "badge_distribution": [
                {"name": name, "count": count}
                for name, count in sorted(badge_dist.items(), key=lambda item: (-item[1], item[0]))
            ],
            "severity_bands": [
                {"band": band, "count": sum(1 for row in rows if row["severity_band"] == band)}
                for band in sorted({row["severity_band"] for row in rows})
            ],
        }

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
        return result

    # Helpers
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
