from __future__ import annotations

from typing import Any
from ..core.logging_setup import get_logger
from ..core.utils import display_designation, is_kam_title, role_level_key, slug
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class AuthMixin:
    def login(self, login_id: str, password: str, role: str | None = None) -> dict[str, Any]:
        login_id = str(login_id or "").strip()
        password = str(password or "")
        if role:
            user = self.db.authenticate(login_id, str(role), password)
            if not user:
                raise BackendError("Invalid employee ID or password.", "invalid_credentials", 401)
        else:
            matches = self.db.authenticate_login(login_id, password)
            if not matches:
                raise BackendError("Invalid employee ID or password.", "invalid_credentials", 401)
            # Prefer an open-phase role; else highest-priority match (ZM before RD).
            user = next(
                (
                    row
                    for row in matches
                    if row["role"] in PHASE_FREE_ROLES or self.phase_is_open(row["role"])
                ),
                matches[0],
            )

        chosen_role = user["role"]
        if chosen_role not in PHASE_FREE_ROLES and not self.phase_is_open(chosen_role):
            raise BackendError(
                "This phase is not open yet. You will be notified when access becomes available.",
                "phase_closed",
                403,
            )
        token = self.db.create_session(int(user["id"]))
        return {
            "token": token,
            "user": self.public_user(user),
            "phase": None if chosen_role in PHASE_FREE_ROLES else self.phase(chosen_role),
        }


    def switch_role(self, user: dict[str, Any], token: str, target_role: str) -> dict[str, Any]:
        target_role = str(target_role or "").strip().lower()
        available = self.db.roles_for_login(user["login_id"])
        if target_role not in available:
            raise BackendError("That portal is not available for this account.", "forbidden", 403)
        if target_role == user["role"]:
            return {
                "token": token,
                "user": self.public_user(user),
                "phase": None if target_role in PHASE_FREE_ROLES else self.phase(target_role),
            }
        if target_role not in PHASE_FREE_ROLES and not self.phase_is_open(target_role):
            raise BackendError(
                "This phase is not open yet. You will be notified when access becomes available.",
                "phase_closed",
                403,
            )
        target = self.db.user_by_login_role(user["login_id"], target_role)
        if not target:
            raise BackendError("That portal is not available for this account.", "forbidden", 403)
        self.db.delete_session(token)
        new_token = self.db.create_session(int(target["id"]))
        return {
            "token": new_token,
            "user": self.public_user(target),
            "phase": None if target_role in PHASE_FREE_ROLES else self.phase(target_role),
        }


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
        payload["available_roles"] = self.db.roles_for_login(str(user.get("login_id") or ""))
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

