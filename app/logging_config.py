"""Centralised logging configuration.

Emits structured JSON log lines using python-json-logger so that log
aggregators (Datadog, CloudWatch, Splunk, etc.) can parse and index them
without regex extraction.

Call `configure_logging()` once at app startup. Each module then uses:

    import logging
    logger = logging.getLogger(__name__)

Sentry integration (sentry-sdk[fastapi]) is automatic — it captures
ERROR+ records and attaches breadcrumbs for INFO/WARNING with zero
additional configuration.
"""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a structured JSON formatter."""
    try:
        formatter: logging.Formatter = JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    except ImportError:
        # Fall back to plain text if pythonjsonlogger is not installed yet
        # (e.g., during initial dev before uv sync).
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Avoid duplicate handlers if called more than once
    root.handlers = [handler]

    # Quieten noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
