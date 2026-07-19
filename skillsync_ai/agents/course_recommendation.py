from __future__ import annotations

import json
from typing import Any

from .llm import chat_json


AGENT_NAME = "Course Recommendation Agent"

COMPETENCY_TERMS = {
    "Communication": ["communication", "presentation", "storytelling", "writing", "influence", "negotiation"],
    "Stakeholder Management": ["stakeholder", "relationship", "influence", "cross-functional", "conflict", "collaboration"],
    "Ownership & Accountability": ["ownership", "accountability", "execution", "initiative", "responsibility", "results"],
    "Team Management": ["team management", "people management", "leadership", "coaching", "delegation", "performance management"],
    "Executive Presence": ["executive presence", "confidence", "credibility", "composure", "senior leadership", "influence"],
    "Consultative Selling": ["consultative", "solution selling", "sales", "negotiation", "customer needs", "persuasion"],
    "Data Analytics": ["data analytics", "data analysis", "insight", "dashboard", "excel", "business intelligence"],
}


def _allowed_levels(current: str) -> set[str]:
    if current == "Beginner":
        return {"beginner", "beginner_intermediate"}
    if current == "Intermediate":
        return {"intermediate", "beginner_intermediate"}
    return {"advanced"}


def _prefilter(
    courses: list[dict[str, Any]], competency: str, current: str, employee: dict[str, Any]
) -> list[dict[str, Any]]:
    """Deterministic backend filter. Agent never sees courses outside this result."""
    terms = COMPETENCY_TERMS.get(competency, [competency.lower()])
    allowed = _allowed_levels(current)
    role_terms = ["sales", "account", "business", "customer", "commercial", "hospitality", "partner"]
    scored = []
    for course in courses:
        if course.get("level") not in allowed:
            continue
        text = " ".join(str(course.get(key) or "") for key in ("title", "subjects", "description")).lower()
        matches = sum(1 for term in terms if term in text)
        if not matches:
            continue
        title_matches = sum(1 for term in terms if term in str(course.get("title", "")).lower())
        role_matches = sum(1 for term in role_terms if term in text)
        year = int(str(course.get("release_date") or "0")[:4] or 0)
        freshness = max(0, min(4, year - 2021))
        item = dict(course)
        item["prefilter_score"] = matches * 5 + title_matches * 4 + min(role_matches, 3) + freshness + 2
        scored.append(item)
    return sorted(
        scored,
        key=lambda item: (item["prefilter_score"], item.get("release_date", "")),
        reverse=True,
    )


def _rank_all_with_agent(
    groups: dict[str, dict[str, Any]], employee: dict[str, Any], emp_code: str
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    compact_groups = {}
    for competency, group in groups.items():
        candidates = []
        for row in group["candidates"]:
            item = {key: row.get(key) for key in ("id", "title", "level", "release_date", "duration", "subjects")}
            item["description"] = str(row.get("description") or "")[:180]
            candidates.append(item)
        compact_groups[competency] = {
            "current_proficiency": group["current"],
            "target_roles": group.get("target_roles", []),
            "target_proficiency": group.get("target_levels", {}),
            "candidates": candidates,
        }
    system = """You are Course Recommendation Agent for hotel-supply Business Development and KAM employees.
For every supplied competency, choose exactly two LinkedIn Learning courses from supplied candidates only. Backend has
already enforced level eligibility: Beginner receives beginner/beginner_intermediate, Intermediate receives
beginner_intermediate/intermediate, and Proficient or Advanced receives advanced. General courses are excluded. Rank by
direct competency relevance, applicability to partner and portfolio work, then freshness. Do not invent IDs. Return JSON:
{"competencies":{"<competency>":{"selections":[{"id":"...","relevance":0,"reason":"...","bd_application":"...","evidence":"..."}],"rejected_summary":"..."}}}."""
    answer = chat_json(
        system,
        json.dumps({"employee": employee, "competencies": compact_groups}, ensure_ascii=True),
        agent_name=AGENT_NAME,
        emp_code=emp_code,
        max_completion_tokens=5000,
    )
    ranked: dict[str, list[dict[str, Any]]] = {}
    audit = []
    for competency, group in groups.items():
        by_id = {str(row["id"]): row for row in group["candidates"]}
        response = ((answer or {}).get("competencies") or {}).get(competency) or {}
        selected = []
        for choice in response.get("selections") or []:
            row = by_id.get(str(choice.get("id") or ""))
            if row and all(str(existing["id"]) != str(row["id"]) for existing in selected):
                item = dict(row)
                item.update(
                    {
                        "relevance": choice.get("relevance", row["prefilter_score"]),
                        "reason": choice.get("reason", "Strong competency fit."),
                        "bd_application": choice.get("bd_application", "Apply in partner and portfolio work."),
                        "evidence": choice.get("evidence", "Course description and subject match."),
                    }
                )
                selected.append(item)
        ranked[competency] = selected or _fallback_choices(group["candidates"])
        audit.append(f"{competency}: {response.get('rejected_summary') or 'deterministic fallback'}")
    return ranked, "; ".join(audit) if answer else "deterministic fallback"


def _fallback_choices(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in candidates[:2]:
        item = dict(row)
        item.update(
            {
                "relevance": min(99, row["prefilter_score"] * 4),
                "reason": "Best deterministic match from backend-filtered active catalogue.",
                "bd_application": "Apply this learning in partner and portfolio work.",
                "evidence": "Matched course title, subject, and description.",
            }
        )
        output.append(item)
    return output
