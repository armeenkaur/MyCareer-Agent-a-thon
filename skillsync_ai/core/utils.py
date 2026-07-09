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

    if level in {"RL1", "RL2"}:
        band = "RL1-2"
    elif level in {"RL3", "RL4"}:
        band = "RL3-4"
    else:
        band = "RL1-2"

    if role == "ZM":
        return "ZM (RL5-6)"
    return f"{role} ({band})"
