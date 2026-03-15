# Sustainability Report Crawler

A local Streamlit app that takes a CSV of company names, crawls the web for their sustainability report PDFs, shows progress, and lets you download selected reports as a zip.

## Quick Start (Windows)

Open PowerShell in the project folder and run:

```powershell
.\run.ps1
```

That's it. The script installs **uv** (if missing), which then automatically downloads Python, creates the virtual environment, installs all dependencies, and starts the app.

A browser window will open at `http://localhost:8501`.

## Manual Start

If you prefer to run the command yourself:

```bash
uv run streamlit run app.py
```

`uv run` handles Python, the virtual environment, and dependency installation in one step. If you don't have `uv`, install it first:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Configuration

Copy `.env.example` to `.env` and fill in your Brave Search API key:

```
BRAVE_API_KEY=your_brave_api_key_here
```

Get a free key at https://api-dashboard.search.brave.com/ (free tier: ~1,000 queries/month).

## CSV Format

The CSV must have a column named **company**, **Company**, **name**, or **Name** with one company name per row.

Example `companies.csv`:

```csv
company
Shell
Unilever
Danone
TotalEnergies
```

Save as UTF-8. Empty rows are skipped.

## Usage

1. Upload a CSV with company names.
2. Click **Start Crawler**.
3. Select rows in the results table and click **Download selected** to get a zip of the PDFs.

## Debugging

- **Console logging** — Log messages are printed to the terminal. You'll see steps like "Credentials OK", "Quota check OK", "Brave search done", "Crawler run finished", and "Crawl complete" with counts. Any exception in the crawler is logged with a full traceback.
- **Persisted error in the UI** — If the crawl fails (e.g. missing API key, quota exceeded, network error), the error message is stored and shown in **Section 2 (Run Crawler)** so it doesn't disappear after the page refreshes.
- **Log level** — Set `LOG_LEVEL=DEBUG` in your `.env` for more verbose logs (e.g. per-company search results). Default is `INFO`.
- **Log file** — Logs are also written to `logs/app.log` in the project folder (rotating, up to 3 backup files).

Where to look when something goes wrong: check the **red error box** in Section 2, then the **terminal** or **logs/app.log** for the full traceback and step-by-step messages.

## Without uv (advanced)

If you cannot use `uv`, you can set up a virtual environment manually:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
streamlit run app.py
```

Requires **Python 3.11+**.
