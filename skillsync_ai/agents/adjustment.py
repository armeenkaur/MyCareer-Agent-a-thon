from __future__ import annotations

from typing import Any

from ..core.config import PROFICIENCY_VALUE, VALUE_PROFICIENCY


def adjust_skill_profile(scores: dict[str, str], context: dict[str, Any]) -> tuple[dict[str, str], list[str]]:
    adjusted = dict(scores)
    changes: list[str] = []
    for skill, signal in context["signals"].items():
        current = PROFICIENCY_VALUE.get(adjusted.get(skill, "Intermediate"), 2)
        if signal <= -2 and current > 1:
            adjusted[skill] = VALUE_PROFICIENCY[current - 1]
            changes.append(f"{skill}: lowered to {adjusted[skill]} due to weak contextual evidence.")
    return adjusted, changes
