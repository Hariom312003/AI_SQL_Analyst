# Deployment Guide

This guide outlines deployment options for the FastAPI backend, Streamlit frontend, and PostgreSQL databases.

```mermaid
graph TD
    User[Client Browser] --> StreamlitCloud[Streamlit Cloud]
    StreamlitCloud --> FastAPI[FastAPI Backend (Background Subprocess)]
    FastAPI --> NeonDB[PostgreSQL Database - Neon / Supabase]
    FastAPI --> VectorStore[Local ChromaDB Persistent Index]
```

## Option A: Unified Streamlit Community Cloud Deployment (Recommended & Free)

The easiest and most cost-effective way to run the entire stack is deploying it directly to **Streamlit Community Cloud** (free tier). The Streamlit application is configured to automatically launch the FastAPI backend as a background process and apply database migrations automatically on startup.

### 1. Database Setup
1. Sign up for a free PostgreSQL database on [Neon](https://neon.tech) or [Supabase](https://supabase.com).
2. Copy the PostgreSQL connection URL (e.g. `postgresql://user:password@ep-cool-snowflake-12345.us-east-2.aws.neon.tech/neondb`).

### 2. Streamlit Cloud Setup
1. Log in to [Streamlit Community Cloud](https://streamlit.io/cloud) using your GitHub account.
2. Select **New App** and select this repository (`Hariom312003/AI_SQL_Analyst`).
3. Set the branch to `main` and entrypoint file to `app.py`.
4. Open the **Advanced settings** section.
5. In the **Secrets** text box, add your environment variables in TOML format:
   ```toml
   DATABASE_URL = "postgresql+asyncpg://user:password@ep-cool-snowflake-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
   SYNC_DATABASE_URL = "postgresql+psycopg2://user:password@ep-cool-snowflake-12345.us-east-2.aws.neon.tech/neondb?sslmode=require"
   GEMINI_API_KEY = "your_actual_gemini_api_key_here"
   LLM_PROVIDER = "gemini"
   ENVIRONMENT = "production"
   ```
6. Click **Deploy!** Streamlit will provision the container, install packages from `requirements.txt`, run migrations, start the backend API, and serve the application.

---

## Option B: Multi-Service Split Deployment (FastAPI Backend + Streamlit UI)

If you prefer to host components on distinct, dedicated cloud providers:

### 1. Database Setup

1. Provision a managed PostgreSQL instance on [Neon](https://neon.tech) or [Supabase](https://supabase.com).
2. Grab the connection string.
3. Apply alembic migrations:
   ```bash
   DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname" alembic upgrade head
   ```

### 2. Backend Deployment (Render or Railway)

1. Create a Web Service connected to the GitHub repository.
2. Select Docker configuration or Python environment:
   - Command: `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`
3. Configure Environment Variables:
   - `DATABASE_URL` (pointing to Neon/Supabase with `asyncpg` scheme)
   - `GEMINI_API_KEY` (Gemini API access credential)
   - `LLM_PROVIDER` (`gemini` or `fake` for testing)

### 3. Frontend UI Deployment (Streamlit Community Cloud)

1. Connect your repository to [Streamlit Community Cloud](https://streamlit.io/cloud).
2. Choose `app.py` as the entrypoint file.
3. Configure Settings / Secrets:
   - `API_BASE_URL` (pointing to the URL of the deployed FastAPI backend web service, e.g. `https://my-backend-app.onrender.com/api/v1`)
4. Launch! Streamlit will automatically map ports and serve the interface.
