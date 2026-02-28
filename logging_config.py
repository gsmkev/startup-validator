"""
Central logging configuration for the Paraguay Startup Validator.

Configure at app startup. Set LOG_LEVEL env var (DEBUG, INFO, WARNING, ERROR).
"""
import logging
import os

_FORMAT = (
    "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Configure root logger. Call at application startup."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format=_FORMAT,
        datefmt=_DATE_FMT,
        force=True,
    )
    # Reduce noise from httpx, httpcore, openai
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
