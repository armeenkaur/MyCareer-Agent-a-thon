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


def create_app(host: str = "0.0.0.0", port: int = 5050) -> ThreadingHTTPServer:
    return create_server(host=host, port=port)


def main() -> None:
    # Render always sets PORT and must bind 0.0.0.0 (not loopback).
    port = int(os.environ.get("PORT", "5050"))
    host = os.environ.get("HOST", "0.0.0.0").strip() or "0.0.0.0"
    if os.environ.get("PORT") and host in {"127.0.0.1", "localhost"}:
        log.warning("HOST=%s ignored under PORT=%s; binding 0.0.0.0 for Render", host, port)
        host = "0.0.0.0"
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    log.info("Starting MyCareer Compass host=%s port=%s", host, port)
    log.info("OPENAI_API_KEY configured=%s model=%s", bool(key), OPENAI_MODEL)
    log.info("OCR_BACKEND=openai-vision+tesseract")
    log.info("File logs → %s", ROOT / "logs" / "skillsync.log")

    tess = TESSERACT_CMD or shutil.which("tesseract")
    if tess:
        log.info("Tesseract found: %s", tess)
    else:
        log.warning("Tesseract not found — OpenAI Vision OCR still works if OPENAI_API_KEY is set")

    server = create_app(host=host, port=port)
    bound_host, bound_port = server.server_address[:2]
    print(f"Serving MyCareer Compass at http://{bound_host}:{bound_port}", flush=True)
    print(f"Open login: /app/login  health: /api/health", flush=True)
    print(f"Logs: {ROOT / 'logs' / 'skillsync.log'}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
