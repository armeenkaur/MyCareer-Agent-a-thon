from __future__ import annotations

from datetime import datetime


def log_entry(emp_code: str, agent: str, message: str) -> dict[str, str]:
    return {
        "time": datetime.now().strftime("%H:%M:%S"),
        "employee": emp_code,
        "agent": agent,
        "message": message,
    }
