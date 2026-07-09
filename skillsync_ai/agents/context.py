from __future__ import annotations

from typing import Any


KEYWORD_MAP = {
    "Communication": ["communication", "presentation", "storytelling", "listening"],
    "Stakeholder Management": ["stakeholder", "collaboration", "partner", "relationship", "internal teams"],
    "Ownership & Accountability": ["ownership", "accountability", "execution", "follow-up", "reliable"],
    "Team Management": ["leadership", "team management", "mentoring", "coaching", "people"],
    "Consultative Selling": ["selling", "negotiation", "deal", "commercial", "pitch"],
    "Data Analytics": ["data", "analytics", "analysis", "power bi", "sql", "reporting"],
    "Portfolio Growth": ["growth", "portfolio", "gmv", "room night", "revenue"],
    "Price Parity Management": ["parity", "pricing", "rates", "ota", "inventory"],
    "Business Acumen": ["business acumen", "strategy", "margin", "conversion", "customer"],
}

WEAK_WORDS = ["develop", "needs", "improve", "could not", "challenge", "opportunity", "lacks", "work on"]
STRONG_WORDS = ["strong", "excellent", "achieved", "delivered", "ownership", "growth", "exceeded"]


def interpret_context(data: Any, emp_code: str) -> dict[str, Any]:
    tna_rows = data.tna.get(emp_code, [])
    appraisal = data.appraisal.get(emp_code, {})
    amber_rows = data.amber.get(emp_code, [])
    text = " ".join(
        [
            " ".join(" ".join(row.values()) for row in tna_rows[:6]),
            " ".join(appraisal.values()),
            " ".join(" ".join(row.values()) for row in amber_rows[:8]),
        ]
    ).lower()
    signals: dict[str, int] = {}
    for skill, keywords in KEYWORD_MAP.items():
        keyword_hits = sum(text.count(keyword) for keyword in keywords)
        weak_hits = sum(text.count(word) for word in WEAK_WORDS)
        strong_hits = sum(text.count(word) for word in STRONG_WORDS)
        signals[skill] = keyword_hits + min(strong_hits, 4) - min(weak_hits, 4)
    summary = f"Read {len(tna_rows)} TNA rows, {'1' if appraisal else '0'} appraisal row, {len(amber_rows)} Amber rows."
    return {"signals": signals, "summary": summary}
