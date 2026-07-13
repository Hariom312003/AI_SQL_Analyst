# API Documentation

This document describes all API coordinates exposed by the FastAPI backend (`backend/api/routes.py`).

## 1. Endpoints List

### `GET /api/v1/health`
- **Description**: Verification health check.
- **Response**: `{"status": "ok"}`

### `POST /api/v1/datasets/upload`
- **Description**: Upload a new CSV dataset. Automatically creates tables and indices.
- **Request Form**: `file` (multipart/form-data CSV)
- **Response**: `DatasetOut` model containing `id`, `name`, `table_name`, `row_count`, etc.

### `GET /api/v1/datasets`
- **Description**: List all registered datasets in the catalog.
- **Response**: `list[DatasetOut]`

### `DELETE /api/v1/datasets/{dataset_id}`
- **Description**: Delete dataset metadata, drop its table from Postgres, and rebuild index.
- **Response**: `{"status": "success", "message": "..."}`

### `GET /api/v1/datasets/{dataset_id}/preview`
- **Description**: Get first 20 rows of the dataset.
- **Response**: `{"dataset_id": "...", "rows": [...]}`

### `GET /api/v1/datasets/{dataset_id}/profile`
- **Description**: Generates stats, null percentages, correlations, and datatypes.
- **Response**: `DatasetProfileOut`

### `GET /api/v1/datasets/{dataset_id}/dashboard`
- **Description**: Assembles default charts and KPI metric values.
- **Response**: Dashboard specification dictionary.

### `PATCH /api/v1/datasets/{dataset_id}/columns/{column_name}`
- **Description**: Enriches business descriptions for RAG context mappings.
- **Request JSON**: `{"description": "..."}`
- **Response**: `DatasetOut`

### `POST /api/v1/chat/ask`
- **Description**: Submits a natural language query through the multi-agent LangGraph workflow.
- **Request JSON**: `{"question": "...", "conversation_id": "..."}`
- **Response**: `ChatResponse` containing SQL query, explanation, Plotly figures, rows, and errors.
