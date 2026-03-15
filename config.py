import os

from dotenv import load_dotenv

load_dotenv()

# ── Brave Search API credentials (required) ───────────────────────────────────
# Obtain a key: https://api-dashboard.search.brave.com/
# Free tier:    ~1,000 queries/month ($5 credit at $5/1,000 queries).
BRAVE_API_KEY: str = os.environ.get("BRAVE_API_KEY", "")
BRAVE_SEARCH_NUM_RESULTS: int = 5  # results returned per company (max 20 per API call)

# ── Monthly quota guard ───────────────────────────────────────────────────────
# Hard stop below the free-tier limit to avoid surprise charges.
# Free tier: ~1,000 queries/month.  We stop at 950 to keep a safety buffer.
MONTHLY_QUERY_LIMIT: int = 950       # hard stop — run is refused above this
QUOTA_WARNING_THRESHOLD: int = 800   # UI warning shown above this

# ── Paths ─────────────────────────────────────────────────────────────────────
STORAGE_PATH = "./storage/key_value_stores/default"
RESULTS_PATH = "./storage/datasets/default"

# ── Crawler behaviour ─────────────────────────────────────────────────────────
MAX_CONCURRENCY = 5       # Max simultaneous requests. Keep low to be respectful.
REQUEST_TIMEOUT_SECS = 30  # Give up on a page after this many seconds
MAX_CRAWL_DEPTH = 2        # How many links deep to follow from a company's homepage
MAX_CANDIDATES_PER_COMPANY = 3  # Max PDF candidates to try per company

# ── Detection ─────────────────────────────────────────────────────────────────
SCORE_THRESHOLD = 2  # Minimum score from detector.py to enqueue a link

# ── Rate limiting ─────────────────────────────────────────────────────────────
MIN_CRAWL_DELAY_SECS = 1.0  # Wait at least this long between requests to the same domain

# ── Search query ──────────────────────────────────────────────────────────────
SEARCH_QUERY_TEMPLATE = "{company} sustainability report filetype:pdf {year}"
CURRENT_YEAR = 2024

# ── PDF size limits (bytes) ───────────────────────────────────────────────────
MIN_PDF_SIZE_BYTES = 100 * 1024        # 100 KB — too small to be a real report
MAX_PDF_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB — something is wrong

# ── HTTP ──────────────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
