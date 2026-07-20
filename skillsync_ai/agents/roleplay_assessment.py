from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from .llm import chat_json, normalize_proficiency
from .ocr_qwen import extract_screenshot_text


AGENT_NAME = "Role-play Assessment Agent"
MIN_READABLE_CHARS = 40
_PROFICIENCY_WORDS = {"beginner", "intermediate", "proficient", "advanced"}

SYSTEM = """You are Role-play Assessment Agent for MyCareer Compass.
Rate only the named competency using only supplied screenshot transcript and the exact four-level rubric. Do not use general
performance assumptions or evidence from another competency. Return JSON only:
{"proficiency":"Beginner|Intermediate|Proficient|Advanced","rationale":"grounded reason","evidence":["short transcript evidence"]}.
If image text is unreadable, return
{"rejected":true,"reason_code":"unreadable","reason":"..."}.
If text is readable but evaluates a different competency, return
{"rejected":true,"reason_code":"competency_mismatch","reason":"..."}.
If text concerns the named competency but lacks enough behavior evidence to apply the rubric, return
{"rejected":true,"reason_code":"insufficient_evidence","reason":"..."}.
If the transcript is keyword stuffing, a typed proficiency label repeated, or otherwise not genuine role-play feedback
(no scenario outcome, rubric comments, scores, or observable behavior), return
{"rejected":true,"reason_code":"invalid_evidence","reason":"..."}.
Never assign a level solely because the word Beginner/Intermediate/Proficient/Advanced appears in the transcript."""

REJECTION_MESSAGES = {
    "unreadable": "Screenshot text could not be read. Upload a clearer screenshot.",
    "competency_mismatch": "Screenshot is readable, but its feedback does not match the selected competency.",
    "insufficient_evidence": "Screenshot is readable, but it lacks enough behavior evidence for the selected competency.",
    "invalid_evidence": "Screenshot does not look like genuine role-play feedback. Upload the actual assessment result screen.",
}


def transcript_is_keyword_stuffed(transcript: str) -> bool:
    """Detect fake screenshots that mostly repeat proficiency labels or one word."""
    tokens = re.findall(r"[A-Za-z]+", transcript.lower())
    if len(tokens) < 8:
        return False
    label_hits = sum(1 for token in tokens if token in _PROFICIENCY_WORDS)
    if label_hits >= 5 and label_hits / len(tokens) >= 0.35:
        return True
    counts = Counter(tokens)
    top_count = counts.most_common(1)[0][1]
    if top_count >= 8 and top_count / len(tokens) >= 0.45:
        return True
    if len(tokens) >= 20 and len(counts) / len(tokens) < 0.15:
        return True
    return False


def assess_roleplay(
    competency: str,
    filename: str,
    payload: bytes,
    definitions: dict[str, str],
    emp_code: str,
) -> dict[str, Any]:
    ocr = extract_screenshot_text(payload, filename)
    transcript = str(ocr.get("text") or "").strip()
    if len(transcript) < MIN_READABLE_CHARS:
        return {
            "status": "reupload_required",
            "proficiency": None,
            "rationale": "Screenshot text is unreadable or incomplete.",
            "ocr_text": transcript,
            "ocr_source": str(ocr.get("source") or ""),
            "error": str(ocr.get("error") or "Unable to read enough screenshot content."),
        }
    if transcript_is_keyword_stuffed(transcript):
        return {
            "status": "reupload_required",
            "proficiency": None,
            "rationale": "Transcript looks like keyword stuffing, not role-play feedback.",
            "ocr_text": transcript,
            "ocr_source": str(ocr.get("source") or ""),
            "error": REJECTION_MESSAGES["invalid_evidence"],
        }
    answer = chat_json(
        SYSTEM,
        json.dumps(
            {
                "employee_code": emp_code,
                "competency": competency,
                "rubric": definitions,
                "screenshot_transcript": transcript[:8000],
            },
            ensure_ascii=True,
        ),
        agent_name=AGENT_NAME,
        emp_code=emp_code,
        max_completion_tokens=1200,
    )
    if not answer:
        return {
            "status": "service_unavailable",
            "proficiency": None,
            "rationale": "Assessment service unavailable. Upload is saved; retry assessment later.",
            "ocr_text": transcript,
            "ocr_source": str(ocr.get("source") or ""),
            "error": "Role-play assessment service unavailable.",
        }
    if answer.get("rejected") or answer.get("unreadable"):
        reason_code = str(answer.get("reason_code") or "insufficient_evidence")
        return {
            "status": "reupload_required",
            "proficiency": None,
            "rationale": str(answer.get("reason") or "Screenshot does not provide sufficient evidence."),
            "ocr_text": transcript,
            "ocr_source": str(ocr.get("source") or ""),
            "error": REJECTION_MESSAGES.get(reason_code, REJECTION_MESSAGES["insufficient_evidence"]),
        }
    proficiency = normalize_proficiency(answer.get("proficiency"))
    if not proficiency:
        return {
            "status": "service_unavailable",
            "proficiency": None,
            "rationale": "Assessment returned no valid proficiency.",
            "ocr_text": transcript,
            "ocr_source": str(ocr.get("source") or ""),
            "error": "Invalid assessment response; retry later.",
        }
    return {
        "status": "completed",
        "proficiency": proficiency,
        "rationale": str(answer.get("rationale") or "Rating grounded in role-play feedback.")[:1000],
        "evidence": [str(value)[:400] for value in (answer.get("evidence") or [])[:4]],
        "ocr_text": transcript,
        "ocr_source": str(ocr.get("source") or ""),
        "error": "",
    }
