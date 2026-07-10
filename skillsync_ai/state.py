from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuntimeState:
    employee_forms: dict[str, dict[str, str]] = field(default_factory=dict)
    manager_forms: dict[str, dict[str, str]] = field(default_factory=dict)
    behavioral_scores: dict[str, dict[str, str]] = field(default_factory=dict)
    behavioral_rationales: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    behavioral_uploads: dict[str, dict[str, str]] = field(default_factory=dict)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_logs: list[dict[str, Any]] = field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = field(default_factory=list)
    api_calls: list[dict[str, Any]] = field(default_factory=list)
