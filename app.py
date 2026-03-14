# Sustainability Report Crawler - Streamlit UI
# Run with: uv run streamlit run app.py  (or: streamlit run app.py)

import asyncio
import threading

import pandas as pd
import streamlit as st

from config import STORAGE_PATH
from crawler.main import run_crawl
from utils.csv_reader import read_companies_csv
from utils.zip_builder import build_zip

st.set_page_config(page_title="Sustainability Report Crawler", layout="wide")
st.title("Sustainability Report Crawler")

if "companies" not in st.session_state:
    st.session_state.companies = []
if "crawl_results" not in st.session_state:
    st.session_state.crawl_results = []
if "crawl_running" not in st.session_state:
    st.session_state.crawl_running = False
if "crawl_progress" not in st.session_state:
    st.session_state.crawl_progress = []  # list of {company, status, ...} as they complete

# ----- Section 1 — Upload -----
st.header("1. Upload companies")
uploaded = st.file_uploader("Upload a CSV file with company names", type=["csv"])

if uploaded is not None:
    companies, error = read_companies_csv(uploaded)
    if error:
        st.error(error)
    else:
        st.session_state.companies = companies
        st.success(f"Loaded {len(companies)} companies.")
        st.dataframe(
            pd.DataFrame({"company": st.session_state.companies}),
            use_container_width=True,
            hide_index=True,
        )
else:
    if st.session_state.companies:
        st.info(f"Using previously loaded list: {len(st.session_state.companies)} companies.")
        st.dataframe(
            pd.DataFrame({"company": st.session_state.companies}),
            use_container_width=True,
            hide_index=True,
        )

# ----- Section 2 — Run -----
st.header("2. Run crawler")
has_companies = len(st.session_state.companies) > 0


def _run_in_thread(companies_list, shared: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def callback(result):
        shared["progress"].append(result)

    try:
        results = loop.run_until_complete(run_crawl(companies_list, callback))
        shared["results"] = results
    except Exception as e:
        shared["error"] = str(e)
    finally:
        loop.close()


if start_crawler := st.button("Start crawler", type="primary", disabled=not has_companies):
    st.session_state.crawl_running = True
    st.session_state.crawl_progress = []
    st.session_state.crawl_results = []
    st.session_state._crawl_shared = {"progress": [], "results": None, "error": None}
    thread = threading.Thread(
        target=_run_in_thread,
        args=(list(st.session_state.companies), st.session_state._crawl_shared),
    )
    thread.start()
    st.session_state._crawl_thread = thread

if not has_companies:
    st.caption("Upload a valid CSV above to enable the crawler.")

# Progress: show live progress; when thread is done, take final results
if st.session_state.crawl_running and "_crawl_thread" in st.session_state:
    t = st.session_state._crawl_thread
    shared = st.session_state._crawl_shared
    n = len(st.session_state.companies)
    if t.is_alive():
        progress_so_far = len(shared["progress"])
        st.progress(min(1.0, progress_so_far / max(1, n)))
        st.caption(f"Processed {progress_so_far} / {n} companies. Refresh the page to see updates.")
    else:
        st.session_state.crawl_running = False
        if shared.get("error"):
            st.error(shared["error"])
        st.session_state.crawl_results = shared.get("results") or []
        st.progress(1.0)
        st.success("Crawl finished.")
        st.rerun()

# ----- Section 3 — Results -----
st.header("3. Results")
if st.session_state.crawl_results:
    df = pd.DataFrame(st.session_state.crawl_results).copy()
    df["select"] = False
    edited = st.data_editor(
        df,
        column_config={
            "select": st.column_config.CheckboxColumn("Select", default=False),
            "company": st.column_config.TextColumn("Company"),
            "status": st.column_config.TextColumn("Status"),
            "pdf_url": st.column_config.LinkColumn("PDF URL"),
            "filename": st.column_config.TextColumn("Filename"),
        },
        use_container_width=True,
        hide_index=True,
    )
    st.session_state._results_edited = edited
else:
    st.session_state._results_edited = None
    st.caption("Run the crawler to see results.")
    edited = pd.DataFrame()

# ----- Section 4 — Download -----
st.header("4. Download selected")
if st.session_state.crawl_results:
    edited = st.session_state.get("_results_edited")
    if edited is not None and "select" in edited.columns:
        selected = edited[edited["select"] == True]
        found = selected[selected["status"] == "found"]
        selected_filenames = found["filename"].dropna().astype(str).tolist()
        selected_filenames = [f for f in selected_filenames if f and str(f).strip()]
    else:
        selected_filenames = []
    can_download = len(selected_filenames) > 0
    zip_bytes = build_zip(selected_filenames, STORAGE_PATH) if can_download else b""
    st.download_button(
        "Download selected",
        data=zip_bytes,
        file_name="sustainability_reports.zip",
        mime="application/zip",
        disabled=not can_download,
    )
    if not can_download:
        st.caption("Select at least one row with status 'found' to download.")
else:
    st.download_button("Download selected", data=b"", file_name="reports.zip", mime="application/zip", disabled=True)
    st.caption("Run the crawler and select rows to enable download.")
