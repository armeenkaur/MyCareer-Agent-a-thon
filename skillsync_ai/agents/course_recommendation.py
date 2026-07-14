from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from .llm import chat_json, load_few_shot, record_decision
from .logging import log_entry
from ..core.config import PROFICIENCY_VALUE


AGENT_NAME = "Agent F CourseCurator"

SKILL_TERMS = {
    "Consultative Selling": ["consultative", "solution selling", "sales", "negotiation", "customer needs", "persuasion"],
    "Data Analytics": ["data analytics", "data analysis", "insight", "dashboard", "excel", "business intelligence"],
    "Portfolio Growth": ["portfolio", "account growth", "account management", "revenue growth", "customer success", "market growth"],
    "Price Parity Management": ["pricing", "price", "revenue management", "competitive pricing", "margin", "rate strategy"],
    "Business Acumen": ["business acumen", "commercial", "business strategy", "finance", "profit", "decision making"],
    "Communication": ["communication", "presentation", "storytelling", "writing", "influence", "negotiation"],
    "Stakeholder Management": ["stakeholder", "relationship", "influence", "cross-functional", "conflict", "collaboration"],
    "Ownership & Accountability": ["ownership", "accountability", "execution", "initiative", "responsibility", "results"],
    "Team Management": ["team management", "people management", "leadership", "coaching", "delegation", "performance management"],
}

CAREER_HIERARCHY = {
    "BDM (RL1-2)": [
        {"id": "bdm", "label": "Business Development Manager", "matrix_key": "BDM (RL3-4)"},
        {"id": "kam", "label": "Key Account Manager", "matrix_key": "KAM (RL1-2)"},
        {"id": "bdfe", "label": "BDFE", "matrix_key": "Supply Category (BDFE (RL2-4)"},
    ],
    "BDM (RL3-4)": [
        {"id": "kam", "label": "Key Account Manager", "matrix_key": "KAM (RL3-4)"},
        {"id": "zm", "label": "Zonal Manager", "matrix_key": "ZM (RL5-6)"},
        {"id": "category-manager", "label": "Category Manager", "matrix_key": "Category Manager (RL3-4)"},
        {"id": "bdfe", "label": "BDFE", "matrix_key": "Supply Category (BDFE (RL2-4)"},
    ],
    "KAM (RL1-2)": [
        {"id": "kam", "label": "Key Account Manager", "matrix_key": "KAM (RL3-4)"},
        {"id": "category-manager", "label": "Category Manager", "matrix_key": "Category Manager (RL3-4)"},
        {"id": "bdfe", "label": "BDFE", "matrix_key": "Supply Category (BDFE (RL2-4)"},
    ],
    "KAM (RL3-4)": [
        {"id": "zm", "label": "Zonal Manager", "matrix_key": "ZM (RL5-6)"},
        {"id": "category-manager", "label": "Category Manager", "matrix_key": "Category Manager (RL3-4)"},
        {"id": "bdfe", "label": "BDFE", "matrix_key": "Supply Category (BDFE (RL2-4)"},
    ],
}


