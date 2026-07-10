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
# OCR: tesseract (default, small) | ollama | hf
OCR_BACKEND = os.environ.get("OCR_BACKEND", os.environ.get("QWEN_VL_BACKEND", "tesseract"))
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_VL_MODEL = os.environ.get("OLLAMA_VL_MODEL", "qwen2.5vl:3b")
OLLAMA_TEXT_MODEL = os.environ.get("OLLAMA_TEXT_MODEL", "llama3.2:3b")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "auto")  # auto | groq | ollama
QWEN_VL_MODEL_ID = os.environ.get("QWEN_VL_MODEL_ID", "Qwen/Qwen2.5-VL-3B-Instruct")
# Back-compat alias
QWEN_VL_BACKEND = OCR_BACKEND
AGENT_DECISION_LOG = ROOT / "agent_decisions.jsonl"
FEW_SHOT_LIMIT = 3
