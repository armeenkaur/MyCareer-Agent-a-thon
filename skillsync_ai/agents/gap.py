from __future__ import annotations

from ..core.config import PROFICIENCY_VALUE


def identify_gaps(ideal: dict[str, str], actual: dict[str, str]) -> list[dict[str, str]]:
    gaps = []
    for skill, ideal_label in ideal.items():
        actual_label = actual.get(skill, "Intermediate")
        gap = PROFICIENCY_VALUE.get(ideal_label, 2) - PROFICIENCY_VALUE.get(actual_label, 2)
        if gap > 0:
            gaps.append(
                {
                    "skill": skill,
                    "current": actual_label,
                    "ideal": ideal_label,
                    "gap": str(gap),
                }
            )
    return gaps
