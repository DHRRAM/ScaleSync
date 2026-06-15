"""Logger helper used by CLI and Maya tools."""

from __future__ import annotations

import logging
import os

DEFAULT_LOG_LEVEL = "INFO"


def configure_logging() -> None:
    """Configure root logging once."""
    level_name = os.getenv("SCALESYNC_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )