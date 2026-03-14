"""Handlers for search pages, IR/sustainability pages, and PDF downloads."""

import os
import re
from urllib.parse import urljoin

from crawlee import Request
from crawlee.crawlers import BeautifulSoupCrawlingContext

from config import (
    MAX_CANDIDATES_PER_COMPANY,
    MAX_CRAWL_DEPTH,
    MAX_PDF_SIZE_BYTES,
    MIN_PDF_SIZE_BYTES,
    SCORE_THRESHOLD,
)
from crawler.detector import score_link

# Set by main.run_crawl() before starting; handlers call it when a company result is ready
_progress_callback = None


def set_progress_callback(callback):
    global _progress_callback
    _progress_callback = callback


def _get_company(context: BeautifulSoupCrawlingContext) -> str:
    """Get company name from request user_data, or empty string."""
    ud = getattr(context.request, "user_data", None) or {}
    if isinstance(ud, dict):
        return ud.get("company", "") or ""
    return getattr(ud, "company", "") or ""


def _invoke_progress(result: dict) -> None:
    if _progress_callback:
        try:
            _progress_callback(result)
        except Exception:
            pass


async def handle_search_page(context: BeautifulSoupCrawlingContext) -> None:
    """Parse Google search results; enqueue high-scoring PDF/IR links (cap at MAX_CANDIDATES_PER_COMPANY)."""
    company = _get_company(context)
    soup = getattr(context, "soup", None)
    if not soup:
        _invoke_progress({"company": company, "status": "error", "pdf_url": "", "filename": ""})
        return

    candidates = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or "google.com" in href:
            continue
        text = (a.get_text() or "").strip()
        score = score_link(href, text)
        if score >= SCORE_THRESHOLD:
            candidates.append((score, href, text))

    candidates.sort(key=lambda x: -x[0])
    to_add = candidates[:MAX_CANDIDATES_PER_COMPANY]
    if not to_add:
        _invoke_progress({"company": company, "status": "not_found", "pdf_url": "", "filename": ""})
        return

    requests_to_add = []
    for _score, url, _text in to_add:
        label = "pdf" if url.lower().rstrip("/").endswith(".pdf") else "ir"
        req = Request.from_url(url, label=label, company=company)
        requests_to_add.append(req)

    await context.add_requests(requests_to_add)


async def handle_ir_page(context: BeautifulSoupCrawlingContext) -> None:
    """Parse IR/sustainability HTML page; enqueue PDF links and sub-pages up to MAX_CRAWL_DEPTH."""
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
        if full_url.lower().rstrip("/").endswith(".pdf"):
            req = Request.from_url(full_url, label="pdf", company=company)
            requests_to_add.append(req)
        else:
            req = Request.from_url(full_url, label="ir", company=company)
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
    """Check PDF size, save to KeyValueStore, push result and call progress_callback."""
    company = _get_company(context)
    url = context.request.url

    http_response = getattr(context, "http_response", None)
    if not http_response:
        _invoke_progress({"company": company, "status": "error", "pdf_url": url, "filename": ""})
        return

    content_type = (getattr(http_response, "headers", None) or {}).get("content-type", "")
    if "application/pdf" not in content_type.lower():
        _invoke_progress({"company": company, "status": "not_found", "pdf_url": url, "filename": ""})
        return

    try:
        body = await http_response.read()
    except Exception:
        _invoke_progress({"company": company, "status": "error", "pdf_url": url, "filename": ""})
        return

    size = len(body) if body else 0
    if size < MIN_PDF_SIZE_BYTES or size > MAX_PDF_SIZE_BYTES:
        _invoke_progress({"company": company, "status": "not_found", "pdf_url": url, "filename": ""})
        return

    filename = _safe_filename(url, company)
    store = await context.get_key_value_store()
    await store.set_value(filename, body, content_type="application/pdf")

    await context.push_data({
        "company": company,
        "status": "found",
        "pdf_url": url,
        "filename": filename,
    })
    _invoke_progress({"company": company, "status": "found", "pdf_url": url, "filename": filename})
