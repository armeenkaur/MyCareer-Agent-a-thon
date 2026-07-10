from __future__ import annotations

from http.server import ThreadingHTTPServer
import os

from .core.config import GROQ_TEXT_MODEL, OLLAMA_HOST, OLLAMA_VL_MODEL, QWEN_VL_BACKEND, ROOT
from .core.logging_setup import get_logger
from .web.server import create_server

log = get_logger("skillsync.app")


def create_app(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    return create_server(host=host, port=port)


def main() -> None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    key_preview = f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "(missing)"
    log.info("Starting MyCareer Compass")
    log.info("GROQ_API_KEY=%s model=%s", key_preview, GROQ_TEXT_MODEL)
    log.info("OCR backend=%s ollama_host=%s ollama_model=%s", QWEN_VL_BACKEND, OLLAMA_HOST, OLLAMA_VL_MODEL)
    log.info("File logs → %s", ROOT / "logs" / "skillsync.log")
    server = create_app()
    print("Serving MyCareer Compass at http://127.0.0.1:5050")
    print(f"Logs: {ROOT / 'logs' / 'skillsync.log'}")
    server.serve_forever()


if __name__ == "__main__":
    main()
