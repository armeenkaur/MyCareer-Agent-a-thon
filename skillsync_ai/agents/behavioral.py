from __future__ import annotations

import json
from ..core.config import PROFICIENCY_ORDER
from ..state import RuntimeState
from .llm import chat_json, normalize_proficiency, record_decision
from .logging import log_entry
from .ocr_qwen import extract_screenshot_text


SYSTEM = """You are BehaviouralEvidence, an in-house assessment agent for hotel-supply Business Development employees.
You receive OCR transcripts from all four behavioural role-play screenshots together. Score each transcript only against
its mapped skill. Never transfer evidence between skills. Return JSON:
{"skills": {"Skill Name": {"proficiency": "Beginner|Intermediate|Proficient|Advanced", "strong_points": [],
"weak_points": [], "rationale": "grounded concise reason"}}}. Use explicit assessment labels, strengths, weaknesses,
scores, and feedback. If one transcript is unreadable, return Intermediate for that skill and state insufficient evidence.
Return every supplied skill exactly once. Never invent HR or performance evidence."""


def extract_behavioral_evidence(emp_code: str, skill: str, filename: str, payload: bytes, state: RuntimeState) -> None:
    ocr = extract_screenshot_text(payload, filename)
    ocr_text = str(ocr.get("text") or "").strip()
    ocr_error = str(ocr.get("error") or "").strip()
    state.behavioral_uploads.setdefault(emp_code, {})[skill] = filename
    state.behavioral_ocr.setdefault(emp_code, {})[skill] = {
        "filename": filename,
        "text": ocr_text[:8000],
        "source": str(ocr.get("source") or ""),
        "error": ocr_error,
    }
    state.agent_logs.append(
        log_entry(emp_code, "Local OCR", f"{skill}: {'ok' if ocr_text else 'failed'} ({ocr.get('source')}); {len(ocr_text)} chars.")
    )


def score_behavioral_batch(emp_code: str, skills: list[str], state: RuntimeState) -> bool:
    evidence = state.behavioral_ocr.get(emp_code, {})
    if not all(skill in evidence for skill in skills):
        return False
    if all(skill in state.behavioral_scores.get(emp_code, {}) for skill in skills):
        return True
    payload = {
        skill: {
            "filename": evidence[skill].get("filename", ""),
            "ocr_transcript": evidence[skill].get("text") or "[EMPTY]",
            "ocr_error": evidence[skill].get("error") or "none",
        }
        for skill in skills
    }
    parsed = chat_json(
        SYSTEM,
        json.dumps({"allowed_labels": PROFICIENCY_ORDER, "assessments": payload}, ensure_ascii=True),
        agent_name="AgentA-Batch",
        state=state,
        emp_code=emp_code,
        throttle=True,
    )
    outputs = (parsed or {}).get("skills") or {}
    normalized = {}
    for skill in skills:
        result = _normalize_result(outputs.get(skill), evidence[skill])
        if result is None:
            state.agent_logs.append(
                log_entry(emp_code, "Agent A BehaviouralEvidence Batch", f"No score stored: missing or invalid model output for {skill}.")
            )
            return False
        normalized[skill] = result
    for skill, result in normalized.items():
        state.behavioral_scores.setdefault(emp_code, {})[skill] = result["proficiency"]
        state.behavioral_rationales.setdefault(emp_code, {})[skill] = result
        state.agent_logs.append(
            log_entry(emp_code, "Agent A BehaviouralEvidence Batch", f"{skill} -> {result['proficiency']} ({result['source']}).")
        )
    record_decision(
        state,
        agent="AgentA-Batch",
        emp_code=emp_code,
        input_summary=f"One batch containing OCR evidence for {', '.join(skills)}",
        output={"skills": {skill: state.behavioral_rationales[emp_code][skill] for skill in skills}},
    )
    return True


def score_behavioral_evidence(emp_code: str, skill: str, filename: str, payload: bytes, state: RuntimeState) -> str:
    """Compatibility wrapper: extract one screenshot; batch scoring happens after all skills arrive."""
    extract_behavioral_evidence(emp_code, skill, filename, payload, state)
    return state.behavioral_scores.get(emp_code, {}).get(skill, "")


def _normalize_result(value: object, evidence: dict[str, str]) -> dict | None:
    row = value if isinstance(value, dict) else {}
    proficiency = normalize_proficiency(row.get("proficiency"))
    if not proficiency:
        return None
    return {
        "proficiency": proficiency,
        "strong_points": _as_list(row.get("strong_points")),
        "weak_points": _as_list(row.get("weak_points")),
        "rationale": str(row.get("rationale") or "Proficiency mapped from extracted assessment text."),
        "ocr_text": evidence.get("text", "")[:4000],
        "ocr_source": evidence.get("source", ""),
        "ocr_error": evidence.get("error", ""),
        "source": "OCR + OpenAI",
    }


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if value and str(value).strip() else []
