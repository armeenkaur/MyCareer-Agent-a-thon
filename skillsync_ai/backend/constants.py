from __future__ import annotations

import threading
from typing import Any


SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
VOICE_TICKET_TTL_SECONDS = 2 * 60 * 60
_VOICE_TICKETS: dict[str, dict[str, Any]] = {}
_VOICE_TICKETS_LOCK = threading.Lock()

BADGE_CATALOG = [
    {"id": "two_hour_club", "title": "Two-Hour Club", "rule": "Reach 2 LinkedIn learning hours", "icon": "bolt"},
    {"id": "ten_hour_club", "title": "Ten-Hour Club", "rule": "Reach 10 LinkedIn hours", "icon": "schedule"},
    {"id": "five_day_streak", "title": "5-Day Streak", "rule": "Learn on 5 consecutive days", "icon": "local_fire_department"},
    {"id": "full_circuit", "title": "Full Circuit", "rule": "Finish all locked LinkedIn courses", "icon": "all_inclusive"},
    {"id": "gap_closer", "title": "Gap Closer", "rule": "Close all focus-area gaps", "icon": "verified"},
]
