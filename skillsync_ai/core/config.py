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
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

PROFICIENCY_ORDER = ["Beginner", "Intermediate", "Proficient", "Advanced"]
PROFICIENCY_VALUE = {name: idx + 1 for idx, name in enumerate(PROFICIENCY_ORDER)}
VALUE_PROFICIENCY = {value: name for name, value in PROFICIENCY_VALUE.items()}

SOURCE_FILES = {
    "competency": ROOT / "MyCareer_Process Flow.xlsx",
    "darwin": ROOT / "Employee Darwin.xlsx",
    "tna": ROOT / "Cleaned Up TNA data.xlsx",
    "appraisal": ROOT / "Appraisal Input.xlsx",
    "amber": ROOT / "Agent-a-thon (Amber).xlsx",
    "variable": ROOT / "Variable Pay scores.xlsx",
}

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile")
AGENT_DECISION_LOG = ROOT / "agent_decisions.jsonl"
FEW_SHOT_LIMIT = 3
