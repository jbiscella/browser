"""markitdown wrapper.

Uses the markitdown *library* (Microsoft, official) rather than the
`markitdown-mcp` server, because that server returns the entire converted
document in one response -- a 300-page PDF is ~200k tokens straight into
context. Same conversion engine, bounded output. See store.emit().

markitdown's own URL fetching is deliberately unused: it goes through plain
`requests` with a default UA, which 403s on arxiv and most CDN-fronted hosts,
and gives no size control. Downloads go through download.py instead.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from markitdown import MarkItDown, StreamInfo
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTFigure, LTImage, LTTextContainer

from webresearch import layout
from webresearch.config import settings

log = logging.getLogger(__name__)

_md = MarkItDown(enable_plugins=False)

_BLANK_LINES = re.compile(r"\n{3,}")

# An image bigger than this could BE content (a diagram/stat card), not decoration.
_BIG_IMAGE_PT = 150

# A page with at least this many large images and fewer than this many characters is a
# symbol chart / diagram plate: its content IS the imagery, and the text layer holds only
# the captions. Warcry p24 (the runemark reference) yields 46 words -- "Blast", "Axe",
# "Scythe" -- with every actual symbol gone, so the Markdown reads complete and is useless.
_VISUAL_MIN_IMAGES = 8
_VISUAL_MAX_CHARS = 900
# Cap auto-rendering: a 300-page art book must not spawn 300 PNGs.
_MAX_AUTO_RENDER = 12

# A PDF this big yielding almost no text is image-only (a scan). markitdown has
# no OCR, so it would silently hand back an empty document.
_SCAN_MIN_BYTES = 100_000
_SCAN_MAX_CHARS = 200
SCANNED_WARNING = (
    "This PDF appears to be image-only (a scan): it has no extractable text layer, "
    "so conversion produced almost nothing. OCR is not installed, so the text cannot "
    "be recovered from this file — find an alternative source for the document."
)


def _tidy(md: str) -> str:
    return _BLANK_LINES.sub("\n\n", md).strip()


def _convert_file_sync(path: Path) -> str:
    return _tidy(_md.convert(str(path)).text_content)


def _convert_pdf_sync(path: Path) -> tuple[str, list[str]]:
    """PDF path, with layout awareness and an honest account of what was lost."""
    notes: list[str] = []

    if layout.looks_multicolumn(path):
        text, n_cols, multi_pages = layout.extract(path)
        md = _tidy(text)
        notes.append(
            f"{n_cols}-column layout detected on {len(multi_pages)} page(s); used "
            "layout-aware extraction so the columns are read in order. (Default "
            "extraction braids columns together into unreadable text.)"
        )
    else:
        md = _convert_file_sync(path)

    lost = inspect_pdf(path)

    # Pages whose CONTENT IS THE IMAGERY -- a symbol chart, a diagram plate, a
    # datacard sheet. Text extraction returns the captions and drops the thing
    # being captioned, so the Markdown looks complete and is useless: Warcry p24
    # is the runemark reference, and yields 46 words ("Blast", "Axe", "Scythe")
    # with every actual symbol gone. Rasterise those pages and link them inline,
    # so a vision-capable reader can resolve what the text cannot carry.
    if lost.visual_pages:
        rendered = _render_visual_pages(path, lost.visual_pages)
        if rendered:
            md += "\n\n" + _visual_appendix(rendered)
            notes.append(
                f"{len(rendered)} page(s) are mostly imagery (symbol charts, diagrams): "
                f"pages {[p for p, _ in rendered]}. Their text layer holds only the "
                "captions — the content itself is graphical. They have been rendered to "
                "PNG and linked at the end of the document; open those with Read to see "
                "them."
            )

    if lost.big_images:
        notes.append(
            f"{lost.big_images} large image(s) were DROPPED (no OCR): diagrams, stat "
            f"cards or charts may be missing. Use render_page(path, <n>) to look at any "
            f"page. Most image-heavy pages: {lost.top_image_pages}."
        )
    if lost.glyphs:
        notes.append(
            f"{lost.glyphs} symbol glyph(s) were dropped. If the text refers to symbols "
            "(e.g. Warcry runemarks), they will be missing — render the page to see them."
        )
    return md, notes


def _render_visual_pages(path: Path, pages: list[int]) -> list[tuple[int, str]]:
    from webresearch import render  # local import: render -> store -> config cycle

    out: list[tuple[int, str]] = []
    for pno in pages[:_MAX_AUTO_RENDER]:
        try:
            info = render.render_page(path, pno)
            out.append((pno, info["path"]))
        except Exception as exc:  # noqa: BLE001 - rendering is a bonus, never fatal
            log.warning("could not render visual page %s of %s: %s", pno, path.name, exc)
    return out


def _visual_appendix(rendered: list[tuple[int, str]]) -> str:
    lines = [
        "---",
        "",
        "## Visual pages (content is imagery, not text)",
        "",
        "These pages are symbol charts, diagrams or datacards. Their text layer holds only",
        "the captions — the meaning is in the graphics. Open the PNGs to read them.",
        "",
    ]
    for pno, img in rendered:
        lines.append(f"### Page {pno}")
        lines.append("")
        lines.append(f"![page {pno}]({img})")
        lines.append("")
    return "\n".join(lines)


@dataclass
class PdfLoss:
    big_images: int
    glyphs: int
    top_image_pages: list[int]
    visual_pages: list[int]  # pages whose CONTENT IS the imagery


def inspect_pdf(path: Path) -> PdfLoss:
    """What will markitdown silently throw away from this PDF?"""
    big = 0
    glyphs = 0
    per_page: list[tuple[int, int]] = []
    visual: list[int] = []
    try:
        for pno, page in enumerate(extract_pages(str(path)), 1):
            n = 0
            chars = 0

            def walk(obj) -> None:
                nonlocal n, glyphs, chars
                for el in obj:
                    if isinstance(el, LTImage):
                        if el.width > _BIG_IMAGE_PT or el.height > _BIG_IMAGE_PT:
                            n += 1
                    elif isinstance(el, LTFigure):
                        walk(el)
                    elif isinstance(el, LTChar):
                        # Private-use-area codepoints are icon fonts (runemarks etc.)
                        if el.get_text() and "" <= el.get_text() <= "":
                            glyphs += 1

            for el in page:
                if isinstance(el, LTTextContainer):
                    chars += len(el.get_text())

            walk(page)
            big += n
            per_page.append((n, pno))

            # A symbol chart / diagram plate: many pictures, barely any words.
            # Judge by RATIO, not raw word count -- a dense 3-column rules page also
            # carries hundreds of decorative images, but thousands of characters too.
            if n >= _VISUAL_MIN_IMAGES and chars < _VISUAL_MAX_CHARS:
                visual.append(pno)
    except Exception as exc:  # noqa: BLE001 - inspection is advisory only
        log.debug("pdf inspection failed for %s: %s", path, exc)

    per_page.sort(reverse=True)
    return PdfLoss(
        big_images=big,
        glyphs=glyphs,
        top_image_pages=[p for n, p in per_page[:3] if n],
        visual_pages=visual,
    )


async def convert_file(path: Path) -> tuple[str, str | None]:
    """Convert any markitdown-supported file. Returns (markdown, warning)."""
    is_pdf = path.suffix.lower() == ".pdf"
    worker = _convert_pdf_sync if is_pdf else (lambda p: (_convert_file_sync(p), []))

    try:
        # pdfminer/pdfplumber are synchronous and CPU-bound: a big PDF blocks
        # 10-60s and would otherwise freeze the whole MCP event loop.
        md, notes = await asyncio.wait_for(
            asyncio.to_thread(worker, path),
            timeout=settings.convert_timeout_secs,
        )
    except asyncio.TimeoutError as exc:
        raise TimeoutError(
            f"Conversion of {path.name} exceeded {settings.convert_timeout_secs}s "
            "(malformed or very large file)."
        ) from exc

    if (
        is_pdf
        and len(md.strip()) < _SCAN_MAX_CHARS
        and path.stat().st_size > _SCAN_MIN_BYTES
    ):
        notes.insert(0, SCANNED_WARNING)

    return md, (" ".join(notes) if notes else None)


def html_to_markdown(html: str, url: str | None = None) -> str:
    """The single HTML->Markdown path, shared by fetch_page and to_markdown."""
    stream_info = StreamInfo(extension=".html", mimetype="text/html", url=url)
    result = _md.convert_stream(io.BytesIO(html.encode("utf-8")), stream_info=stream_info)
    return _tidy(result.text_content)
