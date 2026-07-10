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
    LLM_PROVIDER,
    OLLAMA_HOST,
    OLLAMA_TEXT_MODEL,
    PROFICIENCY_ORDER,
)
from ..core.logging_setup import get_logger
from ..core.utils import clean

log = get_logger("skillsync.llm")


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
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for example in (few_shot or [])[-FEW_SHOT_LIMIT:]:
        messages.append({"role": "user", "content": str(example.get("input", ""))[:4000]})
        messages.append({"role": "assistant", "content": json.dumps(example.get("output", {}))[:4000]})
    messages.append({"role": "user", "content": user})

    provider = (LLM_PROVIDER or "auto").strip().lower()
    log.info(
        "LLM call start agent=%s emp=%s provider=%s user_chars=%s",
        agent_name,
        emp_code or "-",
        provider,
        len(user),
    )

    if provider in {"auto", "groq"}:
        parsed = _chat_groq(messages, agent_name=agent_name, emp_code=emp_code, state=state, temperature=temperature)
        if parsed is not None:
            return parsed
        if provider == "groq":
            return None
        log.warning("Groq failed — falling back to Ollama text for agent=%s", agent_name)

    if provider in {"auto", "ollama"}:
        return _chat_ollama(messages, agent_name=agent_name, emp_code=emp_code, state=state, temperature=temperature)

    detail = f"Unknown LLM_PROVIDER={provider}"
    log.error(detail)
    _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="none", status="error", detail=detail)
    return None


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


def check_ollama_models() -> dict[str, Any]:
    """Return installed Ollama model names + whether required models exist."""
    host = OLLAMA_HOST.rstrip("/")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        names = [str(row.get("name") or "") for row in data.get("models") or []]
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "models": [], "has_vl": False, "has_text": False}

    def _has(target: str) -> bool:
        return any(name == target or name.startswith(f"{target}") for name in names)

    from ..core.config import OLLAMA_VL_MODEL

    return {
        "ok": True,
        "error": "",
        "models": names,
        "has_vl": _has(OLLAMA_VL_MODEL),
        "has_text": _has(OLLAMA_TEXT_MODEL),
        "vl_model": OLLAMA_VL_MODEL,
        "text_model": OLLAMA_TEXT_MODEL,
    }


def _chat_groq(
    messages: list[dict[str, Any]],
    *,
    agent_name: str,
    emp_code: str,
    state: Any | None,
    temperature: float,
) -> dict[str, Any] | None:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    key_preview = f"{api_key[:7]}…{api_key[-4:]}" if len(api_key) > 14 else "(empty)"
    log.info("Groq attempt agent=%s model=%s key=%s", agent_name, GROQ_TEXT_MODEL, key_preview)
    if not api_key:
        detail = "GROQ_API_KEY missing"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="groq", status="skipped", detail=detail)
        return None

    body = {
        "model": GROQ_TEXT_MODEL,
        "temperature": temperature,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    raw, error = _post_groq(api_key, body)
    if error:
        hint = ""
        if "1010" in error or "403" in error:
            hint = " | Cloudflare/network blocked Groq (error 1010). Use hotspot or set LLM_PROVIDER=ollama."
        log.error("Groq FAILED agent=%s detail=%s%s", agent_name, error, hint)
        _log_api_call(
            state,
            agent=agent_name,
            emp_code=emp_code,
            provider="groq",
            status="error",
            detail=error + hint,
        )
        return None
    parsed = _parse_json(raw or "")
    if parsed is None:
        detail = f"Invalid JSON from Groq: {(raw or '')[:240]}"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="groq", status="error", detail=detail)
        return None
    log.info("Groq OK agent=%s keys=%s", agent_name, list(parsed.keys()))
    _log_api_call(
        state,
        agent=agent_name,
        emp_code=emp_code,
        provider="groq",
        status="ok",
        detail=f"model={GROQ_TEXT_MODEL}",
    )
    return parsed


def _chat_ollama(
    messages: list[dict[str, Any]],
    *,
    agent_name: str,
    emp_code: str,
    state: Any | None,
    temperature: float,
) -> dict[str, Any] | None:
    host = OLLAMA_HOST.rstrip("/")
    model = OLLAMA_TEXT_MODEL
    body = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {"temperature": temperature},
    }
    url = f"{host}/api/chat"
    log.info("Ollama text attempt agent=%s model=%s url=%s", agent_name, model, url)
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        raw = clean((payload.get("message") or {}).get("content") or payload.get("response") or "")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:  # noqa: BLE001
            detail = str(exc.reason)
        err = f"Ollama HTTP {exc.code}: {detail}"
        if exc.code == 404:
            err += f" | Run: ollama pull {model}"
        log.error(err)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="ollama", status="error", detail=err)
        return None
    except Exception as exc:  # noqa: BLE001
        err = f"Ollama unreachable/error: {exc} | Is Ollama running? Try: ollama pull {model}"
        log.error(err)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="ollama", status="error", detail=err)
        return None

    parsed = _parse_json(raw)
    if parsed is None:
        detail = f"Invalid JSON from Ollama: {raw[:240]}"
        log.error(detail)
        _log_api_call(state, agent=agent_name, emp_code=emp_code, provider="ollama", status="error", detail=detail)
        return None
    log.info("Ollama text OK agent=%s keys=%s", agent_name, list(parsed.keys()))
    _log_api_call(
        state,
        agent=agent_name,
        emp_code=emp_code,
        provider="ollama",
        status="ok",
        detail=f"model={model}",
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


def _post_groq(api_key: str, body: dict[str, Any]) -> tuple[str | None, str | None]:
    request = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MyCareerCompass/1.0 (+local-hackathon)",
        },
        method="POST",
    )
    log.debug("Groq HTTP POST %s model=%s", GROQ_API_URL, body.get("model"))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw_body = response.read().decode("utf-8")
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
