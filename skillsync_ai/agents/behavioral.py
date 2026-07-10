from __future__ import annotations

import hashlib

from ..core.config import PROFICIENCY_ORDER
from ..state import RuntimeState
from .llm import chat_json, load_few_shot, normalize_proficiency, record_decision
from .logging import log_entry
from .ocr_qwen import extract_screenshot_text

SYSTEM = """You are Agent A BehaviouralEvidence for a Business Development skill profiler.
You receive OCR text transcribed from a Udemy / LinkedIn Learning role-play screenshot for ONE behavioural skill.
Return JSON only with this shape:
{
  "proficiency": "Beginner|Intermediate|Proficient|Advanced",
  "strong_points": ["..."],
  "weak_points": ["..."],
  "rationale": "one short paragraph grounded in the OCR text"
}
Rules:
- Use only the provided OCR transcript (scores, feedback, strengths, weaknesses, outcome).
- Prefer explicit labels in the text when present.
- If transcript is empty/unreadable/unrelated, return Intermediate with weak_points noting insufficient evidence.
- Never invent employer HR data. Never return text outside JSON.
"""


def score_behavioral_evidence(emp_code: str, skill: str, filename: str, payload: bytes, state: RuntimeState) -> str:
    result = _run_agent(skill, filename, payload, state, emp_code)
    score = result["proficiency"]
    state.behavioral_scores.setdefault(emp_code, {})[skill] = score
    state.behavioral_rationales.setdefault(emp_code, {})[skill] = result
    state.behavioral_uploads.setdefault(emp_code, {})[skill] = filename
    source = result.get("source", "agent")
    state.agent_logs.append(
        log_entry(
            emp_code,
            "Agent A BehaviouralEvidence",
            f"{skill} → {score} ({source}). Strong: {', '.join(result.get('strong_points') or []) or 'n/a'}. "
            f"Weak: {', '.join(result.get('weak_points') or []) or 'n/a'}.",
        )
    )
    record_decision(
        state,
        agent="AgentA",
        emp_code=emp_code,
        input_summary=f"skill={skill}; file={filename}; ocr={(result.get('ocr_text') or '')[:500]}",
        output=result,
    )
    return score


def _run_agent(skill: str, filename: str, payload: bytes, state: RuntimeState, emp_code: str) -> dict:
    ocr = extract_screenshot_text(payload, filename)
    ocr_text = (ocr.get("text") or "").strip()
    ocr_error = (ocr.get("error") or "").strip()
    state.agent_logs.append(
        log_entry(
            emp_code,
            "Qwen OCR",
            f"{skill}: {'ok' if ocr_text else 'failed'} ({ocr.get('source')}). {ocr_error or f'{len(ocr_text)} chars extracted'}",
        )
    )

    user = (
        f"Skill under assessment: {skill}.\n"
        f"Allowed labels: {', '.join(PROFICIENCY_ORDER)}.\n\n"
        f"OCR transcript from screenshot `{filename}`:\n"
        f"{ocr_text or '[EMPTY — OCR failed or no text]'}\n\n"
        f"OCR error (if any): {ocr_error or 'none'}\n\n"
        "Return proficiency JSON only."
    )
    few_shot = load_few_shot("AgentA", state)
    parsed = chat_json(SYSTEM, user, agent_name="AgentA", state=state, few_shot=few_shot, emp_code=emp_code)
    if parsed:
        proficiency = normalize_proficiency(parsed.get("proficiency"))
        if proficiency:
            return {
                "proficiency": proficiency,
                "strong_points": _as_list(parsed.get("strong_points")),
                "weak_points": _as_list(parsed.get("weak_points")),
                "rationale": str(parsed.get("rationale") or "").strip() or "Judged from OCR transcript.",
                "ocr_text": ocr_text[:4000],
                "ocr_source": ocr.get("source", ""),
                "ocr_error": ocr_error,
                "source": "Qwen OCR + Groq text",
            }
    return _fallback(skill, filename, payload, ocr_text, ocr_error, ocr.get("source", ""))


def _fallback(
    skill: str,
    filename: str,
    payload: bytes,
    ocr_text: str,
    ocr_error: str,
    ocr_source: str,
) -> dict:
    if not payload:
        score = "Intermediate"
    else:
        digest = hashlib.sha256(f"{skill}:{filename}".encode() + payload[:256]).digest()
        score = PROFICIENCY_ORDER[digest[0] % len(PROFICIENCY_ORDER)]
    return {
        "proficiency": score,
        "strong_points": [],
        "weak_points": ["Groq text agent unavailable or returned invalid JSON"],
        "rationale": "Fallback hash-based proficiency because Groq LLM call failed after OCR step.",
        "ocr_text": ocr_text[:4000],
        "ocr_source": ocr_source,
        "ocr_error": ocr_error,
        "source": "demo fallback",
    }


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []
