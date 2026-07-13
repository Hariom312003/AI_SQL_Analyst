# Deployment Guide

This guide outlines deployment options for the FastAPI backend, Streamlit frontend, and PostgreSQL databases.

```mermaid
graph TD
    User[Client Browser] --> StreamlitCloud[Streamlit Cloud / Render UI]
    StreamlitCloud --> FastAPI[FastAPI Backend - Render / Railway]
    FastAPI --> NeonDB[PostgreSQL Database - Neon / Supabase]
    FastAPI --> VectorStore[Local ChromaDB Persistent Index]
```

## 1. Database Setup (Neon or Supabase)

1. Provision a managed PostgreSQL instance on [Neon](https://neon.tech) or [Supabase](https://supabase.com).
2. Grab the connection string.
3. Apply alembic migrations:
   ```bash
   DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname" alembic upgrade head
   ```

## 2. Backend Deployment (Render or Railway)

1. Create a Web Service connected to the GitHub repository.
2. Select Docker configuration or Python environment:
   - Command: `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`
3. Configure Environment Variables:
   - `DATABASE_URL` (pointing to Neon/Supabase with `asyncpg` scheme)
   - `GEMINI_API_KEY` (Gemini API access credential)
   - `LLM_PROVIDER` (`gemini` or `fake` for testing)

## 3. Frontend UI Deployment (Streamlit Community Cloud)

1. Connect your repository to [Streamlit Community Cloud](https://streamlit.io/cloud).
2. Choose `app.py` as the entrypoint file.
3. Configure Settings / Secrets:
   - `API_BASE_URL` (pointing to the URL of the deployed FastAPI backend web service, e.g. `https://my-backend-app.onrender.com/api/v1`)
4. Launch! Streamlit will automatically map ports and serve the interface.
