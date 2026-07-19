from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    """Ephemeral adapter for LinkedIn sync; business state lives in SQLite."""

    linkedin_hours: dict[str, float] = field(default_factory=dict)
    linkedin_completions: dict[str, int] = field(default_factory=dict)
