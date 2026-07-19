from __future__ import annotations

import json
import re
from typing import Any

from .llm import chat_json


AGENT_NAME = "Evidence Curator Agent"
CURATOR_VERSION = 3

TERMS = {
    "Communication": ["communication", "presentation", "storytelling", "writing", "verbal", "influence", "negotiation", "ppt"],
    "Stakeholder Management": ["stakeholder", "partner", "relationship", "collaboration", "cross-functional", "conflict", "expectation", "coordination"],
    "Ownership & Accountability": ["ownership", "accountability", "execution", "initiative", "responsibility", "follow-up", "delivery", "kra"],
    "Team Management": ["team management", "people management", "leadership", "coach", "mentor", "delegate", "performance management", "team member"],
    "Executive Presence": ["confidence", "composure", "executive", "senior leader", "credibility", "presence", "judgment"],
    "Consultative Selling": ["selling", "sales", "consultative", "partner needs", "commercial", "proposal", "pitch", "deal"],
    "Data Analytics": ["data", "analytics", "analysis", "insight", "dashboard", "excel", "sql", "power bi", "report"],
}


SYSTEM = """You are Evidence Curator Agent for MyCareer Compass.
Select only candidate snippets whose PRIMARY topic is the requested competency.
Never rate the employee, recommend a proficiency, alter an RD rating, or invent evidence.
Never select a snippet that is mainly about a different competency, even if it shares a weak keyword.
Keep candidate IDs unchanged. Prefer the shortest accurate excerpt.
Return JSON only:
{"selected":[{"id":"candidate id","reason":"short relevance reason","excerpt":"exact contiguous substring from the candidate snippet that is only about this competency"}]}.
Select at most four. If nothing is directly relevant, return {"selected":[]}.
Amber may be selected only when its text directly supports the requested competency."""


def curate_evidence(data: Any, emp_code: str, competency: str) -> dict[str, Any]:
    candidates = _candidate_snippets(data, emp_code)
    prefiltered = _prefilter(candidates, competency)
    selected = _select_with_agent(prefiltered, competency, emp_code)
    if selected is None:
        selected = _fallback(prefiltered, competency)
        source = "deterministic fallback"
    else:
        source = "OpenAI"
    selected = _dedupe_by_source_snippet(selected)
    return {
        "competency": competency,
        "evidence": selected,
        "empty_message": "No relevant evidence found." if not selected else "",
        "source": source,
        "curator_version": CURATOR_VERSION,
    }


