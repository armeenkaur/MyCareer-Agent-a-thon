from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import (
    AGENT_DECISION_LOG,
    FEW_SHOT_LIMIT,
    GROQ_API_URL,
    GROQ_TEXT_MODEL,
    PROFICIENCY_ORDER,
)
from ..core.logging_setup import get_logger
from ..core.utils import clean

log = get_logger("skillsync.groq")


def chat_json(
    system: str,
    user: str,
    *,
    agent_name: str,
    state: Any | None = None,
    few_shot: list[dict[str, Any]] | None = None,
    temperature: float = 0.1,
    emp_code: str = "",
) -> dict[str, Any] | None:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    key_preview = f"{api_key[:7]}…{api_key[-4:]}" if len(api_key) > 14 else "(empty)"
    log.info(
        "Groq call start agent=%s emp=%s model=%s key=%s user_chars=%s",
        agent_name,
        emp_code or "-",
        GROQ_TEXT_MODEL,
        key_preview,
        len(user),
    )
    if not api_key:
        detail = "GROQ_API_KEY missing — agent used fallback"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, status="skipped", detail=detail)
        return None

    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for example in (few_shot or [])[-FEW_SHOT_LIMIT:]:
        messages.append({"role": "user", "content": str(example.get("input", ""))[:4000]})
        messages.append({"role": "assistant", "content": json.dumps(example.get("output", {}))[:4000]})
    messages.append({"role": "user", "content": user})
    body = {
        "model": GROQ_TEXT_MODEL,
        "temperature": temperature,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    log.debug("Groq request agent=%s payload_keys=%s", agent_name, list(body.keys()))
    raw, error = _post(api_key, body)
    if error:
        log.error("Groq call FAILED agent=%s emp=%s detail=%s", agent_name, emp_code or "-", error)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, status="error", detail=error)
        return None
    log.debug("Groq raw agent=%s preview=%s", agent_name, (raw or "")[:300])
    parsed = _parse_json(raw or "")
    if parsed is None:
        detail = f"Invalid JSON from Groq: {(raw or '')[:240]}"
        log.error("Groq JSON parse fail agent=%s detail=%s", agent_name, detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, status="error", detail=detail)
        return None
    log.info("Groq call OK agent=%s emp=%s keys=%s", agent_name, emp_code or "-", list(parsed.keys()))
    _log_api_call(
        state,
        agent=agent_name,
        emp_code=emp_code,
        status="ok",
        detail=f"model={GROQ_TEXT_MODEL}",
    )
    return parsed


def record_decision(
    state: Any,
    *,
    agent: str,
    emp_code: str,
    input_summary: str,
    output: dict[str, Any],
) -> None:
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agent": agent,
        "employee": emp_code,
        "input": input_summary[:2000],
        "output": output,
    }
    state.agent_decisions.append(entry)
    log.debug("Decision recorded agent=%s emp=%s", agent, emp_code)
    try:
        AGENT_DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AGENT_DECISION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except OSError as exc:
        log.warning("Could not write agent_decisions.jsonl: %s", exc)


def load_few_shot(agent: str, state: Any) -> list[dict[str, Any]]:
    memory = [row for row in state.agent_decisions if row.get("agent") == agent]
    if len(memory) >= FEW_SHOT_LIMIT:
        return memory[-FEW_SHOT_LIMIT:]
    disk = _read_disk_decisions(agent)
    combined = disk + memory
    return combined[-FEW_SHOT_LIMIT:]


def normalize_proficiency(value: Any) -> str | None:
    text = clean(value)
    if not text:
        return None
    lowered = text.lower()
    for label in PROFICIENCY_ORDER:
        if label.lower() == lowered or label.lower() in lowered:
            return label
    return None


def _log_api_call(
    state: Any | None,
    *,
    agent: str,
    emp_code: str,
    status: str,
    detail: str,
) -> None:
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "employee": emp_code,
        "agent": agent,
        "provider": "groq",
        "status": status,
        "detail": detail[:500],
    }
    if state is not None:
        state.api_calls.append(entry)
        state.agent_logs.append(
            {
                "time": entry["time"],
                "employee": emp_code or "-",
                "agent": f"Groq API ({agent})",
                "message": f"{status}: {detail[:300]}",
            }
        )


def _post(api_key: str, body: dict[str, Any]) -> tuple[str | None, str | None]:
    request = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    log.debug("Groq HTTP POST %s model=%s", GROQ_API_URL, body.get("model"))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = getattr(response, "status", 200)
            raw_body = response.read().decode("utf-8")
            log.debug("Groq HTTP status=%s bytes=%s", status, len(raw_body))
            result = json.loads(raw_body)
        content = clean(result["choices"][0]["message"]["content"])
        usage = result.get("usage") or {}
        log.info(
            "Groq response ok tokens prompt=%s completion=%s total=%s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
            usage.get("total_tokens"),
        )
        return content, None
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")[:800]
        except Exception:  # noqa: BLE001
            body_text = ""
        err = f"HTTP {exc.code}: {body_text or exc.reason}"
        log.error("Groq HTTPError %s", err)
        return None, err
    except (urllib.error.URLError, TimeoutError) as exc:
        err = f"Network error: {exc}"
        log.error("Groq network error: %s", exc)
        return None, err
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        err = f"Bad response shape: {exc}"
        log.error("Groq bad response: %s", exc)
        return None, err


def _parse_json(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _read_disk_decisions(agent: str) -> list[dict[str, Any]]:
    path = Path(AGENT_DECISION_LOG)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[-40:]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("agent") == agent:
                rows.append(row)
    except OSError:
        return []
    return rows
