"""Render a page with a real browser and hand back Markdown."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import TimeoutError as PWTimeout

from webresearch.browser import manager, page_semaphore
from webresearch.config import settings
from webresearch.convert import convert_file, html_to_markdown
from webresearch.download import download

log = logging.getLogger(__name__)

_CHROME = ("script", "style", "nav", "header", "footer", "aside", "noscript", "iframe", "svg", "form")


_DOC_EXTS = {".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".zip", ".epub"}


def _ext_says_document(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in _DOC_EXTS


async def _looks_like_html(url: str) -> bool:
    """Pre-flight: a .pdf link should be downloaded, not rendered.

    Trust the Content-Type only on a 2xx. Some CDNs (SWICA's, for one) answer
    HEAD with 400 + an HTML error page while GET returns the PDF perfectly well
    -- reading the content-type off that error response would have us render a
    PDF as a web page. On any non-2xx, fall back to the URL extension.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=8.0,
            headers={"User-Agent": settings.user_agent},
        ) as client:
            resp = await client.head(url)
            if resp.is_success:
                ctype = resp.headers.get("content-type", "").lower()
                if ctype:
                    return "html" in ctype or "xml" in ctype
            else:
                log.debug("HEAD %s -> %s; falling back to extension", url, resp.status_code)
    except Exception as exc:  # noqa: BLE001 - HEAD is advisory only
        log.debug("HEAD failed for %s (%s); falling back to extension", url, exc)

    return not _ext_says_document(url)


async def render_markdown(url: str, wait_selector: str | None = None) -> tuple[str, str]:
    """Returns (markdown, title)."""
    async with page_semaphore, manager.context() as ctx:
        page = await ctx.new_page()
        page.set_default_timeout(settings.nav_timeout_ms)
        await page.goto(url, wait_until="domcontentloaded", timeout=settings.nav_timeout_ms)

        if wait_selector:
            with contextlib.suppress(PWTimeout):
                await page.wait_for_selector(wait_selector, timeout=10_000)

        with contextlib.suppress(PWTimeout):
            await page.wait_for_load_state("networkidle", timeout=5_000)

        # Nudge lazy-loaded content into existence.
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(0.3)

        title = await page.title()
        html = await page.content()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_CHROME):
        tag.decompose()

    return html_to_markdown(str(soup), url=url), title or url


async def fetch_page(url: str, wait_selector: str | None = None) -> dict:
    """Render if it's a page; download+convert if it's a document.

    The agent will inevitably call fetch_page on a .pdf link -- make it work.
    Returns a dict with `markdown`, `title`, `source` and optionally `path`
    (set when the URL turned out to be a document) and `warning`.
    """
    if await _looks_like_html(url):
        md, title = await render_markdown(url, wait_selector)
        return {"markdown": md, "title": title, "source": url, "path": None, "warning": None}

    log.info("%s is not HTML -- downloading and converting instead", url)
    info = await download(url)
    path = Path(info["path"])
    md, warning = await convert_file(path)
    return {
        "markdown": md,
        "title": path.stem,
        "source": url,
        "path": path,
        "warning": warning,
        "download": info,
    }
