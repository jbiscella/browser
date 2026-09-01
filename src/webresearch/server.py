"""FastMCP server exposing the research toolset.

CRITICAL: stdout is the JSON-RPC transport. A single stray print() corrupts the
stream and the server dies with a parse error. Log to stderr, never print.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from webresearch import browser, convert, fetch, providers, render, search, store
from webresearch.config import settings
from webresearch.download import download as download_file

log = logging.getLogger("webresearch")


@asynccontextmanager
async def _lifespan(_server: FastMCP):
    try:
        yield {}
    finally:
        await browser.manager.close()


mcp = FastMCP("research", lifespan=_lifespan)


@mcp.tool()
async def web_search(query: str, engine: str = "auto", max_results: int = 10) -> dict:
    """Search the web. Prefers official APIs, falls back to a real browser.

    "auto" walks a chain, cleanest source first:
      1. tavily -- official API, ToS-clean. Used only if TAVILY_API_KEY is set.
      2. brave / bing / google (scraped in a real Chromium) -- no key needed, but
         scraping a results page violates that engine's Terms of Service. Fine at
         personal volume; don't run it at scale.
      3. commoncrawl -- free, keyless, no ToS issue, but it indexes URLs rather
         than page text, so it only answers DOMAIN-SCOPED queries
         (e.g. "site:swica.ch conditions pdf"). Great for finding a publisher's
         official documents; useless for a general question.

    The response includes `licit` (was the source ToS-clean?) and `quota`
    (remaining API allowance). If you need a document from a known publisher,
    prefer a domain-scoped query -- it's both more reliable and legally cleaner.

    Args:
        query: The search query.
        engine: "auto" (default), or pin one of:
                tavily, brave, bing, google, commoncrawl.
        max_results: How many results to return (default 10).

    Returns {engine, licit, query, count, results: [{title, url, snippet}], quota}.
    Pass a result's `url` to fetch_page (to read it) or download (to save it).
    """
    return await search.search(query, engine=engine, max_results=max_results)


@mcp.tool()
def search_quota() -> dict:
    """Remaining free-tier allowance on the configured search API, and the live chain.

    tavily: 1000 credits/month, resets monthly. Shows configured=false when
    TAVILY_API_KEY is unset -- in which case search falls back to browser
    scraping, which works but violates the search engines' Terms of Service.
    """
    return {
        "providers": providers.status(),
        "chain": search.chain_description(),
    }


@mcp.tool()
async def fetch_page(url: str, wait_selector: str | None = None) -> dict:
    """Load a URL in a real browser (JS rendered) and return it as Markdown.

    If the URL is actually a document (PDF, docx, ...) it is downloaded and
    converted instead of rendered, so this works on a .pdf link too.

    OUTPUT IS BOUNDED. The full text is always written to disk and `path` points
    at it; `content` holds only the first ~20k characters. If `truncated` is
    true, do NOT try to get the rest by re-fetching -- use search_document(path,
    pattern) to jump to what you need, then read_document(path, offset).

    Args:
        url: Page or document URL.
        wait_selector: Optional CSS selector to wait for before reading the page.
    """
    result = await fetch.fetch_page(url, wait_selector=wait_selector)
    return store.emit(
        result["markdown"],
        stem=result["title"],
        source=url,
        warning=result["warning"],
    )


@mcp.tool()
async def download(url: str, filename: str | None = None) -> dict:
    """Download a file (PDF, docx, ...) to the documents directory.

    Returns {path, filename, bytes, content_type, detected_type} -- NOT the
    content. Follow with to_markdown(path) to read it.

    Sends a browser User-Agent and retries through the browser on 403/429, so it
    works on hosts (arxiv, Cloudflare-fronted sites) that reject plain HTTP clients.

    Args:
        url: File URL.
        filename: Optional name to save as; otherwise inferred from the URL/headers.
    """
    return await download_file(url, filename)


@mcp.tool()
async def to_markdown(source: str) -> dict:
    """Convert a document to Markdown with markitdown (PDF, docx, pptx, xlsx, html...).

    `source` may be a local file path OR a URL (which is downloaded first).

    OUTPUT IS BOUNDED: the full Markdown is written to disk (`path`), and only
    the first ~20k characters come back in `content`. For a long document, use
    search_document(path, pattern) then read_document(path, offset) rather than
    reading it end-to-end.

    Note: scanned/image-only PDFs have no text layer and will convert to almost
    nothing -- a `warning` field is set when that is detected.

    Args:
        source: Local path or http(s) URL of the document.
    """
    if source.startswith(("http://", "https://")):
        info = await download_file(source)
        path = Path(info["path"])
        origin: str | None = source
    else:
        path = Path(source).expanduser()
        if not path.is_absolute():
            path = settings.docs_dir / path
        if not path.is_file():
            raise FileNotFoundError(f"No such file: {path}")
        origin = None

    md, warning = await convert.convert_file(path)
    md_path = path.with_suffix(".md")
    if md_path.exists() and md_path.resolve() == path.resolve():
        md_path = None  # source already .md; emit() will pick a fresh name
    else:
        md_path.write_text(md, encoding="utf-8")

    return store.emit(md, stem=path.stem, source=origin, path=md_path, warning=warning)


@mcp.tool()
def read_document(path: str, offset: int = 0, limit: int = 20_000) -> dict:
    """Read a character window from a saved document. The way to page a big file.

    Args:
        path: Path returned by fetch_page / to_markdown / download.
        offset: Character offset to start at (use an offset from search_document).
        limit: Max characters to return (clamped).

    Returns {content, offset, next_offset, total_chars, eof}. Pass `next_offset`
    back in as `offset` to continue.
    """
    return store.read_window(path, offset=offset, limit=limit)


@mcp.tool()
def search_document(
    path: str, pattern: str, context_chars: int = 300, max_matches: int = 20
) -> dict:
    """Regex-search a saved document; get back offsets and surrounding excerpts.

    THIS IS THE RIGHT WAY INTO A LARGE DOCUMENT. For a 300-page PDF you almost
    never want page 1 -- you want the section about X. Search for X, then
    read_document(path, offset=<hit offset>) to read around it.

    Args:
        path: Path to a saved document.
        pattern: Python regex (case-insensitive, multiline).
        context_chars: Characters of context around each hit.
        max_matches: Cap on returned matches.
    """
    return store.search_text(
        path, pattern, context_chars=context_chars, max_matches=max_matches
    )


@mcp.tool()
def render_page(path: str, page: int, scale: float = 2.0) -> dict:
    """Render one page of a PDF to a PNG image, so you can LOOK at it.

    Use this whenever text extraction is not enough:
      - diagrams, maps, measuring/visibility illustrations
      - stat cards and datacards
      - symbol/icon charts (e.g. Warhammer runemarks) — these are glyphs and are
        NOT recoverable from the text layer
      - tables that were drawn as images

    to_markdown() sets a `warning` naming the most image-heavy pages; render those.
    Then open the returned `path` with the Read tool to actually view the page.

    Args:
        path: Path to a PDF (from download / list_documents).
        page: 1-indexed page number.
        scale: Render scale; 2.0 (~150 DPI) is readable. Raise for fine print.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = settings.docs_dir / p
    if not p.is_file():
        raise FileNotFoundError(f"No such file: {p}")
    return render.render_page(p, page, scale)