def build_recommendations(data: Any, state: Any, emp_code: str, profile: dict[str, Any]) -> dict[str, Any]:
    cached = state.recommendations.get(emp_code)
    if cached:
        return cached
    employee = data.employees.get(emp_code, {})
    gaps = profile.get("gaps") or []
    career_options = _career_options(data, employee, profile.get("scores", {})) if not gaps else []
    result: dict[str, Any] = {
        "skills": {},
        "external": {},
        "career_options": career_options,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ideal_reached": not bool(gaps),
        "mentor": employee.get("manager", "") if not gaps else "",
        "exploration_path": "",
    }
    target_skills = [g["skill"] for g in gaps]
    if not target_skills:
        target_skills = list(dict.fromkeys(skill for option in career_options for skill in option["skills"]))

    candidate_groups: dict[str, dict[str, Any]] = {}
    for skill in target_skills:
        current = profile.get("scores", {}).get(skill, "Advanced" if not gaps else "Beginner")
        candidates = _prefilter(data.courses, skill, current, employee)[:15]
        candidate_groups[skill] = {
            "current": current,
            "target_roles": [option["label"] for option in career_options if skill in option["skills"]],
            "target_levels": {option["label"]: option["target_levels"].get(skill) for option in career_options if skill in option["skills"]},
            "candidates": candidates,
        }

    ranked, audit = _rank_all_with_agent(candidate_groups, employee, emp_code, state)
    for skill, group in candidate_groups.items():
        chosen = ranked.get(skill) or _fallback_choices(group["candidates"])
        result["skills"][skill] = chosen[:2]
        result["external"][skill] = []
        state.agent_logs.append(
            log_entry(emp_code, AGENT_NAME, f"{skill}: selected {len(chosen[:2])} from {len(candidates)} candidates; {audit}")
        )

    state.recommendations[emp_code] = result
    record_decision(
        state,
        agent=AGENT_NAME,
        emp_code=emp_code,
        input_summary=f"role={employee.get('designation')} level={employee.get('level')} skills={target_skills}",
        output={
            "ideal_reached": result["ideal_reached"],
            "exploration_path": result["exploration_path"],
            "career_options": result["career_options"],
            "mentor": result["mentor"],
            "recommendations": {
                skill: [{k: c.get(k) for k in ("id", "title", "level", "release_date", "relevance", "reason")} for c in rows]
                for skill, rows in result["skills"].items()
            },
        },
    )
    return result


def _allowed_levels(current: str) -> set[str]:
    if current == "Beginner":
        return {"beginner", "beginner_intermediate", "general"}
    if current == "Intermediate":
        return {"intermediate", "beginner_intermediate", "general"}
    return {"advanced", "general"}


def _prefilter(courses: list[dict[str, Any]], skill: str, current: str, employee: dict[str, Any]) -> list[dict[str, Any]]:
    terms = SKILL_TERMS.get(skill, [skill.lower()])
    allowed = _allowed_levels(current)
    role_terms = ["sales", "account", "business", "customer", "commercial", "hospitality", "partner"]
    scored = []
    for course in courses:
        if course.get("level") not in allowed:
            continue
        text = " ".join(str(course.get(k) or "") for k in ("title", "subjects", "description")).lower()
        matches = sum(1 for term in terms if term in text)
        if not matches:
            continue
        title_matches = sum(1 for term in terms if term in str(course.get("title", "")).lower())
        role_matches = sum(1 for term in role_terms if term in text)
        year = int(str(course.get("release_date") or "0")[:4] or 0)
        freshness = max(0, min(4, year - 2021))
        level_bonus = 2 if course.get("level") != "general" else 0
        score = matches * 5 + title_matches * 4 + min(role_matches, 3) + freshness + level_bonus
        item = dict(course)
        item["prefilter_score"] = score
        scored.append(item)
    return sorted(scored, key=lambda item: (item["prefilter_score"], item.get("release_date", "")), reverse=True)


