from __future__ import annotations

from .admin import AdminMixin
from .assessments import AssessmentsMixin
from .auth import AuthMixin
from .base import BackendBase
from .career import CareerMixin
from .confidence import ConfidenceMixin
from .constants import BADGE_CATALOG
from .employees import EmployeesMixin
from .errors import BackendError
from .evidence import EvidenceMixin
from .feedback import FeedbackMixin
from .leaderboard import LeaderboardMixin
from .learning import LearningMixin
from .phases import PhasesMixin
from .roleplays import RoleplaysMixin

__all__ = ["BackendError", "MyCareerBackend", "BADGE_CATALOG"]


class MyCareerBackend(
    AuthMixin,
    PhasesMixin,
    EmployeesMixin,
    FeedbackMixin,
    AssessmentsMixin,
    EvidenceMixin,
    RoleplaysMixin,
    CareerMixin,
    LearningMixin,
    ConfidenceMixin,
    LeaderboardMixin,
    AdminMixin,
    BackendBase,
):
    """Domain mixins compose the full MyCareer backend surface."""

