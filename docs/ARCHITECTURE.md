# Architecture

This document goes deeper than the README: agent-by-agent design, RAG
rationale, the SQL safety model, and — deliberately included rather than
polished away — the real bugs found while building and verifying this
project. A recruiter or engineer evaluating this repo should be able to
tell the difference between "this was built" and "this was actually run
and debugged," and the clearest way to show that is to document what
broke and how it was found.

## 1. The multi-agent pipeline

Implemented as a single LangGraph `StateGraph` (`backend/agents/workflow.py`)
over a shared `AgentState` TypedDict (`backend/agents/state.py`). Each node
is a thin wrapper (`run(state, ...)`) around either an LLM-provider method
or a pure utility function, decorated with `@instrumented("<agent_name>")`
for consistent start/success/failure logging (`backend/agents/instrumentation.py`).

| Agent | File | Responsibility | LLM call? |
|---|---|---|---|
| Intent | `intent_agent.py` | Resolve conversational follow-ups into a self-contained question; classify intent type | Yes |
| Schema Retrieval | inline node in `workflow.py` | Pull top-k relevant schema docs from ChromaDB | No |
| SQL | `sql_agent.py` | Generate a single SELECT statement | Yes |
| Validator | `validator_agent.py` | Read-only enforcement + hallucination detection via sqlglot | No |
| Repair | `repair_agent.py` | Regenerate SQL given a validation/execution error | Yes |
| Execution | `execution_agent.py` | Run the SQL against Postgres, row-capped and timeout-bounded | No |
| Explanation | `explanation_agent.py` | Turn raw rows into an executive-style answer | Yes |
| Visualization | `visualization_agent.py` | Choose a chart type from the result shape | No |
| Dashboard | `dashboard_agent.py` | Assemble KPI cards + a default chart for a whole dataset | No |
| Memory | `memory_agent.py` | Format conversation history for the Intent Agent | No |

Control flow: `intent → schema_retrieval → sql → validation →
[execution | repair | explanation]`, with `repair → validation` forming a
loop bounded by `settings.sql_repair_max_attempts` (default 2) on *both*
the validation-failure and execution-failure paths, so a persistently
broken query still terminates gracefully (falls through to explanation
with the last error) rather than looping forever. This is directly
tested in `tests/test_agent_workflow.py::test_workflow_gives_up_gracefully_after_max_repair_attempts`.

