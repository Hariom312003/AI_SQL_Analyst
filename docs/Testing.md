# Testing Guide

This guide explains how to run the test suite and verify changes.

## 1. Test Setup

The project uses `pytest` and `pytest-asyncio` for asynchronous endpoint testing. 
To run tests locally without external dependencies:
1. Ensure the `.env` file uses the offline fake provider:
   ```env
   LLM_PROVIDER=fake
   ```
2. Navigate to the root directory and run:
   ```bash
   pytest
   ```

## 2. Test Suite Structure

Located in `tests/`:
- **`test_agent_workflow.py`**: Validates the LangGraph execution flow, state progression, and check constraints (e.g. giving up after max repair attempts).
- **`test_csv_ingestion.py`**: Validates schema detection, type inference, and table mappings.
- **`test_dashboard_agent.py`**: Validates summary cards and KPI chart selections.
- **`test_fake_provider.py`**: Focuses on deterministic keyword matching, token overlap sorting, date calculations, and conversational memory filters.
- **`test_gemini_provider.py`**: Validates the SDK interface for real Gemini integrations.
- **`test_llm_json_utils.py`**: Tests markdown stripping and fallback parser handlers.
- **`test_sql_validation.py`**: Tests read-only SQL parsing validation (detects write attempts and tables/columns hallucinations).
