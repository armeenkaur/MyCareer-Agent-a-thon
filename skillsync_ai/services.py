"""Backward-compatible service facade. """

from .agents.behavioral import score_behavioral_evidence as behavioral_agent_score
from .agents.confidence import score_confidence as confidence_agent
from .agents.context import interpret_context as interpret_context_agent
from .agents.adjustment import adjust_skill_profile as adjust_skill_agent
from .agents.gap import identify_gaps as gap_agent
from .core.config import (
    PROFICIENCY_ORDER,
    PROFICIENCY_VALUE,
    ROOT,
    SOURCE_FILES,
    UPLOAD_DIR,
    VALUE_PROFICIENCY,
)
from .core.utils import clean, escape, role_level_key, rounded_profile_label, slug
from .data_sources import WorkbookData
from .profile_pipeline import analytics, compute_or_get_profile, inputs_ready, run_pipeline
from .state import RuntimeState
