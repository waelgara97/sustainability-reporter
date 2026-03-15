"""Crawler entry point: uses Google Custom Search API to find URLs, then crawls them."""

import asyncio
import logging
from datetime import timedelta

import httpx
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler

from config import (
    MAX_CONCURRENCY,
    MAX_CRAWL_DEPTH,
    MIN_CRAWL_DELAY_SECS,
    REQUEST_TIMEOUT_SECS,
    USER_AGENT,
    SCORE_THRESHOLD,
)
from crawler.handlers import set_progress_callback, _invoke_progress
from crawler.router import build_router
from crawler.search import _check_credentials, google_search
from crawler.detector import score_link

logger = logging.getLogger(__name__)


async def run_crawl(companies: list[str], progress_callback) -> list[dict]:
    """
    Run the full crawl pipeline for the given companies.

    1. Validates that Google API credentials are present (fails fast with a clear message).
    2. Calls the Google Custom Search API for each company to get candidate URLs.
    3. Seeds those URLs into BeautifulSoupCrawler (no google.com scraping).
    4. Crawler follows IR pages and downloads PDFs.
    5. Returns one result dict per company: {company, status, pdf_url, filename}.

    companies         — list of company name strings from the CSV
    progress_callback — called with a result dict after each company completes
    """
    # Fail fast if credentials are missing — much better than a silent empty run
    _check_credentials()

    set_progress_callback(progress_callback)

    # ── Step 1: Google Custom Search API ──────────────────────────────────────
    # Run all search queries in parallel to save time; one query per company.
    async with httpx.AsyncClient(follow_redirects=True) as client:
        search_results: list[list[str]] = await asyncio.gather(
            *[google_search(c, client) for c in companies],
            return_exceptions=False,  # exceptions return [] from google_search itself
        )

    # ── Step 2: Build initial request queue ───────────────────────────────────
    # google_search() already scored+sorted the URLs.  We pick the top
    # MAX_CANDIDATES_PER_COMPANY that clear SCORE_THRESHOLD, label them,
    # and attach the company name via user_data.
    initial_requests: list[Request] = []
    companies_with_no_hits: list[str] = []

    for company, urls in zip(companies, search_results):
        if not urls:
            companies_with_no_hits.append(company)
            continue

        added = 0
        from config import MAX_CANDIDATES_PER_COMPANY  # local import avoids circular
        for url in urls:
            if added >= MAX_CANDIDATES_PER_COMPANY:
                break
            label = "pdf" if url.lower().rstrip("/").endswith(".pdf") else "ir"
            initial_requests.append(
                Request.from_url(
                    url,
                    label=label,
                    user_data={"company": company},
                    headers={"User-Agent": USER_AGENT},
                )
            )
            added += 1

        if added == 0:
            companies_with_no_hits.append(company)

    # Report companies the API returned no usable URLs for
    for company in companies_with_no_hits:
        _invoke_progress({"company": company, "status": "not_found", "pdf_url": "", "filename": ""})

    # ── Step 3: Run the crawler ───────────────────────────────────────────────
    if initial_requests:
        router = build_router()
        crawler = BeautifulSoupCrawler(
            request_handler=router,
            max_concurrency=MAX_CONCURRENCY,
            min_concurrency=1,
            navigation_timeout=timedelta(seconds=REQUEST_TIMEOUT_SECS),
            max_crawl_depth=MAX_CRAWL_DEPTH,
            use_session_pool=True,
            retry_on_blocked=True,
        )
        await crawler.run(initial_requests)

        # ── Step 4: Collect results from the dataset ──────────────────────────
        dataset = await crawler.get_dataset()
        page = await dataset.get_data(limit=10_000)
        items = page.items  # DatasetItemsListPage → .items is a plain list

        results_by_company: dict[str, dict] = {}
        for item in items:
            c = item.get("company")
            if not c:
                continue
            # Prefer "found" over any earlier entry for the same company
            if item.get("status") == "found" or c not in results_by_company:
                results_by_company[c] = item
    else:
        results_by_company = {}

    # ── Step 5: Build final result list in input order ────────────────────────
    all_results: list[dict] = []
    for c in companies:
        all_results.append(
            results_by_company.get(
                c,
                {"company": c, "status": "not_found", "pdf_url": "", "filename": ""},
            )
        )
    return all_results
