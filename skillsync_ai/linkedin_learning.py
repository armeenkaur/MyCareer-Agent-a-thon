from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from .agents.llm import throttle_api_call
from .core.config import (
    LINKEDIN_LEARNING_CLIENT_ID,
    LINKEDIN_LEARNING_CLIENT_SECRET,
    LINKEDIN_REPORT_URL,
    LINKEDIN_TOKEN_URL,
)


def sync_learning_activity(data: Any, state: Any) -> dict[str, Any]:
    if not LINKEDIN_LEARNING_CLIENT_ID or not LINKEDIN_LEARNING_CLIENT_SECRET:
        return _finish("error", "LinkedIn client ID or secret missing.", 0, 0)
    try:
        token = _access_token()
        reports = _learner_reports(token)
    except Exception as exc:  # noqa: BLE001
        return _finish("error", str(exc), 0, 0)

    by_code = {code.lower(): code for code in data.employees}
    by_name = {str(emp.get("name") or "").strip().lower(): code for code, emp in data.employees.items()}
    matched = 0
    for report in reports:
        learner = report.get("learnerDetails") or {}
        unique_id = str(learner.get("uniqueUserId") or "").strip().lower()
        email_id = str(learner.get("email") or "").split("@", 1)[0].strip().lower()
        name = str(learner.get("name") or "").strip().lower()
        emp_code = by_code.get(unique_id) or by_code.get(email_id) or by_name.get(name)
        if not emp_code:
            continue
        seconds = 0
        completions = 0
        for activity in report.get("activities") or []:
            if activity.get("engagementType") == "SECONDS_VIEWED":
                seconds = max(seconds, int(activity.get("engagementValue") or 0))
            elif activity.get("engagementType") == "COMPLETIONS":
                completions += int(activity.get("engagementValue") or 0)
        state.linkedin_hours[emp_code] = round(seconds / 3600, 2)
        state.linkedin_completions[emp_code] = completions
        matched += 1
    return _finish("ok", f"Matched {matched} of {len(reports)} LinkedIn learners.", len(reports), matched)


def _access_token() -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": LINKEDIN_LEARNING_CLIENT_ID,
        "client_secret": LINKEDIN_LEARNING_CLIENT_SECRET,
    }).encode("utf-8")
    request = urllib.request.Request(LINKEDIN_TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    throttle_api_call()
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"LinkedIn token HTTP {exc.code}: {detail}") from exc
    token = str(payload.get("access_token") or "")
    if not token:
        raise RuntimeError("LinkedIn token response missing access_token.")
    return token


def _learner_reports(token: str) -> list[dict[str, Any]]:
    started_at = int((datetime.now(timezone.utc) - timedelta(days=14)).timestamp() * 1000)
    params = {
        "q": "criteria",
        "start": 0,
        "count": 500,
        "startedAt": started_at,
        "timeOffset.duration": 14,
        "timeOffset.unit": "DAY",
        "aggregationCriteria.primary": "INDIVIDUAL",
        "contentSource": "LINKEDIN_LEARNING",
        "sortBy.engagementMetricType": "SECONDS_VIEWED",
    }
    request = urllib.request.Request(
        f"{LINKEDIN_REPORT_URL}?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    throttle_api_call()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"LinkedIn report HTTP {exc.code}: {detail}") from exc
    return list(payload.get("elements") or [])


def _finish(status: str, message: str, learners: int, matched: int) -> dict[str, Any]:
    return {
        "status": status,
        "message": message,
        "learners": learners,
        "matched": matched,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
