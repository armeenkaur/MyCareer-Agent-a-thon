from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from ..core.config import ROOT

_LOG_DIR = ROOT / "logs"
_LOGGER: logging.Logger | None = None


def get_logger(name: str = "skillsync") -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None and name == "skillsync":
        return _LOGGER
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        _LOG_DIR / "skillsync.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console)
    if name == "skillsync":
        _LOGGER = logger
    return logger