def _rank_all_with_agent(groups: dict[str, dict[str, Any]], employee: dict[str, Any], emp_code: str, state: Any) -> tuple[dict[str, list[dict[str, Any]]], str]:
    compact_groups = {}
    for skill, group in groups.items():
        compact = []
        for row in group["candidates"]:
            item = {k: row.get(k) for k in ("id", "title", "level", "release_date", "duration", "subjects")}
            item["description"] = str(row.get("description") or "")[:160]
            compact.append(item)
        compact_groups[skill] = {
            "current_proficiency": group["current"],
            "target_roles": group.get("target_roles", []),
            "target_proficiency": group.get("target_levels", {}),
            "candidates": compact,
        }
    system = """You are CourseCurator for a hotel-supply Business Development and Key Account Management workforce.
For every supplied competency, choose exactly two LinkedIn Learning courses. Judge applicability to partner conversations,
commercial outcomes, portfolio growth, execution, analytics, pricing, and cross-functional work. Respect these rules:
Beginner accepts beginner, beginner_intermediate, or especially relevant recent general content. Intermediate accepts
intermediate, beginner_intermediate, or especially relevant recent general content. Proficient and Advanced accept
advanced or especially relevant recent general content. General is never a level shortcut: use it only when its content
fits the learner. Prefer description relevance over keyword coincidence, then freshness. Avoid technical/domain courses
whose matching word has a different meaning. Return JSON: {skills: {skill: {selections: [{id, relevance 0-100,
reason, bd_application, freshness_assessment, evidence}], rejected_summary}}, confidence}. Do not invent IDs."""
    user = json.dumps({"employee": employee, "skill_groups": compact_groups}, ensure_ascii=True)
    answer = chat_json(
        system,
        user,
        agent_name=AGENT_NAME,
        state=state,
        emp_code=emp_code,
        max_completion_tokens=6000,
    )
    ranked = {}
    audit_parts = []
    for skill, group in groups.items():
        candidates = group["candidates"]
        by_id = {str(row["id"]): row for row in candidates}
        skill_answer = ((answer or {}).get("skills") or {}).get(skill) or {}
        picked = []
        for choice in skill_answer.get("selections") or []:
            row = by_id.get(str(choice.get("id")))
            if row and row not in picked:
                item = dict(row)
                item.update({
                    "relevance": choice.get("relevance", row["prefilter_score"]),
                    "reason": choice.get("reason", "Strong fit for identified skill gap."),
                    "bd_application": choice.get("bd_application", "Apply in partner and portfolio work."),
                    "freshness_assessment": choice.get("freshness_assessment", row.get("release_date")),
                    "evidence": choice.get("evidence", "Course description and subject match."),
                })
                picked.append(item)
        ranked[skill] = picked or _fallback_choices(candidates)
        audit_parts.append(f"{skill}: {skill_answer.get('rejected_summary') or 'fallback'}")
    return ranked, "; ".join(audit_parts) if answer else "single-call deterministic fallback"


def _fallback_choices(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    picked = []
    for row in candidates[:2]:
        item = dict(row)
        item.update({"relevance": min(99, row["prefilter_score"] * 4), "reason": "Best deterministic match from active catalogue.", "bd_application": "Apply this learning in partner and portfolio work.", "freshness_assessment": row.get("release_date"), "evidence": "Matched course title, subject, and description."})
        picked.append(item)
    return picked


def _career_options(data: Any, employee: dict[str, Any], scores: dict[str, str]) -> list[dict[str, Any]]:
    current_key = _current_role_key(employee)
    options = []
    for route in CAREER_HIERARCHY.get(current_key, []):
        target_ideal = data.ideal_for_role_key(route["matrix_key"])
        skills = [
            skill
            for skill, target in target_ideal.items()
            if PROFICIENCY_VALUE.get(target, 0) > PROFICIENCY_VALUE.get(scores.get(skill), 0)
        ]
        if not skills:
            skills = sorted(
                target_ideal,
                key=lambda skill: PROFICIENCY_VALUE.get(target_ideal.get(skill), 0),
                reverse=True,
            )[:3]
        options.append({
            "id": route["id"],
            "label": route["label"],
            "matrix_key": route["matrix_key"],
            "skills": skills,
            "target_levels": {skill: target_ideal[skill] for skill in skills},
        })
    return options


def _current_role_key(employee: dict[str, Any]) -> str:
    title = str(employee.get("designation") or "").lower()
    level = str(employee.get("level") or "").upper()
    band = "RL1-2" if level in {"RL1", "RL2"} else "RL3-4"
    if "key account" in title:
        return f"KAM ({band})"
    if "business development" in title or "area development" in title:
        return f"BDM ({band})"
    return ""


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def duration_hours(value: str) -> float:
    parts = [int(part) for part in str(value or "0").split(":") if part.isdigit()]
    if len(parts) == 3:
        return round(parts[0] + parts[1] / 60 + parts[2] / 3600, 2)
    return 0.0


def gap_levels(profile: dict[str, Any]) -> int:
    return sum(max(0, PROFICIENCY_VALUE.get(g.get("ideal"), 0) - PROFICIENCY_VALUE.get(g.get("current"), 0)) for g in profile.get("gaps") or [])