Schema retrieval has no dedicated agent file — it's a one-line call into
`rag/retriever.py` wired directly as a node in `workflow.py`. Splitting it
into its own file would have added indirection without adding testable
surface area (there's no branching logic to unit test beyond what
`retriever.py`'s own tests would cover).

## 2. LLM provider abstraction

`backend/llm/base.py` defines `LLMProvider` with four methods
(`resolve_intent`, `generate_sql`, `repair_sql`, `explain_results`) —
task-specific rather than one generic `complete(prompt)` call, so prompts
live next to the provider that fulfills them (`backend/prompts/`) and
every agent can be unit-tested against a provider without any network
access.

Three implementations:

- **`GeminiProvider`** (`gemini_provider.py`) — the recommended default.
  Uses `google-genai` (the current unified SDK; the older
  `google-generativeai` package is deprecated). Fails fast with a clear
  `ValueError` if no API key is configured, rather than a cryptic SDK
  error three calls deep. Default model `gemini-2.5-flash` (stable,
  low-churn); `gemini-3.5-flash` exists as a newer option with a more
  generous free-tier quota as of mid-2026 — both are one env var away,
  nothing else changes.
- **`AnthropicProvider`** (`anthropic_provider.py`) — alternative, paid.
- **`FakeLLMProvider`** (`fake_provider.py`) — offline, deterministic,
  rule-based. This is the one worth explaining, since "no mocked logic"
  was an explicit requirement and this needs to be understood as
  something different from a mock.

Both real providers share `json_utils.extract_json()` (markdown-fence
stripping + brace extraction) rather than duplicating regex logic — this
was refactored out specifically when `GeminiProvider` was added, since at
that point the JSON-recovery logic was about to be duplicated a second time.

### Why `FakeLLMProvider` is not a "fake implementation"

A mock returns canned data and doesn't do the actual work. `FakeLLMProvider`
does the actual work — it's a real, deterministic NL→SQL algorithm:
keyword-based aggregation/ranking detection, TF-IDF-style token-overlap
scoring to pick metric/dimension columns *by SQL type* (numeric vs. text,
not just keyword guessing), month-name → `EXTRACT(MONTH FROM ...)`
filters, `top N` → `LIMIT N`, and — the trickiest case — distinguishing
"a column *name* was mentioned" (dimension) from "a column *value* was
mentioned" (filter), which is what makes a follow-up like "Only
Electronics" correctly become `WHERE category = 'Electronics'` while
preserving `GROUP BY product` from the prior turn, instead of
misinterpreting "Electronics" as a request to group by category.
`tests/test_fake_provider.py::test_categorical_value_mention_becomes_a_filter_not_a_dimension`
pins this down, and it was verified against the *live* system, not just
the isolated unit test (see §5).

It exists so the whole pipeline — every agent, the full graph, the API,
the UI — runs and is testable with zero API keys and zero network calls.
It is explicitly **not** claimed to have real language understanding;
`README.md` and the module docstring both say so directly. Swapping in a
real provider is one `.env` line.

## 3. RAG design

`backend/rag/`:

- **`schema_loader.py`** — reads `Dataset`/`DatasetColumn` rows and turns
  them into retrieval documents: one per table, one per column, including
  the editable business-glossary `description` field and up to 3 sample
  values.
- **`embeddings.py`** — a pluggable `EmbeddingProvider` interface. Default
  implementation is scikit-learn TF-IDF, not BAAI bge-m3 — this sandbox
  has no network route to huggingface.co to download real embedding
  weights. The interface (`fit`/`embed`) is the only contract
  `retriever.py` depends on, so swapping in `sentence-transformers` +
  bge-m3 later touches one file.
- **`retriever.py`** — ChromaDB `PersistentClient`, but embeddings are
  computed by *us* and passed directly to `collection.add(embeddings=...)`
  rather than wrapping TF-IDF as a Chroma `EmbeddingFunction`. Reason: TF-IDF's
  vocabulary must stay consistent between fit and query, and the schema
  corpus is small enough (tens to low-thousands of docs) that the simplest
  correct approach is to refit + fully rebuild the collection whenever
  schema changes (new dataset uploaded, column description edited), rather
  than doing incremental inserts against a fixed vocabulary.

### A real scaling limitation found during testing

Retrieval searches globally across *all* uploaded datasets with a fixed
`top_k=8` — intentional, matching the spec's vision of a company having
Sales.csv/HR.csv/Finance.csv side by side and RAG figuring out which
table/columns are relevant. But during live testing, uploading the same
CSV twice (creating two datasets with near-identical column
descriptions) caused `customer_name` to occasionally fall out of the
top-8 results for a query that needed it, because near-duplicate TF-IDF
vectors from two datasets compete for the same slots. This is documented
in the README rather than silently fixed, because the "right" fix
(dataset-scoped retrieval, or an adaptive top_k) is a real design
decision, not a one-line patch — the Streamlit sidebar's "active
dataset" selector is already positioned to carry that scoping through
once it's built.

## 4. SQL safety model (defense in depth)

Four independent layers, not one:

1. **Validator Agent** (`validator_agent.py`): parses with `sqlglot`,
   rejects anything that isn't a single top-level `exp.Select` statement.
   This one check is a complete, sqlglot-version-independent read-only
   guarantee — SQL grammar doesn't allow DROP/DELETE/UPDATE/ALTER/
   TRUNCATE/INSERT to appear *nested inside* a SELECT, so there's no need
   to enumerate dangerous statement types separately (an earlier draft
   did enumerate `exp.Insert`/`exp.Delete`/etc. for defense-in-depth, but
   this was removed as unnecessary surface area that depended on guessing
   exact sqlglot class names across versions).
2. **Hallucination detection**: table names checked against
   `schema_catalog.get_known_tables()`, which reflects the *live* Postgres
   schema via `sqlalchemy.inspect()` — not our own metadata records, so it
   can't drift out of sync with reality. Column checks are skipped for
   CTE queries (a CTE can introduce computed/renamed columns that won't
   match physical columns) but table-level and read-only checks still
   apply. SELECT-list aliases are collected and excluded from "unknown
   column" checks — Postgres allows `ORDER BY`/`GROUP BY` to reference an
   output alias, and an earlier version of this check didn't account for
   that, which would have produced false-positive rejections for
   perfectly valid SQL using a differently-named alias.
3. **Execution Agent**: wraps every query as
   `SELECT * FROM (<query>) AS _subquery LIMIT <max_result_rows>` — a hard
   cap regardless of what the generated SQL says — plus a 5-second
   Postgres `statement_timeout`.
4. **Repair loop**: bounded retries (see §1), so a persistently-invalid
   query can't loop forever.

## 5. What was actually run, and what broke

Everything below was executed for real in this build's sandbox, not
just reasoned about:

- **47 pytest tests**, all passing, covering validation, ingestion,
  the offline NL→SQL heuristic, JSON extraction, the dashboard agent, and
  a full LangGraph workflow smoke test (including a forced repair loop
  and a forced give-up-gracefully case).
- **A live end-to-end run** (`run_live_demo.py`): real PostgreSQL 16,
  real FastAPI server, real CSV upload (400 synthetic order rows), real
  business-glossary enrichment, four real natural-language questions
  through the real HTTP API (including the "Only Electronics" follow-up),
  real profiling and dashboard endpoints.
- **A Streamlit boot check** (`verify_streamlit.py`): confirms `app.py`
  starts and serves its shell with no import/syntax errors. Cannot verify
  visual rendering or interactive behavior — no browser in this sandbox.
- **Docker was reviewed, not executed** — no Docker daemon is available
  in this sandbox (`docker: not found`). The Dockerfiles and Compose file
  were read line-by-line against the actual running system's behavior.

### Bugs this process actually found and fixed

1. **pandas 3.0's `future.infer_string` default**: text columns report
   `dtype` as `'str'` (a dedicated `StringDtype`), not the legacy
   `object`. Code written against `dtype == object` silently stopped
   working — three places: CSV ingestion's date-column detection,
   ingestion's numeric-string coercion, and the dashboard agent's
   categorical-column detection (the last one wasn't caught by unit
   tests at all — only the live demo run showed `"num charts": 0` where
   a chart should have existed). Fixed by centralizing the check in
   `backend/utils/dtypes.py::is_text_like()`, used by both
   `ingestion.py` and `dashboard_agent.py`, with a regression test added
   for each (`tests/test_dashboard_agent.py` didn't exist before this
   bug was found).
2. **Identifier detection used substring matching** (`"id" in name`),
   which would mislabel a column like `amount_paid` as an "Identifier
   field" (`"id" in "paid"` is `True`). Fixed with exact/suffix matching
   (`name == "id" or name.endswith("_id")`) in the same `dtypes.py` module.
3. **Dashboard KPI cards summed identifier columns** ("Total order_id: 80200")
   — meaningless. Fixed by excluding identifier-like columns from the
   numeric-KPI candidates.
4. **Explanation quality for edge cases**: a single-column aggregate
   result (e.g. "total revenue") fell through to a generic "returned 1
   row across 1 column" non-answer instead of stating the value; a
   single-row ranking result said "100% of the total across the 1 row
   shown," which is always true and therefore meaningless. Both fixed
   with dedicated branches in `FakeLLMProvider.explain_results()`.
5. **Docker Compose network misconfiguration**: the `backend` service's
   `.env`-sourced `DATABASE_URL`/`SYNC_DATABASE_URL` pointed at
   `localhost`, which inside the Compose network resolves to the backend
   container itself, not the `postgres` service. Fixed with explicit
   `environment:` overrides in `docker-compose.yml` using the service
   name `postgres`.
6. **No migration step in the Docker startup flow at all** — a fresh
   `docker compose up` would have started the API against a database
   with no tables. Fixed by adding `docker/entrypoint.sh`, which waits
   for Postgres, runs `alembic upgrade head` (confirmed idempotent — a
   second run against an already-migrated database is a clean no-op),
   then starts uvicorn.
7. **Sandbox process-management quirks** (not application bugs, but
   worth recording since they shaped how verification was done):
   background processes (`nohup ... &`) didn't reliably survive between
   tool calls in this environment; `pgrep -f "uvicorn backend.api.main"`
   matched its own invocation's command-line text, causing a false
   "already running" result; a long shell polling loop combined with
   several sequential steps in one script exceeded a call-duration
   limit. Worked around by managing the server as a Python
   `subprocess.Popen` child within a single script
   (`run_live_demo.py`, `verify_streamlit.py`) rather than relying on
   shell job control.

## 6. Design tradeoffs

- **Sync + async engines side by side** (`backend/database/postgres.py`):
  the async engine (asyncpg) serves normal FastAPI request handling; a
  separate sync engine (psycopg2) is used specifically for
  `pandas.DataFrame.to_sql()` and the agents' raw SQL execution, since
  pandas doesn't support async engines and the agents' execution path
  doesn't need to be async. This is a deliberate hybrid, not an
  oversight.
- **Dependency injection via `app.state`**, not module-level globals:
  the compiled LangGraph workflow and LLM provider are built once in
  `main.py`'s `lifespan` and attached to `app.state`, retrieved in
  `routes.py` via a `Depends(get_workflow)` function. An earlier version
  built these as bare module-level globals in `routes.py` at import
  time — functionally identical, but not overridable via
  `app.dependency_overrides` for testing, and not matching the explicit
  DI requirement. Refactored during a review pass.
- **One consolidated `routes.py`**, not a versioned `api/v1/` package
  with one file per resource — matches this project's flatter file
  layout. Sections are marked with comments (`# --- Datasets ---`,
  `# --- Chat ---`) rather than split into files, since the whole file
  is under 250 lines.
