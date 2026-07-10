from __future__ import annotations

import hashlib

from ..core.config import PROFICIENCY_ORDER
from ..state import RuntimeState
from .llm import normalize_proficiency, record_decision, vision_json
from .logging import log_entry

SYSTEM = """You are Agent A BehaviouralEvidence for a Business Development skill profiler.
You read a Udemy / LinkedIn Learning role-play screenshot for ONE behavioural skill.
Return JSON only with this shape:
{
  "proficiency": "Beginner|Intermediate|Proficient|Advanced",
  "strong_points": ["..."],
  "weak_points": ["..."],
  "rationale": "one short paragraph"
}
Rules:
- Use only visible screenshot evidence (scores, feedback, strengths, weaknesses, outcome).
- Prefer explicit labels on the screenshot when present.
- If unreadable or unrelated, return Intermediate with weak_points noting insufficient evidence.
- Never invent employer HR data. Never return text outside JSON.
"""


def score_behavioral_evidence(emp_code: str, skill: str, filename: str, payload: bytes, state: RuntimeState) -> str:
    result = _run_agent(skill, filename, payload, state)
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
        input_summary=f"skill={skill}; file={filename}",
        output=result,
    )
    return score


def _run_agent(skill: str, filename: str, payload: bytes, state: RuntimeState) -> dict:
    user = (
        f"Skill under assessment: {skill}.\n"
        "Extract proficiency plus strong and weak points from the screenshot.\n"
        f"Allowed labels: {', '.join(PROFICIENCY_ORDER)}.\n"
        "Respond with JSON only."
    )
    parsed = vision_json(SYSTEM, user, filename, payload)
    if parsed:
        proficiency = normalize_proficiency(parsed.get("proficiency"))
        if proficiency:
            return {
                "proficiency": proficiency,
                "strong_points": _as_list(parsed.get("strong_points")),
                "weak_points": _as_list(parsed.get("weak_points")),
                "rationale": str(parsed.get("rationale") or "").strip() or "Vision model judgment.",
                "source": "Groq vision",
            }
    return _fallback(skill, filename, payload)


def _fallback(skill: str, filename: str, payload: bytes) -> dict:
    if not payload:
        score = "Intermediate"
    else:
        digest = hashlib.sha256(f"{skill}:{filename}".encode() + payload[:256]).digest()
        score = PROFICIENCY_ORDER[digest[0] % len(PROFICIENCY_ORDER)]
    return {
        "proficiency": score,
        "strong_points": ["Demo fallback used — set GROQ_API_KEY for live vision scoring"],
        "weak_points": ["No live model response"],
        "rationale": "Fallback hash-based proficiency because Groq vision was unavailable.",
        "source": "demo fallback",
    }


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []
