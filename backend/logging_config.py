"""Centralized Loguru configuration.

Every module in this project does `from loguru import logger` directly --
loguru's logger is a pre-configured global singleton, so there's no need for
the stdlib's per-module `getLogger(__name__)` boilerplate. This module just
sets the sink/format once, at startup.
"""
from __future__ import annotations

import sys

from loguru import logger


def configure_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> | {message}"
        ),
        backtrace=False,
        diagnose=False,
    )
