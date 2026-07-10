from __future__ import annotations

import json
from typing import Any

from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, VALUE_PROFICIENCY
from ..core.utils import clean
from .llm import chat_json, load_few_shot, normalize_proficiency, record_decision

SYSTEM = """You are Agent C ProfileAdjuster for Business Development skill profiling.
You receive BD Skill Profile v0 (already manager-weighted 80/20 for functional skills) and Agent B context ratings.
Your job: produce BD Skill Profile v1.

HARD RULE — NEVER RAISE:
- Profile v0 already embeds manager 80% weight. You must NEVER raise any skill above its v0 level.
- You may only LOWER a skill or leave it unchanged (hold).
- Ignore any Agent B "raise" suggestion for increasing above v0.

SCENARIOS:
1) B weak / lower, v0 high → LOWER by 1 level (or 2 if evidence quotes are strong and explicit).
2) B strong / raise → HOLD at v0. Do not raise.
3) B ≈ v0 / hold → NO CHANGE.
4) Mixed signals → prefer lowering only when manager-weighted context evidence is clearly weak; else hold.
5) Missing / empty evidence → leave v0 unchanged.
6) Never invent skills. Only use the skill list provided.
7) Always emit an adjustment log entry per skill that changed: skill, before, after, why.
8) Allowed labels only: Beginner, Intermediate, Proficient, Advanced.

Return JSON only:
{
  "scores": {"<skill>": "Beginner|Intermediate|Proficient|Advanced"},
  "adjustments": [
    {"skill": "...", "before": "...", "after": "...", "why": "..."}
  ],
  "summary": "short paragraph"
}
"""


def adjust_skill_profile(
    profile_v0: dict[str, str],
    context: dict[str, Any],
    *,
    emp_code: str,
    state: Any,
) -> tuple[dict[str, str], list[str], dict[str, Any]]:
    user = (
        f"Profile v0 (ceiling — never raise above these):\n{json.dumps(profile_v0, indent=2)}\n\n"
        f"Agent B context:\n{json.dumps(context.get('skills', {}), indent=2)}\n\n"
        f"Agent B summary: {context.get('summary', '')}\n\n"
        f"Allowed labels: {json.dumps(PROFICIENCY_ORDER)}\n"
        "Return Profile v1 JSON. NEVER raise any skill above v0."
    )
    few_shot = load_few_shot("AgentC", state)
    parsed = chat_json(SYSTEM, user, agent_name="AgentC", state=state, few_shot=few_shot, emp_code=emp_code)
    if parsed and isinstance(parsed.get("scores"), dict):
        scores, adjustments, payload = _from_agent(parsed, profile_v0)
        payload["source"] = "Groq"
    else:
        scores, adjustments, payload = _fallback(profile_v0, context)
        payload["source"] = "rule fallback"
    scores, adjustments = _clamp_no_raise(profile_v0, scores, adjustments)
    payload["scores"] = scores
    payload["adjustments"] = adjustments
    record_decision(
        state,
        agent="AgentC",
        emp_code=emp_code,
        input_summary=user[:1500],
        output=payload,
    )
    return scores, adjustments, payload


def _clamp_no_raise(
    profile_v0: dict[str, str],
    scores: dict[str, str],
    adjustments: list[str],
) -> tuple[dict[str, str], list[str]]:
    clamped = dict(scores)
    notes = list(adjustments)
    for skill, v0_label in profile_v0.items():
        v0 = PROFICIENCY_VALUE.get(v0_label, 2)
        after_label = clamped.get(skill, v0_label)
        after = PROFICIENCY_VALUE.get(after_label, v0)
        if after > v0:
            clamped[skill] = v0_label
            notes.append(f"{skill}: raise blocked — kept {v0_label} (cannot exceed manager-weighted v0).")
        elif after < v0:
            clamped[skill] = VALUE_PROFICIENCY[after]
        else:
            clamped[skill] = v0_label
    # drop adjustment lines that describe a raise
    filtered = []
    for note in notes:
        if "→" in note and skill_raise_in_note(note, profile_v0):
            continue
        filtered.append(note)
    return clamped, filtered


def skill_raise_in_note(note: str, profile_v0: dict[str, str]) -> bool:
    for skill, v0_label in profile_v0.items():
        if not note.startswith(f"{skill}:"):
            continue
        if "→" not in note:
            return False
        try:
            before_s, after_part = note.split("→", 1)
            before = normalize_proficiency(before_s.split(":")[-1])
            after = normalize_proficiency(after_part.split(".")[0])
        except ValueError:
            return False
        if before and after and PROFICIENCY_VALUE.get(after, 0) > PROFICIENCY_VALUE.get(before, 0):
            return True
        if after and PROFICIENCY_VALUE.get(after, 0) > PROFICIENCY_VALUE.get(v0_label, 0):
            return True
    return False


def _from_agent(
    parsed: dict[str, Any],
    profile_v0: dict[str, str],
) -> tuple[dict[str, str], list[str], dict[str, Any]]:
    scores: dict[str, str] = {}
    for skill, current in profile_v0.items():
        candidate = normalize_proficiency((parsed.get("scores") or {}).get(skill)) or current
        scores[skill] = candidate
    adjustments: list[str] = []
    raw_adj = parsed.get("adjustments") or []
    if isinstance(raw_adj, list):
        for row in raw_adj:
            if not isinstance(row, dict):
                continue
            skill = clean(row.get("skill"))
            before = normalize_proficiency(row.get("before")) or profile_v0.get(skill, "")
            after = normalize_proficiency(row.get("after")) or scores.get(skill, "")
            why = clean(row.get("why")) or "Adjusted from context evidence."
            if skill and before and after and before != after:
                scores[skill] = after
                adjustments.append(f"{skill}: {before} → {after}. {why}")
    for skill, before in profile_v0.items():
        after = scores.get(skill, before)
        if after != before and not any(item.startswith(f"{skill}:") for item in adjustments):
            adjustments.append(f"{skill}: {before} → {after}. Agent C score change.")
    payload = {
        "scores": scores,
        "adjustments": adjustments,
        "summary": clean(parsed.get("summary")) or "Profile adjusted.",
    }
    return scores, adjustments, payload


def _fallback(
    profile_v0: dict[str, str],
    context: dict[str, Any],
) -> tuple[dict[str, str], list[str], dict[str, Any]]:
    adjusted = dict(profile_v0)
    changes: list[str] = []
    for skill, row in (context.get("skills") or {}).items():
        if skill not in adjusted:
            continue
        current = PROFICIENCY_VALUE.get(adjusted[skill], 2)
        suggested = PROFICIENCY_VALUE.get(row.get("suggested", "Intermediate"), 2)
        direction = row.get("direction", "hold")
        if direction == "lower" and suggested < current:
            nxt = max(1, current - 1)
            adjusted[skill] = VALUE_PROFICIENCY[nxt]
            changes.append(f"{skill}: {VALUE_PROFICIENCY[current]} → {adjusted[skill]}. Context suggests weakness.")
        # raise intentionally ignored — cannot exceed manager-weighted v0
    payload = {
        "scores": adjusted,
        "adjustments": changes,
        "summary": "Rule fallback adjuster applied lower-only scenarios (no raise above v0).",
    }
    return adjusted, changes, payload
