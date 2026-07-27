from __future__ import annotations

import json
from typing import Any
from ..agents.course_recommendation import AGENT_NAME as COURSE_AGENT, _fallback_choices, _prefilter, _rank_all_with_agent, curate_other_sources, resolve_other_source
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from ..core.logging_setup import get_logger
from ..core.utils import display_designation, is_kam_title, role_level_key, slug
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class LearningMixin:
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


    def assert_courses_journey_ready(self, employee_code: str) -> None:
        """Courses unlock only after Assessments → Lattice → Aspiration (ZM/RD profiles stay)."""
        if not self.lattice_unlocked(employee_code):
            raise BackendError(
                "Complete both voice roleplay sessions before selecting courses.",
                "lattice_locked",
                409,
            )
        if not self.career_state(employee_code).get("choice"):
            raise BackendError(
                "Lock a career aspiration before selecting courses.",
                "aspiration_required",
                409,
            )


    def recommendations(self, employee_code: str) -> dict[str, Any]:
        self.assert_courses_journey_ready(employee_code)
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
        self.assert_courses_journey_ready(employee_code)
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
        self.record_learning_day(employee_code)
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
