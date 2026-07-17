from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    """Ephemeral adapter for LLM/OCR and LinkedIn clients; business state lives in SQLite."""

    agent_logs: list[dict[str, Any]] = field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = field(default_factory=list)
    api_calls: list[dict[str, Any]] = field(default_factory=list)
    agent_prompt_feedback: dict[str, list[str]] = field(default_factory=dict)
    linkedin_hours: dict[str, float] = field(default_factory=dict)
    linkedin_completions: dict[str, int] = field(default_factory=dict)
    linkedin_sync: dict[str, Any] = field(default_factory=dict)
