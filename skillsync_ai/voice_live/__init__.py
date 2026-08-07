from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE


VOICE_KINDS = ("functional", "behavioural")

# Strong = must rate. Supporting = null OK. Union of strong across both = all 7 (no both-null).
ROLEPLAY_STRONG: dict[str, list[str]] = {
    "behavioural": [
        "Communication",
        "Ownership & Accountability",
        "Team Management",
        "Executive Presence",
        "Stakeholder Relationship",
    ],
    "functional": [
        "Consultative Selling",
        "Data Analytics",
        "Stakeholder Relationship",
        "Communication",
        "Executive Presence",
    ],
}

ROLEPLAY_SUPPORTING: dict[str, list[str]] = {
    "behavioural": [
        "Data Analytics",
        "Consultative Selling",
    ],
    "functional": [
        "Ownership & Accountability",
        "Team Management",
    ],
}

# Per-kind skill list (strong + supporting). Used by UI + scoring.
ROLEPLAY_BUCKETS: dict[str, list[str]] = {
    kind: list(ROLEPLAY_STRONG[kind]) + list(ROLEPLAY_SUPPORTING[kind])
    for kind in VOICE_KINDS
}

ALL_ROLEPLAY_SKILLS: list[str] = [
    "Communication",
    "Ownership & Accountability",
    "Team Management",
    "Executive Presence",
    "Stakeholder Relationship",
    "Data Analytics",
    "Consultative Selling",
]

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(kind: str) -> str:
    path = PROMPTS_DIR / f"{kind}.md"
    if not path.is_file():
        return (
            f"You are a MyCareer Compass roleplay assessor for the {kind} competency bucket. "
            "Conduct a professional spoken roleplay. Do not invent tools. Keep turns concise."
        )
    body = path.read_text(encoding="utf-8").strip()
    lang_sticky = (
        "LANGUAGE LOCK (highest priority every turn): "
        "Answer ONLY in the language of the learner's most recent utterance. "
        "Full English line from them → your entire reply in English (no Hindi). "
        "Full Hindi line from them → your entire reply in Hindi. "
        "Do not keep the previous language after they switch.\n\n"
    )
    shared = PROMPTS_DIR / "voice_naturalness.md"
    if shared.is_file():
        return f"{lang_sticky}{shared.read_text(encoding='utf-8').strip()}\n\n---\n\n{body}"
    return f"{lang_sticky}{body}"


def scoring_instruction(
    kind: str,
    *,
    strict: bool = False,
    user_turns: int = 0,
    elapsed_sec: float = 0.0,
) -> str:
    strong = ROLEPLAY_STRONG[kind]
    supporting = ROLEPLAY_SUPPORTING[kind]
    all_skills = ROLEPLAY_BUCKETS[kind]
    strong_list = ", ".join(f'"{s}"' for s in strong)
    supporting_list = ", ".join(f'"{s}"' for s in supporting)
    skill_schema = ", ".join(
        (
            f'"{s}":{{"level":"<Beginner|Intermediate|Proficient|Advanced>","confidence":<0.0-1.0>}}'
            if s in strong
            else f'"{s}":null|{{"level":"<level>","confidence":<0.0-1.0>}}'
        )
        for s in all_skills
    )
    scenario_hint = ""
    if kind == "behavioural":
        scenario_hint = (
            "Use evidence from the cross-functional enterprise implementation kick-off with Sarah Patel. "
            "Strong skills (must rate): Communication, Ownership & Accountability, Team Management, "
            "Executive Presence, Stakeholder Relationship. "
            "Supporting (null only if no usable signal): Data Analytics, Consultative Selling. "
        )
    elif kind == "functional":
        scenario_hint = (
            "Use evidence from the hotel-chain partnership pitch with Priya Nair. "
            "Strong skills (must rate): Consultative Selling, Data Analytics, Stakeholder Relationship, "
            "Communication, Executive Presence. "
            "Supporting (null only if no usable signal): Ownership & Accountability, Team Management. "
        )
    evidence_rules = (
        f"SESSION STATS (ground truth): learner speaking turns≈{max(0, int(user_turns))}, "
        f"elapsed≈{max(0.0, float(elapsed_sec)):.0f}s. "
        "EVIDENCE RULES — mandatory, non-negotiable: "
        "Rate ONLY from what the learner actually said in THIS call. Never invent evidence. "
        "confidence = strength of spoken evidence for that skill (0.0=none, 1.0=rich multi-turn proof). "
        "Thin talk / greetings / one short answer is NOT enough for Intermediate or above. "
        "If evidence for a skill is weak or missing: strong skills → level Beginner and confidence ≤0.30; "
        "supporting skills → null (preferred) or Beginner with confidence ≤0.25. "
        "Intermediate requires clear relevant content across multiple learner turns on that skill. "
        "Proficient/Advanced require rich, specific, multi-turn demonstration — never use them on a short/thin call. "
        "If learner turns < 6 OR the discussion barely covered the scenario: "
        "most strong skills must be Beginner with confidence ≤0.35; supporting almost all null; "
        "do NOT output Intermediate/Proficient/Advanced with confidence >0.40. "
        "Do not give five skills Intermediate/Proficient just because the call happened — "
        "under-score when unsure. "
    )
    base = (
        "SCORING MODE. The live roleplay has ended. Do not continue the roleplay. "
        "Do not apologize. Do not refuse. Do not write prose. "
        "Respond in English keys/levels only (JSON). "
        f"{scenario_hint}"
        f"{evidence_rules}"
        f"Rate ALL competencies: strong must be objects; supporting may be null. "
        f"Strong required: {strong_list}. Supporting optional: {supporting_list}. "
        "Allowed levels exactly: Beginner, Intermediate, Proficient, Advanced. "
        "confidence must be a number from 0.0 to 1.0. "
        "Output a single JSON object only, no markdown fences, no commentary: "
        '{"ratings":{' + skill_schema + "}}"
        " If you must use audio modality, speak ONLY the JSON characters with no other words."
    )
    if strict:
        return (
            base
            + " Your previous reply was invalid. Reply again with ONLY that JSON object and nothing else."
        )
    return base


def merge_roleplay_scores(session_scores: list[dict[str, Any]]) -> dict[str, str]:
    """Confidence-weighted mean across sessions. Both-null is an error."""
    merged: dict[str, str] = {}
    for skill in ALL_ROLEPLAY_SKILLS:
        weighted_sum = 0.0
        weight_sum = 0.0
        fallback_values: list[float] = []
        for scores in session_scores:
            entry = scores.get(skill)
            if not isinstance(entry, dict):
                continue
            level = str(entry.get("level") or "").strip()
            if level not in PROFICIENCY_VALUE:
                continue
            value = float(PROFICIENCY_VALUE[level])
            try:
                confidence = float(entry.get("confidence"))
            except (TypeError, ValueError):
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            fallback_values.append(value)
            if confidence <= 0:
                continue
            weighted_sum += value * confidence
            weight_sum += confidence
        if weight_sum > 0:
            mean = weighted_sum / weight_sum
        elif fallback_values:
            mean = sum(fallback_values) / len(fallback_values)
        else:
            raise ValueError(f"No score evidence for {skill} across roleplays.")
        idx = min(range(len(PROFICIENCY_ORDER)), key=lambda i: abs((i + 1) - mean))
        merged[skill] = PROFICIENCY_ORDER[idx]
    return merged
