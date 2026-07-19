from __future__ import annotations

from typing import Any
import html
import re


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def escape(value: Any) -> str:
    return html.escape(clean(value))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def is_kam_title(*parts: str) -> bool:
    """True when Darwin designation/role is on the Key Account Manager track."""
    title = " ".join(str(part or "") for part in parts).lower()
    return (
        "key account" in title
        or "account & client" in title
        or "account and client" in title
        or "account and key" in title
        or "account & key" in title
    )


def display_designation(designation: str = "", role_name: str = "", *, short: bool = True) -> str:
    """Portal label: KAM for Key Account Manager track; otherwise Darwin designation."""
    raw = clean(designation) or clean(role_name)
    if is_kam_title(designation, role_name):
        return "KAM" if short else "Key Account Manager"
    return raw


def role_level_key(designation: str, level: str, role_name: str = "") -> str:
    role = "BDM"
    title = f"{designation} {role_name}".lower()
    if is_kam_title(designation, role_name):
        role = "KAM"
    elif "zonal" in title or clean(designation).lower().startswith("zm"):
        role = "ZM"

    if role == "ZM":
        return "ZM (RL6)" if level == "RL6" else "ZM (RL4-5)"
    if role == "KAM":
        return "KAM (RL4)" if level == "RL4" else "KAM (RL2-3)"
    return "BDM (RL4)" if level == "RL4" else "BDM (RL2-3)"
