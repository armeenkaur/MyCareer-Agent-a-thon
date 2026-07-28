from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any
from ..agents.roleplay_assessment import AGENT_NAME as ROLEPLAY_AGENT, assess_roleplay
from ..agents.llm import normalize_proficiency
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR, VOICE_INPUT_SAMPLE_RATE, VOICE_PLAYBACK_SAMPLE_RATE
from ..core.logging_setup import get_logger
from ..core.utils import display_designation, is_kam_title, role_level_key, slug
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from ..voice_live import (
    ALL_ROLEPLAY_SKILLS,
    ROLEPLAY_BUCKETS,
    ROLEPLAY_STRONG,
    ROLEPLAY_SUPPORTING,
    VOICE_KINDS,
    merge_roleplay_scores,
)
from .constants import BADGE_CATALOG, SCREENSHOT_EXTENSIONS, VOICE_TICKET_TTL_SECONDS, _VOICE_TICKETS, _VOICE_TICKETS_LOCK
from .errors import BackendError
log = get_logger('skillsync.backend')
 
class RoleplaysMixin:
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
        result: dict[str, Any] = {
            "employee": employee,
            "roleplays": rows,
            "sessions": self.voice_roleplay_sessions(employee_code, include_scores=True),
            "lattice_unlocked": self.lattice_unlocked(employee_code),
        }
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
        sessions = {row["kind"]: row for row in self.voice_roleplay_sessions(employee_code)}
        return all(sessions.get(kind, {}).get("status") == "completed" for kind in VOICE_KINDS)


    def voice_roleplay_sessions(
        self, employee_code: str, *, include_scores: bool = False
    ) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            stored = {
                row["kind"]: dict(row)
                for row in connection.execute(
                    "SELECT * FROM voice_roleplay_sessions WHERE employee_code=?",
                    (employee_code,),
                ).fetchall()
            }
        output = []
        for kind in VOICE_KINDS:
            row = stored.get(kind, {})
            item: dict[str, Any] = {
                "kind": kind,
                "label": "Functional roleplay" if kind == "functional" else "Behavioural roleplay",
                "competencies": list(ROLEPLAY_BUCKETS[kind]),
                "status": row.get("status", "not_started"),
                "error": row.get("error", ""),
                "updated_at": row.get("updated_at"),
            }
            if include_scores:
                scores: dict[str, Any] = {}
                raw = row.get("scores_json") or "{}"
                try:
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    if isinstance(parsed, dict):
                        scores = parsed
                except json.JSONDecodeError:
                    scores = {}
                item["scores"] = scores
            output.append(item)
        return output


    def start_voice_roleplay(self, user: dict[str, Any], kind: str) -> dict[str, Any]:
        if user.get("role") != "employee":
            raise BackendError("Employee access required.", "forbidden", 403)
        if not self.phase_is_open("employee"):
            raise BackendError("Employee phase is closed.", "phase_closed", 403)
        kind = str(kind or "").strip().lower()
        if kind not in VOICE_KINDS:
            raise BackendError("kind must be functional or behavioural.")
        employee_code = str(user["employee_code"])
        existing = next((row for row in self.voice_roleplay_sessions(employee_code) if row["kind"] == kind), None)
        if existing and existing["status"] == "completed":
            raise BackendError("This roleplay session is already completed.", "already_completed", 409)
        session_id = uuid.uuid4().hex
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO voice_roleplay_sessions(employee_code, kind, status, scores_json, error, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(employee_code, kind) DO UPDATE SET
                    status='in_progress', error='', updated_at=excluded.updated_at
                """,
                (employee_code, kind, "in_progress", "{}", "", now),
            )
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=VOICE_TICKET_TTL_SECONDS)
        with _VOICE_TICKETS_LOCK:
            self._purge_voice_tickets_locked()
            _VOICE_TICKETS[session_id] = {
                "session_id": session_id,
                "employee_code": employee_code,
                "kind": kind,
                "expires_at": expires_at,
            }
        return {
            "session_id": session_id,
            "kind": kind,
            "competencies": list(ROLEPLAY_BUCKETS[kind]),
            "ws_path": f"/ws/voice-roleplay?session_id={session_id}",
            "expires_at": expires_at.isoformat(),
            "playback_sample_rate": VOICE_PLAYBACK_SAMPLE_RATE,
            "input_sample_rate": VOICE_INPUT_SAMPLE_RATE,
        }


    def voice_roleplay_ticket(self, session_id: str, user: dict[str, Any]) -> dict[str, Any]:
        session_id = str(session_id or "").strip()
        if not session_id:
            raise BackendError("session_id is required.", "unauthorized", 401)
        with _VOICE_TICKETS_LOCK:
            self._purge_voice_tickets_locked()
            ticket = _VOICE_TICKETS.get(session_id)
        if not ticket:
            raise BackendError("Voice session ticket not found or expired.", "unauthorized", 401)
        if ticket["employee_code"] != user.get("employee_code"):
            raise BackendError("Voice session does not belong to this employee.", "forbidden", 403)
        return dict(ticket)

    @staticmethod

    def _purge_voice_tickets_locked() -> None:
        now = datetime.now(timezone.utc)
        expired = [key for key, value in _VOICE_TICKETS.items() if value.get("expires_at") and value["expires_at"] < now]
        for key in expired:
            _VOICE_TICKETS.pop(key, None)


    def complete_voice_roleplay(
        self,
        session_id: str,
        employee_code: str,
        ratings: dict[str, Any],
    ) -> dict[str, Any]:
        with _VOICE_TICKETS_LOCK:
            ticket = _VOICE_TICKETS.pop(session_id, None)
        kind = (ticket or {}).get("kind")
        if not kind:
            # Allow complete via API using stored in_progress row when ticket already consumed
            sessions = self.voice_roleplay_sessions(employee_code)
            in_progress = [row for row in sessions if row["status"] == "in_progress"]
            if len(in_progress) == 1:
                kind = in_progress[0]["kind"]
            else:
                raise BackendError("Voice session ticket not found.", "not_found", 404)
        cleaned = self._normalize_voice_scores(kind, ratings)
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO voice_roleplay_sessions(employee_code, kind, status, scores_json, error, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(employee_code, kind) DO UPDATE SET
                    status='completed', scores_json=excluded.scores_json, error='', updated_at=excluded.updated_at
                """,
                (employee_code, kind, "completed", json.dumps(cleaned), "", now),
            )
            self._upsert_voice_ai_scores(connection, employee_code, now)
        self._audit(
            employee_code,
            "voice_roleplay",
            kind,
            f"Voice session {kind}",
            {"ratings": cleaned},
            "completed",
        )
        if self.phase_progress("employee")["is_complete"]:
            with self.db.transaction() as connection:
                connection.execute(
                    "UPDATE phases SET status='complete', closed_at=? WHERE phase='employee'",
                    (utc_now(),),
                )
        return {
            "status": "completed",
            "kind": kind,
            "sessions": self.voice_roleplay_sessions(employee_code, include_scores=False),
            "lattice_unlocked": self.lattice_unlocked(employee_code),
        }

    def _normalize_voice_scores(self, kind: str, ratings: dict[str, Any]) -> dict[str, Any]:
        """Validate strong/supporting score map with confidence. Supporting may be null."""
        if not isinstance(ratings, dict):
            raise BackendError("Ratings must be an object.")
        required = ROLEPLAY_STRONG[kind]
        optional = ROLEPLAY_SUPPORTING[kind]
        expected = set(required) | set(optional)
        unknown = set(ratings) - expected
        if unknown:
            raise BackendError(f"Unknown competencies in ratings: {', '.join(sorted(unknown))}.")
        missing_required = [skill for skill in required if skill not in ratings]
        if missing_required:
            raise BackendError(f"Ratings missing required competencies: {', '.join(missing_required)}.")
        cleaned: dict[str, Any] = {}
        for skill in list(required) + list(optional):
            if skill not in ratings:
                cleaned[skill] = None
                continue
            entry = ratings[skill]
            if entry is None:
                if skill in required:
                    raise BackendError(f"Required competency cannot be null: {skill}.")
                cleaned[skill] = None
                continue
            if isinstance(entry, str):
                level = normalize_proficiency(entry.strip())
                confidence = 0.7
            elif isinstance(entry, dict):
                level = normalize_proficiency(str(entry.get("level") or "").strip())
                try:
                    confidence = float(entry.get("confidence"))
                except (TypeError, ValueError) as exc:
                    raise BackendError(f"Invalid confidence for {skill}.") from exc
            else:
                raise BackendError(f"Invalid rating shape for {skill}.")
            if level is None:
                raise BackendError(f"Invalid proficiency for {skill}.")
            cleaned[skill] = {
                "level": level,
                "confidence": max(0.0, min(1.0, confidence)),
            }
        return cleaned

    def _upsert_voice_ai_scores(
        self, connection: Any, employee_code: str, now: str
    ) -> None:
        """Write AI proficiency: partial after one session; confidence-weighted merge after both."""
        rows = connection.execute(
            "SELECT kind, status, scores_json FROM voice_roleplay_sessions WHERE employee_code=?",
            (employee_code,),
        ).fetchall()
        completed: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row["status"] != "completed":
                continue
            try:
                parsed = json.loads(row["scores_json"] or "{}")
            except json.JSONDecodeError:
                parsed = {}
            if isinstance(parsed, dict):
                completed[row["kind"]] = parsed
        if len(completed) >= 2 and all(kind in completed for kind in VOICE_KINDS):
            try:
                merged = merge_roleplay_scores([completed[kind] for kind in VOICE_KINDS])
            except ValueError as exc:
                raise BackendError(str(exc), "score_merge_failed", 422) from exc
            rationale = "Voice roleplay confidence-weighted merge (functional + behavioural)."
            for competency, level in merged.items():
                self._write_roleplay_ai_row(
                    connection, employee_code, competency, level, rationale, now
                )
            return
        # Single session: write non-null skills only.
        for kind, scores in completed.items():
            for competency, entry in scores.items():
                if not isinstance(entry, dict):
                    continue
                level = entry.get("level")
                if level not in PROFICIENCY_ORDER:
                    continue
                conf = entry.get("confidence")
                rationale = f"Voice roleplay ({kind}) end-of-call rating (confidence={conf})."
                self._write_roleplay_ai_row(
                    connection, employee_code, competency, str(level), rationale, now
                )

    @staticmethod
    def _write_roleplay_ai_row(
        connection: Any,
        employee_code: str,
        competency: str,
        level: str,
        rationale: str,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO roleplay_assessments(
                employee_code,competency,filename,file_path,status,ai_proficiency,rationale,ocr_text,error,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(employee_code,competency) DO UPDATE SET
                status=excluded.status, ai_proficiency=excluded.ai_proficiency,
                rationale=excluded.rationale, error='', updated_at=excluded.updated_at
            """,
            (
                employee_code,
                competency,
                "voice_roleplay",
                "",
                "completed",
                level,
                rationale,
                "",
                "",
                now,
            ),
        )

    def fail_voice_roleplay(self, session_id: str, error: str) -> None:
        with _VOICE_TICKETS_LOCK:
            ticket = _VOICE_TICKETS.get(session_id)
        if not ticket:
            return
        with self.db.transaction() as connection:
            connection.execute(
                """
                UPDATE voice_roleplay_sessions
                SET status='failed', error=?, updated_at=?
                WHERE employee_code=? AND kind=? AND status!='completed'
                """,
                (str(error or "")[:500], utc_now(), ticket["employee_code"], ticket["kind"]),
            )

    def reset_voice_roleplays(self, admin: dict[str, Any], employee_code: str) -> dict[str, Any]:
        """Clear BDM voice roleplay sessions + AI competency scores so employee can retake."""
        if admin.get("role") != "admin":
            raise BackendError("Admin access required.", "forbidden", 403)
        employee = self.employee(employee_code)
        competencies = list(ALL_ROLEPLAY_SKILLS)
        with self.db.transaction() as connection:
            connection.execute(
                "DELETE FROM voice_roleplay_sessions WHERE employee_code=?",
                (employee_code,),
            )
            if competencies:
                placeholders = ",".join("?" for _ in competencies)
                connection.execute(
                    f"DELETE FROM roleplay_assessments WHERE employee_code=? AND competency IN ({placeholders})",
                    (employee_code, *competencies),
                )
        self._audit(
            employee_code,
            "voice_roleplay",
            "reset",
            f"Admin {admin.get('employee_code') or admin.get('name') or 'admin'} reset BDM assessments",
            {"competencies": competencies},
            "reset",
        )
        return {
            "status": "reset",
            "employee_code": employee["employee_code"],
            "sessions": self.voice_roleplay_sessions(employee_code, include_scores=True),
            "lattice_unlocked": False,
        }

