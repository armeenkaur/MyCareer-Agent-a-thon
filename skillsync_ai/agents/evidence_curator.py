from __future__ import annotations

import json
import re
from typing import Any

from .llm import chat_json


AGENT_NAME = "Evidence Curator Agent"

TERMS = {
    "Communication": ["communication", "presentation", "storytelling", "writing", "verbal", "influence", "negotiation"],
    "Stakeholder Management": ["stakeholder", "partner", "relationship", "collaboration", "cross-functional", "conflict", "expectation"],
    "Ownership & Accountability": ["ownership", "accountability", "execution", "initiative", "responsibility", "follow-up", "delivery"],
    "Team Management": ["team", "people", "leadership", "coach", "mentor", "delegate", "performance management"],
    "Executive Presence": ["confidence", "composure", "executive", "senior leader", "credibility", "presence", "judgment"],
    "Consultative Selling": ["selling", "sales", "consultative", "partner needs", "commercial", "proposal", "pitch", "negotiation", "deal"],
    "Data Analytics": ["data", "analytics", "analysis", "insight", "dashboard", "excel", "sql", "power bi", "report"],
}


SYSTEM = """You are Evidence Curator Agent for MyCareer Compass.
Select only source snippets that are directly relevant to the requested competency. Never rate the employee, recommend a
proficiency, alter an RD rating, or invent evidence. Keep source labels and candidate IDs unchanged. Return JSON only:
{"selected": [{"id": "candidate id", "reason": "short relevance reason"}]}. Select at most six. If nothing is directly
relevant, return {"selected": []}. Amber may be selected only when its text directly supports the requested competency."""


def curate_evidence(data: Any, emp_code: str, competency: str, state: Any) -> dict[str, Any]:
    candidates = _candidate_snippets(data, emp_code)
    prefiltered = _prefilter(candidates, competency)
    selected = _select_with_agent(prefiltered, competency, emp_code, state)
    if selected is None:
        selected = _fallback(prefiltered, competency)
        source = "deterministic fallback"
    else:
        source = "OpenAI"
    return {
        "competency": competency,
        "evidence": selected,
        "empty_message": "No relevant evidence found." if not selected else "",
        "source": source,
    }


def _candidate_snippets(data: Any, emp_code: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counter = 0

    def add(source: str, label: str, text: Any) -> None:
        nonlocal counter
        cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
        if not cleaned or cleaned.lower() in {"no input", "none", "na", "n/a"}:
            return
        counter += 1
        rows.append({"id": f"E{counter}", "source": source, "label": label, "snippet": cleaned[:900]})

    for index, row in enumerate(data.tna.get(emp_code, []), 1):
        add("TNA", f"Employee input {index}", row.get("Employee Input"))
        add("TNA", f"Reporting manager input {index}", row.get("Reporting Manager Input"))
        add("TNA", f"Mapped competency {index}", " | ".join(filter(None, [row.get("Standard Skill (EI)"), row.get("Skill Cluster (EI)"), row.get("Standard Skill (RM)"), row.get("Skill Cluster (RM)")])))
    for key, value in data.appraisal.get(emp_code, {}).items():
        if key not in {"EMP Code", "EMP Full Name"}:
            add("Appraisal", key, value)
    for key, value in data.interview.get(emp_code, {}).items():
        if key not in {"EMP Code", "EMP Name"}:
            add("Interview", key, value)
    for index, row in enumerate(data.amber.get(emp_code, []), 1):
        text = " | ".join(filter(None, [row.get("Question"), row.get("Answer"), row.get("Follow-up Comments"), row.get("Driver(Element Name)"), row.get("Mood")]))
        add("Amber", f"Amber response {index}", text)
    return rows


def _prefilter(candidates: list[dict[str, str]], competency: str) -> list[dict[str, str]]:
    terms = TERMS.get(competency, [competency.lower()])
    ranked = []
    for row in candidates:
        text = f"{row['label']} {row['snippet']}".lower()
        score = sum(1 for term in terms if term in text)
        if score:
            ranked.append((score, row))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in ranked[:30]]


def _select_with_agent(
    candidates: list[dict[str, str]], competency: str, emp_code: str, state: Any
) -> list[dict[str, str]] | None:
    if not candidates:
        return []
    answer = chat_json(
        SYSTEM,
        json.dumps({"employee_code": emp_code, "competency": competency, "candidates": candidates}, ensure_ascii=True),
        agent_name=AGENT_NAME,
        state=state,
        emp_code=emp_code,
        max_completion_tokens=1800,
    )
    if not answer or not isinstance(answer.get("selected"), list):
        return None
    by_id = {row["id"]: row for row in candidates}
    output = []
    for choice in answer["selected"][:6]:
        if not isinstance(choice, dict):
            continue
        row = by_id.get(str(choice.get("id") or ""))
        if row and row not in output:
            output.append({**row, "relevance": str(choice.get("reason") or "Directly relevant evidence.")[:240]})
    return output


def _fallback(candidates: list[dict[str, str]], competency: str) -> list[dict[str, str]]:
    return [{**row, "relevance": f"Keyword match for {competency}."} for row in candidates[:6]]
