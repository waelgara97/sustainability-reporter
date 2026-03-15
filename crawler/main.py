"""Crawler entry point: uses Brave Search API to find URLs, then crawls them."""

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
)
from crawler.handlers import completed_companies, set_progress_callback, _invoke_progress
from crawler.router import build_router
from crawler.search import _check_credentials, brave_search
from utils.quota import check_quota, record_queries

logger = logging.getLogger(__name__)


async def run_crawl(companies: list[str], progress_callback) -> list[dict]:
    """
    Run the full crawl pipeline for the given companies.

    1. Validates that Brave API key is present (fails fast with a clear message).
    2. Checks monthly quota — raises RuntimeError if batch would exceed the limit.
    3. Calls the Brave Search API for each company to get candidate URLs.
    4. Records the queries used against the monthly quota.
    5. Seeds those URLs into BeautifulSoupCrawler.
    6. Crawler follows IR pages and downloads PDFs.
    7. Returns one result dict per company: {company, status, pdf_url, filename}.

    companies         — list of company name strings from the CSV
    progress_callback — called with a result dict after each company completes
    """
    # Fail fast if credentials are missing
    _check_credentials()
    logger.info("Credentials OK")

    # Fail fast if this batch would exceed the monthly quota
    check_quota(len(companies))
    logger.info("Quota check OK, %s queries will be used", len(companies))

    set_progress_callback(progress_callback)
    completed_companies.clear()
    logger.info("Starting crawl for %s companies", len(companies))

    # ── Step 1: Brave Search API ───────────────────────────────────────────────
    # Run search queries sequentially with a 1.1-second pause between them.
    # Brave's free tier enforces 1 request/second; parallel calls cause 429 errors.
    async with httpx.AsyncClient(follow_redirects=True) as client:
        search_results: list[list[dict]] = []
        for i, company in enumerate(companies):
            result = await brave_search(company, client)
            search_results.append(result)
            if i < len(companies) - 1:
                await asyncio.sleep(1.1)

    # Record queries used (do this after the API calls succeed)
    record_queries(len(companies))
    total_candidates = sum(len(items) for items in search_results)
    logger.info("Brave search done: %s candidate URLs for %s companies", total_candidates, len(companies))

    # ── Step 2: Build initial request queue ───────────────────────────────────
    # brave_search() returns sorted list[dict] (url, publication_year, ...) per company.
    # Enqueue each candidate with user_data for short-circuit and aggregation.
    initial_requests: list[Request] = []
    companies_with_no_hits: list[str] = []

    for company, items in zip(companies, search_results):
        if not items:
            companies_with_no_hits.append(company)
            continue

        for item in items:
            url = item["url"]
            label = "pdf" if url.lower().rstrip("/").endswith(".pdf") else "ir"
            initial_requests.append(
                Request.from_url(
                    url,
                    label=label,
                    user_data={
                        "company": company,
                        "publication_year": item.get("publication_year"),
                    },
                    headers={"User-Agent": USER_AGENT},
                )
            )

    # Report companies the API returned no usable URLs for
    for company in companies_with_no_hits:
        _invoke_progress({
            "company": company, "status": "not_found", "pdf_url": "", "filename": "",
            "publication_year": None,
        })

    # ── Step 3: Run the crawler ───────────────────────────────────────────────
    if initial_requests:
        logger.info("Starting crawler for %s requests", len(initial_requests))
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
        logger.info("Crawler run finished")

        # ── Step 4: Collect results from the dataset ──────────────────────────
        dataset = await crawler.get_dataset()
        page = await dataset.get_data(limit=10_000)
        items = page.items  # DatasetItemsListPage → .items is a plain list

        results_by_company: dict[str, dict] = {}
        for item in items:
            c = item.get("company")
            if not c:
                continue
            existing = results_by_company.get(c)
            # Exactly one entry per company: prefer "found", then by max publication_year
            if item.get("status") == "found":
                if existing is None or existing.get("status") != "found":
                    results_by_company[c] = item
                else:
                    # Keep the one with higher publication_year
                    ey = existing.get("publication_year") or 0
                    iy = item.get("publication_year") or 0
                    if iy > ey:
                        results_by_company[c] = item
            elif c not in results_by_company:
                results_by_company[c] = item
    else:
        results_by_company = {}

    # ── Step 5: Build final result list in input order ────────────────────────
    all_results: list[dict] = []
    for c in companies:
        r = results_by_company.get(c)
        if r is not None and "publication_year" not in r:
            r = {**r, "publication_year": None}
        all_results.append(
            r
            if r is not None
            else {"company": c, "status": "not_found", "pdf_url": "", "filename": "", "publication_year": None},
        )
    found_n = sum(1 for r in all_results if r.get("status") == "found")
    not_found_n = sum(1 for r in all_results if r.get("status") == "not_found")
    error_n = sum(1 for r in all_results if r.get("status") == "error")
    logger.info("Crawl complete — found: %s, not_found: %s, error: %s", found_n, not_found_n, error_n)
    return all_results
