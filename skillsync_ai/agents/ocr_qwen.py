from __future__ import annotations

import io
import shutil
from typing import Any

from ..core.config import TESSERACT_CMD
from ..core.logging_setup import get_logger

log = get_logger("skillsync.ocr")


def extract_screenshot_text(payload: bytes, filename: str = "screenshot.png") -> dict[str, str]:
    """OCR screenshot text. Default backend: Tesseract (small, corporate-network friendly)."""
    if not payload:
        return {"text": "", "source": "ocr", "error": "empty image payload"}

    log.info("OCR start file=%s bytes=%s backend=tesseract", filename, len(payload))
    return _extract_tesseract(payload, filename)


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
        # Light preprocess helps UI screenshots
        gray = ImageOps.grayscale(image)
        gray = ImageOps.autocontrast(gray)
        text = pytesseract.image_to_string(gray) or ""
        text = text.strip()
        log.info("Tesseract OCR ok file=%s chars=%s cmd=%s", filename, len(text), cmd)
        return {"text": text, "source": "tesseract", "error": ""}
    except Exception as exc:  # noqa: BLE001
        err = f"Tesseract OCR failed: {exc}"
        log.exception(err)
        return {"text": "", "source": "tesseract", "error": err}
