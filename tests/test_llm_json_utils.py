"""Tests for backend.llm.json_utils.extract_json -- the shared, robust JSON
recovery logic both AnthropicProvider and GeminiProvider rely on."""
from __future__ import annotations

import pytest

from backend.llm.json_utils import extract_json


def test_extracts_plain_json():
    assert extract_json('{"sql": "SELECT 1;"}') == {"sql": "SELECT 1;"}


def test_strips_markdown_json_fence():
    raw = '```json\n{"sql": "SELECT 1;"}\n```'
    assert extract_json(raw) == {"sql": "SELECT 1;"}


def test_strips_bare_markdown_fence():
    raw = '```\n{"sql": "SELECT 1;"}\n```'
    assert extract_json(raw) == {"sql": "SELECT 1;"}


def test_recovers_json_surrounded_by_prose():
    raw = 'Here is the SQL you asked for:\n{"sql": "SELECT 1;"}\nLet me know if you need changes!'
    assert extract_json(raw) == {"sql": "SELECT 1;"}


def test_handles_nested_objects():
    raw = '{"resolved_question": "x", "filters": ["a", "b"], "meta": {"k": 1}}'
    result = extract_json(raw)
    assert result["filters"] == ["a", "b"]
    assert result["meta"]["k"] == 1


def test_raises_on_genuinely_unparseable_input():
    with pytest.raises(Exception):
        extract_json("this is not json at all")
