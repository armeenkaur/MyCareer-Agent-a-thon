from __future__ import annotations

import json
from typing import Any

from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE
from ..core.utils import clean
from .llm import chat_json, load_few_shot, normalize_proficiency, record_decision

SYSTEM = """You are Agent B ContextRater for Business Development skill profiling.
You read TNA, annual appraisal feedback (or interview feedback only when appraisal is missing), and Amber evidence.
Weighting rules:
- TNA has employee input and manager input. Prefer manager wording at ~80% and employee at ~20%.
- Amber is manager-only evidence — treat it as manager-weighted signal.
- Appraisal is treated as recent (≤6 months) for this hackathon — always usable when present.
Output JSON only:
{
  "skills": {
    "<skill name>": {
      "suggested": "Beginner|Intermediate|Proficient|Advanced",
      "direction": "raise|lower|hold",
      "evidence_quotes": ["short quote", "..."],
      "weight_note": "how manager vs employee evidence was weighed"
    }
  },
  "summary": "short overall read"
}
Cover every skill listed in the user message. If no evidence for a skill, suggested=Intermediate, direction=hold, evidence_quotes=[].
Never invent quotes that are not grounded in the provided text.
"""


def interpret_context(data: Any, emp_code: str, skills: list[str], state: Any) -> dict[str, Any]:
    packet = _evidence_packet(data, emp_code)
    user = (
        f"Employee code: {emp_code}\n"
        f"Skills to rate: {json.dumps(skills)}\n"
        f"Allowed proficiency labels: {json.dumps(PROFICIENCY_ORDER)}\n\n"
        f"TNA rows (employee + manager inputs):\n{packet['tna_text']}\n\n"
        f"Appraisal or interview fallback evidence (treated recent):\n{packet['appraisal_text']}\n\n"
        f"Amber (manager-only):\n{packet['amber_text']}\n\n"
        "Return JSON with a suggested proficiency per skill."
    )
    few_shot = load_few_shot("AgentB", state)
    parsed = chat_json(SYSTEM, user, agent_name="AgentB", state=state, few_shot=few_shot, emp_code=emp_code)
    if parsed and isinstance(parsed.get("skills"), dict):
        result = _normalize_agent_output(parsed, skills)
        result["source"] = "OpenAI"
    else:
        result = _fallback(packet, skills)
        result["source"] = "heuristic fallback"
    record_decision(
        state,
        agent="AgentB",
        emp_code=emp_code,
        input_summary=user[:1500],
        output=result,
    )
    return result


def _normalize_agent_output(parsed: dict[str, Any], skills: list[str]) -> dict[str, Any]:
    skills_out: dict[str, Any] = {}
    raw_skills = parsed.get("skills") or {}
    for skill in skills:
        row = raw_skills.get(skill) or {}
        suggested = normalize_proficiency(row.get("suggested")) or "Intermediate"
        direction = clean(row.get("direction")).lower()
        if direction not in {"raise", "lower", "hold"}:
            direction = "hold"
        quotes = row.get("evidence_quotes") or []
        if not isinstance(quotes, list):
            quotes = [str(quotes)]
        skills_out[skill] = {
            "suggested": suggested,
            "direction": direction,
            "evidence_quotes": [str(q).strip() for q in quotes if str(q).strip()][:4],
            "weight_note": clean(row.get("weight_note")) or "Manager-weighted read of available evidence.",
        }
    return {
        "skills": skills_out,
        "summary": clean(parsed.get("summary")) or "Context rating complete.",
        "signals": {skill: _signal(row) for skill, row in skills_out.items()},
    }


def _signal(row: dict[str, Any]) -> int:
    value = PROFICIENCY_VALUE.get(row["suggested"], 2)
    if row["direction"] == "raise":
        return value
    if row["direction"] == "lower":
        return -value
    return 0


def _fallback(packet: dict[str, str], skills: list[str]) -> dict[str, Any]:
    text = f"{packet['tna_text']} {packet['appraisal_text']} {packet['amber_text']}".lower()
    weak = ["develop", "needs", "improve", "challenge", "lacks", "work on", "gap"]
    strong = ["strong", "excellent", "achieved", "delivered", "exceeded", "ownership"]
    weak_hits = sum(text.count(w) for w in weak)
    strong_hits = sum(text.count(w) for w in strong)
    skills_out: dict[str, Any] = {}
    for skill in skills:
        skill_hit = text.count(skill.lower().split()[0])
        if weak_hits > strong_hits and skill_hit:
            suggested, direction = "Beginner", "lower"
        elif strong_hits > weak_hits and skill_hit:
            suggested, direction = "Proficient", "raise"
        else:
            suggested, direction = "Intermediate", "hold"
        skills_out[skill] = {
            "suggested": suggested,
            "direction": direction,
            "evidence_quotes": [],
            "weight_note": "Heuristic fallback (no LLM). Manager-weighted intent preserved in live agent.",
        }
    return {
        "skills": skills_out,
        "summary": (
            f"Fallback context read. TNA chars={len(packet['tna_text'])}, "
            f"appraisal chars={len(packet['appraisal_text'])}, amber chars={len(packet['amber_text'])}."
        ),
        "signals": {skill: _signal(row) for skill, row in skills_out.items()},
    }


def _evidence_packet(data: Any, emp_code: str) -> dict[str, str]:
    tna_rows = data.tna.get(emp_code, [])
    appraisal = data.appraisal.get(emp_code, {})
    interview = data.interview.get(emp_code, {})
    amber_rows = data.amber.get(emp_code, [])
    tna_bits = []
    for row in tna_rows[:8]:
        emp_in = row.get("Employee Input") or row.get("Employee input") or ""
        mgr_in = row.get("Reporting Manager Input") or row.get("Manager Input") or ""
        tna_bits.append(f"Employee(20%): {emp_in} | Manager(80%): {mgr_in}")
    source_row = appraisal or interview
    source_name = "Annual appraisal" if appraisal else "Interview fallback"
    appraisal_text = " | ".join(f"{k}: {v}" for k, v in source_row.items() if v and k != "EMP Code")[:2500]
    amber_bits = []
    for row in amber_rows[:10]:
        amber_bits.append(
            f"Q: {row.get('Question', '')} A: {row.get('Answer', '')} "
            f"Follow-up: {row.get('Follow-up Comments', '')}"
        )
    return {
        "tna_text": "\n".join(tna_bits) or "No TNA rows",
        "appraisal_text": f"{source_name}: {appraisal_text}" if appraisal_text else "No appraisal or interview row",
        "amber_text": "\n".join(amber_bits) or "No Amber rows",
    }
