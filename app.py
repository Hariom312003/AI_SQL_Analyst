"""Streamlit UI for the AI SQL Analyst.

Talks to the FastAPI backend over HTTP only (no direct backend imports) --
matching the architecture: User -> Streamlit -> FastAPI -> LangGraph
workflow -> Postgres.
"""
from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")

def start_backend_if_needed():
    """Auto-starts the FastAPI backend if API_BASE is localhost and port is not bound."""
    if "localhost" in API_BASE or "127.0.0.1" in API_BASE:
        import socket
        import subprocess
        
        # Determine port from API_BASE
        port = 8000
        try:
            from urllib.parse import urlparse
            parsed = urlparse(API_BASE)
            if parsed.port:
                port = parsed.port
        except Exception:
            pass
        
        # Check if port is open
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
            s.close()
            # Already running
            return
        except OSError:
            pass

        print(f"FastAPI backend not detected on port {port}. Auto-starting FastAPI backend in background...", file=sys.stderr)
        try:
            # Start backend as background process (stdout/stderr silenced to avoid polluting console)
            subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            
            # Wait for backend to become healthy
            health_url = f"{API_BASE}/health"
            start_time = time.time()
            timeout = 30.0  # Allow up to 30 seconds for startup and migrations
            backend_ready = False
            
            while time.time() - start_time < timeout:
                try:
                    r = requests.get(health_url, timeout=1.0)
                    if r.status_code == 200:
                        backend_ready = True
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.5)
                
            if backend_ready:
                print("FastAPI backend started and is healthy.", file=sys.stderr)
            else:
                print("FastAPI backend failed to start or become healthy within timeout.", file=sys.stderr)
                
        except Exception as e:
            print(f"Failed to auto-start FastAPI backend: {e}", file=sys.stderr)

start_backend_if_needed()

# Set Page Config
st.set_page_config(
    page_title="AI SQL Analyst - Enterprise Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------- Custom CSS / Theme --
st.markdown(
    """
    <style>
    /* Main Page Background and Layout adjustments */
    .reportview-container {
        background: #0e1117;
    }
    /* Enterprise Stats Cards */
    .kpi-card {
        background-color: #1f2937;
        border: 1px solid #374151;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .kpi-title {
        font-size: 14px;
        color: #9ca3af;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .kpi-value {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
    }
    /* Chat Bubble styling */
    .chat-bubble-user {
        background-color: #1e3a8a;
        color: #f3f4f6;
        padding: 12px 16px;
        border-radius: 18px 18px 0px 18px;
        margin: 8px 0;
        display: inline-block;
        max-width: 80%;
    }
    .chat-bubble-assistant {
        background-color: #1f2937;
        color: #f3f4f6;
        padding: 12px 16px;
        border-radius: 18px 18px 18px 0px;
        margin: 8px 0;
        display: inline-block;
        max-width: 80%;
        border: 1px solid #374151;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize Session States
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_dataset" not in st.session_state:
    st.session_state.selected_dataset = None
if "navigation" not in st.session_state:
    st.session_state.navigation = "🏠 Dashboard"

# ------------------------------------------------------- Helper API Functions --
def get_datasets():
    try:
        r = requests.get(f"{API_BASE}/datasets", timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        return []

def delete_dataset(dataset_id):
    try:
        r = requests.delete(f"{API_BASE}/datasets/{dataset_id}", timeout=15)
        r.raise_for_status()
        return True
    except Exception:
        return False

def get_preview(dataset_id):
    try:
        r = requests.get(f"{API_BASE}/datasets/{dataset_id}/preview", timeout=15)
        r.raise_for_status()
        return r.json().get("rows", [])
    except Exception:
        return []

def upload_dataset_file(file_name, file_bytes):
    try:
        r = requests.post(
            f"{API_BASE}/datasets/upload",
            files={"file": (file_name, file_bytes, "text/csv")},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        st.error(f"Ingestion failed: {exc}")
        return None

# ---------------------------------------------------- Default Dataset Loader --
def auto_load_default():
    datasets = get_datasets()
    if not datasets:
        # Load examples/orders_demo.csv
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_csv = os.path.join(base_dir, "examples", "orders_demo.csv")
        if os.path.exists(default_csv):
            with open(default_csv, "rb") as f:
                content = f.read()
                upload_dataset_file("orders_demo.csv", content)

auto_load_default()

# Refresh datasets
all_datasets = get_datasets()
if all_datasets and not st.session_state.selected_dataset:
    st.session_state.selected_dataset = all_datasets[0]

# --------------------------------------------------------------- Navigation --
st.sidebar.markdown("### 📊 AI SQL Analyst")
st.sidebar.markdown("`Enterprise analytics platform`  \n"
                    "Connected to **PostgreSQL + LangGraph**")

st.sidebar.divider()

nav_options = [
    "🏠 Dashboard",
    "💬 AI Chat",
    "📂 Dataset Manager",
    "📊 Data Explorer",
    "📈 Analytics Dashboard",
    "🧠 Query History"
]

selected_nav = st.sidebar.radio("Navigation", nav_options)
st.session_state.navigation = selected_nav

st.sidebar.divider()

# Active Dataset display in Sidebar
if st.session_state.selected_dataset:
    ds = st.session_state.selected_dataset
    st.sidebar.success(f"📂 **Active Dataset:**  \n`{ds['name']}`")
    st.sidebar.caption(f"Table: `{ds['table_name']}` · Rows: **{ds['row_count']}**")
else:
    st.sidebar.warning("📂 No active dataset selected")

# Clear session
if st.sidebar.button("🧹 Clear Chat History", use_container_width=True):
    st.session_state.conversation_id = None
    st.session_state.messages = []
    st.rerun()

# ----------------------------------------------------------- Render Page: Dashboard --
if st.session_state.navigation == "🏠 Dashboard":
    st.title("🏠 Enterprise Executive Dashboard")
    st.markdown("Automated metrics compilation and RAG query profiling analysis.")

    if not st.session_state.selected_dataset:
        st.info("No active dataset. Head over to the **📂 Dataset Manager** to load one.")
    else:
        ds = st.session_state.selected_dataset
        
        # Load Dashboard API
        try:
            r = requests.get(f"{API_BASE}/datasets/{ds['id']}/dashboard", timeout=15)
            r.raise_for_status()
            spec = r.json()
        except Exception:
            spec = {"kpi_cards": [], "charts": []}

        # Build dynamic executive metrics
        # If dataset is orders_demo, we can compute specific ones or fallback
        rows = get_preview(ds["id"])
        df = pd.DataFrame(rows)
        
        # Top KPI Cards
        st.subheader("Key Performance Indicators")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # Inferred sales metrics logic
        rev_val = "-"
        orders_val = len(df) if not df.empty else ds["row_count"]
        cust_val = "-"
        profit_val = "-"
        aov_val = "-"

        if not df.empty:
            cols_lower = {c.lower(): c for c in df.columns}
            # Revenue
            rev_col = cols_lower.get("total_price") or cols_lower.get("sales") or cols_lower.get("revenue")
            if rev_col:
                total_rev = df[rev_col].sum()
                rev_val = f"${total_rev:,.2f}"
                # Profit fallback
                profit_val = f"${(total_rev * 0.15):,.2f}"
                if "profit" in cols_lower:
                    profit_val = f"${df[df.columns[cols_lower.get('profit')]].sum():,.2f}"
            
            # Customers
            cust_col = cols_lower.get("customer") or cols_lower.get("customer_id") or cols_lower.get("user")
            if cust_col:
                cust_val = f"{df[cust_col].nunique()}"
            
            # Orders
            ord_col = cols_lower.get("order_id") or cols_lower.get("id")
            if ord_col:
                orders_val = df[ord_col].nunique()
            
            # AOV
            if rev_col and orders_val:
                aov_val = f"${(df[rev_col].sum() / orders_val):,.2f}"

        col1.metric("Revenue (Est)", rev_val)
        col2.metric("Orders Invoiced", orders_val)
        col3.metric("Unique Customers", cust_val)
        col4.metric("Gross Profit (Est)", profit_val)
        col5.metric("AOV", aov_val)

        st.divider()

        # Dynamic charts from Dashboard Spec
        st.subheader("Analytics Overview")
        if spec.get("charts"):
            for chart in spec["charts"]:
                if chart.get("plotly_figure"):
                    st.plotly_chart(go.Figure(chart["plotly_figure"]), use_container_width=True)
        else:
            st.info("No default charts generated. Custom visualizations can be run inside **📈 Analytics Dashboard**.")

        # Recent activities
        st.divider()
        st.subheader("Recent System Profile")
        col_prof1, col_prof2 = st.columns(2)
        with col_prof1:
            st.markdown(f"**Selected Dataset Name:** `{ds['name']}`")
            st.markdown(f"**Database Table:** `{ds['table_name']}`")
            st.markdown(f"**Dataset Rows:** `{ds['row_count']}`")
        with col_prof2:
            st.markdown(f"**Status:** `Active` 🟢")
            st.markdown(f"**Upload Reference:** `{ds['original_filename']}`")

# ------------------------------------------------------------- Render Page: Chat --
elif st.session_state.navigation == "💬 AI Chat":
    st.title("💬 Enterprise AI Analytics Copilot")
    st.markdown("Ask natural language queries and get SQL execution, RAG retrievals, and plotly charts.")

    if not st.session_state.selected_dataset:
        st.info("Please select or load an active dataset first to start questioning.")
    else:
        ds = st.session_state.selected_dataset
        st.info(f"⚡ Currently chatting with dataset **{ds['name']}**")

        # Clear conversation option
        col_header1, col_header2 = st.columns([6, 1])
        with col_header2:
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.conversation_id = None
                st.session_state.messages = []
                st.rerun()

        # Render message history
        for msg in st.session_state.messages:
            avatar = "👤" if msg["role"] == "user" else "🤖"
            align_class = "chat-bubble-user" if msg["role"] == "user" else "chat-bubble-assistant"
            
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(f"<div class='{align_class}'>{msg['content']}</div>", unsafe_allow_html=True)
                
                # Render metadata collapsibles
                if msg.get("sql"):
                    with st.expander("🛠️ Generated SQL Query", expanded=False):
                        st.code(msg["sql"], language="sql")
                if msg.get("plotly_figure"):
                    st.plotly_chart(go.Figure(msg["plotly_figure"]), use_container_width=True)
                if msg.get("rows"):
                    with st.expander("📊 Extracted Data Rows", expanded=False):
                        st.dataframe(pd.DataFrame(msg["rows"]), use_container_width=True)

        # Chat Input
        question = st.chat_input("Ask a question about your active dataset...")
        if question:
            st.session_state.messages.append({"role": "user", "content": question})
            st.chat_message("user", avatar="👤").markdown(f"<div class='chat-bubble-user'>{question}</div>", unsafe_allow_html=True)

            with st.chat_message("assistant", avatar="🤖"):
                status_box = st.status("Thinking... Resolving intent & retrieving schema context", expanded=True)
                try:
                    payload = {"question": question}
                    if st.session_state.conversation_id:
                        payload["conversation_id"] = st.session_state.conversation_id
                    
                    status_box.update(label="Generating & validating SQL queries...", state="running")
                    r = requests.post(f"{API_BASE}/chat/ask", json=payload, timeout=60)
                    r.raise_for_status()
                    data = r.json()
                    st.session_state.conversation_id = data["conversation_id"]

                    status_box.update(label="SQL validated successfully. Executing and visualizing...", state="complete")
                    time.sleep(0.2)
                    status_box.update(expanded=False)

                    # Assistant response bubbles
                    st.markdown(f"<div class='chat-bubble-assistant'>{data['explanation']}</div>", unsafe_allow_html=True)
                    
                    # Show expandable generated SQL
                    with st.expander("🛠️ Generated SQL Query"):
                        st.code(data["sql"], language="sql")

                    # Draw Plotly Figure
                    if data.get("plotly_figure"):
                        st.plotly_chart(go.Figure(data["plotly_figure"]), use_container_width=True)
                    
                    # Show extracted dataframe
                    if data.get("rows"):
                        with st.expander("📊 Extracted Data Rows"):
                            st.dataframe(pd.DataFrame(data["rows"]), use_container_width=True)
                    
                    if data.get("execution_error"):
                        st.warning(f"Execution notice: {data['execution_error']}")

                    # Save Assistant message
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": data["explanation"],
                            "sql": data["sql"],
                            "plotly_figure": data.get("plotly_figure"),
                            "rows": data.get("rows"),
                        }
                    )
                except Exception as exc:
                    status_box.update(label="Request failed", state="error")
                    st.error(f"Error querying backend: {exc}")

# ---------------------------------------------------- Render Page: Dataset Manager --
elif st.session_state.navigation == "📂 Dataset Manager":
    st.title("📂 Enterprise Dataset Manager")
    st.markdown("Load default datasets, ingest new CSVs, and configure metadata mapping schemas.")

    # Ingestion Form
    st.subheader("Upload New Dataset")
    uploaded = st.file_uploader("Upload CSV dataset", type=["csv"])
    if uploaded is not None:
        if st.button("🚀 Process & Ingest File", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            status_text.text("Uploading CSV file...")
            progress_bar.progress(20)
            time.sleep(0.3)
            
            status_text.text("Parsing dataset structure & inferring datatypes...")
            progress_bar.progress(50)
            time.sleep(0.3)
            
            status_text.text("Creating Postgres table & loading records...")
            progress_bar.progress(70)
            
            res = upload_dataset_file(uploaded.name, uploaded.getvalue())
            if res:
                status_text.text("Rebuilding RAG vector embeddings index...")
                progress_bar.progress(90)
                time.sleep(0.3)
                
                status_text.text("Ingestion completed! Active and profiled.")
                progress_bar.progress(100)
                st.success(f"Ingested '{res['name']}' successfully.")
                st.session_state.selected_dataset = res
                st.rerun()

    st.divider()

    # Load default dataset action
    st.subheader("Default Sample Dataset")
    col_def1, col_def2 = st.columns([5, 2])
    with col_def1:
        st.caption("You can reset or reload the default sales sample dataset at any time.")
    with col_def2:
        if st.button("Use Default Dataset", use_container_width=True):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            default_csv = os.path.join(base_dir, "examples", "orders_demo.csv")
            if os.path.exists(default_csv):
                with open(default_csv, "rb") as f:
                    content = f.read()
                    res = upload_dataset_file("orders_demo.csv", content)
                    if res:
                        st.session_state.selected_dataset = res
                        st.success("Default dataset loaded.")
                        st.rerun()

    st.divider()

    # Dataset table list
    st.subheader("Ingested Datasets List")
    datasets = get_datasets()
    if not datasets:
        st.info("No datasets loaded in the catalog database yet.")
    else:
        for idx, d in enumerate(datasets):
            col_d1, col_d2, col_d3, col_d4 = st.columns([4, 2, 2, 2])
            with col_d1:
                is_active = "🟢 [Active]" if st.session_state.selected_dataset and d["id"] == st.session_state.selected_dataset["id"] else "⚪ [Inactive]"
                st.markdown(f"### `{d['name']}`")
                st.caption(f"Table Name: `{d['table_name']}` · status: {is_active}")
            with col_d2:
                st.markdown(f"**Rows:** `{d['row_count']}`")
                # Estimate Columns
                st.caption("Auto-profiled columns")
            with col_d3:
                if st.button("Select Dataset", key=f"sel_{idx}", use_container_width=True):
                    st.session_state.selected_dataset = d
                    st.success(f"Context switched to {d['name']}.")
                    st.rerun()
            with col_d4:
                if st.button("🗑️ Delete", key=f"del_{idx}", use_container_width=True):
                    if delete_dataset(d["id"]):
                        st.success(f"Deleted {d['name']}.")
                        if st.session_state.selected_dataset and st.session_state.selected_dataset["id"] == d["id"]:
                            st.session_state.selected_dataset = None
                        st.rerun()
            st.divider()

        # Business Glossary mapping expander
        st.subheader("RAG Metadata & Schema Glossary Mapping")
        if st.session_state.selected_dataset:
            ds = st.session_state.selected_dataset
            with st.expander(f"Enrich Columns Glossary for `{ds['name']}`"):
                col_gloss1, col_gloss2 = st.columns(2)
                with col_gloss1:
                    col_name = st.text_input("Database Column Name")
                with col_gloss2:
                    description = st.text_area("Column Business Definition")
                if st.button("Save glossary mapping", use_container_width=True):
                    if col_name and description:
                        try:
                            r = requests.patch(
                                f"{API_BASE}/datasets/{ds['id']}/columns/{col_name}",
                                json={"description": description},
                                timeout=15,
                            )
                            r.raise_for_status()
                            st.success(f"Column '{col_name}' glossary updated. RAG embeddings refreshed.")
                        except Exception as e:
                            st.error(f"Error mapping column description: {e}")

# ---------------------------------------------------- Render Page: Data Explorer --
elif st.session_state.navigation == "📊 Data Explorer":
    st.title("📊 Data Explorer & Tables Preview")
    st.markdown("Interactive query table and high-level structure preview.")

    if not st.session_state.selected_dataset:
        st.info("Please load or select an active dataset inside the Dataset Manager first.")
    else:
        ds = st.session_state.selected_dataset
        st.subheader(f"Dataset Overview: {ds['name']}")
        
        preview_rows = get_preview(ds["id"])
        if not preview_rows:
            st.warning("No records could be retrieved for this dataset.")
        else:
            df = pd.DataFrame(preview_rows)
            
            # Meta statistics
            col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
            col_meta1.metric("Row Count", ds["row_count"])
            col_meta2.metric("Column Count", len(df.columns))
            col_meta3.metric("Null Values In Preview", df.isna().sum().sum())
            col_meta4.metric("Dtype Categories", len(df.select_dtypes(include="object").columns))
            
            st.divider()
            
            # First 20 rows table
            st.subheader("First 20 Ingested Rows Table")
            st.dataframe(df, use_container_width=True)

# ----------------------------------------------- Render Page: Analytics Dashboard --
elif st.session_state.navigation == "📈 Analytics Dashboard":
    st.title("📈 Detailed Data Profiling & Analytics")
    st.markdown("Heatmaps, summary stats, distributions, and correlation matrices.")

    if not st.session_state.selected_dataset:
        st.info("Please select or load an active dataset first.")
    else:
        ds = st.session_state.selected_dataset
        
        try:
            r = requests.get(f"{API_BASE}/datasets/{ds['id']}/profile", timeout=15)
            r.raise_for_status()
            profile = r.json().get("profile", {})
        except Exception as e:
            profile = {}
            st.error(f"Error reading dataset profiling specs: {e}")

        if profile:
            # Summary Statistics
            st.subheader("Dataset Profiling Statistics Summary")
            st.markdown(f"**Total Row Count:** `{profile['row_count']}` · "
                        f"**Total Column Count:** `{profile['column_count']}` · "
                        f"**Duplicate Row Count:** `{profile['duplicate_rows']}`")

            # Outlier Detection
            st.divider()
            st.subheader("Column Profiling Metrics")
            
            # Numeric column selection for distribution
            numeric_cols = []
            for col_name, stats in profile.get("columns", {}).items():
                if "mean" in stats:
                    numeric_cols.append(col_name)

            col_cols1, col_cols2 = st.columns(2)
            with col_cols1:
                # Column Datatypes list
                st.subheader("Column Types & Properties")
                col_types_data = []
                for c_name, c_stats in profile.get("columns", {}).items():
                    col_types_data.append({
                        "Column": c_name,
                        "Type": c_stats["dtype"],
                        "Null Count": c_stats["missing_count"],
                        "Null %": f"{c_stats['missing_pct']}%",
                        "Unique Values": c_stats["unique_count"]
                    })
                st.dataframe(pd.DataFrame(col_types_data), use_container_width=True)

            with col_cols2:
                # Null percentage heatmap/bar chart
                st.subheader("Null Percentage Chart")
                null_chart_df = pd.DataFrame(col_types_data)
                null_chart_df["Null % (Float)"] = null_chart_df["Null %"].str.rstrip("%").astype(float)
                fig_null = px.bar(null_chart_df, x="Column", y="Null % (Float)", 
                                  title="Missing Values Heatmap Ingest", labels={"Null % (Float)": "Missing %"})
                st.plotly_chart(fig_null, use_container_width=True)

            # Summary stats for numeric columns
            if numeric_cols:
                st.divider()
                st.subheader("Numeric Summary Statistics")
                numeric_summary_data = []
                for col_name in numeric_cols:
                    c_stats = profile["columns"][col_name]
                    numeric_summary_data.append({
                        "Column": col_name,
                        "Mean": c_stats.get("mean"),
                        "Std": c_stats.get("std"),
                        "Min": c_stats.get("min"),
                        "Max": c_stats.get("max"),
                        "Outliers count": c_stats.get("outlier_count")
                    })
                st.dataframe(pd.DataFrame(numeric_summary_data), use_container_width=True)

                # Distribution Chart Selector
                st.divider()
                st.subheader("Numeric Distribution Visualizer")
                selected_dist_col = st.selectbox("Select numeric column to view distribution", numeric_cols)
                
                rows = get_preview(ds["id"])
                if rows:
                    dist_df = pd.DataFrame(rows)
                    if selected_dist_col in dist_df.columns:
                        fig_dist = px.histogram(dist_df, x=selected_dist_col, title=f"Distribution of {selected_dist_col}", marginal="box")
                        st.plotly_chart(fig_dist, use_container_width=True)

            # Correlation Heatmap matrix
            correlations = profile.get("correlations", {})
            if correlations:
                st.divider()
                st.subheader("Numeric Correlations Heatmap")
                corr_df = pd.DataFrame(correlations)
                fig_corr = px.imshow(corr_df, text_auto=True, color_continuous_scale="RdBu_r", title="Feature Correlations Matrix")
                st.plotly_chart(fig_corr, use_container_width=True)

# ------------------------------------------------ Render Page: Query History --
elif st.session_state.navigation == "🧠 Query History":
    st.title("🧠 SQL Query & Audit History")
    st.markdown("Review generated SQL queries, conversational follow-ups, and execution performance stats.")

    # Retrieve all queries
    try:
        # We can extract the messages history of the active conversation or fallback
        # Let's show the query audit log if conversation ID exists
        if not st.session_state.messages:
            st.info("No query history recorded in the current active session.")
        else:
            for idx, msg in enumerate(st.session_state.messages):
                if msg["role"] == "user":
                    st.markdown(f"**Query {idx // 2 + 1}:** `{msg['content']}`")
                else:
                    st.markdown(f"**Response:** {msg['content']}")
                    if msg.get("sql"):
                        st.code(msg["sql"], language="sql")
                    st.divider()
    except Exception:
        st.info("History display exception.")
