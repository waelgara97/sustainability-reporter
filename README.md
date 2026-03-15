# Sustainability Report Crawler

A local Streamlit app that takes a CSV of company names, crawls the web for their sustainability report PDFs, shows progress, and lets you download selected reports as a zip.

## Prerequisites

- **Python 3.11+**
- **uv** (recommended) or **pip**

To install uv (optional):

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Install

From the project root:

**With uv:**

```bash
uv sync
```

**With pip:**

On Windows, if you have multiple Python versions, create the venv with 3.11+ explicitly (e.g. `py -3.11` or `py -3.13`). If the default `python` is 3.9, the app will not start.

```bash
# Windows (use explicit version if you have 3.9 and 3.11+ installed)
py -3.11 -m venv .venv
# or: py -3.13 -m venv .venv

# macOS/Linux, or when python is already 3.11+
python -m venv .venv

.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

## Run

```bash
# With uv
uv run streamlit run app.py

# With pip (activate venv first)
streamlit run app.py
```

A browser window will open. Upload a CSV, click "Start crawler", then select rows and use "Download selected" to get a zip of the PDFs.

## CSV format

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

## Troubleshooting

### "streamlit is not recognized" or "uv is not recognized"
- **Streamlit**: Use the module form: `python -m streamlit run app.py` (after activating your venv). If that fails, you don’t have Streamlit installed—see Install above.
- **uv**: Install [uv](https://docs.astral.sh/uv/getting-started/installation/) or use **pip** instead (create a venv and `pip install -r requirements.txt`).

### "cannot import name 'TypeAlias' from 'typing'" or app fails to start
Your venv was created with **Python 3.9**. This project needs **Python 3.10+** (3.11+ recommended). Recreate the venv with a newer Python—see the Install section (use `py -3.11 -m venv .venv` or `py -3.13 -m venv .venv` on Windows).

### "Could not find a version that satisfies the requirement crawlee[beautifulsoup]>=1.3.0"
You need **Python 3.10 or 3.11+**. Crawlee 1.x does not support Python 3.9.

- Check version: `python --version` or `py -0p`
- Install Python 3.11: [python.org](https://www.python.org/downloads/) or `winget install Python.Python.3.11`
- Create a venv with that version and reinstall:
  ```powershell
  py -3.11 -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  streamlit run app.py
  ```

### Run script (Windows)
From the project folder in PowerShell:
```powershell
.\run.ps1
```
This uses Python 3.11 if available; otherwise it prints what to install.

