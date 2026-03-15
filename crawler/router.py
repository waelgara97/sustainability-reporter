"""Routes crawlee requests to the appropriate handler by label."""

from crawlee.crawlers import BeautifulSoupCrawlingContext
from crawlee.router import Router

from .handlers import handle_ir_page, handle_pdf_download


def build_router() -> Router:
    """
    Build and return the URL router used by BeautifulSoupCrawler.

    Labels are set when URLs are enqueued (in main.py and handle_ir_page):
        "pdf"  → handle_pdf_download  — download a PDF directly with httpx
        "ir"   → handle_ir_page       — parse an IR/sustainability HTML page
        (default) → handle_ir_page    — any unlabeled or unknown URL

    Note: there is NO "search" handler.  Google search is done via the
    Custom Search API (crawler/search.py) before the crawler starts, so
    google.com URLs are never added to the queue.
    """
    router: Router[BeautifulSoupCrawlingContext] = Router()

    @router.handler("pdf")
    async def pdf_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_pdf_download(context)

    @router.handler("ir")
    async def ir_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_ir_page(context)

    @router.default_handler
    async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_ir_page(context)

    return router
