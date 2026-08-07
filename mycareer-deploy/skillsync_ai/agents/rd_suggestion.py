from __future__ import annotations

import json
import re
from typing import Any

from .llm import chat_json, normalize_proficiency
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE


AGENT_NAME = "RD Rating Suggestion Agent"

SYSTEM = """You are the RD Rating Suggestion Agent for MyCareer Compass.

Your job: suggest ONE proficiency level for a single competency to help an RD validate a ZM assessment.
You advise only — the RD makes the final call. Do not invent facts. Use only the payload you receive.

════════════════════════════════════════
INPUTS
════════════════════════════════════════
• competency, zm_rating, zm_note, rubric (Beginner→Advanced definitions for THIS competency)
• evidence[] with source, label, signal, snippet
• evidence_summary: counts of development vs performance rows (trust this)

════════════════════════════════════════
WHAT EVIDENCE MEANS
════════════════════════════════════════

signal "employee_learning_need" / "skill_taxonomy_tag":
  TNA skill names or learning themes (e.g. "Data & Analytics", "Data-Driven Planning").
  These mean the person (or manager via TNA) flagged the skill as a learning / focus theme.
  They are NOT proof of demonstrated Proficient/Advanced performance.
  A short title with no sentence describing outcomes is NEVER performance evidence.

signal "appraisal_development_gap":
  Manager answered a "development areas / grow further" appraisal question.
  Example: "Use data to plan your discussions with hotel partners…"
  That is coaching to BUILD the practice — evidence of a gap, not of Proficient use of analytics.

signal "performance":
  Concrete demonstrated behavior / outcomes already happening for this competency.

signal "general":
  Read carefully; may be weak or ambiguous. Short noun phrases under TNA are skill tags, not praise.

════════════════════════════════════════
DECISION RULES (strict order)
════════════════════════════════════════
1. Match the rubric definition — do not invent a level outside the four options.
2. If evidence_summary.performance_count == 0 AND evidence_summary.development_count >= 1:
   → You MUST suggest Beginner or Intermediate only.
   → Do NOT return Proficient or Advanced.
   → Do NOT copy zm_rating when zm_rating is Proficient/Advanced.
   → Prefer Intermediate when coaching implies they can grow into analysis;
     prefer Beginner when coaching says to start basic use of data/reports.
3. If performance evidence exists, weight demonstrated behavior first; temper with development gaps.
4. Empty / only weak evidence → return zm_rating.
5. You MAY suggest below zm_rating when development-only evidence contradicts a high ZM rating.
6. You may suggest above zm_rating only with clear performance evidence (at most one level up).

Worked example (follow this pattern):
  zm_rating=Proficient, no ZM note.
  evidence = TNA skill tags "Data & Analytics" + "Data-Driven Planning"
             + Appraisal development area "Use data to plan discussions with hotel partners".
  performance_count=0, development_count>=1.
  Correct suggestion: Intermediate (or Beginner) — NEVER Proficient.

════════════════════════════════════════
OUTPUT
════════════════════════════════════════
JSON only: {"proficiency":"Beginner|Intermediate|Proficient|Advanced"}
No other keys."""


