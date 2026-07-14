from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .llm import chat_json, record_decision
from .logging import log_entry


AGENT_NAME = "Agent G WebLearningScout"


def populate_external_resources(recommendation: dict[str, Any], employee: dict[str, Any], state: Any, emp_code: str) -> None:
    if recommendation.get("external_searched"):
        return
    candidates: dict[str, list[dict[str, str]]] = {}
    for skill in recommendation.get("skills", {}):
        role = employee.get("designation") or "Business Development"
        level = employee.get("level") or ""
        rows = []
        rows.extend(_search(f'"{skill}" "{role}" {level} site:youtube.com/watch', "YouTube", 5))
        rows.extend(_search(f'"{skill}" business leadership site:ted.com/talks', "TED / TEDx", 5))
        rows.extend(_search(f'"{skill}" business development case study', "Case study", 5))
        candidates[skill] = rows

    selected, source = _rank(candidates, employee, state, emp_code)
    for skill in recommendation.get("skills", {}):
        recommendation.setdefault("external", {})[skill] = selected.get(skill) or _search_fallback(skill, employee)
    recommendation["external_searched"] = True
    recommendation["external_source"] = source
    state.agent_logs.append(log_entry(emp_code, AGENT_NAME, f"Saved external learning resources for {len(candidates)} skills ({source})."))
    record_decision(
        state,
        agent=AGENT_NAME,
        emp_code=emp_code,
        input_summary=f"role={employee.get('designation')} level={employee.get('level')} skills={list(candidates)}",
        output={"source": source, "selected": selected},
    )


def _search(query: str, resource_type: str, limit: int) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MyCareerCompass/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=7) as response:
            page = response.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return []
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.DOTALL)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', page, re.DOTALL)
    rows = []
    for index, (href, title) in enumerate(links[:limit]):
        decoded = html.unescape(href)
        parsed = urllib.parse.urlparse(decoded)
        if "duckduckgo.com" in parsed.netloc:
            decoded = urllib.parse.parse_qs(parsed.query).get("uddg", [decoded])[0]
        rows.append({
            "id": f"web-{abs(hash(decoded))}",
            "type": resource_type,
            "title": _strip_html(title),
            "description": _strip_html(snippets[index]) if index < len(snippets) else f"Live web result for {query}.",
            "url": decoded,
        })
    return rows


def _rank(candidates: dict[str, list[dict[str, str]]], employee: dict[str, Any], state: Any, emp_code: str) -> tuple[dict[str, list[dict[str, str]]], str]:
    usable = {skill: rows for skill, rows in candidates.items() if rows}
    if not usable:
        return {}, "live search unavailable; tailored search fallback"
    system = """You are WebLearningScout for hotel-supply Business Development and KAM employees.
For every skill, select at most two YouTube videos, at most two TED/TEDx talks, and at most two credible case studies.
Use only supplied URLs. Prefer current, practical, role-relevant content; reject generic clickbait and unrelated technical
meanings. Return JSON: {skills: {skill: [resource ids]}, reasoning: {skill: short reason}}."""
    payload = json.dumps({"employee": employee, "candidates": usable}, ensure_ascii=True)
    answer = chat_json(system, payload, agent_name=AGENT_NAME, state=state, emp_code=emp_code)
    selected: dict[str, list[dict[str, str]]] = {}
    for skill, rows in usable.items():
        by_id = {row["id"]: row for row in rows}
        ids = ((answer or {}).get("skills") or {}).get(skill) or []
        chosen = [by_id[item] for item in ids if item in by_id]
        if not chosen:
            counts: dict[str, int] = {}
            for row in rows:
                kind = row["type"]
                if counts.get(kind, 0) < 1:
                    chosen.append(row)
                    counts[kind] = counts.get(kind, 0) + 1
        selected[skill] = chosen[:6]
    return selected, "live search + agent ranking" if answer else "live search + deterministic ranking"


def _search_fallback(skill: str, employee: dict[str, Any]) -> list[dict[str, str]]:
    role = employee.get("designation") or "Business Development"
    query = urllib.parse.quote_plus(f"{skill} {role}")
    return [
        {"id": f"youtube-search-{_key(skill)}", "type": "YouTube", "title": f"Search current {skill} videos", "description": "A live tailored search used when individual results cannot be retrieved.", "url": f"https://www.youtube.com/results?search_query={query}"},
        {"id": f"ted-search-{_key(skill)}", "type": "TED / TEDx", "title": f"Search current talks on {skill}", "description": "A live tailored TED search used when individual results cannot be retrieved.", "url": f"https://www.ted.com/search?q={query}"},
        {"id": f"case-search-{_key(skill)}", "type": "Case study", "title": f"Search current {skill} case studies", "description": "A live tailored case-study search used when individual results cannot be retrieved.", "url": f"https://www.google.com/search?q={query}+case+study"},
    ]


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