@mcp.tool()
def list_documents() -> dict:
    """List everything saved in the documents directory (downloads + conversions)."""
    return store.list_documents()


@mcp.tool()
async def research(query: str, max_results: int = 5, preview_chars: int = 1500) -> dict:
    """Search the web AND fetch the top results in one call. Start here.

    Returns a per-source preview plus a `path` to the full text of each. Output
    is bounded by construction (~preview_chars per source), so this is safe to
    call on a broad query. Then use search_document/read_document on whichever
    source looks relevant.

    Args:
        query: What to research.
        max_results: How many top results to fetch (default 5).
        preview_chars: Characters of each source to include inline (default 1500).
    """
    found = await search.search(query, max_results=max_results)

    async def _one(item: dict) -> dict:
        base = {"title": item["title"], "url": item["url"], "snippet": item["snippet"]}
        try:
            result = await fetch.fetch_page(item["url"])
            md = result["markdown"]
            path = store.save_text(md, stem=result["title"] or item["url"])
            return {
                **base,
                "path": str(path),
                "total_chars": len(md),
                "preview": md[:preview_chars],
                "warning": result["warning"],
            }
        except Exception as exc:  # noqa: BLE001 - one bad source must not sink the call
            return {**base, "error": str(exc)[:200]}

    sources = await asyncio.gather(*(_one(r) for r in found["results"]))

    return {
        "query": query,
        "engine": found["engine"],
        "count": len(sources),
        "sources": list(sources),
        "note": (
            "Previews only. Each source's full text is at its `path` -- use "
            "search_document(path, pattern) / read_document(path, offset) to go deeper."
        ),
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,  # NEVER stdout: that's the JSON-RPC transport.
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    def _bye(signum, _frame):
        log.info("signal %s -- shutting down", signum)
        raise SystemExit(0)

    for sig in (signal.SIGTERM, signal.SIGINT):
        with __import__("contextlib").suppress(ValueError):
            signal.signal(sig, _bye)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
