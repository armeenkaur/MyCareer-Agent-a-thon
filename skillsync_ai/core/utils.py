from __future__ import annotations

from typing import Any
import html
import re

from .config import PROFICIENCY_ORDER, VALUE_PROFICIENCY


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def escape(value: Any) -> str:
    return html.escape(clean(value))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def rounded_profile_label(score: float) -> str:
    value = max(1, min(len(PROFICIENCY_ORDER), int(round(score))))
    return VALUE_PROFICIENCY[value]


def role_level_key(designation: str, level: str) -> str:
    role = "BDM"
    title = designation.lower()
    if "key account" in title:
        role = "KAM"
    elif "zonal" in title or title.startswith("zm"):
        role = "ZM"

    if role == "ZM":
        return "ZM (RL6)" if level == "RL6" else "ZM (RL4-5)"
    if role == "KAM":
        return "KAM (RL4)" if level == "RL4" else "KAM (RL2-3)"
    return "BDM (RL4)" if level == "RL4" else "BDM (RL2-3)"
