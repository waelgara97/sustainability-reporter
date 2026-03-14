"""Routes requests to the appropriate handler by label (search, pdf, ir)."""

from crawlee.crawlers import BeautifulSoupCrawlingContext
from crawlee.router import Router

from .handlers import handle_search_page, handle_ir_page, handle_pdf_download


def build_router():
    """Build a Router that dispatches by request label. Used by main.py."""
    router = Router[BeautifulSoupCrawlingContext]()

    @router.handler("search")
    async def search_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_search_page(context)

    @router.handler("pdf")
    async def pdf_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_pdf_download(context)

    @router.handler("ir")
    async def ir_handler(context: BeautifulSoupCrawlingContext) -> None:
        await handle_ir_page(context)

    @router.default_handler
    async def default_handler(context: BeautifulSoupCrawlingContext) -> None:
        # Unlabeled or unknown: treat as IR page
        await handle_ir_page(context)

    return router
