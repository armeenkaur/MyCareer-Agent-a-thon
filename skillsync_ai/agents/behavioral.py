from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request

from ..core.config import GROQ_API_URL, GROQ_VISION_MODEL, PROFICIENCY_ORDER
from ..core.utils import clean
from ..state import RuntimeState
from .logging import log_entry


def score_behavioral_evidence(emp_code: str, skill: str, filename: str, payload: bytes, state: RuntimeState) -> str:
    score = _groq_behavioral_score(skill, filename, payload)
    source = "Groq"
    if score is None:
        source = "demo fallback"
        if not payload:
            score = "Intermediate"
        else:
            digest = hashlib.sha256(emp_code.encode() + skill.encode() + filename.encode() + payload[:256]).digest()
            score = PROFICIENCY_ORDER[digest[0] % len(PROFICIENCY_ORDER)]
    state.behavioral_scores.setdefault(emp_code, {})[skill] = score
    state.behavioral_uploads.setdefault(emp_code, {})[skill] = filename
    state.agent_logs.append(log_entry(emp_code, "Behavioural Evidence Agent", f"{skill} screenshot assigned {score} via {source}."))
    return score


def _groq_behavioral_score(skill: str, filename: str, payload: bytes) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not payload:
        return None
    mime_type = mimetypes.guess_type(filename)[0] or "image/png"
    image_url = f"data:{mime_type};base64,{base64.b64encode(payload).decode('ascii')}"
    prompt = (
        "You are rating a Business Development employee's behavioural role-play screenshot. "
        f"Skill being assessed: {skill}. "
        "Return exactly one proficiency label from this set: Beginner, Intermediate, Proficient, Advanced. "
        "Use the screenshot evidence only. If the screenshot is unreadable, return Intermediate."
    )
    body = {
        "model": GROQ_VISION_MODEL,
        "temperature": 0,
        "max_tokens": 12,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        GROQ_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return None
    return _extract_proficiency(clean(result["choices"][0]["message"]["content"]))


def _extract_proficiency(content: str) -> str | None:
    normalized = content.lower()
    for label in PROFICIENCY_ORDER:
        if label.lower() in normalized:
            return label
    return None
