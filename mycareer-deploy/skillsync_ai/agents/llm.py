from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import threading
import time
from typing import Any

from ..core.config import (
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
    emp_code: str = "",
    throttle: bool = True,
    max_completion_tokens: int = 3000,
) -> dict[str, Any] | None:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

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
        max_completion_tokens=max_completion_tokens,
    )


def chat_image_json(
    system: str,
    prompt: str,
    image_data_url: str,
    *,
    agent_name: str,
    emp_code: str = "",
    max_completion_tokens: int = 3000,
) -> dict[str, Any] | None:
    """Send one image with a text prompt and require a JSON response."""
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}},
            ],
        },
    ]
    log.info("Vision call start agent=%s emp=%s", agent_name, emp_code or "-")
    throttle_api_call()
    return _chat_openai(
        messages,
        agent_name=agent_name,
        emp_code=emp_code,
        max_completion_tokens=max_completion_tokens,
    )


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
    max_completion_tokens: int,
) -> dict[str, Any] | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    log.info("OpenAI attempt agent=%s emp=%s model=%s key_configured=%s", agent_name, emp_code or "-", OPENAI_MODEL, bool(api_key))
    if not api_key:
        log.error("OPENAI_API_KEY missing")
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
        return None
    parsed = _parse_json(raw or "")
    if parsed is None:
        log.error("Invalid JSON from OpenAI: %s", (raw or "")[:240])
        return None
    log.info("OpenAI OK agent=%s keys=%s", agent_name, list(parsed.keys()))
    return parsed


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
