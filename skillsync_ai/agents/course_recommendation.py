from __future__ import annotations

import json
from typing import Any

from .llm import chat_json


AGENT_NAME = "Course Recommendation Agent"

COMPETENCY_TERMS = {
    "Communication": ["communication", "presentation", "storytelling", "writing", "influence", "negotiation"],
    "Stakeholder Relationship": ["stakeholder", "relationship", "influence", "cross-functional", "conflict", "collaboration"],
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


# Verified public links only (YouTube oEmbed + live article HEAD). TED talks use
# official YouTube uploads — ted.com slugs and LLM-invented video IDs often 404.
OTHER_SOURCE_FALLBACKS: dict[str, list[dict[str, Any]]] = {
    "Communication": [
        {"kind": "youtube", "title": "Think Fast, Talk Smart — Communication Techniques", "url": "https://www.youtube.com/watch?v=HAnw168huqA", "duration_minutes": 21},
        {"kind": "case_study", "title": "HBR: The Science of Strong Business Writing", "url": "https://hbr.org/2021/07/the-science-of-strong-business-writing", "duration_minutes": 15},
        {"kind": "tedx", "title": "TEDx: How to speak so that people want to listen", "url": "https://www.youtube.com/watch?v=eIho2S0ZahI", "duration_minutes": 10},
    ],
    "Consultative Selling": [
        {"kind": "youtube", "title": "Science of Persuasion", "url": "https://www.youtube.com/watch?v=cFdCzN7RYbw", "duration_minutes": 12},
        {"kind": "case_study", "title": "Solution Selling — Overview", "url": "https://en.wikipedia.org/wiki/Solution_selling", "duration_minutes": 12},
        {"kind": "tedx", "title": "TEDx: The surprising habits of original thinkers", "url": "https://www.youtube.com/watch?v=fxbCHn6gE3U", "duration_minutes": 15},
    ],
    "Data Analytics": [
        {"kind": "youtube", "title": "But what is a neural network? — Deep learning intro", "url": "https://www.youtube.com/watch?v=aircAruvnKk", "duration_minutes": 19},
        {"kind": "case_study", "title": "HBR: Good Data Won't Guarantee Good Decisions", "url": "https://hbr.org/2012/04/good-data-wont-guarantee-good-decisions", "duration_minutes": 12},
        {"kind": "tedx", "title": "TEDx: The best stats you've ever seen", "url": "https://www.youtube.com/watch?v=hVimVzgtD6w", "duration_minutes": 20},
    ],
    "Executive Presence": [
        {"kind": "youtube", "title": "How to Speak — Executive Communication", "url": "https://www.youtube.com/watch?v=Unzc731iCUY", "duration_minutes": 20},
        {"kind": "case_study", "title": "HBR: The Authenticity Paradox", "url": "https://hbr.org/2015/01/the-authenticity-paradox", "duration_minutes": 15},
        {"kind": "tedx", "title": "TEDx: Your body language may shape who you are", "url": "https://www.youtube.com/watch?v=Ks-_Mh1QhMc", "duration_minutes": 21},
    ],
    "Ownership & Accountability": [
        {"kind": "youtube", "title": "Extreme Ownership — Leadership Accountability", "url": "https://www.youtube.com/watch?v=ljqra3BcqWM", "duration_minutes": 16},
        {"kind": "case_study", "title": "Accountability — Overview", "url": "https://en.wikipedia.org/wiki/Accountability", "duration_minutes": 12},
        {"kind": "tedx", "title": "TEDx: How great leaders inspire action", "url": "https://www.youtube.com/watch?v=qp0HIF3SfI4", "duration_minutes": 18},
    ],
    "Stakeholder Relationship": [
        {"kind": "youtube", "title": "10 ways to have a better conversation", "url": "https://www.youtube.com/watch?v=R1vskiVDwl4", "duration_minutes": 12},
        {"kind": "case_study", "title": "HBR: Managing Your Boss", "url": "https://hbr.org/2005/01/managing-your-boss", "duration_minutes": 15},
        {"kind": "tedx", "title": "TEDx: How to turn a group of strangers into a team", "url": "https://www.youtube.com/watch?v=3boKz0Exros", "duration_minutes": 13},
    ],
    "Team Management": [
        {"kind": "youtube", "title": "The puzzle of motivation", "url": "https://www.youtube.com/watch?v=rrkrvAUbU9Y", "duration_minutes": 18},
        {"kind": "case_study", "title": "HBR: What Great Managers Do", "url": "https://hbr.org/2005/03/what-great-managers-do", "duration_minutes": 14},
        {"kind": "tedx", "title": "TEDx: Why good leaders make you feel safe", "url": "https://www.youtube.com/watch?v=lmyZMtPVodo", "duration_minutes": 12},
    ],
}


def _normalize_other_kind(kind: str) -> str:
    value = str(kind or "").strip().lower().replace(" ", "_")
    if value in {"webinar", "internal_webinar", "ted", "ted_talk", "tedx_talk"}:
        return "tedx"
    if value in {"case", "casestudy"}:
        return "case_study"
    if value in {"yt", "video"}:
        return "youtube"
    return value if value in {"youtube", "case_study", "tedx"} else ""


def _fallback_other_sources(competency: str) -> list[dict[str, Any]]:
    rows = OTHER_SOURCE_FALLBACKS.get(competency) or OTHER_SOURCE_FALLBACKS["Communication"]
    return [
        {
            "kind": row["kind"],
            "title": row["title"],
            "url": row["url"],
            "duration_minutes": row["duration_minutes"],
            "id": f"other:{row['kind']}:{competency}",
            "competency": competency,
            "source": "other",
            "label": {"youtube": "YouTube", "case_study": "Case Study", "tedx": "TEDx Talk"}.get(row["kind"], row["kind"]),
        }
        for row in rows
    ]


def resolve_other_source(competency: str, kind: str) -> dict[str, Any] | None:
    """Return verified catalog row for competency+kind (repairs stale locked journeys)."""
    kind = _normalize_other_kind(kind)
    if not kind:
        return None
    for row in _fallback_other_sources(competency or "Communication"):
        if row["kind"] == kind:
            return row
    return None


def curate_other_sources(competencies: list[str], emp_code: str = "") -> dict[str, list[dict[str, Any]]]:
    """Return verified YouTube / case study / TEDx links per competency.

    Uses curated catalog only — LLM-invented video IDs frequently 404.
    """
    _ = emp_code  # kept for call-site compatibility / future audit
    unique = [name for name in competencies if name]
    return {competency: _fallback_other_sources(competency) for competency in unique}
