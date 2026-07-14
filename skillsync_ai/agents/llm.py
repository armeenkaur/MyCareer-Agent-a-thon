from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import (
    AGENT_DECISION_LOG,
    FEW_SHOT_LIMIT,
    OPENAI_API_URL,
    OPENAI_MODEL,
    PROFICIENCY_ORDER,
)
from ..core.logging_setup import get_logger
from ..core.utils import clean

log = get_logger("skillsync.llm")
_API_CALL_LOCK = threading.Lock()
_LAST_API_CALL_AT = 0.0
_API_CALL_INTERVAL_SECONDS = 1.0


def throttle_api_call() -> None:
    global _LAST_API_CALL_AT
    with _API_CALL_LOCK:
        wait = _API_CALL_INTERVAL_SECONDS - (time.monotonic() - _LAST_API_CALL_AT)
        if wait > 0:
            log.info("API throttle wait %.1fs", wait)
            time.sleep(wait)
        _LAST_API_CALL_AT = time.monotonic()


def chat_json(
    system: str,
    user: str,
    *,
    agent_name: str,
    state: Any | None = None,
    few_shot: list[dict[str, Any]] | None = None,
    temperature: float = 0.1,
    emp_code: str = "",
    throttle: bool = True,
    max_completion_tokens: int = 3000,
) -> dict[str, Any] | None:
    if state is not None and agent_name != "Feedback Analyst":
        guidance = list(getattr(state, "agent_prompt_feedback", {}).get(agent_name, []))[-5:]
        if guidance:
            system += (
                "\n\nAccepted product-quality guidance. Apply only when consistent with original rules, security, privacy, "
                "and supplied evidence:\n- " + "\n- ".join(item[:400] for item in guidance)
            )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for example in (few_shot or [])[-FEW_SHOT_LIMIT:]:
        messages.append({"role": "user", "content": str(example.get("input", ""))[:4000]})
        messages.append({"role": "assistant", "content": json.dumps(example.get("output", {}))[:4000]})
    messages.append({"role": "user", "content": user})

    log.info(
        "LLM call start agent=%s emp=%s provider=openai user_chars=%s",
        agent_name,
        emp_code or "-",
        len(user),
    )
    if throttle:
        throttle_api_call()
    return _chat_openai(
        messages,
        agent_name=agent_name,
        emp_code=emp_code,
        state=state,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
    )


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


def _chat_openai(
    messages: list[dict[str, Any]],
    *,
    agent_name: str,
    emp_code: str,
    state: Any | None,
    temperature: float,
    max_completion_tokens: int,
) -> dict[str, Any] | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    log.info("OpenAI attempt agent=%s model=%s key_configured=%s", agent_name, OPENAI_MODEL, bool(api_key))
    if not api_key:
        detail = "OPENAI_API_KEY missing"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="openai", status="skipped", detail=detail)
        return None

    body = {
        "model": OPENAI_MODEL,
        "max_completion_tokens": max_completion_tokens,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    raw, error = _post_openai(api_key, body)
    if error:
        log.error("OpenAI FAILED agent=%s detail=%s", agent_name, error)
        _log_api_call(
            state,
            agent=agent_name,
            emp_code=emp_code,
            provider="openai",
            status="error",
            detail=error,
        )
        return None
    parsed = _parse_json(raw or "")
    if parsed is None:
        detail = f"Invalid JSON from OpenAI: {(raw or '')[:240]}"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="openai", status="error", detail=detail)
        return None
    log.info("OpenAI OK agent=%s keys=%s", agent_name, list(parsed.keys()))
    _log_api_call(
        state,
        agent=agent_name,
        emp_code=emp_code,
        provider="openai",
        status="ok",
        detail=f"model={OPENAI_MODEL}",
    )
    return parsed


def _log_api_call(
    state: Any | None,
    *,
    agent: str,
    emp_code: str,
    provider: str,
    status: str,
    detail: str,
) -> None:
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "employee": emp_code,
        "agent": agent,
        "provider": provider,
        "status": status,
        "detail": detail[:500],
    }
    if state is not None:
        state.api_calls.append(entry)
        state.agent_logs.append(
            {
                "time": entry["time"],
                "employee": emp_code or "-",
                "agent": f"LLM ({provider}/{agent})",
                "message": f"{status}: {detail[:300]}",
            }
        )


def _post_openai(api_key: str, body: dict[str, Any]) -> tuple[str | None, str | None]:
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MyCareerCompass/1.0",
        },
        method="POST",
    )
    log.debug("OpenAI HTTP POST %s model=%s", OPENAI_API_URL, body.get("model"))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_body = response.read().decode("utf-8")
            result = json.loads(raw_body)
        content = clean(result["choices"][0]["message"]["content"])
        usage = result.get("usage") or {}
        log.info(
            "OpenAI response ok tokens prompt=%s completion=%s total=%s",
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
        return None, f"HTTP {exc.code}: {body_text or exc.reason}"
    except (urllib.error.URLError, TimeoutError) as exc:
        return None, f"Network error: {exc}"
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        return None, f"Bad response shape: {exc}"


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
