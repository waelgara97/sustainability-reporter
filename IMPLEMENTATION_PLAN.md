# Sustainability Report Crawler — Implementation Plan

**For:** Junior Engineer  
**Goal:** Build a local Streamlit app that takes a CSV of company names, crawls the web for their sustainability report PDFs, shows live progress, and lets the user download the ones they want.

---

## Before you start — what you need to know

### What this app does, end to end

1. User uploads a CSV file containing a list of company names
2. App reads the CSV and shows the companies in a table
3. User clicks "Run crawler"
4. For each company, the crawler searches the web, finds its sustainability report PDF URL, and downloads the PDF to a local folder on the machine
5. App shows live progress as each company is processed
6. When done, a results table appears showing which companies have a PDF and which don't
7. User selects rows with checkboxes and clicks "Download selected" to get a zip file of the chosen PDFs

### What you are NOT building

- No user login or accounts
- No database
- No cloud storage
- No React, no JavaScript, no separate frontend server
- No Docker

Everything runs on one machine, started with one command.

---

## Tech stack — what each tool does

| Tool | What it is | Why we use it |
|---|---|---|
| Python 3.11+ | Programming language | Everything is written in Python |
| Streamlit | Python library that creates a web UI | Lets us build the UI without writing any HTML or JavaScript |
| Crawlee | Python library for crawling websites | Handles retries, rate limiting, queue persistence, file downloads |
| BeautifulSoup4 | HTML parser | Reads HTML pages to find PDF links |
| httpx | HTTP client | Makes web requests inside Crawlee |
| pandas | Data library | Reads the CSV, builds the results table |
| uv | Package manager | Faster than pip, manages the virtual environment |

---

## Project structure

This is every file you will create. Nothing more.

```
sustainability-crawler/
│
├── app.py                          # The Streamlit UI — the only file the user runs
│
├── crawler/
│   ├── __init__.py                 # Empty file. Makes crawler a Python package.
│   ├── main.py                     # Starts the crawl for a list of companies
│   ├── router.py                   # Decides what to do with each URL
│   ├── handlers.py                 # Functions that process each type of page
│   └── detector.py                 # Logic that decides if a PDF is a sustainability report
│
├── utils/
│   ├── __init__.py                 # Empty file. Makes utils a Python package.
│   ├── csv_reader.py               # Reads and validates the uploaded CSV
│   └── zip_builder.py             # Packages selected PDFs into a zip for download
│
├── config.py                       # All settings in one place (keywords, timeouts, paths)
├── pyproject.toml                  # Project dependencies
├── .env                            # Secrets and environment variables (never commit this)
├── .gitignore                      # Files git should ignore
└── README.md                       # How to install and run the project
```

When the app runs, Crawlee will automatically create a `storage/` folder. Do not touch it — Crawlee manages it.

```
storage/                            # Auto-created by Crawlee at runtime
├── datasets/                       # Where structured results are saved
├── key_value_stores/               # Where downloaded PDFs are saved
└── request_queues/                 # Crawlee's internal queue state (enables resume)
```

---

## What each file does

### `app.py`

This is the entire frontend. It is a single Streamlit file.

It has four sections that render in order:

**Section 1 — Upload**
- A `st.file_uploader` component that accepts `.csv` files
- When a file is uploaded, call `csv_reader.py` to parse it
- Display the parsed companies in a `st.dataframe`
- Show a count of how many companies were loaded
- If the CSV has wrong columns or is empty, show an error with `st.error`

**Section 2 — Run**
- A `st.button("Start crawler")` that is disabled until a valid CSV is loaded
- When clicked, call `crawler/main.py` with the list of companies
- Show a `st.progress` bar and a `st.empty` text field that updates as each company finishes
- The crawler writes progress to a shared Python list or a `queue.Queue`. The UI reads from it on each rerun.

**Section 3 — Results**
- After the crawl finishes, show a `st.dataframe` with columns: `company`, `status`, `pdf_url`, `filename`
- `status` is either `found`, `not_found`, or `error`
- Add checkboxes using `st.data_editor` with a boolean column so the user can select rows

**Section 4 — Download**
- A `st.download_button` that calls `zip_builder.py` to create a zip of selected PDFs
- Only enabled when at least one row is selected

**Important note on Streamlit reruns:** Streamlit re-executes the entire `app.py` file from top to bottom every time the user interacts with the page. This means you cannot use regular Python variables to store state between interactions. Use `st.session_state` for anything that needs to persist — the company list, crawl results, selected rows.

---

### `crawler/main.py`

This is the entry point for the crawl logic. `app.py` calls this.

It does three things:

1. Takes a list of company names as input
2. For each company, constructs a search URL: `https://www.google.com/search?q={company}+sustainability+report+filetype:pdf`
3. Seeds those URLs into Crawlee's `RequestQueue` and starts the crawler

```python
# Signature the app.py will call
async def run_crawl(companies: list[str], progress_callback) -> list[dict]:
    """
    companies: list of company name strings from the CSV
    progress_callback: a function the crawler calls after each company finishes
                       so app.py can update the progress bar
    returns: list of result dicts with keys: company, status, pdf_url, filename
    """
```

The `progress_callback` is how the crawler talks back to the UI. After processing each company, call it with the result dict so Streamlit can update the progress bar.

---

### `crawler/router.py`

Crawlee lets you attach different handler functions to different URL patterns. This file sets that up.

There are three URL types to handle:

| URL pattern | What it is | Handler to call |
|---|---|---|
| `google.com/search` | Search results page | `handlers.handle_search_page` |
| URLs ending in `.pdf` | A direct PDF link | `handlers.handle_pdf_download` |
| Everything else | A company IR or sustainability page | `handlers.handle_ir_page` |

```python
from crawlee.crawlers import BeautifulSoupCrawler
from .handlers import handle_search_page, handle_ir_page, handle_pdf_download

def build_router():
    router = Router()
    router.add_handler(".*google\\.com/search.*", handle_search_page)
    router.add_handler(".*\\.pdf$", handle_pdf_download)
    router.default_handler(handle_ir_page)
    return router
```

---

### `crawler/handlers.py`

Three async functions, one per URL type.

**`handle_search_page(context)`**
- Receives a BeautifulSoup-parsed Google search results page
- Finds all `<a>` links in the results
- For each link, call `detector.score_link(url, anchor_text)`
- If score is above the threshold in `config.py`, add that URL to the queue with `context.add_requests()`
- Cap at 3 candidate links per company to avoid crawling the entire web

