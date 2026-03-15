"""Handlers for IR/sustainability pages and PDF downloads.

Note: there is no handle_search_page here. Google search is performed via the
Custom Search JSON API (crawler/search.py) before the crawler starts, so
google.com URLs are never placed in the crawlee queue.
"""

import asyncio
import os
import re
from urllib.parse import urljoin

import httpx
from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawlingContext

from config import (
    MAX_CANDIDATES_PER_COMPANY,
    MAX_CRAWL_DEPTH,
    MAX_PDF_SIZE_BYTES,
    MIN_CRAWL_DELAY_SECS,
    MIN_PDF_SIZE_BYTES,
    SCORE_THRESHOLD,
    STORAGE_PATH,
    USER_AGENT,
)
from crawler.detector import score_link

# Set by main.run_crawl() before starting; handlers call it when a company result is ready
_progress_callback = None

# Companies for which we already successfully downloaded a PDF; main clears before each run
completed_companies: set[str] = set()


def set_progress_callback(callback):
    global _progress_callback
    _progress_callback = callback


def _get_company(context: BeautifulSoupCrawlingContext) -> str:
    """Get company name from request user_data."""
    ud = context.request.user_data or {}
    return ud.get("company", "") or ""


def _invoke_progress(result: dict) -> None:
    if _progress_callback:
        try:
            _progress_callback(result)
        except Exception:
            pass


async def handle_ir_page(context: BeautifulSoupCrawlingContext) -> None:
    """Parse IR/sustainability HTML page; enqueue PDF links and sub-pages up to MAX_CRAWL_DEPTH."""
    await asyncio.sleep(MIN_CRAWL_DELAY_SECS)

    company = _get_company(context)
    soup = getattr(context, "soup", None)
    if not soup:
        return

    depth = getattr(context.request, "crawl_depth", 0)
    if depth >= MAX_CRAWL_DEPTH:
        return

    base_url = context.request.url
    requests_to_add = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        full_url = urljoin(base_url, href)
        if not full_url.startswith("http"):
            continue
        text = (a.get_text() or "").strip()
        score = score_link(full_url, text)
        if score < SCORE_THRESHOLD:
            continue
        label = "pdf" if full_url.lower().rstrip("/").endswith(".pdf") else "ir"
        req = Request.from_url(
            full_url,
            label=label,
            user_data={"company": company},
            headers={"User-Agent": USER_AGENT},
        )
        requests_to_add.append(req)

    await context.add_requests(requests_to_add[:MAX_CANDIDATES_PER_COMPANY])


def _safe_filename(url: str, company: str) -> str:
    """Generate a safe filename for the PDF."""
    base = os.path.basename(url.split("?")[0])
    if not base or not base.lower().endswith(".pdf"):
        base = "report.pdf"
    safe_company = re.sub(r"[^\w\-]", "_", company)[:50]
    return f"{safe_company}_{base}"


async def handle_pdf_download(context: BeautifulSoupCrawlingContext) -> None:
    """
    Download the PDF directly with httpx (bypasses BeautifulSoup which is HTML-only),
    save it to STORAGE_PATH on disk, push result to dataset, and call progress_callback.
    Short-circuits if this company is already in completed_companies.
    """
    company = _get_company(context)
    if company in completed_companies:
        return

    url = context.request.url
    publication_year = (context.request.user_data or {}).get("publication_year")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)

        content_type = response.headers.get("content-type", "")
        if "application/pdf" not in content_type.lower():
            _invoke_progress({
                "company": company, "status": "not_found", "pdf_url": url, "filename": "",
                "publication_year": None,
            })
            return

        body = response.content
        size = len(body) if body else 0
        if size < MIN_PDF_SIZE_BYTES or size > MAX_PDF_SIZE_BYTES:
            _invoke_progress({
                "company": company, "status": "not_found", "pdf_url": url, "filename": "",
                "publication_year": None,
            })
            return

        filename = _safe_filename(url, company)
        os.makedirs(STORAGE_PATH, exist_ok=True)
        file_path = os.path.join(STORAGE_PATH, filename)
        with open(file_path, "wb") as f:
            f.write(body)

    except Exception:
        _invoke_progress({
            "company": company, "status": "error", "pdf_url": url, "filename": "",
            "publication_year": None,
        })
        return

    completed_companies.add(company)
    await context.push_data({
        "company": company,
        "status": "found",
        "pdf_url": url,
        "filename": filename,
        "publication_year": publication_year,
    })
    _invoke_progress({
        "company": company, "status": "found", "pdf_url": url, "filename": filename,
        "publication_year": publication_year,
    })
