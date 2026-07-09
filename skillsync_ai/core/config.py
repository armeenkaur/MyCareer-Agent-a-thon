from __future__ import annotations

from pathlib import Path
import os


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "uploads"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"

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
