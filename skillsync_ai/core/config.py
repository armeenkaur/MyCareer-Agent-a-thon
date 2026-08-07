from __future__ import annotations

from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "uploads"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
STITCH_DIR = ROOT / "stitch_mycareer_compass"


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        # Do not override shell / process env (tests, docker, CI).
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _resolve_database_path() -> Path:
    """Prefer explicit path, then Render persistent disk (/var/data), else repo data/."""
    override = (os.environ.get("MYCAREER_DATABASE_PATH") or "").strip()
    if override:
        return Path(override)
    render_disk = Path(os.environ.get("RENDER_DISK_PATH") or "/var/data")
    try:
        if render_disk.is_dir() and os.access(render_disk, os.W_OK):
            return render_disk / "mycareer.db"
    except OSError:
        pass
    return ROOT / "data" / "mycareer.db"


DATABASE_PATH = _resolve_database_path()
ON_RENDER = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))


def database_is_ephemeral() -> bool:
    """True when SQLite lives on Render's wipeable checkout filesystem."""
    if not ON_RENDER:
        return False
    try:
        resolved = DATABASE_PATH.resolve()
    except OSError:
        return True
    if str(resolved).startswith("/var/data"):
        return False
    try:
        resolved.relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


# Hackathon default: all workflow windows open so ZM/RD/employee/feedback work without admin gates.
# Set OPEN_ALL_PHASES_BY_DEFAULT=0 to keep admin-controlled phase gates.
OPEN_ALL_PHASES_BY_DEFAULT = _env_bool("OPEN_ALL_PHASES_BY_DEFAULT", True)

PROFICIENCY_ORDER = ["Beginner", "Intermediate", "Proficient", "Advanced"]
PROFICIENCY_VALUE = {name: idx + 1 for idx, name in enumerate(PROFICIENCY_ORDER)}

SOURCE_FILES = {
    "competency": ROOT / "data" / "MyCareer_Process Flow.xlsx",
    "darwin": ROOT / "data" / "Employee Darwin.xlsx",
    "tna": ROOT / "data" / "Cleaned Up TNA data.xlsx",
    "appraisal": ROOT / "data" / "Appraisal Input.xlsx",
    "amber": ROOT / "data" / "Agent-a-thon (Amber).xlsx",
    "interview": ROOT / "data" / "Interview Input.xlsx",
    "courses": ROOT / "data" / "LinkedIn_Learning_Courses_EN.xlsx",
}

OPENAI_API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
LINKEDIN_LEARNING_CLIENT_ID = os.environ.get("LINKEDIN_LEARNING_CLIENT_ID", "").strip()
LINKEDIN_LEARNING_CLIENT_SECRET = os.environ.get("LINKEDIN_LEARNING_CLIENT_SECRET", "").strip()
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_REPORT_URL = "https://api.linkedin.com/v2/learningActivityReports"

# Azure Voice Live (in-house roleplay) — key from .env only, never log the value.
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "").strip()
AZURE_VOICE_LIVE_URL = os.environ.get(
    "AZURE_VOICE_LIVE_URL",
    "wss://centralindia.api.cognitive.microsoft.com/voice-live/realtime"
    "?api-version=2025-05-01-preview&model=gpt-realtime-2025-08-28",
).strip()
# Hotels-VoiceBot female HD (Diya). Wait for session.updated before greeting so alloy
# (male default) is not used. Override with OpenAI shimmer if preferred.
AZURE_VOICE_LIVE_VOICE = os.environ.get(
    "AZURE_VOICE_LIVE_VOICE",
    "en-IN-Diya:DragonHDLatestNeural",
).strip()
AZURE_VOICE_LIVE_VOICE_TYPE = os.environ.get(
    "AZURE_VOICE_LIVE_VOICE_TYPE",
    "azure-standard",
).strip() or "azure-standard"
AZURE_VOICE_LIVE_VOICE_FALLBACK = os.environ.get(
    "AZURE_VOICE_LIVE_VOICE_FALLBACK",
    "en-US-AvaNeural",
).strip()
AZURE_VOICE_LIVE_VOICE_FALLBACK_TYPE = os.environ.get(
    "AZURE_VOICE_LIVE_VOICE_FALLBACK_TYPE",
    "azure-standard",
).strip() or "azure-standard"
# Browser PCM: playback Hz (Voice Live output ~24000); mic capture → Azure input rate.
VOICE_PLAYBACK_SAMPLE_RATE = int(os.environ.get("VOICE_PLAYBACK_SAMPLE_RATE", "24000"))
VOICE_INPUT_SAMPLE_RATE = int(os.environ.get("VOICE_INPUT_SAMPLE_RATE", "16000"))
# How long after learner stops speaking before bot replies (ms). Default 1500 = 1.5s.
VOICE_SILENCE_DURATION_MS = int(os.environ.get("VOICE_SILENCE_DURATION_MS", "1500"))
