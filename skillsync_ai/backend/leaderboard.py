from __future__ import annotations

import json
from typing import Any
from ..core.logging_setup import get_logger
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .constants import BADGE_CATALOG, SCREENSHOT_EXTENSIONS, VOICE_TICKET_TTL_SECONDS, _VOICE_TICKETS, _VOICE_TICKETS_LOCK
log = get_logger('skillsync.backend')

class LeaderboardMixin:
    def leaderboard(self, user: dict[str, Any], *, force_refresh: bool = False) -> dict[str, Any]:
        """Flat leaderboard ranked by journey hours % then courses completed.

        Dense ranking (1223). Ranks + hours freeze to an IST daily snapshot.
        """
        cache_key = self._leaderboard_cache_key(user)
        snapshot_date = ist_today()
        if not force_refresh:
            cached = self._leaderboard_snapshot(cache_key, snapshot_date)
            if cached is not None:
                return cached
        payload = self._compute_leaderboard(user)
        payload["snapshot_date"] = snapshot_date
        payload["ranking"] = "dense"
        self._save_leaderboard_snapshot(cache_key, snapshot_date, payload)
        return payload


    def _leaderboard_cache_key(self, user: dict[str, Any]) -> str:
        role = str(user.get("role") or "")
        if role in {"admin", "lteam", "employee"}:
            return f"{role}:all"
        return f"{role}:{user.get('login_id') or ''}"


    def _leaderboard_snapshot(self, cache_key: str, snapshot_date: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM leaderboard_snapshots WHERE cache_key=? AND snapshot_date=?",
                (cache_key, snapshot_date),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None


    def _save_leaderboard_snapshot(self, cache_key: str, snapshot_date: str, payload: dict[str, Any]) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO leaderboard_snapshots(cache_key, snapshot_date, payload_json, computed_at)
                VALUES(?,?,?,?)
                ON CONFLICT(cache_key, snapshot_date) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    computed_at=excluded.computed_at
                """,
                (cache_key, snapshot_date, json.dumps(payload, default=str), utc_now()),
            )


    def _compute_leaderboard(self, user: dict[str, Any]) -> dict[str, Any]:
        """Flat leaderboard ranked by journey hours % then courses completed."""
        scoped = self.scoped_employees(user)
        viewer_code = ""
        if user["role"] == "employee":
            viewer_code = str(user.get("employee_code") or "")
            with self.db.connect() as connection:
                scoped = [dict(row) for row in connection.execute("SELECT * FROM employees ORDER BY employee_code")]

        catalog_by_id = {str(course.get("id") or ""): course for course in (self.data.courses or [])}
        rows: list[dict[str, Any]] = []
        with self.db.connect() as connection:
            for employee in scoped:
                code = employee["employee_code"]
                # Employees need a final profile for gap metadata; managers still see full roster.
                has_profile = bool(self.final_profile(code))
                if user["role"] == "employee" and not has_profile:
                    continue

                metrics = self._learning_completion_metrics(code, connection, catalog_by_id)
                gaps: list[dict[str, Any]] = []
                focus_areas = 0
                severity = 0
                if has_profile:
                    target = self.learning_target(code)
                    severity = int(target["total_gap_levels"])
                    gaps = [
                        {
                            "competency": gap["competency"],
                            "gap_levels": int(gap.get("gap_levels") or 0),
                        }
                        for gap in (target.get("gaps") or [])
                    ]
                    focus_areas = len(gaps)

                activity = connection.execute(
                    "SELECT learning_hours,completions FROM linkedin_activity WHERE employee_code=?",
                    (code,),
                ).fetchone()
                linkedin_hours = float(activity["learning_hours"]) if activity else 0.0
                linkedin_completions = int(activity["completions"]) if activity else 0

                rows.append(
                    {
                        "employee_code": code,
                        "name": employee["name"],
                        "severity_band": severity,
                        "focus_areas": focus_areas,
                        "gaps": gaps,
                        "gap_cohort": severity,
                        "learning_hours": linkedin_hours,
                        "completions": linkedin_completions,
                        "hours_pct": metrics["hours_pct"],
                        "completed_hours": metrics["completed_hours"],
                        "total_hours": metrics["total_hours"],
                        "courses_completed": metrics["courses_completed"],
                        "courses_total": metrics["courses_total"],
                        "journey_locked": metrics["journey_locked"],
                        "full_circuit": metrics["full_circuit"],
                    }
                )

        ranked = sorted(
            rows,
            key=lambda row: (-float(row["hours_pct"]), -int(row["courses_completed"]), str(row["name"] or "")),
        )
        previous_key = None
        rank = 0
        for row in ranked:
            key = (float(row["hours_pct"]), int(row["courses_completed"]))
            if previous_key is None or key != previous_key:
                rank += 1
                previous_key = key
            row["rank"] = rank

        for row in ranked:
            row["badges"] = self._sync_badges_for_row(row)

        rows = sorted(ranked, key=lambda row: (row["rank"], str(row["name"] or "")))
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
        if user["role"] in {"zm", "rd", "admin", "lteam"}:
            stats = self._leaderboard_stats(rows)

        return {
            "leaderboard": rows,
            "viewer": {
                "role": user["role"],
                "employee_code": viewer_code or None,
                "severity_band": viewer_row["severity_band"] if viewer_row else None,
                "focus_areas": viewer_row["focus_areas"] if viewer_row else None,
                "rank": viewer_row["rank"] if viewer_row else None,
                "learning_hours": viewer_row["learning_hours"] if viewer_row else None,
                "hours_pct": viewer_row["hours_pct"] if viewer_row else None,
                "completed_hours": viewer_row["completed_hours"] if viewer_row else None,
                "total_hours": viewer_row["total_hours"] if viewer_row else None,
                "courses_completed": viewer_row["courses_completed"] if viewer_row else None,
                "completions": viewer_row["completions"] if viewer_row else None,
                "gaps": viewer_gaps,
                "kudos": self.list_kudos(viewer_code) if viewer_code else [],
            },
            "badges": viewer_badges,
            "badge_catalog": BADGE_CATALOG,
            "stats": stats,
        }

    @staticmethod

    def _duration_to_minutes(value: Any) -> int:
        if value in (None, ""):
            return 0
        if isinstance(value, (int, float)):
            return max(0, int(value))
        text = str(value).strip().lower()
        if not text:
            return 0
        if text.endswith("m") and text[:-1].replace(".", "", 1).isdigit():
            return max(0, int(float(text[:-1])))
        if text.endswith("h") and text[:-1].replace(".", "", 1).isdigit():
            return max(0, int(float(text[:-1]) * 60))
        parts = text.split(":")
        try:
            nums = [int(float(part)) for part in parts]
        except ValueError:
            return 0
        if len(nums) == 3:
            return max(0, nums[0] * 60 + nums[1])
        if len(nums) == 2:
            # LinkedIn often uses HH:MM
            return max(0, nums[0] * 60 + nums[1])
        if len(nums) == 1:
            return max(0, nums[0])
        return 0


    def _learning_completion_metrics(
        self,
        employee_code: str,
        connection: Any,
        catalog_by_id: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        selections = connection.execute(
            "SELECT course_id FROM learning_selections WHERE employee_code=?",
            (employee_code,),
        ).fetchall()
        external = connection.execute(
            "SELECT resource_id, resource_json FROM external_learning WHERE employee_code=?",
            (employee_code,),
        ).fetchall()
        progress_rows = connection.execute(
            "SELECT course_id, status, progress_pct FROM course_progress WHERE employee_code=?",
            (employee_code,),
        ).fetchall()
        activity = connection.execute(
            "SELECT learning_hours FROM linkedin_activity WHERE employee_code=?",
            (employee_code,),
        ).fetchone()
        progress_by_id = {str(row["course_id"]): dict(row) for row in progress_rows}

        total_minutes = 0
        completed_minutes = 0
        courses_total = 0
        courses_completed = 0

        def accumulate(course_id: str, duration_minutes: int) -> None:
            nonlocal total_minutes, completed_minutes, courses_total, courses_completed
            courses_total += 1
            prog = progress_by_id.get(str(course_id)) or {}
            status = str(prog.get("status") or "not_started")
            pct = 100 if status == "completed" else max(0, min(100, int(prog.get("progress_pct") or 0)))
            if status == "completed":
                courses_completed += 1
            minutes = max(0, int(duration_minutes or 0))
            if minutes:
                total_minutes += minutes
                completed_minutes += int(round(minutes * pct / 100))

        for row in selections:
            course_id = str(row["course_id"])
            course = catalog_by_id.get(course_id) or {}
            accumulate(course_id, self._duration_to_minutes(course.get("duration")))

        for row in external:
            payload = self.db.decode_json(row["resource_json"], {})
            accumulate(str(row["resource_id"]), self._duration_to_minutes(payload.get("duration_minutes")))

        linkedin_hours = float(activity["learning_hours"]) if activity else 0.0
        if total_minutes > 0:
            from_sync = min(total_minutes, int(round(linkedin_hours * 60)))
            completed_minutes = max(completed_minutes, from_sync)
            completed_minutes = min(completed_minutes, total_minutes)
            hours_pct = round((completed_minutes / total_minutes) * 100, 1)
        elif courses_total > 0:
            hours_pct = round((courses_completed / courses_total) * 100, 1)
        else:
            hours_pct = 0.0

        return {
            "total_hours": round(total_minutes / 60, 1),
            "completed_hours": round(completed_minutes / 60, 1),
            "hours_pct": hours_pct,
            "courses_completed": courses_completed,
            "courses_total": courses_total,
            "journey_locked": courses_total > 0,
            "full_circuit": bool(courses_total and courses_completed >= courses_total),
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
        earned: list[tuple[str, str, dict[str, Any]]] = []
        if hours >= 2:
            earned.append(("two_hour_club", "Two-Hour Club", {"hours": hours}))
        if hours >= 10:
            earned.append(("ten_hour_club", "Ten-Hour Club", {"hours": hours}))
        streak = self.learning_streak(code)
        if streak >= 5:
            earned.append(("five_day_streak", "5-Day Streak", {"streak_days": streak}))
        if row.get("full_circuit"):
            earned.append(("full_circuit", "Full Circuit", {}))
        if int(row.get("focus_areas") or 0) == 0 and int(row.get("severity_band") or 0) == 0:
            earned.append(("gap_closer", "Gap Closer", {"focus_areas": 0}))

        earned_ids = {badge_id for badge_id, _, _ in earned}
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
            if earned_ids:
                placeholders = ",".join("?" for _ in earned_ids)
                connection.execute(
                    f"DELETE FROM employee_badges WHERE employee_code=? AND badge_id NOT IN ({placeholders})",
                    (code, *earned_ids),
                )
            else:
                connection.execute("DELETE FROM employee_badges WHERE employee_code=?", (code,))
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
        badge_earned: dict[str, int] = {badge["id"]: 0 for badge in BADGE_CATALOG}
        for row in rows:
            for badge in row.get("badges") or []:
                badge_id = badge.get("id")
                if badge_id in badge_earned:
                    badge_earned[badge_id] += 1
        skill_gaps: dict[str, int] = {}
        for row in rows:
            for gap in row.get("gaps") or []:
                skill = str(gap.get("competency") or "").strip()
                if not skill:
                    continue
                skill_gaps[skill] = skill_gaps.get(skill, 0) + 1
        return {
            "team_size": team_size,
            "total_hours": total_hours,
            "avg_hours": avg_hours,
            "journey_locked": locked,
            "journey_locked_pct": int(round((locked / team_size) * 100)) if team_size else 0,
            "focus_area_distribution": [
                {"focus_areas": key, "count": focus_dist[key]} for key in sorted(focus_dist)
            ],
            "skill_gap_distribution": [
                {"competency": skill, "count": skill_gaps[skill]}
                for skill in sorted(skill_gaps, key=lambda name: (-skill_gaps[name], name))
            ],
            "hours_buckets": [{"label": label, "count": count} for label, count in hours_buckets.items()],
            "badge_distribution": [
                {
                    "id": badge["id"],
                    "name": badge["title"],
                    "rule": badge["rule"],
                    "icon": badge.get("icon") or "military_tech",
                    "count": badge_earned.get(badge["id"], 0),
                }
                for badge in BADGE_CATALOG
            ],
            "severity_bands": [
                {"band": band, "count": sum(1 for row in rows if row["severity_band"] == band)}
                for band in sorted({row["severity_band"] for row in rows})
            ],
        }

