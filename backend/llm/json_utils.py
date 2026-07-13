"""Shared JSON-extraction helper for LLM providers.

Every provider prompts the model to respond with ONLY JSON, but real models
(especially via chat-style APIs) sometimes wrap it in markdown code fences or
add a stray sentence before/after anyway. Centralizing the recovery logic
here means both AnthropicProvider and GeminiProvider get the same robustness
and it's unit-testable in isolation, without a network call.
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)
_BRACE_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(raw: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM text response.

    Handles: plain JSON, JSON wrapped in ``` or ```json fences, and JSON
    with surrounding prose. Raises json.JSONDecodeError if nothing usable
    is found, so callers see a clear failure rather than a silent None.
    """
    text = raw.strip()

    fenced = _FENCE_RE.match(text)
    if fenced:
        text = fenced.group(1).strip()

    match = _BRACE_RE.search(text)
    candidate = match.group(0) if match else text

    return json.loads(candidate)
