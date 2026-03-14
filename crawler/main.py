"""Crawler entry point: seeds search URLs and runs the crawl."""

from datetime import timedelta
from urllib.parse import quote_plus

from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawler

from config import (
    MAX_CONCURRENCY,
    MAX_CRAWL_DEPTH,
    REQUEST_TIMEOUT_SECS,
    SEARCH_QUERY_TEMPLATE,
    CURRENT_YEAR,
)
from crawler.handlers import set_progress_callback
from crawler.router import build_router


def _search_url(company: str) -> str:
    query = SEARCH_QUERY_TEMPLATE.format(company=company, year=CURRENT_YEAR)
    return f"https://www.google.com/search?q={quote_plus(query)}"


async def run_crawl(companies: list[str], progress_callback) -> list[dict]:
    """
    Run the crawler for the given companies.

    companies: list of company name strings from the CSV
    progress_callback: called after each company finishes with a result dict
    returns: list of result dicts with keys: company, status, pdf_url, filename
    """
    set_progress_callback(progress_callback)

    initial_requests = [
        Request.from_url(_search_url(c), label="search", company=c)
        for c in companies
    ]

    router = build_router()
    crawler = BeautifulSoupCrawler(
        request_handler=router,
        navigation_timeout=timedelta(seconds=REQUEST_TIMEOUT_SECS),
        max_crawl_depth=MAX_CRAWL_DEPTH,
    )

    await crawler.run(initial_requests)

    # Collect all items from the default dataset
    dataset = await crawler.get_dataset()
    items = await dataset.list_items(limit=10_000)

    # Prefer "found" result per company; fill not_found for the rest
    results_by_company = {}
    for item in items:
        c = item.get("company")
        if not c:
            continue
        if item.get("status") == "found":
            results_by_company[c] = item
        elif c not in results_by_company:
            results_by_company[c] = item

    all_results = []
    for c in companies:
        all_results.append(results_by_company.get(c, {
            "company": c,
            "status": "not_found",
            "pdf_url": "",
            "filename": "",
        }))

    return all_results
