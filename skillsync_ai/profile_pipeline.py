from __future__ import annotations

from datetime import datetime
from typing import Any

from .agents.adjustment import adjust_skill_profile
from .agents.coaching import classify_vs_ideal, narrate_coaching
from .agents.confidence import score_confidence
from .agents.context import interpret_context
from .agents.gap import identify_gaps
from .agents.logging import log_entry
from .core.config import PROFICIENCY_VALUE
from .core.logging_setup import get_logger
from .core.utils import rounded_profile_label
from .data_sources import WorkbookData
from .state import RuntimeState

log = get_logger("skillsync.pipeline")


def inputs_ready(data: WorkbookData, state: RuntimeState, emp_code: str) -> bool:
    if emp_code not in state.employee_forms or emp_code not in state.manager_forms:
        return False
    uploads = state.behavioral_uploads.get(emp_code, {})
    return all(skill in uploads for skill in data.behavioral_skills)


def compute_or_get_profile(data: WorkbookData, state: RuntimeState, emp_code: str) -> dict[str, Any] | None:
    if emp_code in state.profiles:
        return state.profiles[emp_code]
    if not inputs_ready(data, state, emp_code):
        return None
    return run_pipeline(data, state, emp_code)


def run_pipeline(data: WorkbookData, state: RuntimeState, emp_code: str) -> dict[str, Any] | None:
    if not inputs_ready(data, state, emp_code):
        log.info("Pipeline skip emp=%s — inputs not ready", emp_code)
        return None
    log.info("Pipeline START emp=%s", emp_code)
    state.profiles.pop(emp_code, None)

    profile_v0, raw_scores, assembly_notes = assemble_profile_v0(data, state, emp_code)
    log.info("Profile v0 ready emp=%s skills=%s", emp_code, list(profile_v0.keys()))
    all_skills = data.functional_skills + data.behavioral_skills

    context = interpret_context(data, emp_code, all_skills, state)
    state.agent_logs.append(log_entry(emp_code, "Agent B ContextRater", context.get("summary", "Context rated.")))
    log.info("Agent B done emp=%s source=%s", emp_code, context.get("source"))

    profile_v1, adjustments, adjust_payload = adjust_skill_profile(
        profile_v0, context, emp_code=emp_code, state=state
    )
    adjustments = assembly_notes + adjustments
    state.agent_logs.append(
        log_entry(
            emp_code,
            "Agent C ProfileAdjuster",
            adjust_payload.get("summary") or ("; ".join(adjustments) or "No adjustments."),
        )
    )
    log.info("Agent C done emp=%s source=%s changes=%s", emp_code, adjust_payload.get("source"), len(adjustments))

    ideal = data.ideal_for_employee(emp_code)
    gaps = identify_gaps(ideal, profile_v1)
    state.agent_logs.append(
        log_entry(emp_code, "Gap Matrix", f"Identified {len(gaps)} gaps against ideal role/level profile.")
    )
    log.info("Gaps emp=%s count=%s", emp_code, len(gaps))

    good_skills, work_on_skills = classify_vs_ideal(profile_v1, ideal)
    coaching = narrate_coaching(
        emp_code=emp_code,
        good_skills=good_skills,
        work_on_skills=work_on_skills,
        state=state,
    )
    state.agent_logs.append(
        log_entry(
            emp_code,
            "Agent E CoachingNarrator",
            f"Good={len(good_skills)}, work-on={len(work_on_skills)} ({coaching.get('source')}).",
        )
    )
    log.info("Agent E done emp=%s source=%s", emp_code, coaching.get("source"))

    confidence = score_confidence(data, emp_code, profile_v1, context, gaps, state)
    state.agent_logs.append(log_entry(emp_code, "Agent D Confidence", confidence["explanation"]))
    log.info(
        "Agent D done emp=%s source=%s band=%s score=%s",
        emp_code,
        confidence.get("source"),
        confidence.get("band"),
        confidence.get("score"),
    )

    profile = {
        "scores": profile_v1,
        "profile_v0": profile_v0,
        "raw_scores": raw_scores,
        "gaps": gaps,
        "good_skills": good_skills,
        "work_on_skills": work_on_skills,
        "coaching": coaching,
        "confidence": confidence,
        "context": context,
        "adjustments": adjustments,
        "ideal": ideal,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    state.profiles[emp_code] = profile
    state.agent_logs.append(log_entry(emp_code, "Pipeline", "BD Skill Profile v1 + coaching + confidence + gaps ready."))
    log.info(
        "Pipeline DONE emp=%s groq_calls=%s ok=%s err=%s",
        emp_code,
        len(state.api_calls),
        sum(1 for c in state.api_calls if c.get("status") == "ok"),
        sum(1 for c in state.api_calls if c.get("status") == "error"),
    )
    return profile


def assemble_profile_v0(
    data: WorkbookData,
    state: RuntimeState,
    emp_code: str,
) -> tuple[dict[str, str], dict[str, float], list[str]]:
    final_scores: dict[str, str] = {}
    raw_scores: dict[str, float] = {}
    notes: list[str] = []

    for skill in data.functional_skills:
        emp_value = PROFICIENCY_VALUE[state.employee_forms[emp_code][skill]]
        manager_value = PROFICIENCY_VALUE[state.manager_forms[emp_code][skill]]
        if abs(emp_value - manager_value) > 2:
            raw = float(manager_value)
            notes.append(f"{skill}: employee-manager gap exceeded 2; manager rating used.")
        else:
            raw = manager_value * 0.8 + emp_value * 0.2
        raw_scores[skill] = raw
        final_scores[skill] = rounded_profile_label(raw)

    for skill in data.behavioral_skills:
        label = state.behavioral_scores[emp_code][skill]
        final_scores[skill] = label
        raw_scores[skill] = float(PROFICIENCY_VALUE[label])

    state.agent_logs.append(
        log_entry(emp_code, "Profile Assembly", "Created BD Skill Profile v0 (5 functional math + 4 behavioural agent).")
    )
    return final_scores, raw_scores, notes


def analytics(data: WorkbookData, state: RuntimeState) -> dict[str, Any]:
    completed = {code: profile for code, profile in state.profiles.items()}
    gap_by_level: dict[str, int] = {}
    gap_by_role: dict[str, int] = {}
    gap_by_manager: dict[str, int] = {}
    low_confidence = []
    for code, profile in completed.items():
        employee = data.employees.get(code, {})
        gap_count = len(profile["gaps"])
        level = employee.get("level", "Unknown")
        role = employee.get("designation", "Unknown")
        manager = employee.get("manager", "Unknown")
        gap_by_level[level] = gap_by_level.get(level, 0) + gap_count
        gap_by_role[role] = gap_by_role.get(role, 0) + gap_count
        gap_by_manager[manager] = gap_by_manager.get(manager, 0) + gap_count
        if profile["confidence"]["band"] == "Low":
            low_confidence.append(code)

    missing_behavioral = []
    for code in data.employees:
        uploads = state.behavioral_uploads.get(code, {})
        missing = [skill for skill in data.behavioral_skills if skill not in uploads]
        if missing:
            missing_behavioral.append(code)

    return {
        "employee_count": len(data.employees),
        "employee_forms": len(state.employee_forms),
        "manager_forms": len(state.manager_forms),
        "completed_profiles": len(completed),
        "gap_by_level": gap_by_level,
        "gap_by_role": gap_by_role,
        "gap_by_manager": gap_by_manager,
        "low_confidence": low_confidence,
        "missing_employee_form": [code for code in data.employees if code not in state.employee_forms],
        "missing_manager_form": [code for code in data.employees if code not in state.manager_forms],
        "missing_behavioral": missing_behavioral,
        "uploaded_screenshots": sum(len(v) for v in state.behavioral_uploads.values()),
    }
