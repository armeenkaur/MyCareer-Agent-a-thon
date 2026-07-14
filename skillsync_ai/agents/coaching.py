from __future__ import annotations

import json
from typing import Any

from ..core.config import PROFICIENCY_VALUE
from ..core.utils import clean
from .llm import chat_json, load_few_shot, record_decision

SYSTEM = """You are Agent E CoachingNarrator for Business Development employees.
You receive two lists derived from comparing BD Skill Profile v1 to the ideal matrix:
- good_skills: at or above ideal
- work_on_skills: below ideal (gaps)
Write supportive, clear coaching copy for the employee. Do NOT mention numeric levels,
proficiency labels (Beginner/Intermediate/etc), confidence scores, manager ratings,
variable pay, peers, or internal agent names.
Return JSON only:
{
  "good_intro": "one short sentence introducing strengths",
  "work_intro": "one short sentence introducing development areas (empty string if work_on_skills is empty)",
  "on_track_message": "short encouragement if work_on_skills is empty, else empty string",
  "closing": "one short closing line"
}
"""


def classify_vs_ideal(profile_v1: dict[str, str], ideal: dict[str, str]) -> tuple[list[str], list[str]]:
    good: list[str] = []
    work_on: list[str] = []
    for skill, ideal_label in ideal.items():
        actual = profile_v1.get(skill, "Intermediate")
        if PROFICIENCY_VALUE.get(actual, 2) >= PROFICIENCY_VALUE.get(ideal_label, 2):
            good.append(skill)
        else:
            work_on.append(skill)
    return good, work_on


def narrate_coaching(
    *,
    emp_code: str,
    good_skills: list[str],
    work_on_skills: list[str],
    state: Any,
) -> dict[str, Any]:
    user = (
        f"good_skills: {json.dumps(good_skills)}\n"
        f"work_on_skills: {json.dumps(work_on_skills)}\n"
        "Write employee-facing coaching JSON."
    )
    few_shot = load_few_shot("AgentE", state)
    parsed = chat_json(SYSTEM, user, agent_name="AgentE", state=state, few_shot=few_shot, emp_code=emp_code)
    if parsed:
        result = {
            "good_intro": clean(parsed.get("good_intro"))
            or "These are the skills you are already strong in for your role:",
            "work_intro": clean(parsed.get("work_intro"))
            or ("These are the skills you need to work on:" if work_on_skills else ""),
            "on_track_message": clean(parsed.get("on_track_message"))
            or ("You're on track for your role and level." if not work_on_skills else ""),
            "closing": clean(parsed.get("closing")) or "Keep building — small focused practice compounds.",
            "source": "OpenAI",
        }
    else:
        result = {
            "good_intro": "These are the skills you are good in:",
            "work_intro": "These are the skills you need to work on:" if work_on_skills else "",
            "on_track_message": "You're on track for your role and level." if not work_on_skills else "",
            "closing": "Focus on the development areas above and re-check after your next practice cycle.",
            "source": "template fallback",
        }
    result["good_skills"] = good_skills
    result["work_on_skills"] = work_on_skills
    record_decision(
        state,
        agent="AgentE",
        emp_code=emp_code,
        input_summary=user,
        output=result,
    )
    return result
