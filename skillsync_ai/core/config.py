from __future__ import annotations

from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "uploads"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


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
        if key:
            os.environ[key] = value


_load_dotenv()

PROFICIENCY_ORDER = ["Beginner", "Intermediate", "Proficient", "Advanced"]
PROFICIENCY_VALUE = {name: idx + 1 for idx, name in enumerate(PROFICIENCY_ORDER)}
VALUE_PROFICIENCY = {value: name for name, value in PROFICIENCY_VALUE.items()}

SOURCE_FILES = {
    "competency": ROOT / "data" / "MyCareer_Process Flow.xlsx",
    "darwin": ROOT / "data" / "Employee Darwin.xlsx",
    "tna": ROOT / "data" / "Cleaned Up TNA data.xlsx",
    "appraisal": ROOT / "data" / "Appraisal Input.xlsx",
    "amber": ROOT / "data" / "Agent-a-thon (Amber).xlsx",
    "variable": ROOT / "data" / "Variable Pay scores.xlsx",
    "interview": ROOT / "data" / "Interview Input.xlsx",
    "courses": ROOT / "data" / "LinkedIn_Learning_Courses_EN.xlsx",
}

OPENAI_API_URL = os.environ.get("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
# OCR stays local and deterministic; OpenAI receives extracted text only.
OCR_BACKEND = "tesseract"
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
AGENT_DECISION_LOG = ROOT / "agent_decisions.jsonl"
FEW_SHOT_LIMIT = 3
LINKEDIN_LEARNING_CLIENT_ID = os.environ.get("LINKEDIN_LEARNING_CLIENT_ID", "").strip()
LINKEDIN_LEARNING_CLIENT_SECRET = os.environ.get("LINKEDIN_LEARNING_CLIENT_SECRET", "").strip()
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_REPORT_URL = "https://api.linkedin.com/v2/learningActivityReports"
