# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-07-14

### Added
- **LangGraph Agent Workflow**: Implemented Intent, SQL Generation, SQL Validation, SQL Repair, and Explanation agents.
- **RAG Schema Index**: Integrated ChromaDB for semantic search over dataset column glossary context.
- **FastAPI Backend Services**: Exposed routes for database upload, dynamic profiles, Plotly charts, and chat executions.
- **Modernized UI Layout**: Sidebar navigation containing 🏠 Dashboard, 💬 AI Chat, 📂 Dataset Manager, 📊 Data Explorer, and 📈 Analytics Dashboard.
- **Dataset Manager Actions**: Added lightweight HTTP support to preview datasets (first 20 rows) and delete datasets (drop table).
- **Default Ingest**: Built first-boot auto-ingest for sample `orders_demo.csv` file.

### Fixed
- Fixed host compatibility with Python 3.14 by launching the uvicorn backend and test execution environments inside WSL Ubuntu (running Python 3.12).
- Resolved system-level cp1252 charmap encoding exception on Windows command prompts.
