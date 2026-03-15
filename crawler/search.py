"""
Google Custom Search JSON API helper.

Uses the official API instead of scraping google.com directly.
Scraping Google is unreliable (JS rendering, CAPTCHAs, IP bans, ToS violation).

Required env vars (set in .env):
    GOOGLE_API_KEY  — from https://console.cloud.google.com/ → Credentials
    GOOGLE_CSE_ID   — from https://programmablesearchengine.google.com/

Free tier: 100 queries/day. Each call to google_search() uses 1 query.
"""

import logging

import httpx

from config import (
    CURRENT_YEAR,
    GOOGLE_API_KEY,
    GOOGLE_CSE_ID,
    GOOGLE_SEARCH_NUM_RESULTS,
    SEARCH_QUERY_TEMPLATE,
    USER_AGENT,
)
from crawler.detector import score_link

logger = logging.getLogger(__name__)

_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


def _check_credentials() -> None:
    """Raise a clear error early if API credentials are missing."""
    if not GOOGLE_API_KEY:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Create a key at https://console.cloud.google.com/ and add it to your .env file."
        )
    if not GOOGLE_CSE_ID:
        raise EnvironmentError(
            "GOOGLE_CSE_ID is not set. "
            "Create a Custom Search Engine at https://programmablesearchengine.google.com/ "
            "and add its ID to your .env file."
        )


async def google_search(company: str, client: httpx.AsyncClient) -> list[str]:
    """
    Query the Google Custom Search API for sustainability report URLs for *company*.

    Returns a list of URLs sorted by relevance score (highest first), capped at
    GOOGLE_SEARCH_NUM_RESULTS. Returns an empty list on API error (logged, not raised)
    so the caller can record a 'not_found' result and move on.
    """
    query = SEARCH_QUERY_TEMPLATE.format(company=company, year=CURRENT_YEAR)
    params = {
        "q": query,
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "num": GOOGLE_SEARCH_NUM_RESULTS,
    }
    try:
        response = await client.get(
            _SEARCH_ENDPOINT,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("Google API HTTP error for %r: %s", company, exc)
        return []
    except Exception as exc:
        logger.warning("Google API request failed for %r: %s", company, exc)
        return []

    raw_items = data.get("items") or []

    # Score and sort so the most likely sustainability-report URLs come first
    scored = []
    for item in raw_items:
        url = item.get("link", "").strip()
        title = item.get("title", "")
        snippet = item.get("snippet", "")
        if not url:
            continue
        anchor_text = f"{title} {snippet}"
        scored.append((score_link(url, anchor_text), url))

    scored.sort(key=lambda x: -x[0])
    return [url for _score, url in scored]
