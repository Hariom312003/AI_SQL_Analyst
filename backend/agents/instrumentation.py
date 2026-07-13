"""Shared logging/timing decorator so every agent node logs consistently
(satisfies the 'each agent must have logging' requirement without repeating
boilerplate in every file)."""
from __future__ import annotations

import functools
import time

from loguru import logger


def instrumented(agent_name: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state, *args, **kwargs):
            start = time.perf_counter()
            logger.info("[{}] started", agent_name)
            try:
                result = fn(state, *args, **kwargs)
                logger.info("[{}] finished in {:.1f}ms", agent_name, (time.perf_counter() - start) * 1000)
                return result
            except Exception:
                logger.exception("[{}] failed", agent_name)
                raise

        return wrapper

    return decorator
