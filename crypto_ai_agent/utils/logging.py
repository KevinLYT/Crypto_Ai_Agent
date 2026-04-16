"""Logging helpers for consistent application startup configuration."""

from __future__ import annotations

import logging


_DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """
    Configure process-wide logging once at startup.

    This keeps the MVP lightweight while still giving the app a clearer,
    production-style logging baseline than bare `basicConfig(level=...)`.
    """
    numeric_level = getattr(logging, str(level).upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format=_DEFAULT_LOG_FORMAT)

