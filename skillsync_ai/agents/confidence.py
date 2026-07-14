from __future__ import annotations

import json
from typing import Any

from ..core.config import PROFICIENCY_VALUE
from ..core.utils import clean
from .llm import chat_json, load_few_shot, record_decision

SYSTEM = """You are Agent D Confidence for Business Development skill profiling.
You judge how trustworthy BD Skill Profile v1 is.
Inputs: profile scores, demographics, variable pay %, and a peer cohort with similar role/level/experience.
Look for contradictions such as:
- High skill profile but lower variable% than weaker peers in the same cohort
- Low skill profile but higher variable% than stronger peers
- Thin evidence / missing context
Return JSON only:
{
  "score": 0-100,
  "band": "High|Medium|Low",
  "explanation": "short why for admins",
  "peer_note": "peer/variable comparison note"
}
Bands: High >= 75, Medium >= 55, else Low.
"""


def score_confidence(
    data: Any,
    emp_code: str,
    scores: dict[str, str],
    context: dict[str, Any],
    gaps: list[dict[str, str]],
    state: Any,
) -> dict[str, Any]:
    employee = data.employees.get(emp_code, {})
    variable = data.variable.get(emp_code, {})
    peers = _peer_cohort(data, emp_code)
    user = (
        f"Employee: {json.dumps({k: employee.get(k) for k in ('code','name','designation','level','total_exp_years','cohort')})}\n"
        f"Variable pay avg: {variable.get('avg')}\n"
        f"Profile v1: {json.dumps(scores)}\n"
        f"Gap count: {len(gaps)}\n"
        f"Context summary: {context.get('summary', '')}\n"
        f"Peer cohort (same role/level/exp band): {json.dumps(peers)}\n"
        "Return confidence JSON."
    )
    few_shot = load_few_shot("AgentD", state)
    parsed = chat_json(SYSTEM, user, agent_name="AgentD", state=state, few_shot=few_shot, emp_code=emp_code)
    if parsed and parsed.get("score") is not None:
        result = _normalize(parsed, float(variable.get("avg") or 0))
        result["source"] = "OpenAI"
    else:
        result = _fallback(data, emp_code, scores, context, gaps, peers)
        result["source"] = "heuristic fallback"
    record_decision(
        state,
        agent="AgentD",
        emp_code=emp_code,
        input_summary=user[:1500],
        output=result,
    )
    return result


def _normalize(parsed: dict[str, Any], kra_avg: float) -> dict[str, Any]:
    try:
        score = int(float(parsed.get("score")))
    except (TypeError, ValueError):
        score = 60
    score = max(0, min(100, score))
    band = clean(parsed.get("band"))
    if band not in {"High", "Medium", "Low"}:
        band = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
    return {
        "score": score,
        "band": band,
        "explanation": clean(parsed.get("explanation")) or f"{band} confidence ({score}%).",
        "peer_note": clean(parsed.get("peer_note")),
        "kra_avg": kra_avg,
    }


def _fallback(
    data: Any,
    emp_code: str,
    scores: dict[str, str],
    context: dict[str, Any],
    gaps: list[dict[str, str]],
    peers: list[dict[str, Any]],
) -> dict[str, Any]:
    variable = data.variable.get(emp_code, {})
    avg_kra = float(variable.get("avg") or 0)
    evidence_rows = (
        len(data.tna.get(emp_code, []))
        + (1 if data.appraisal.get(emp_code) else 0)
        + len(data.amber.get(emp_code, []))
    )
    skill_avg = sum(PROFICIENCY_VALUE[v] for v in scores.values()) / max(len(scores), 1)
    consistency_penalty = 0
    peer_note = "No peer cohort available."
    if peers:
        peer_var = [p["variable_avg"] for p in peers if p.get("variable_avg")]
        peer_skill = [p["skill_avg"] for p in peers if p.get("skill_avg")]
        if peer_var and avg_kra:
            mean_var = sum(peer_var) / len(peer_var)
            mean_skill = sum(peer_skill) / len(peer_skill) if peer_skill else skill_avg
            if skill_avg >= mean_skill + 0.4 and avg_kra + 0.05 < mean_var:
                consistency_penalty = 15
                peer_note = "Profile stronger than peers but variable% lower — confidence reduced."
            elif skill_avg + 0.4 <= mean_skill and avg_kra > mean_var + 0.05:
                consistency_penalty = 10
                peer_note = "Profile weaker than peers but variable% higher — confidence reduced."
            else:
                peer_note = "Peer/variable relationship broadly consistent."
    evidence_bonus = min(20, evidence_rows * 2)
    gap_penalty = min(15, len(gaps) * 3)
    score = max(35, min(95, 62 + evidence_bonus - consistency_penalty - gap_penalty))
    band = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
    return {
        "score": score,
        "band": band,
        "explanation": f"{band} confidence ({score}%). Evidence rows={evidence_rows}, KRA avg={avg_kra:.1%}, gaps={len(gaps)}.",
        "peer_note": peer_note,
        "kra_avg": avg_kra,
    }


def _peer_cohort(data: Any, emp_code: str) -> list[dict[str, Any]]:
    employee = data.employees.get(emp_code, {})
    level = employee.get("level")
    designation = employee.get("designation")
    exp = float(employee.get("total_exp_years") or 0)
    peers: list[dict[str, Any]] = []
    for code, other in data.employees.items():
        if code == emp_code:
            continue
        if other.get("level") != level:
            continue
        if other.get("designation") != designation:
            continue
        other_exp = float(other.get("total_exp_years") or 0)
        if abs(other_exp - exp) > 2.0:
            continue
        var = data.variable.get(code, {})
        peers.append(
            {
                "code": code,
                "exp": other_exp,
                "variable_avg": float(var.get("avg") or 0),
                "skill_avg": None,
            }
        )
        if len(peers) >= 8:
            break
    return peers
