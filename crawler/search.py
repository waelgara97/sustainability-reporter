"""
Brave Search API helper.

Uses the official Brave Search API to find sustainability report URLs.

Required env var (set in .env):
    BRAVE_API_KEY  — from https://api-dashboard.search.brave.com/

Free tier: ~1,000 queries/month ($5 credit at $5/1,000 queries).
Each call to brave_search() uses 1 query.
"""

import logging

import httpx

from config import (
    BRAVE_API_KEY,
    BRAVE_SEARCH_NUM_RESULTS,
    CURRENT_YEAR,
    MAX_CANDIDATES_PER_COMPANY,
    SEARCH_QUERY_TEMPLATE,
    USER_AGENT,
)
from crawler.detector import extract_publication_year, score_link

logger = logging.getLogger(__name__)

_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _check_credentials() -> None:
    """Raise a clear error early if the API key is missing."""
    if not BRAVE_API_KEY:
        raise EnvironmentError(
            "BRAVE_API_KEY is not set. "
            "Get a free key at https://api-dashboard.search.brave.com/ and add it to your .env file."
        )


async def brave_search(company: str, client: httpx.AsyncClient) -> list[dict]:
    """
    Query the Brave Search API for sustainability report URLs for *company*.

    One search call per company. Uses a rolling 3-year freshness window.
    Returns a list of dicts with url, title, description, score, publication_year,
    sorted by publication_year desc (None as 0), then score desc, limited to
    MAX_CANDIDATES_PER_COMPANY. Returns empty list on API error.
    """
    q = SEARCH_QUERY_TEMPLATE.format(company=company)
    freshness_range = f"{CURRENT_YEAR - 4}-01-01to{CURRENT_YEAR}-12-31"
    params = {
        "q": q,
        "count": BRAVE_SEARCH_NUM_RESULTS,
        "search_lang": "en",
        "result_filter": "web",
        "freshness": freshness_range,
    }
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
        "User-Agent": USER_AGENT,
    }
    try:
        response = await client.get(
            _SEARCH_ENDPOINT,
            params=params,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Brave API HTTP error for %r: %s", company, exc)
        return []
    except Exception as exc:
        logger.warning("Brave API request failed for %r: %s", company, exc)
        return []

    raw_items = (data.get("web") or {}).get("results") or []

    results = []
    for item in raw_items:
        url = item.get("url", "").strip()
        title = item.get("title", "") or ""
        description = item.get("description", "") or ""
        if not url:
            continue
        snippet = f"{title} {description}".strip()
        score = score_link(url, snippet)
        publication_year = extract_publication_year(url, snippet)
        results.append({
            "url": url,
            "title": title,
            "description": description,
            "score": score,
            "publication_year": publication_year,
        })

    # Sort: primary publication_year descending (None as 0), secondary score descending
    results.sort(key=lambda x: (-(x["publication_year"] or 0), -x["score"]))
    limited = results[:MAX_CANDIDATES_PER_COMPANY]
    logger.info("Search for %r: %s results", company, len(limited))
    return limited
