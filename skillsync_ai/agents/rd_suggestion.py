from __future__ import annotations

import json
import re
from typing import Any

from .llm import chat_json, normalize_proficiency
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE


AGENT_NAME = "RD Rating Suggestion Agent"

SYSTEM = """You are RD Rating Suggestion Agent for MyCareer Compass.
Suggest one proficiency for the named competency to help an RD validate.
Use only: ZM rating, optional ZM note, supporting evidence snippets, and the four-level rubric.
Do not invent facts.

Critical interpretation rules:
- "Employee learning need" / Learning Input From Employee / employee TNA input means the employee self-identified a development need
  (they feel weak and want to learn). That is NEVER positive proof of Proficient or Advanced.
- Prefer ZM rating when other evidence agrees.
- If employee learning-need evidence is present for this competency, do not suggest above Intermediate, and do not raise above the ZM rating.
- Only move one level up from ZM when non-learning-need evidence clearly supports higher performance.

Return JSON only:
{"proficiency":"Beginner|Intermediate|Proficient|Advanced"}.
Do not include rationale or explanation fields.
If evidence is empty, return the ZM rating."""


def suggest_rd_rating(
    competency: str,
    zm_rating: str | None,
    zm_note: str | None,
    evidence: list[dict[str, Any]],
    rubric: dict[str, str],
    emp_code: str = "",
) -> dict[str, Any]:
    zm = normalize_proficiency(zm_rating) or "Intermediate"
    learning_need = _has_employee_learning_need(evidence)
    snippets = []
    for row in evidence or []:
        text = str(row.get("snippet") or row.get("excerpt") or row.get("text") or "").strip()
        if text:
            snippets.append(
                {
                    "source": row.get("source") or row.get("kind") or "",
                    "label": row.get("label") or "",
                    "signal": "employee_learning_need" if _row_is_learning_need(row) else "general",
                    "snippet": text[:500],
                }
            )
    answer = chat_json(
        SYSTEM,
        json.dumps(
            {
                "employee_code": emp_code,
                "competency": competency,
                "zm_rating": zm,
                "zm_note": str(zm_note or "")[:800],
                "employee_learning_need_present": learning_need,
                "evidence": snippets[:6],
                "rubric": rubric,
                "allowed_levels": PROFICIENCY_ORDER,
            },
            ensure_ascii=True,
        ),
        agent_name=AGENT_NAME,
        emp_code=emp_code,
        max_completion_tokens=600,
    )
    if not answer:
        proficiency = _apply_learning_need_cap(zm, zm, learning_need)
        return {"proficiency": proficiency, "source": "fallback"}
    proficiency = normalize_proficiency(answer.get("proficiency")) or zm
    # Keep suggestion within one level of ZM unless ZM missing.
    if zm in PROFICIENCY_VALUE and proficiency in PROFICIENCY_VALUE:
        if abs(PROFICIENCY_VALUE[proficiency] - PROFICIENCY_VALUE[zm]) > 1:
            proficiency = zm
    proficiency = _apply_learning_need_cap(proficiency, zm, learning_need)
    return {"proficiency": proficiency, "source": "agent"}


def _row_is_learning_need(row: dict[str, Any]) -> bool:
    label = str(row.get("label") or "").lower()
    source = str(row.get("source") or "").lower()
    if "learning need" in label or "employee learning" in label:
        return True
    if source == "tna" and re.search(r"employee\s+input", label):
        return True
    return False


def _has_employee_learning_need(evidence: list[dict[str, Any]] | None) -> bool:
    return any(_row_is_learning_need(row) for row in (evidence or []))


def _apply_learning_need_cap(proficiency: str, zm: str, learning_need: bool) -> str:
    """Employee flagged a learning need → never suggest above Intermediate, and never above ZM."""
    if not learning_need:
        return proficiency
    capped = proficiency
    if PROFICIENCY_VALUE.get(capped, 0) > PROFICIENCY_VALUE["Intermediate"]:
        capped = "Intermediate"
    if zm in PROFICIENCY_VALUE and PROFICIENCY_VALUE.get(capped, 0) > PROFICIENCY_VALUE[zm]:
        capped = zm
    return capped


def _fallback(zm: str, snippets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"proficiency": zm, "source": "fallback"}
