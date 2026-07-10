from __future__ import annotations

import base64
import json
import mimetypes
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
    GROQ_VISION_MODEL,
    PROFICIENCY_ORDER,
)
from ..core.utils import clean


def chat_json(
    system: str,
    user: str,
    *,
    agent_name: str,
    few_shot: list[dict[str, Any]] | None = None,
    temperature: float = 0.1,
) -> dict[str, Any] | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
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
    raw = _post(api_key, body)
    if raw is None:
        return None
    return _parse_json(raw)


def vision_json(
    system: str,
    user: str,
    filename: str,
    payload: bytes,
    *,
    temperature: float = 0.1,
) -> dict[str, Any] | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not payload:
        return None
    mime_type = mimetypes.guess_type(filename)[0] or "image/png"
    image_url = f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
    body = {
        "model": GROQ_VISION_MODEL,
        "temperature": temperature,
        "max_tokens": 500,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
    }
    raw = _post(api_key, body)
    if raw is None:
        return None
    return _parse_json(raw)


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
    try:
        AGENT_DECISION_LOG.parent.mkdir(parents=True, exist_ok=True)
        with AGENT_DECISION_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
    except OSError:
        pass


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


def _post(api_key: str, body: dict[str, Any]) -> str | None:
    request = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
        return clean(result["choices"][0]["message"]["content"])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError):
        return None


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