def _candidate_snippets(data: Any, emp_code: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    counter = 0

    def add(source: str, label: str, text: Any) -> None:
        nonlocal counter
        for chunk in _split_chunks(text):
            counter += 1
            rows.append({"id": f"E{counter}", "source": source, "label": label, "snippet": chunk[:900]})

    for index, row in enumerate(data.tna.get(emp_code, []), 1):
        add("TNA", f"Employee input {index}", row.get("Employee Input"))
        add("TNA", f"Reporting manager input {index}", row.get("Reporting Manager Input"))
        for field in ("Standard Skill (EI)", "Skill Cluster (EI)", "Standard Skill (RM)", "Skill Cluster (RM)"):
            value = row.get(field)
            if value:
                # Skill field names are internal TNA columns — keep snippet only.
                add("TNA", "", value)
    for key, value in data.appraisal.get(emp_code, {}).items():
        if key not in {"EMP Code", "EMP Full Name"}:
            add("Appraisal", key, value)
    for key, value in data.interview.get(emp_code, {}).items():
        if key not in {"EMP Code", "EMP Name"}:
            # Round columns are source metadata — do not surface as labels.
            add("Interview", "", value)
    for index, row in enumerate(data.amber.get(emp_code, []), 1):
        for field in ("Question", "Answer", "Follow-up Comments", "Driver(Element Name)", "Mood"):
            value = row.get(field)
            if value:
                add("Amber", f"Amber {field} {index}", value)
    return rows


def _split_chunks(text: Any) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned or cleaned.lower() in {"no input", "none", "na", "n/a"}:
        return []
    parts: list[str] = []
    for pipe_chunk in re.split(r"\s*\|\s*", cleaned):
        pipe_chunk = pipe_chunk.strip()
        if not pipe_chunk:
            continue
        if len(pipe_chunk) <= 280:
            parts.append(pipe_chunk)
            continue
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", pipe_chunk)
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if not buffer:
                buffer = sentence
            elif len(buffer) + 1 + len(sentence) <= 320:
                buffer = f"{buffer} {sentence}"
            else:
                parts.append(buffer)
                buffer = sentence
        if buffer:
            parts.append(buffer)
    # Prefer granular parts; keep original only if split failed.
    return parts or [cleaned[:900]]


def _score_text(text: str, competency: str) -> int:
    terms = TERMS.get(competency, [competency.lower()])
    return sum(1 for term in terms if term in text)


def _prefilter(candidates: list[dict[str, str]], competency: str) -> list[dict[str, str]]:
    ranked: list[tuple[float, int, dict[str, str]]] = []
    for row in candidates:
        text = f"{row['label']} {row['snippet']}".lower()
        own = _score_text(text, competency)
        if own <= 0:
            continue
        best_other = 0
        for other in TERMS:
            if other == competency:
                continue
            best_other = max(best_other, _score_text(text, other))
        # Drop snippets that are clearly about another competency.
        if best_other > own:
            continue
        ranked.append((own - (0.6 * best_other), own, row))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in ranked[:30]]


def _select_with_agent(
    candidates: list[dict[str, str]], competency: str, emp_code: str
) -> list[dict[str, str]] | None:
    if not candidates:
        return []
    answer = chat_json(
        SYSTEM,
        json.dumps({"employee_code": emp_code, "competency": competency, "candidates": candidates}, ensure_ascii=True),
        agent_name=AGENT_NAME,
        emp_code=emp_code,
        max_completion_tokens=1800,
    )
    if not answer or not isinstance(answer.get("selected"), list):
        return None
    by_id = {row["id"]: row for row in candidates}
    output: list[dict[str, str]] = []
    for choice in answer["selected"][:4]:
        if not isinstance(choice, dict):
            continue
        row = by_id.get(str(choice.get("id") or ""))
        if not row or any(existing["id"] == row["id"] for existing in output):
            continue
        snippet = row["snippet"]
        excerpt = str(choice.get("excerpt") or "").strip()
        if excerpt and excerpt.lower() in snippet.lower():
            # Preserve original casing from snippet when possible.
            start = snippet.lower().find(excerpt.lower())
            snippet = snippet[start : start + len(excerpt)].strip() if start >= 0 else excerpt
        elif excerpt and len(excerpt) >= 24:
            # Agent paraphrased — keep original candidate but prefer shorter if excerpt is subset-ish.
            snippet = excerpt[:900]
        refined = {**row, "snippet": snippet, "relevance": str(choice.get("reason") or "Directly relevant evidence.")[:240]}
        if not _is_primary_for(refined["snippet"], competency):
            continue
        output.append(refined)
    return output


def _is_primary_for(snippet: str, competency: str) -> bool:
    text = snippet.lower()
    own = _score_text(text, competency)
    if own <= 0:
        return False
    for other in TERMS:
        if other != competency and _score_text(text, other) > own:
            return False
    return True


def _fallback(candidates: list[dict[str, str]], competency: str) -> list[dict[str, str]]:
    selected = []
    for row in candidates:
        if not _is_primary_for(f"{row['label']} {row['snippet']}", competency):
            continue
        selected.append({**row, "relevance": f"Keyword match for {competency}."})
        if len(selected) >= 4:
            break
    return selected


def _dedupe_by_source_snippet(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output: list[dict[str, str]] = []
    for row in rows:
        key = (row.get("source", ""), re.sub(r"\s+", " ", row.get("snippet", "")).strip().lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output
