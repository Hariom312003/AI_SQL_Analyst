# 📊 AI SQL Analyst: Enterprise Natural Language Analytics Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.12-blue.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.139.0-green.svg)](requirements.txt)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.9-orange.svg)](requirements.txt)
[![Gemini](https://img.shields.io/badge/Gemini-2.5--flash-blueviot.svg)](requirements.txt)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](requirements.txt)
[![Build Status](https://github.com/Hariom312003/AI_SQL_Analyst/actions/workflows/CI.yml/badge.svg)](https://github.com/Hariom312003/AI_SQL_Analyst/actions)

AI SQL Analyst is a state-of-the-art, multi-agent conversational data analytics platform. It translates plain English questions into verified, read-only SQL queries, executes them against PostgreSQL, explains the findings in executive summaries, and dynamically builds Plotly visualizations.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User[Client Browser - Streamlit] -->|HTTP REST| API[FastAPI Backend Server]
    API -->|Workflow Trigger| LangGraph[LangGraph State Workflow]
    LangGraph -->|Semantic Context| ChromaDB[ChromaDB Vector Store]
    LangGraph -->|SQL Prompts| Gemini[Gemini LLM Provider]
    LangGraph -->|AST Validation| sqlglot[sqlglot Parser]
    LangGraph -->|Execute SELECT| PostgreSQL[(PostgreSQL DB Instance)]
    API -->|Profile Specs| Profiler[Data Profiling Engine]
    API -->|KPIs Spec| Dashboard[Dashboard Spec Builder]
```

For complete technical specifications, see:
* [Architecture Documentation](docs/Architecture.md)
* [RAG Semantic Context](docs/RAG.md)
* [Multi-Agent Execution Pipeline](docs/LangGraph.md)
* [Database Schema Details](docs/Database.md)
* [SQL AST Validation and Security Model](docs/Security.md)

---

## ⚡ Main Features

- **📂 Seamless Ingest & Auto-load**: Automatically detects if the catalog is empty and loads a default sales sample dataset (`orders_demo.csv`). Large CSVs are parsed, schemas are inferred, and Postgres tables are populated automatically with live progress logs.
- **💬 Conversational Memory**: Uses an Intent Agent to resolve implicit follow-ups (e.g. asking "Show total sales by product", then sending "Only Electronics" correctly appends the filter to the previous chart context).
- **🛠️ Self-Correcting SQL Repair**: If validation or execution fails, the workflow loops back to feed compile errors to the Repair Agent, attempting self-correction up to a maximum limit.
- **🔒 Static AST Security Validation**: Enforces read-only statements via `sqlglot` before database execution, blocking write commands (`INSERT`, `UPDATE`, `DROP`) and hallucinated references.
- **📈 Data Profiling & Dashboards**: Generates null percentage bar charts, numeric distribution box plots, outlier metrics, and feature correlation heatmaps automatically.

---

## ⚙️ Configuration & Setup

### 1. Requirements
- **WSL (Ubuntu)** with Python 3.12 (highly recommended for stable compilation and library imports)
- **PostgreSQL 16**

### 2. Environment Setup
Copy `.env.example` to `.env` and configure:
```env
DATABASE_URL=postgresql+asyncpg://sql_analyst:sql_analyst@localhost:5432/sql_analyst
LLM_PROVIDER=fake # Set to 'gemini' for real Gemini API queries
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Local Installation & Launch

Run database schema migrations inside WSL:
```bash
.venv_wsl/bin/alembic upgrade head
```

Boot the FastAPI backend server inside WSL:
```bash
.venv_wsl/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

Start the Streamlit frontend client inside WSL (this binds to your localhost for easy access from Windows browsers):
```bash
.venv_wsl/bin/streamlit run app.py
```

Open your browser and navigate to:
👉 **[http://localhost:8501](http://localhost:8501)**

---

## 📊 Example Queries to Try

1. **Revenue aggregate:** `What is the total revenue?`
2. **Top-N ranking:** `Show top 5 customers by revenue`
3. **Time filters:** `Which product had the highest total sales in June?`
4. **Follow-up Memory**:
   - Step 1: `Show total sales by product`
   - Step 2: `Only Electronics`

---

## 🚀 Deployment Guide

### Database (Neon or Supabase)
1. Provision a Postgres instance and copy the URI.
2. Apply migrations: `DATABASE_URL="postgresql+asyncpg://..." alembic upgrade head`

### Backend (Render or Railway)
- Create a Web Service pointed to this repository.
- Bind the start command to: `uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`
- Define `DATABASE_URL` and `GEMINI_API_KEY` in environment config variables.

### Frontend (Streamlit Community Cloud)
- Deploy your repo and set `app.py` as the entrypoint.
- Define `API_BASE_URL` in secrets pointing to the backend's Render service URL.
- See the full [Deployment Guide](docs/Deployment.md) for step-by-step instructions.

---

## 🤝 Contribution

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

### Author
Developed with ❤️ by **[Hariom Gupta](https://github.com/Hariom312003)**
