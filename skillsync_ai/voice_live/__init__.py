from __future__ import annotations

from pathlib import Path


VOICE_KINDS = ("functional", "behavioural")

ROLEPLAY_BUCKETS: dict[str, list[str]] = {
    "functional": [
        "Consultative Selling",
        "Data Analytics",
        "Stakeholder Relationship",
    ],
    "behavioural": [
        "Communication",
        "Ownership & Accountability",
        "Team Management",
        "Executive Presence",
    ],
}

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(kind: str) -> str:
    path = PROMPTS_DIR / f"{kind}.md"
    if not path.is_file():
        return (
            f"You are a MyCareer Compass roleplay assessor for the {kind} competency bucket. "
            "Conduct a professional spoken roleplay. Do not invent tools. Keep turns concise."
        )
    return path.read_text(encoding="utf-8").strip()


def scoring_instruction(kind: str, *, strict: bool = False) -> str:
    skills = ROLEPLAY_BUCKETS[kind]
    skill_list = ", ".join(f'"{s}"' for s in skills)
    scenario_hint = ""
    if kind == "behavioural":
        scenario_hint = (
            "Use evidence from the cross-functional project kick-off with Sarah Patel. "
            "Map stakeholder alignment / influence-without-authority / pushback handling to "
            '"Executive Presence". '
            "Communication = clarity/structure/summaries; "
            "Ownership & Accountability = role/decision rights/risks/follow-through; "
            "Team Management = direction/delegation/collaboration/commitment. "
        )
    base = (
        "SCORING MODE. The live roleplay has ended. Do not continue the roleplay. "
        "Do not apologize. Do not refuse. Do not write prose. "
        "Respond in English keys/levels only (JSON). "
        f"{scenario_hint}"
        f"Rate EACH competency exactly once: {skill_list}. "
        "Allowed levels exactly: Beginner, Intermediate, Proficient, Advanced. "
        "If evidence is thin or the employee said little, still rate — use Beginner for weak/missing signal. "
        "Output a single JSON object only, no markdown fences, no commentary: "
        '{"ratings":{' + ", ".join(f'"{s}":"<level>"' for s in skills) + "}}"
    )
    if strict:
        return (
            base
            + " Your previous reply was invalid. Reply again with ONLY that JSON object and nothing else."
        )
    return base
