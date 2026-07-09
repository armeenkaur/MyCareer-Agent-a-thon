from __future__ import annotations

from typing import Any

from ..core.config import PROFICIENCY_VALUE


def score_confidence(
    data: Any,
    emp_code: str,
    scores: dict[str, str],
    context: dict[str, Any],
    gaps: list[dict[str, str]],
) -> dict[str, Any]:
    variable = data.variable.get(emp_code, {})
    avg_kra = float(variable.get("avg") or 0)
    evidence_rows = len(data.tna.get(emp_code, [])) + (1 if data.appraisal.get(emp_code) else 0) + len(data.amber.get(emp_code, []))
    skill_avg = sum(PROFICIENCY_VALUE[v] for v in scores.values()) / max(len(scores), 1)
    consistency_penalty = 0
    if avg_kra and avg_kra < 0.95 and skill_avg >= 3:
        consistency_penalty = 12
    elif avg_kra and avg_kra > 1.05 and skill_avg <= 2:
        consistency_penalty = 8
    evidence_bonus = min(20, evidence_rows * 2)
    gap_penalty = min(15, len(gaps) * 3)
    score = max(35, min(95, 62 + evidence_bonus - consistency_penalty - gap_penalty))
    band = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
    explanation = (
        f"{band} confidence ({score}%). Evidence rows={evidence_rows}, "
        f"KRA avg={avg_kra:.1%}, gap count={len(gaps)}."
    )
    return {"score": score, "band": band, "explanation": explanation, "kra_avg": avg_kra}
