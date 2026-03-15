# Sustainability Report Crawler - Streamlit UI
# Run with: uv run streamlit run app.py  (or: streamlit run app.py)

import asyncio
import logging
import os
import threading
import time
from calendar import month_name
from logging.handlers import RotatingFileHandler

import pandas as pd
import streamlit as st

from config import MONTHLY_QUERY_LIMIT, QUOTA_WARNING_THRESHOLD, STORAGE_PATH

# ── Logging configuration (console + optional file) ───────────────────────────
_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
logging.basicConfig(level=_LOG_LEVEL, format=_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
# Remove default handler so we can add our own (avoids duplicate logs if root has one)
_root = logging.getLogger()
_root.handlers.clear()
_console = logging.StreamHandler()
_console.setLevel(_LOG_LEVEL)
_console.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
_root.addHandler(_console)
_root.setLevel(_LOG_LEVEL)
_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
try:
    os.makedirs(_log_dir, exist_ok=True)
    _file = RotatingFileHandler(
        os.path.join(_log_dir, "app.log"),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    _file.setLevel(_LOG_LEVEL)
    _file.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    _root.addHandler(_file)
except OSError:
    pass  # Log directory not writable; console only
logger = logging.getLogger(__name__)
from crawler.main import run_crawl
from utils.csv_reader import read_companies_csv
from utils.quota import get_usage
from utils.zip_builder import build_zip


@st.cache_data(show_spinner=False)
def _cached_zip(filenames_tuple: tuple[str, ...], storage_path: str) -> bytes:
    """Build zip only when the selection changes, not on every rerender."""
    return build_zip(list(filenames_tuple), storage_path)


st.set_page_config(
    page_title="Sustainability Report Crawler",
    layout="wide",
    page_icon="🌿",
)

# ── Botanical Garden custom CSS ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── Google Font: Lato (clean, natural feel) ── */
    @import url('https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700&family=Playfair+Display:wght@600&display=swap');

    /* ── Root palette ── */
    :root {
        --bg-main:       #F4F1EB;
        --bg-card:       #FFFFFF;
        --green-deep:    #2D5016;
        --green-mid:     #4A7C2F;
        --green-light:   #7BAE5A;
        --green-pale:    #C8DCBA;
        --sage:          #8FAF82;
        --earth:         #8B6914;
        --cream:         #F5F0E6;
        --text-main:     #2C3325;
        --text-muted:    #6B7A5E;
        --border:        #D4E4C4;
        --found:         #2D7D46;
        --not-found:     #C47B00;
        --error:         #B03030;
    }

    /* ── Page background ── */
    .stApp {
        background-color: var(--bg-main);
        font-family: 'Lato', sans-serif;
        color: var(--text-main);
    }

    /* ── Main title ── */
    h1 {
        font-family: 'Playfair Display', serif !important;
        color: var(--green-deep) !important;
        font-size: 2.2rem !important;
        letter-spacing: 0.02em;
        padding-bottom: 0.2rem;
    }

    /* ── Section headers (h2) ── */
    h2 {
        font-family: 'Playfair Display', serif !important;
        color: var(--green-mid) !important;
        font-size: 1.3rem !important;
        border-left: 4px solid var(--green-light);
        padding-left: 0.6rem;
        margin-top: 1.4rem !important;
    }

    h3 {
        color: var(--green-mid) !important;
    }

    /* ── Metric widget ── */
    [data-testid="stMetric"] {
        background: var(--cream);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 0.8rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-size: 0.8rem; }
    [data-testid="stMetricValue"] { color: var(--green-deep) !important; font-weight: 700; }

    /* ── Primary button ── */
    .stButton > button[kind="primary"] {
        background-color: var(--green-mid) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 1rem !important;
        padding: 0.55rem 1.6rem !important;
        font-family: 'Lato', sans-serif;
        font-weight: 700;
        transition: background-color 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: var(--green-deep) !important;
    }
    .stButton > button[kind="primary"]:disabled {
        background-color: var(--sage) !important;
        opacity: 0.6 !important;
    }

    /* ── Download button ── */
    .stDownloadButton > button {
        background-color: var(--earth) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700;
        font-family: 'Lato', sans-serif;
    }
    .stDownloadButton > button:hover {
        background-color: #6B5010 !important;
    }

    /* ── Progress bar ── */
    [data-testid="stProgressBar"] > div > div {
        background-color: var(--green-mid) !important;
    }
    [data-testid="stProgressBar"] {
        background-color: var(--green-pale) !important;
        border-radius: 8px;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--green-light) !important;
        border-radius: 10px !important;
        background: var(--cream) !important;
    }

    /* ── Divider ── */
    hr {
        border-color: var(--border) !important;
    }

    /* ── Info / success / warning / error alerts ── */
    [data-testid="stAlert"] {
        border-radius: 8px !important;
        font-size: 0.9rem;
    }

    /* ── Data table ── */
    [data-testid="stDataFrame"], [data-testid="data-grid-canvas"] {
        border-radius: 10px !important;
        overflow: hidden;
    }

    /* ── Section card helper class ── */
    .section-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }

    /* ── Live progress company row ── */
    .progress-row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding: 0.35rem 0;
        font-size: 0.88rem;
        border-bottom: 1px solid var(--border);
        color: var(--text-main);
    }
    .progress-row:last-child { border-bottom: none; }
    .badge {
        display: inline-block;
        border-radius: 5px;
        padding: 1px 8px;
        font-size: 0.78rem;
        font-weight: 700;
        min-width: 72px;
        text-align: center;
    }
    .badge-found    { background:#D4EDDA; color:#155724; }
    .badge-notfound { background:#FFF3CD; color:#856404; }
    .badge-error    { background:#F8D7DA; color:#721C24; }
    .badge-running  { background:#D1ECF1; color:#0C5460; }

    /* ── Stat pills ── */
    .stat-pill {
        display: inline-block;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.82rem;
        font-weight: 700;
        margin-right: 6px;
    }
    .pill-found    { background:var(--green-pale); color:var(--found); }
    .pill-notfound { background:#FFF3CD; color:var(--not-found); }
    .pill-error    { background:#F8D7DA; color:var(--error); }
    .pill-total    { background:#E8EAF6; color:#3949AB; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ────────────────────────────────────────────────────
for key, default in [
    ("companies", []),
    ("crawl_results", []),
    ("crawl_running", False),
    ("crawl_progress", []),
    ("crawl_error", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Page title ────────────────────────────────────────────────────────────────
st.title("🌿 Sustainability Report Crawler")
st.markdown(
    "<p style='color:#6B7A5E;font-size:0.95rem;margin-top:-0.6rem;'>Upload a company list and let the crawler find their sustainability reports.</p>",
    unsafe_allow_html=True,
)

# ── Quota banner ─────────────────────────────────────────────────────────────
usage = get_usage()
used = usage["used"]
remaining = usage["remaining"]
month_label = f"{month_name[usage['month']]} {usage['year']}"

quota_col1, quota_col2 = st.columns([4, 1])
with quota_col1:
    bar_value = min(1.0, used / MONTHLY_QUERY_LIMIT)
    if used >= MONTHLY_QUERY_LIMIT:
        st.error(
            f"🚫 Monthly quota exhausted — {used}/{MONTHLY_QUERY_LIMIT} queries used in {month_label}. "
            "Wait until next month or upgrade your Brave plan."
        )
    elif used >= QUOTA_WARNING_THRESHOLD:
        st.warning(
            f"⚠️ Quota almost full — {used}/{MONTHLY_QUERY_LIMIT} queries used in {month_label} "
            f"({remaining} remaining)."
        )
    else:
        st.info(
            f"🔍 Brave API quota — {used}/{MONTHLY_QUERY_LIMIT} queries used in {month_label} "
            f"({remaining} remaining)."
        )
    st.progress(bar_value)
with quota_col2:
    st.metric("Remaining", remaining, help=f"Brave search queries left in {month_label}")

st.divider()

# ── Section 1 — Upload ────────────────────────────────────────────────────────
st.header("1. Upload Companies")

quota_exhausted = used >= MONTHLY_QUERY_LIMIT

uploaded = st.file_uploader(
    "Upload a CSV file with company names  (column: `company` or `name`)",
    type=["csv"],
    disabled=quota_exhausted,
)

if quota_exhausted:
    st.error("Quota exhausted — uploads disabled until the quota resets next month.")
elif uploaded is not None:
    companies, error = read_companies_csv(uploaded)
    if error:
        st.error(error)
    else:
        if len(companies) > remaining:
            st.warning(
                f"Your CSV has {len(companies)} companies but only {remaining} queries remain. "
                f"Please upload a smaller batch (max {remaining} companies)."
            )
        st.session_state.companies = companies
        st.success(f"✅ Loaded **{len(companies)} companies**.")
        st.dataframe(
            pd.DataFrame({"🏢 Company": st.session_state.companies}),
            use_container_width=True,
            hide_index=True,
        )
else:
    if st.session_state.companies:
        st.info(f"Using previously loaded list: **{len(st.session_state.companies)} companies**.")
        st.dataframe(
            pd.DataFrame({"🏢 Company": st.session_state.companies}),
            use_container_width=True,
            hide_index=True,
        )

st.divider()

# ── Section 2 — Run ───────────────────────────────────────────────────────────
st.header("2. Run Crawler")

has_companies = len(st.session_state.companies) > 0
batch_exceeds_quota = len(st.session_state.companies) > remaining
run_disabled = not has_companies or quota_exhausted or batch_exceeds_quota


def _run_in_thread(companies_list, shared: dict):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def callback(result):
        shared["progress"].append(result)

    try:
        results = loop.run_until_complete(run_crawl(companies_list, callback))
        shared["results"] = results
    except Exception as e:
        logger.exception("Crawl failed: %s", e)
        shared["error"] = str(e)
    finally:
        loop.close()


if start_crawler := st.button("🚀 Start Crawler", type="primary", disabled=run_disabled):
    st.session_state.crawl_running = True
    st.session_state.crawl_progress = []
    st.session_state.crawl_results = []
    st.session_state.crawl_error = None
    st.session_state._crawl_shared = {"progress": [], "results": None, "error": None}
    thread = threading.Thread(
        target=_run_in_thread,
        args=(list(st.session_state.companies), st.session_state._crawl_shared),
    )
    thread.start()
    st.session_state._crawl_thread = thread

if not has_companies:
    st.caption("Upload a valid CSV above to enable the crawler.")
elif quota_exhausted:
    st.caption("Monthly quota exhausted — crawler disabled until next month.")
elif batch_exceeds_quota:
    st.caption(
        f"Batch too large: {len(st.session_state.companies)} companies "
        f"> {remaining} remaining queries. Reduce your CSV to enable the crawler."
    )

if st.session_state.get("crawl_error"):
    st.error(st.session_state.crawl_error)

# ── Live progress ─────────────────────────────────────────────────────────────
if st.session_state.crawl_running and "_crawl_thread" in st.session_state:
    t = st.session_state._crawl_thread
    shared = st.session_state._crawl_shared
    n = len(st.session_state.companies)
    completed = shared["progress"]
    progress_so_far = len(completed)

    # ── Top summary bar ──
    pct = min(1.0, progress_so_far / max(1, n))
    st.markdown(
        f"<p style='font-size:0.9rem;color:#4A7C2F;font-weight:700;margin-bottom:4px;'>"
        f"Processing… {progress_so_far} / {n} companies  ({int(pct*100)}%)</p>",
        unsafe_allow_html=True,
    )
    st.progress(pct)

    # ── Stat pills ──
    found_count    = sum(1 for r in completed if r.get("status") == "found")
    notfound_count = sum(1 for r in completed if r.get("status") == "not_found")
    error_count    = sum(1 for r in completed if r.get("status") == "error")
    remaining_count = n - progress_so_far
    st.markdown(
        f"""
        <div style="margin:6px 0 10px;">
          <span class="stat-pill pill-found">✅ Found: {found_count}</span>
          <span class="stat-pill pill-notfound">🔍 Not found: {notfound_count}</span>
          <span class="stat-pill pill-error">❌ Error: {error_count}</span>
          <span class="stat-pill pill-total">⏳ Remaining: {remaining_count}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Completed rows ──
    if completed:
        rows_html = ""
        for r in reversed(completed[-20:]):  # show latest 20
            status = r.get("status", "")
            company = r.get("company", "")
            if status == "found":
                badge = '<span class="badge badge-found">found</span>'
                detail = f'<span style="color:#888;font-size:0.8rem;">— {r.get("filename","")}</span>'
            elif status == "not_found":
                badge = '<span class="badge badge-notfound">not found</span>'
                detail = ""
            else:
                badge = '<span class="badge badge-error">error</span>'
                detail = ""
            rows_html += (
                f'<div class="progress-row">{badge}'
                f'<span style="flex:1">{company}</span>{detail}</div>'
            )

        # Show currently-running company if thread is still alive
        if t.is_alive() and progress_so_far < n:
            next_company = st.session_state.companies[progress_so_far]
            rows_html = (
                f'<div class="progress-row">'
                f'<span class="badge badge-running">running…</span>'
                f'<span style="flex:1">{next_company}</span>'
                f'</div>'
            ) + rows_html

        st.markdown(
            f'<div class="section-card" style="max-height:320px;overflow-y:auto;">'
            f'{rows_html}</div>',
            unsafe_allow_html=True,
        )

    if t.is_alive():
        time.sleep(0.5)
        st.rerun()
    else:
        st.session_state.crawl_running = False
        if shared.get("error"):
            st.session_state.crawl_error = shared["error"]
        else:
            st.session_state.crawl_error = None
        st.session_state.crawl_results = shared.get("results") or []
        st.progress(1.0)
        final_found = sum(1 for r in st.session_state.crawl_results if r.get("status") == "found")
        st.success(
            f"🌿 Crawl complete — **{final_found}** of **{n}** reports found."
        )
        st.rerun()

st.divider()

# ── Section 3 — Results ───────────────────────────────────────────────────────
st.header("3. Results")
if st.session_state.crawl_results:
    df = pd.DataFrame(st.session_state.crawl_results).copy()
    df["select"] = False
    # Display publication_year: None or 0 → "Unknown", valid years as string
    if "publication_year" in df.columns:
        df["publication_year"] = df["publication_year"].apply(
            lambda y: "Unknown" if (y is None or y == 0) else str(int(y))
        )

    # Colour-hint the status column label
    total = len(df)
    found_n = (df["status"] == "found").sum()
    notfound_n = (df["status"] == "not_found").sum()
    error_n = (df["status"] == "error").sum()
    st.markdown(
        f"""
        <div style="margin-bottom:8px;">
          <span class="stat-pill pill-found">✅ Found: {found_n}</span>
          <span class="stat-pill pill-notfound">🔍 Not found: {notfound_n}</span>
          <span class="stat-pill pill-error">❌ Error: {error_n}</span>
          <span class="stat-pill pill-total">Total: {total}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    edited = st.data_editor(
        df,
        column_config={
            "select": st.column_config.CheckboxColumn("Select", default=False),
            "company": st.column_config.TextColumn("Company"),
            "status": st.column_config.TextColumn("Status"),
            "publication_year": st.column_config.TextColumn("Publication year"),
            "pdf_url": st.column_config.LinkColumn("PDF URL"),
            "filename": st.column_config.TextColumn("Filename"),
        },
        column_order=["company", "status", "publication_year", "pdf_url", "filename", "select"],
        use_container_width=True,
        hide_index=True,
    )
    st.session_state._results_edited = edited
else:
    st.session_state._results_edited = None
    st.caption("Run the crawler to see results here.")
    edited = pd.DataFrame()

st.divider()

# ── Section 4 — Download ──────────────────────────────────────────────────────
st.header("4. Download Selected")
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
    zip_bytes = _cached_zip(tuple(selected_filenames), STORAGE_PATH) if can_download else b""
    st.download_button(
        f"⬇️ Download {len(selected_filenames)} report(s) as ZIP",
        data=zip_bytes,
        file_name="sustainability_reports.zip",
        mime="application/zip",
        disabled=not can_download,
    )
    if not can_download:
        st.caption("Select at least one row with status **found** to enable download.")
else:
    st.download_button(
        "⬇️ Download selected",
        data=b"",
        file_name="reports.zip",
        mime="application/zip",
        disabled=True,
    )
    st.caption("Run the crawler and select rows to enable download.")
