from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any


@dataclass
class RuntimeState:
    employee_forms: dict[str, dict[str, str]] = field(default_factory=dict)
    manager_forms: dict[str, dict[str, str]] = field(default_factory=dict)
    behavioral_scores: dict[str, dict[str, str]] = field(default_factory=dict)
    behavioral_rationales: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    behavioral_uploads: dict[str, dict[str, str]] = field(default_factory=dict)
    behavioral_ocr: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)
    behavioral_submitted: set[str] = field(default_factory=set)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    agent_logs: list[dict[str, Any]] = field(default_factory=list)
    agent_decisions: list[dict[str, Any]] = field(default_factory=list)
    api_calls: list[dict[str, Any]] = field(default_factory=list)
    recommendations: dict[str, dict[str, Any]] = field(default_factory=dict)
    career_choices: dict[str, str] = field(default_factory=dict)
    learning_selections: dict[str, list[str]] = field(default_factory=dict)
    learning_completed: dict[str, set[str]] = field(default_factory=dict)
    external_clicks: dict[str, dict[str, str]] = field(default_factory=dict)
    external_selections: dict[str, list[str]] = field(default_factory=dict)
    external_completed: dict[str, set[str]] = field(default_factory=dict)
    linkedin_hours: dict[str, float] = field(default_factory=dict)
    linkedin_completions: dict[str, int] = field(default_factory=dict)
    linkedin_sync: dict[str, Any] = field(default_factory=dict)
    feedback: list[dict[str, Any]] = field(default_factory=list)
    agent_prompt_feedback: dict[str, list[str]] = field(default_factory=dict)
    pipeline_running: set[str] = field(default_factory=set)
    pipeline_status: dict[str, str] = field(default_factory=dict)
    pipeline_lock: Any = field(default_factory=threading.Lock, repr=False)
