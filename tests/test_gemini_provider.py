"""Tests for GeminiProvider using a mocked google-genai client.

These verify that OUR code drives the SDK correctly (right method calls,
right parameter shapes, retry behavior, JSON extraction) without needing a
real GEMINI_API_KEY or network access. They cannot verify Google's actual
API behavior -- only that this code would call it correctly. That's an
honest, meaningful limit: no test suite running in this sandbox can prove
a live third-party API integration works without live credentials, and
fabricating that claim would be dishonest. What CAN be verified -- request
shape, retry logic, JSON recovery, fail-fast on a missing key -- is
verified here.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.llm.gemini_provider import GeminiProvider


def _make_provider_with_mock_client():
    with patch("backend.llm.gemini_provider.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        provider = GeminiProvider(api_key="fake-key-for-testing", model="gemini-2.5-flash")
    return provider, mock_client


def test_raises_a_clear_error_without_an_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider(api_key=None)


def test_complete_calls_generate_content_with_expected_shape():
    provider, mock_client = _make_provider_with_mock_client()
    mock_response = MagicMock()
    mock_response.text = "Hello from Gemini"
    mock_client.models.generate_content.return_value = mock_response

    result = provider._complete("system prompt", "user prompt")

    assert result == "Hello from Gemini"
    mock_client.models.generate_content.assert_called_once()
    _, kwargs = mock_client.models.generate_content.call_args
    assert kwargs["model"] == "gemini-2.5-flash"
    assert kwargs["contents"] == "user prompt"
    assert kwargs["config"].system_instruction == "system prompt"


def test_generate_sql_extracts_sql_from_a_json_response():
    provider, mock_client = _make_provider_with_mock_client()
    mock_response = MagicMock()
    mock_response.text = '{"sql": "SELECT 1;"}'
    mock_client.models.generate_content.return_value = mock_response

    assert provider.generate_sql("how many rows", []) == "SELECT 1;"


def test_generate_sql_handles_a_markdown_fenced_response():
    """Gemini sometimes wraps JSON in a fence even when asked not to --
    this is exactly what json_utils.extract_json exists to recover from."""
    provider, mock_client = _make_provider_with_mock_client()
    mock_response = MagicMock()
    mock_response.text = '```json\n{"sql": "SELECT 2;"}\n```'
    mock_client.models.generate_content.return_value = mock_response

    assert provider.generate_sql("how many rows", []) == "SELECT 2;"


def test_retries_once_on_a_transient_failure_then_succeeds():
    provider, mock_client = _make_provider_with_mock_client()
    ok_response = MagicMock()
    ok_response.text = "ok"
    mock_client.models.generate_content.side_effect = [Exception("transient"), ok_response]

    assert provider._complete("sys", "user") == "ok"
    assert mock_client.models.generate_content.call_count == 2


def test_raises_after_exhausting_all_retries():
    provider, mock_client = _make_provider_with_mock_client()
    mock_client.models.generate_content.side_effect = Exception("persistent failure")

    with pytest.raises(Exception, match="persistent failure"):
        provider._complete("sys", "user")