def suggest_rd_rating(
    competency: str,
    zm_rating: str | None,
    zm_note: str | None,
    evidence: list[dict[str, Any]],
    rubric: dict[str, str],
    emp_code: str = "",
) -> dict[str, Any]:
    zm = normalize_proficiency(zm_rating) or "Intermediate"
    rows = [row for row in (evidence or []) if _snippet_text(row)]
    snippets = [_evidence_payload_row(row) for row in rows]
    summary = _evidence_summary(rows)
    payload = {
        "employee_code": emp_code,
        "competency": competency,
        "zm_rating": zm,
        "zm_note": str(zm_note or "")[:800],
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
        proficiency = _development_only_default(zm, summary)
        return {"proficiency": proficiency, "source": "fallback"}

    proficiency = normalize_proficiency(answer.get("proficiency")) or zm
    proficiency = _reject_high_when_development_only(proficiency, summary)
    # Allow any level at/below ZM; only block jumping more than one level above ZM.
    proficiency = _clamp_upward_vs_zm(proficiency, zm)
    return {"proficiency": proficiency, "source": "agent"}


def _evidence_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    development = 0
    performance = 0
    for row in rows:
        signal = classify_evidence_signal(row)
        if signal in {"employee_learning_need", "skill_taxonomy_tag", "appraisal_development_gap"}:
            development += 1
        elif signal == "performance":
            performance += 1
    return {
        "development_count": development,
        "performance_count": performance,
        "total": len(rows),
    }


def _development_only(summary: dict[str, int]) -> bool:
    return summary.get("performance_count", 0) == 0 and summary.get("development_count", 0) >= 1


def _development_only_default(zm: str, summary: dict[str, int]) -> str:
    if _development_only(summary):
        return "Intermediate" if PROFICIENCY_VALUE.get(zm, 0) >= PROFICIENCY_VALUE["Intermediate"] else zm
    return zm


def _reject_high_when_development_only(proficiency: str, summary: dict[str, int]) -> str:
    """LLM often mirrors high ZM; block Proficient+ when no performance evidence exists."""
    if not _development_only(summary):
        return proficiency
    if PROFICIENCY_VALUE.get(proficiency, 0) > PROFICIENCY_VALUE["Intermediate"]:
        return "Intermediate"
    return proficiency


def _clamp_upward_vs_zm(proficiency: str, zm: str) -> str:
    if zm not in PROFICIENCY_VALUE or proficiency not in PROFICIENCY_VALUE:
        return proficiency
    # Never force suggestion UP when model went below ZM (old ±1 abs bug mirrored high ZM).
    if PROFICIENCY_VALUE[proficiency] <= PROFICIENCY_VALUE[zm]:
        return proficiency
    if PROFICIENCY_VALUE[proficiency] - PROFICIENCY_VALUE[zm] > 1:
        # Cap at one level above ZM.
        for level, value in PROFICIENCY_VALUE.items():
            if value == PROFICIENCY_VALUE[zm] + 1:
                return level
        return zm
    return proficiency


def _snippet_text(row: dict[str, Any]) -> str:
    return str(row.get("snippet") or row.get("excerpt") or row.get("text") or "").strip()


def _looks_like_skill_tag(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or len(cleaned) > 80:
        return False
    if re.search(r"[.!?]", cleaned):
        return False
    # Titles / taxonomy phrases, not narrative performance.
    words = cleaned.split()
    return 1 <= len(words) <= 8


def _evidence_payload_row(row: dict[str, Any]) -> dict[str, Any]:
    text = _snippet_text(row)
    return {
        "source": row.get("source") or row.get("kind") or "",
        "label": row.get("label") or "",
        "signal": classify_evidence_signal(row),
        "snippet": text[:500],
    }


def classify_evidence_signal(row: dict[str, Any]) -> str:
    """Pre-tag row for the LLM / development-only guard."""
    if _row_is_development_gap(row):
        return "appraisal_development_gap"
    if _row_is_learning_need(row):
        return "employee_learning_need"
    if _row_is_skill_taxonomy(row):
        return "skill_taxonomy_tag"
    if _row_is_performance(row):
        return "performance"
    return "general"


def _row_is_learning_need(row: dict[str, Any]) -> bool:
    label = str(row.get("label") or "").lower().strip()
    source = str(row.get("source") or "").lower().strip()
    if "reporting manager" in label:
        return False
    if "learning need" in label or "employee learning" in label:
        return True
    if source == "tna" and re.search(r"employee\s+input", label):
        return True
    if source == "tna" and not label:
        return True
    if source == "tna" and re.search(r"standard\s*skill|skill\s*cluster", label):
        return True
    return False


def _row_is_skill_taxonomy(row: dict[str, Any]) -> bool:
    """Short TNA titles (incl. RM) like 'Data-Driven Planning' — learning themes, not performance."""
    source = str(row.get("source") or "").lower().strip()
    if source != "tna":
        return False
    return _looks_like_skill_tag(_snippet_text(row))


def _row_is_development_gap(row: dict[str, Any]) -> bool:
    label = str(row.get("label") or "").lower()
    source = str(row.get("source") or "").lower()
    if source != "appraisal":
        return False
    return bool(
        re.search(
            r"development\s+area|needs?\s+to\s+develop|grow\s+further|"
            r"areas?\s+of\s+improvement|skill\s+gap|improve\s+further",
            label,
        )
    )


def _row_is_performance(row: dict[str, Any]) -> bool:
    if _row_is_development_gap(row) or _row_is_learning_need(row) or _row_is_skill_taxonomy(row):
        return False
    text = _snippet_text(row)
    if len(text) < 40:
        return False
    return bool(
        re.search(
            r"\b(used|uses|using|drove|led|analyzed|analysed|delivered|built|improved|"
            r"owns|owned|demonstrated|achieved|created|managed)\b",
            text,
            re.I,
        )
    )
