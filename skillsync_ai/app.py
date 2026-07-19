from __future__ import annotations

from http.server import ThreadingHTTPServer
import os
import shutil

from .core.config import (
    OPENAI_MODEL,
    ROOT,
    TESSERACT_CMD,
)
from .core.logging_setup import get_logger
from .web.server import create_server

log = get_logger("skillsync.app")


def create_app(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    return create_server(host=host, port=port)


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    log.info("Starting MyCareer Compass")
    log.info("OPENAI_API_KEY configured=%s model=%s", bool(key), OPENAI_MODEL)
    log.info("OCR_BACKEND=openai-vision+tesseract")
    log.info("File logs → %s", ROOT / "logs" / "skillsync.log")

    tess = TESSERACT_CMD or shutil.which("tesseract")
    if tess:
        log.info("Tesseract found: %s", tess)
    else:
        log.error("Tesseract not found. Run: brew install tesseract && pip install pytesseract pillow")

    server = create_app()
    print("Serving MyCareer Compass at http://127.0.0.1:5050")
    print(f"Logs: {ROOT / 'logs' / 'skillsync.log'}")
    if not (TESSERACT_CMD or shutil.which("tesseract")):
        print("ACTION REQUIRED: brew install tesseract && pip install pytesseract pillow")
    server.serve_forever()


if __name__ == "__main__":
    main()
