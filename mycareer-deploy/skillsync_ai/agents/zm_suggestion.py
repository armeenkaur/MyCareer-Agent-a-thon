"""ZM rating suggestion from supporting evidence only (no prior ZM rating)."""

from __future__ import annotations

import json
from typing import Any

from .llm import chat_json, normalize_proficiency
from .rd_suggestion import (
    _evidence_payload_row,
    _evidence_summary,
    _reject_high_when_development_only,
    _snippet_text,
)
from ..core.config import PROFICIENCY_ORDER


AGENT_NAME = "ZM Rating Suggestion Agent"

SYSTEM = """You are the ZM Rating Suggestion Agent for MyCareer Compass.

Your job: suggest ONE proficiency level for a single competency to help a Zonal Manager start their assessment.
You advise only — the ZM makes the final call. Do not invent facts. Use only the payload you receive.

════════════════════════════════════════
INPUTS
════════════════════════════════════════
• competency, rubric (Beginner→Advanced definitions for THIS competency)
• evidence[] with source, label, signal, snippet
• evidence_summary: counts of development vs performance rows (trust this)

════════════════════════════════════════
WHAT EVIDENCE MEANS
════════════════════════════════════════

signal "employee_learning_need" / "skill_taxonomy_tag":
  Learning / focus themes. NOT proof of Proficient/Advanced performance.

signal "appraisal_development_gap":
  Coaching to BUILD the skill — evidence of a gap, not of strong demonstrated performance.

signal "performance":
  Concrete demonstrated behavior / outcomes already happening for this competency.

signal "general":
  Read carefully; may be weak or ambiguous.

════════════════════════════════════════
DECISION RULES (strict order)
════════════════════════════════════════
1. Match the rubric definition — do not invent a level outside the four options.
2. If evidence_summary.performance_count == 0 AND evidence_summary.development_count >= 1:
   → You MUST suggest Beginner or Intermediate only.
   → Prefer Intermediate when coaching implies growth potential; Beginner when they must start basics.
3. If performance evidence exists, weight demonstrated behavior first; temper with development gaps.
4. Prefer conservative ratings when evidence is thin or mixed.

════════════════════════════════════════
OUTPUT
════════════════════════════════════════
JSON only: {"proficiency":"Beginner|Intermediate|Proficient|Advanced"}
No other keys."""


def suggest_zm_rating(
    competency: str,
    evidence: list[dict[str, Any]],
    rubric: dict[str, str],
    emp_code: str = "",
) -> dict[str, Any] | None:
    """Return a proficiency suggestion, or None when there is no usable evidence."""
    rows = [row for row in (evidence or []) if _snippet_text(row)]
    if not rows:
        return None
    snippets = [_evidence_payload_row(row) for row in rows]
    summary = _evidence_summary(rows)
    payload = {
        "employee_code": emp_code,
        "competency": competency,
        "evidence": snippets[:8],
        "evidence_summary": summary,
        "rubric": rubric,
        "allowed_levels": PROFICIENCY_ORDER,
    }
    answer = chat_json(
        SYSTEM,
        json.dumps(payload, ensure_ascii=True),
        agent_name=AGENT_NAME,
        emp_code=emp_code,
        max_completion_tokens=600,
    )
    if not answer:
        proficiency = "Intermediate"
        return {"proficiency": proficiency, "source": "fallback"}

    proficiency = normalize_proficiency(answer.get("proficiency")) or "Intermediate"
    proficiency = _reject_high_when_development_only(proficiency, summary)
    return {"proficiency": proficiency, "source": "agent"}
