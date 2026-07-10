from __future__ import annotations

from http.server import ThreadingHTTPServer
import os
import shutil

from .agents.llm import check_ollama_models
from .core.config import (
    GROQ_TEXT_MODEL,
    LLM_PROVIDER,
    OCR_BACKEND,
    OLLAMA_TEXT_MODEL,
    ROOT,
    TESSERACT_CMD,
)
from .core.logging_setup import get_logger
from .web.server import create_server

log = get_logger("skillsync.app")


def create_app(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    return create_server(host=host, port=port)


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    key_preview = f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "(missing)"
    log.info("Starting MyCareer Compass")
    log.info("GROQ_API_KEY=%s model=%s LLM_PROVIDER=%s", key_preview, GROQ_TEXT_MODEL, LLM_PROVIDER)
    log.info("OCR_BACKEND=%s", OCR_BACKEND)
    log.info("File logs → %s", ROOT / "logs" / "skillsync.log")

    if (OCR_BACKEND or "").lower() == "tesseract":
        tess = TESSERACT_CMD or shutil.which("tesseract")
        if tess:
            log.info("Tesseract found: %s", tess)
        else:
            log.error("Tesseract not found. Run: brew install tesseract && pip install pytesseract pillow")
    else:
        status = check_ollama_models()
        if not status.get("ok"):
            log.warning("Ollama check failed: %s", status.get("error"))
        else:
            log.info("Ollama models: %s", status.get("models") or "(none)")
            if not status.get("has_text"):
                log.warning("Missing text model for LLM fallback. Optional: ollama pull %s", OLLAMA_TEXT_MODEL)

    server = create_app()
    print("Serving MyCareer Compass at http://127.0.0.1:5050")
    print(f"Logs: {ROOT / 'logs' / 'skillsync.log'}")
    if (OCR_BACKEND or "").lower() == "tesseract" and not (TESSERACT_CMD or shutil.which("tesseract")):
        print("ACTION REQUIRED: brew install tesseract && pip install pytesseract pillow")
    server.serve_forever()


if __name__ == "__main__":
    main()
