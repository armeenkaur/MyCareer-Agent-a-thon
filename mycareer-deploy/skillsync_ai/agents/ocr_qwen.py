from __future__ import annotations

import base64
import io
import shutil

from ..core.config import TESSERACT_CMD
from ..core.logging_setup import get_logger
from .llm import chat_image_json

log = get_logger("skillsync.ocr")
VISION_AGENT = "Role-play Screenshot OCR"
MIN_USEFUL_CHARS = 40
VISION_MAX_DIMENSION = 2200

VISION_SYSTEM = """You transcribe role-play result screenshots.
Return JSON only: {"text":"all visible text in natural reading order"}.
Copy names, labels, scores, feedback, strengths, development areas, and behavior statements exactly.
Do not summarize, infer, assess proficiency, or add text not visible in the image."""


def extract_screenshot_text(payload: bytes, filename: str = "screenshot.png") -> dict[str, str]:
    """Use OpenAI Vision first, then local multi-pass Tesseract fallback."""
    if not payload:
        return {"text": "", "source": "ocr", "error": "empty image payload"}

    log.info("OCR start file=%s bytes=%s backend=openai-vision", filename, len(payload))
    vision = _extract_openai_vision(payload, filename)
    if len(vision["text"]) >= MIN_USEFUL_CHARS:
        return vision

    local = _extract_tesseract(payload, filename)
    if len(local["text"]) > len(vision["text"]):
        return local
    if vision["text"]:
        return vision
    return {
        "text": local["text"],
        "source": local["source"],
        "error": local["error"] or vision["error"],
    }


def _extract_openai_vision(payload: bytes, filename: str) -> dict[str, str]:
    try:
        image_data_url = _image_data_url(payload)
        answer = chat_image_json(
            VISION_SYSTEM,
            "Transcribe every visible word from this screenshot.",
            image_data_url,
            agent_name=VISION_AGENT,
            max_completion_tokens=4000,
        )
        text = str((answer or {}).get("text") or "").strip()
        if not text:
            return {"text": "", "source": "openai-vision", "error": "Vision OCR returned no text."}
        log.info("OpenAI Vision OCR ok file=%s chars=%s", filename, len(text))
        return {"text": text, "source": "openai-vision", "error": ""}
    except Exception as exc:  # noqa: BLE001
        error = f"OpenAI Vision OCR unavailable: {exc}"
        log.warning(error)
        return {"text": "", "source": "openai-vision", "error": error}


def _image_data_url(payload: bytes) -> str:
    from PIL import Image

    image = Image.open(io.BytesIO(payload)).convert("RGB")
    image.thumbnail((VISION_MAX_DIMENSION, VISION_MAX_DIMENSION), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _extract_tesseract(payload: bytes, filename: str) -> dict[str, str]:
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError as exc:
        err = (
            "Missing OCR deps. Install: pip install pytesseract pillow && brew install tesseract. "
            f"Detail: {exc}"
        )
        log.error(err)
        return {"text": "", "source": "tesseract", "error": err}

    cmd = TESSERACT_CMD or shutil.which("tesseract") or ""
    if not cmd:
        err = "tesseract binary not found. Run: brew install tesseract"
        log.error(err)
        return {"text": "", "source": "tesseract", "error": err}
    pytesseract.pytesseract.tesseract_cmd = cmd

    try:
        image = Image.open(io.BytesIO(payload)).convert("RGB")
        gray = ImageOps.autocontrast(ImageOps.grayscale(image))
        threshold = gray.point(lambda value: 255 if value > 165 else 0)
        candidates = [
            pytesseract.image_to_string(gray, config="--oem 3 --psm 6").strip(),
            pytesseract.image_to_string(gray, config="--oem 3 --psm 11").strip(),
            pytesseract.image_to_string(threshold, config="--oem 3 --psm 6").strip(),
        ]
        text = max(candidates, key=len)
        log.info("Tesseract OCR ok file=%s chars=%s cmd=%s", filename, len(text), cmd)
        return {"text": text, "source": "tesseract", "error": ""}
    except Exception as exc:  # noqa: BLE001
        err = f"Tesseract OCR failed: {exc}"
        log.exception(err)
        return {"text": "", "source": "tesseract", "error": err}