**`handle_ir_page(context)`**
- Receives a parsed HTML page (a company's investor relations or sustainability page)
- Finds all `<a>` tags with `href` attributes
- For each link, call `detector.score_link(url, anchor_text)`
- If it ends in `.pdf` and scores above threshold, add it to the queue
- If it looks like a sub-page (e.g. `/sustainability/reports`), add it to the queue for further crawling
- Set a `max_crawl_depth` from `config.py` so it does not crawl forever

**`handle_pdf_download(context)`**
- Receives a response where the content type is `application/pdf`
- Checks the file size — skip anything under 100KB (too small to be a real report) or over 200MB (something is wrong)
- Save the PDF using Crawlee's `KeyValueStore`: `await context.key_value_store.set_value(filename, content, content_type="application/pdf")`
- Write a result row to Crawlee's `Dataset`: `await context.push_data({company, pdf_url, filename, status: "found"})`
- Call `progress_callback` with the result

---

### `crawler/detector.py`

One function that scores a URL and its anchor text.

```python
def score_link(url: str, anchor_text: str) -> int:
    """
    Returns an integer score. Higher = more likely to be a sustainability report.
    The threshold for "good enough" is set in config.py (default: 2).
    """
```

Scoring rules — each matching rule adds points:

| Rule | Points |
|---|---|
| URL contains `sustainability` | +3 |
| URL contains `esg` | +3 |
| URL contains `csr` | +2 |
| URL contains `responsibility` | +2 |
| URL contains `climate` | +1 |
| URL contains `environment` | +1 |
| URL ends in `.pdf` | +2 |
| Anchor text contains `sustainability report` | +3 |
| Anchor text contains `annual report` | +1 |
| URL contains a 4-digit year (2018–2025) | +1 |
| URL contains `annual-report` | +1 |

This is a points system, not a rigid filter. A link with `sustainability-report-2024.pdf` in the URL would score 3+2+2+1 = 8, well above the threshold.

---

### `utils/csv_reader.py`

One function:

```python
def read_companies_csv(uploaded_file) -> tuple[list[str], str | None]:
    """
    uploaded_file: the object from st.file_uploader
    Returns: (list of company name strings, error message or None)
    
    Validation rules:
    - File must not be empty
    - Must have at least one column
    - The column containing company names must be called 'company' or 'Company' or 'name' or 'Name'
    - Strip leading/trailing whitespace from each company name
    - Skip rows where the company name is blank
    - Return an error string (not an exception) if any rule fails
    """
```

The function returns a tuple so `app.py` can handle errors cleanly without try/except:

```python
companies, error = read_companies_csv(uploaded_file)
if error:
    st.error(error)
else:
    st.session_state.companies = companies
```

---

### `utils/zip_builder.py`

One function:

```python
def build_zip(selected_filenames: list[str], storage_path: str) -> bytes:
    """
    selected_filenames: list of PDF filenames the user checked
    storage_path: path to where Crawlee saved the PDFs (from config.py)
    Returns: zip file as bytes, ready to pass to st.download_button
    """
```

Use Python's built-in `zipfile` module. No extra dependencies needed.

---

### `config.py`

All tuneable settings in one place. When something needs to change (too slow, too fast, missing reports), this is the only file to edit.

```python
# Paths
STORAGE_PATH = "./storage/key_value_stores/default"
RESULTS_PATH = "./storage/datasets/default"

# Crawler behaviour
MAX_CONCURRENCY = 5           # Max simultaneous requests. Keep low to be respectful.
REQUEST_TIMEOUT_SECS = 30     # Give up on a page after this many seconds
MAX_CRAWL_DEPTH = 2           # How many links deep to follow from a company's homepage
MAX_CANDIDATES_PER_COMPANY = 3  # Max PDF candidates to try per company

# Detection
SCORE_THRESHOLD = 2           # Minimum score from detector.py to enqueue a link

# Rate limiting
MIN_CRAWL_DELAY_SECS = 1.0    # Wait at least this long between requests to the same domain

# Search
SEARCH_QUERY_TEMPLATE = "{company} sustainability report filetype:pdf {year}"
CURRENT_YEAR = 2024
```

---

### `pyproject.toml`

```toml
[project]
name = "sustainability-crawler"
version = "0.1.0"
requires-python = ">=3.11"

[project.dependencies]
streamlit = ">=1.32.0"
crawlee = { version = ">=1.3.0", extras = ["beautifulsoup"] }
pandas = ">=2.0.0"
python-dotenv = ">=1.0.0"
```

---

### `.env`

```
# Add any API keys here if needed later (e.g. for a search API)
# Do not commit this file to git
```

---

### `.gitignore`

```
.env
storage/
__pycache__/
.venv/
*.pyc
downloads/
```

---

### `README.md`

Write this after everything works. It should contain exactly:
1. One-line description of what the app does
2. Prerequisites (Python 3.11+, uv)
3. Install commands
4. Run command
5. What the CSV must look like (with an example)

---

## Implementation order

Do not skip steps or build out of order. Each step builds on the last.

### Step 1 — Environment setup (Day 1, ~2 hours)

Install `uv` if not already installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Create the project:
```bash
mkdir sustainability-crawler
cd sustainability-crawler
uv init
uv add streamlit crawlee[beautifulsoup] pandas python-dotenv
```

Create every file and folder from the project structure above. All the Python files can be empty for now — just create them so the imports work.

Verify your environment works:
```bash
uv run streamlit hello
```
If a browser opens with the Streamlit demo page, you are set up correctly.

---

### Step 2 — CSV reader and basic UI (Day 1, ~3 hours)

Build `utils/csv_reader.py` first and test it in isolation before touching the UI.

Create a test CSV file:
```
company
Shell
Unilever
Danone
TotalEnergies
```

Write `csv_reader.py` and test it manually from a Python shell:
```python
# In a Python shell
from utils.csv_reader import read_companies_csv
# Pass a file-like object
```

Then build the first two sections of `app.py` — the upload section and the company preview table. At this point the "Start crawler" button should appear but do nothing when clicked.

Run it:
```bash
uv run streamlit run app.py
```

You should see a working file uploader. Upload your test CSV and confirm the companies appear in the table.

**Do not proceed until this works.**

---

### Step 3 — Detector (Day 2, ~2 hours)

Build `crawler/detector.py` with the scoring function.

Test it before connecting it to anything else:
```python
from crawler.detector import score_link

# Should return a high score
print(score_link("https://shell.com/sustainability-report-2024.pdf", "Download PDF"))

# Should return 0 or very low
print(score_link("https://shell.com/careers/jobs", "Apply now"))
```

Adjust keyword weights until sensible links score above 2 and irrelevant links score 0–1.

---

### Step 4 — Handlers and router (Day 2–3, ~4 hours)

Build `crawler/handlers.py`. Start with just `handle_pdf_download` — it is the simplest.

Test `handle_pdf_download` by hardcoding a known PDF URL and running the crawler against it directly (not through the UI yet).

Then build `handle_search_page` and `handle_ir_page`.

Build `crawler/router.py` to wire the handlers to URL patterns.

---

### Step 5 — Main crawler entry point (Day 3, ~3 hours)

Build `crawler/main.py`. Connect it to the router and handlers.

Test the end-to-end crawl from a Python script (not the UI yet):

```python
# test_crawl.py — run this directly to test the crawler
import asyncio
from crawler.main import run_crawl

results = asyncio.run(run_crawl(["Shell", "Unilever"], progress_callback=print))
print(results)
```

Check the `storage/` folder. You should see PDFs appearing.

**Do not proceed until at least 1 out of 2 test companies produces a PDF.**

---

### Step 6 — Connect crawler to UI (Day 4, ~3 hours)

Now wire `app.py` to `crawler/main.py`.

The main challenge here is that Crawlee is `async` but Streamlit is synchronous. You need to run the async crawl in a thread. Use this pattern:

```python
import asyncio
import threading

def run_in_thread(companies, callback):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_crawl(companies, callback))

thread = threading.Thread(target=run_in_thread, args=(companies, callback))
thread.start()
```

Add the progress bar to `app.py`. Use `st.session_state` to store results as they come in.

---

### Step 7 — Results table and download (Day 4–5, ~3 hours)

Build the results section in `app.py`:
- Show the results table with `st.data_editor` and a boolean checkbox column
- Wire the "Download selected" button to `zip_builder.py`
- Test the full flow: upload CSV → run → check boxes → download zip → open the zip and verify the PDFs are there

---

### Step 8 — Cleanup and README (Day 5, ~2 hours)

- Remove any hardcoded values and move them to `config.py`
- Make sure the app handles error cases gracefully: what if a company has no results? What if a PDF download fails? The app must not crash — it should show `not_found` in the results table and continue
- Write `README.md`
- Test the full flow with a list of 10 real companies

---

## Common mistakes to avoid

**Don't store state in regular Python variables in `app.py`.** Streamlit reruns the entire file on every interaction. Use `st.session_state` for anything that needs to survive between interactions.

**Don't run the async crawler directly in `app.py`.** Wrap it in a thread as shown in Step 6.

**Don't crawl too aggressively.** Keep `MAX_CONCURRENCY` at 5 or below. Add the `MIN_CRAWL_DELAY_SECS`. Hammering websites will get you blocked and is disrespectful.

**Don't skip the intermediate tests.** The instruction to test each module before connecting it to the next is not optional. Debugging a broken file upload + broken CSV reader + broken crawler all at once is much harder than debugging each in isolation.

**Don't hardcode company names or URLs in the code.** Everything must flow from the CSV input.

---

## Definition of done

The implementation is complete when:

- [ ] A user can drag and drop a CSV onto the app and see their company list load
- [ ] Clicking "Start crawler" shows a live progress indicator that updates per company
- [ ] After completion, a results table shows `found` or `not_found` for each company
- [ ] Checking rows and clicking download produces a valid zip file containing the PDFs
- [ ] Running the app on 10 companies finds PDFs for at least 6 of them
- [ ] The app does not crash if a company has no results or a download fails
- [ ] All settings are in `config.py` and not scattered through the code
