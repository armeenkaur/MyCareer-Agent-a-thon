from __future__ import annotations

import base64
import json
import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..backend import BackendError, MyCareerBackend


LOGGER = logging.getLogger(__name__)
MAX_JSON_BODY_BYTES = 100 * 1024 * 1024


class BackendAPI:
    def __init__(self, backend: MyCareerBackend) -> None:
        self.backend = backend

    def handle_options(self, handler: Any) -> None:
        handler.send_response(204)
        self._cors(handler)
        handler.end_headers()

    def handle_get(self, handler: Any) -> None:
        parsed = urlparse(handler.path)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        try:
            if parsed.path == "/api/health":
                self._send(handler, 200, {"status": "ok", "service": "MyCareer Compass Backend"})
                return
            if parsed.path == "/api/meta":
                self._send(
                    handler,
                    200,
                    {
                        "competencies": [
                            {
                                "competency": row["skill"],
                                "tag": row["tag"],
                                "definition": row["definition"],
                                "ideal_profiles": row["ideals"],
                            }
                            for row in self.backend.data.competencies
                        ],
                        "rubric": self.backend.data.level_definitions,
                        "proficiency_levels": ["Beginner", "Intermediate", "Proficient", "Advanced"],
                        "roleplay_links": self.backend.data.roleplay_links,
                        "terminology": {"preferred": "competency", "avoid": "skill"},
                    },
                )
                return
            user = self._user(handler)
            if parsed.path == "/api/me":
                self._send(handler, 200, {"user": self.backend.public_user(user)})
            elif parsed.path == "/api/phases":
                self._send(handler, 200, {"phases": self.backend.phases()})
            elif parsed.path == "/api/employee-summaries":
                self._send(handler, 200, {"employees": self.backend.employee_summaries(user)})
            elif parsed.path == "/api/final-profile":
                employee_code = self._employee_code(user, query)
                self._send(handler, 200, self.backend.profile_for_user(user, employee_code))
            elif parsed.path == "/api/assessment":
                self._require_role(user, {"zm", "rd", "admin"})
                employee_code = self._required_query(query, "employee_code")
                if user["role"] in {"zm", "rd"}:
                    self.backend._assert_employee_scope(user, employee_code)
                role = user["role"] if user["role"] in {"zm", "rd"} else query.get("role", "rd")
                if role not in {"zm", "rd"}:
                    raise BackendError("Assessment role must be zm or rd.")
                self._send(handler, 200, {"assessment": self.backend.assessment(employee_code, role)})
            elif parsed.path == "/api/rd/validation":
                employee_code = self._required_query(query, "employee_code")
                self._send(handler, 200, self.backend.rd_validation_context(user, employee_code))
            elif parsed.path == "/api/employee/roleplays":
                employee_code = self._employee_code(user, query)
                self._send(
                    handler,
                    200,
                    {"roleplays": self.backend.roleplays(employee_code), "lattice_unlocked": self.backend.lattice_unlocked(employee_code)},
                )
            elif parsed.path == "/api/employee/career":
                self._send(handler, 200, self.backend.career_state(self._employee_code(user, query)))
            elif parsed.path == "/api/employee/courses":
                self._send(handler, 200, self.backend.recommendations(self._employee_code(user, query)))
            elif parsed.path == "/api/employee/learning":
                self._send(handler, 200, self.backend.learning_journey(self._employee_code(user, query)))
            elif parsed.path == "/api/leaderboard":
                self._send(handler, 200, {"leaderboard": self.backend.leaderboard(user)})
            elif parsed.path == "/api/admin/confidence":
                self._require_role(user, {"admin"})
                self._send(handler, 200, self.backend.confidence(self._required_query(query, "employee_code")))
            elif parsed.path == "/api/admin/roleplays":
                self._require_role(user, {"admin"})
                self._send(
                    handler,
                    200,
                    self.backend.admin_roleplays(
                        user,
                        self._required_query(query, "employee_code"),
                        str(query.get("competency") or ""),
                    ),
                )
            elif parsed.path == "/api/admin/overview":
                self._require_role(user, {"admin"})
                employees = self.backend.employee_summaries(user)
                with self.backend.db.connect() as connection:
                    active_journeys = int(
                        connection.execute("SELECT COUNT(DISTINCT employee_code) FROM learning_selections").fetchone()[0]
                    )
                    learning_hours = float(
                        connection.execute("SELECT COALESCE(SUM(learning_hours),0) FROM linkedin_activity").fetchone()[0]
                    )
                self._send(
                    handler,
                    200,
                    {
                        "phases": self.backend.phases(),
                        "employees": employees,
                        "leaderboard": self.backend.leaderboard(user),
                        "insights": self.backend.talent_insights(),
                        "metrics": {
                            "total_employees": len(employees),
                            "zm_completed": sum(row["zm_status"] == "submitted" for row in employees),
                            "rd_completed": sum(row["rd_status"] == "submitted" for row in employees),
                            "roleplays_completed": sum(row["roleplays_completed"] == row["roleplays_total"] for row in employees),
                            "locked_aspirations": sum(bool(row["aspiration"]) for row in employees),
                            "active_journeys": active_journeys,
                            "learning_hours": round(learning_hours, 1),
                        },
                    },
                )
            elif parsed.path == "/api/admin/audit":
                self._require_role(user, {"admin"})
                self._send(handler, 200, {"audit": self.backend.agent_audit(int(query.get("limit", "100")))})
            else:
                self._send(handler, 404, {"error": {"code": "not_found", "message": "API route not found."}})
        except BackendError as exc:
            self._error(handler, exc)
        except Exception:
            LOGGER.exception("Unhandled GET API error")
            self._error(handler, BackendError("Internal server error.", "internal_error", 500))

    def handle_post(self, handler: Any) -> None:
        parsed = urlparse(handler.path)
        try:
            body = self._body(handler)
            if parsed.path == "/api/auth/login":
                result = self.backend.login(
                    str(body.get("login_id") or ""), str(body.get("role") or ""), str(body.get("password") or "")
                )
                self._send(handler, 200, result)
                return
            user = self._user(handler)
            if parsed.path == "/api/auth/logout":
                self.backend.logout(self._token(handler))
                self._send(handler, 200, {"status": "ok"})
            elif parsed.path == "/api/auth/password":
                self._send(
                    handler,
                    200,
                    self.backend.change_password(
                        user,
                        str(body.get("current_password") or ""),
                        str(body.get("new_password") or ""),
                    ),
                )
            elif parsed.path == "/api/admin/phases/open":
                self._require_role(user, {"admin"})
                phase = self.backend.open_phase(user, str(body.get("phase") or ""), bool(body.get("override")))
                self._send(handler, 200, {"phase": phase})
            elif parsed.path == "/api/admin/phases/close":
                self._require_role(user, {"admin"})
                self._send(handler, 200, {"phase": self.backend.close_phase(user, str(body.get("phase") or ""))})
            elif parsed.path == "/api/assessment":
                self._require_role(user, {"zm", "rd"})
                result = self.backend.save_assessment(
                    user,
                    str(body.get("employee_code") or ""),
                    body.get("ratings") if isinstance(body.get("ratings"), dict) else {},
                    body.get("notes") if isinstance(body.get("notes"), dict) else {},
                    bool(body.get("submit")),
                )
                self._send(handler, 200, {"assessment": result})
            elif parsed.path == "/api/employee/roleplays":
                self._require_role(user, {"employee"})
                try:
                    payload = base64.b64decode(str(body.get("content_base64") or ""), validate=True)
                except (ValueError, TypeError):
                    raise BackendError("content_base64 must contain valid base64 screenshot data.")
                result = self.backend.submit_roleplay(
                    user, str(body.get("competency") or ""), str(body.get("filename") or "roleplay.png"), payload
                )
                self._send(handler, 200, result)
            elif parsed.path == "/api/employee/career":
                self._require_role(user, {"employee"})
                self._send(handler, 200, self.backend.choose_career(user, str(body.get("aspiration_role") or "")))
            elif parsed.path == "/api/admin/career/reset":
                self._require_role(user, {"admin"})
                self.backend.reset_career(user, str(body.get("employee_code") or ""))
                self._send(handler, 200, {"status": "reset"})
            elif parsed.path == "/api/admin/learning/reset":
                self._require_role(user, {"admin"})
                self._send(
                    handler,
                    200,
                    self.backend.reset_learning(user, str(body.get("employee_code") or "")),
                )
            elif parsed.path == "/api/employee/learning/checkout":
                self._require_role(user, {"employee"})
                course_ids = body.get("course_ids") if isinstance(body.get("course_ids"), list) else []
                other_sources = body.get("other_sources") if isinstance(body.get("other_sources"), list) else []
                self._send(
                    handler,
                    200,
                    self.backend.checkout(user, [str(value) for value in course_ids], other_sources),
                )
            elif parsed.path == "/api/employee/learning/progress":
                self._require_role(user, {"employee"})
                self._send(
                    handler,
                    200,
                    self.backend.update_course_progress(
                        user,
                        str(body.get("course_id") or ""),
                        str(body.get("action") or ""),
                    ),
                )
            elif parsed.path == "/api/admin/linkedin/sync":
                self._require_role(user, {"admin"})
                self._send(handler, 200, self.backend.sync_linkedin(user))
            else:
                self._send(handler, 404, {"error": {"code": "not_found", "message": "API route not found."}})
        except BackendError as exc:
            self._error(handler, exc)
        except json.JSONDecodeError:
            self._error(handler, BackendError("Request body must be valid JSON."))
        except Exception:
            LOGGER.exception("Unhandled POST API error")
            self._error(handler, BackendError("Internal server error.", "internal_error", 500))

    @staticmethod
    def _body(handler: Any) -> dict[str, Any]:
        try:
            length = int(handler.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise BackendError("Content-Length must be a valid integer.") from exc
        if length < 0 or length > MAX_JSON_BODY_BYTES:
            raise BackendError("Request body exceeds the 100 MB safety limit.", "payload_too_large", 413)
        if not length:
            return {}
        payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise BackendError("JSON request body must be an object.")
        return payload

    def _user(self, handler: Any) -> dict[str, Any]:
        return self.backend.user_for_token(self._token(handler))

    @staticmethod
    def _token(handler: Any) -> str:
        authorization = str(handler.headers.get("Authorization") or "")
        if not authorization.startswith("Bearer "):
            raise BackendError("Bearer token required.", "unauthorized", 401)
        return authorization.removeprefix("Bearer ").strip()

    @staticmethod
    def _required_query(query: dict[str, str], key: str) -> str:
        value = str(query.get(key) or "").strip()
        if not value:
            raise BackendError(f"Query parameter {key} is required.")
        return value

    @staticmethod
    def _require_role(user: dict[str, Any], roles: set[str]) -> None:
        if user.get("role") not in roles:
            raise BackendError("You do not have access to this resource.", "forbidden", 403)

    def _employee_code(self, user: dict[str, Any], query: dict[str, str]) -> str:
        if user["role"] == "employee":
            return str(user["employee_code"])
        employee_code = self._required_query(query, "employee_code")
        if user["role"] in {"zm", "rd"}:
            self.backend._assert_employee_scope(user, employee_code)
        return employee_code

    @staticmethod
    def _cors(handler: Any) -> None:
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, handler: Any, status: int, payload: Any) -> None:
        body = json.dumps(payload, default=str).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        self._cors(handler)
        handler.end_headers()
        handler.wfile.write(body)

    def _error(self, handler: Any, exc: BackendError) -> None:
        self._send(handler, exc.status, {"error": {"code": exc.code, "message": exc.message}})
