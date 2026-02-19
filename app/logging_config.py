"""
Centralised logging configuration.

Sets up structured logging that is natively compatible with Sentry's Python SDK.
Call `configure_logging()` once at app startup. Each module should then use:

    import logging
    logger = logging.getLogger(__name__)

Sentry integration (when added later) will automatically capture ERROR+ records
and attach breadcrumbs for INFO/WARNING records with zero extra code changes.
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with a structured formatter."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Avoid duplicate handlers if called more than once
    if not root.handlers:
        root.addHandler(handler)
    else:
        root.handlers = [handler]

    # Quieten noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
