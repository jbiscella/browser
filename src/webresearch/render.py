"""Render a PDF page to PNG so the agent can *look* at it.

The escape hatch for everything text extraction cannot reach: diagrams, stat
cards, symbol/runemark charts, tables drawn as images, layouts too baroque to
linearise. A vision-capable model reads the rendered page directly, which beats
OCR on this kind of content -- OCR would inherit the same column-order problem
and still lose the symbols.

pypdfium2 (BSD-3/Apache-2.0, already installed via markitdown). Not PyMuPDF,
which is AGPL and would contaminate a 0BSD project.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pypdfium2 as pdfium

from webresearch.store import resolve_in_docs

log = logging.getLogger(__name__)

# ~150 DPI. Enough to read 8pt rules text; small enough not to blow up context.
_DEFAULT_SCALE = 2.0
_MAX_SCALE = 4.0


def page_count(path: Path) -> int:
    pdf = pdfium.PdfDocument(str(path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def render_page(path: Path, page: int, scale: float = _DEFAULT_SCALE) -> dict:
    """Render one 1-indexed page to a PNG next to the source. Returns its path."""
    scale = max(0.5, min(float(scale), _MAX_SCALE))
    pdf = pdfium.PdfDocument(str(path))
    try:
        total = len(pdf)
        if not 1 <= page <= total:
            raise ValueError(f"page {page} out of range: {path.name} has {total} pages")

        image = pdf[page - 1].render(scale=scale).to_pil()
    finally:
        pdf.close()

    out = resolve_in_docs(f"{path.stem}-p{page}", ".png")
    image.save(out)

    return {
        "path": str(out),
        "source": str(path),
        "page": page,
        "total_pages": total,
        "width": image.width,
        "height": image.height,
        "hint": (
            "Open this PNG with the Read tool to look at the page — that is how you "
            "read diagrams, stat cards and symbol charts that text extraction drops."
        ),
    }
