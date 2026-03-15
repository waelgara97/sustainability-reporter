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
    SEARCH_QUERY_TEMPLATE,
    USER_AGENT,
)
from crawler.detector import score_link

logger = logging.getLogger(__name__)

_SEARCH_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


def _check_credentials() -> None:
    """Raise a clear error early if the API key is missing."""
    if not BRAVE_API_KEY:
        raise EnvironmentError(
            "BRAVE_API_KEY is not set. "
            "Get a free key at https://api-dashboard.search.brave.com/ and add it to your .env file."
        )


async def brave_search(company: str, client: httpx.AsyncClient) -> list[str]:
    """
    Query the Brave Search API for sustainability report URLs for *company*.

    Returns a list of URLs sorted by relevance score (highest first).
    Returns an empty list on API error (logged, not raised) so the caller
    can record a 'not_found' result and move on.
    """
    query = SEARCH_QUERY_TEMPLATE.format(company=company, year=CURRENT_YEAR)
    params = {
        "q": query,
        "count": BRAVE_SEARCH_NUM_RESULTS,
        "search_lang": "en",
        "result_filter": "web",
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

    # Score and sort so the most likely sustainability-report URLs come first
    scored = []
    for item in raw_items:
        url = item.get("url", "").strip()
        title = item.get("title", "")
        description = item.get("description", "")
        if not url:
            continue
        anchor_text = f"{title} {description}"
        scored.append((score_link(url, anchor_text), url))

    scored.sort(key=lambda x: -x[0])
    return [url for _score, url in scored]
