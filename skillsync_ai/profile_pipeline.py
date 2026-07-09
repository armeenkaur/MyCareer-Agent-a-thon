from __future__ import annotations

from datetime import datetime
from typing import Any

from .agents.adjustment import adjust_skill_profile
from .agents.confidence import score_confidence
from .agents.context import interpret_context
from .agents.gap import identify_gaps
from .agents.logging import log_entry
from .core.config import PROFICIENCY_VALUE
from .core.utils import rounded_profile_label
from .data_sources import WorkbookData
from .state import RuntimeState


def compute_or_get_profile(data: WorkbookData, state: RuntimeState, emp_code: str) -> dict[str, Any] | None:
    if emp_code in state.profiles:
        return state.profiles[emp_code]
    if emp_code not in state.employee_forms or emp_code not in state.manager_forms:
        return None

    final_scores, raw_scores, adjustments = _functional_and_behavioral_scores(data, state, emp_code)
    context = interpret_context(data, emp_code)
    final_scores, context_adjustments = adjust_skill_profile(final_scores, context)
    adjustments.extend(context_adjustments)
    gaps = identify_gaps(data.ideal_for_employee(emp_code), final_scores)
    confidence = score_confidence(data, emp_code, final_scores, context, gaps)

    profile = {
        "scores": final_scores,
        "raw_scores": raw_scores,
        "gaps": gaps,
        "confidence": confidence,
        "context": context,
        "adjustments": adjustments,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    state.profiles[emp_code] = profile
    state.agent_logs.extend(
        [
            log_entry(emp_code, "Profile Assembly", "Created deterministic 9-skill BD profile."),
            log_entry(emp_code, "Feedback/TNA/Amber Agent", context["summary"]),
            log_entry(emp_code, "Skill Adjustment Agent", "; ".join(adjustments) or "No contextual adjustment needed."),
            log_entry(emp_code, "Confidence Agent", confidence["explanation"]),
            log_entry(emp_code, "Gap Agent", f"Identified {len(gaps)} gaps against ideal role/level profile."),
        ]
    )
    return profile


def analytics(data: WorkbookData, state: RuntimeState) -> dict[str, Any]:
    completed = {code: compute_or_get_profile(data, state, code) for code in state.manager_forms}
    completed = {code: profile for code, profile in completed.items() if profile}
    gap_by_level: dict[str, int] = {}
    gap_by_manager: dict[str, int] = {}
    low_confidence = []
    for code, profile in completed.items():
        employee = data.employees.get(code, {})
        gap_count = len(profile["gaps"])
        gap_by_level[employee.get("level", "Unknown")] = gap_by_level.get(employee.get("level", "Unknown"), 0) + gap_count
        gap_by_manager[employee.get("manager", "Unknown")] = gap_by_manager.get(employee.get("manager", "Unknown"), 0) + gap_count
        if profile["confidence"]["band"] == "Low":
            low_confidence.append(code)
    return {
        "employee_count": len(data.employees),
        "employee_forms": len(state.employee_forms),
        "manager_forms": len(state.manager_forms),
        "completed_profiles": len(completed),
        "gap_by_level": gap_by_level,
        "gap_by_manager": gap_by_manager,
        "low_confidence": low_confidence,
        "missing_employee_form": [code for code in data.employees if code not in state.employee_forms],
        "missing_manager_form": [code for code in data.employees if code not in state.manager_forms],
    }


def _functional_and_behavioral_scores(
    data: WorkbookData,
    state: RuntimeState,
    emp_code: str,
) -> tuple[dict[str, str], dict[str, float], list[str]]:
    final_scores: dict[str, str] = {}
    raw_scores: dict[str, float] = {}
    adjustments: list[str] = []

    for skill in data.functional_skills:
        emp_value = PROFICIENCY_VALUE[state.employee_forms[emp_code].get(skill, "Intermediate")]
        manager_value = PROFICIENCY_VALUE[state.manager_forms[emp_code].get(skill, "Intermediate")]
        if abs(emp_value - manager_value) > 2:
            raw = float(manager_value)
            adjustments.append(f"{skill}: employee-manager gap exceeded 2; manager rating used.")
        else:
            raw = manager_value * 0.8 + emp_value * 0.2
        raw_scores[skill] = raw
        final_scores[skill] = rounded_profile_label(raw)

    for skill in data.behavioral_skills:
        final_scores[skill] = state.behavioral_scores.get(emp_code, {}).get(skill, "Intermediate")
        raw_scores[skill] = float(PROFICIENCY_VALUE[final_scores[skill]])

    return final_scores, raw_scores, adjustments
