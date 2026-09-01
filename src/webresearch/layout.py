"""Layout-aware PDF text extraction (recursive XY-cut), for multi-column documents.

Why this exists: markitdown's PDF path (pdfminer) reads a page in roughly
y-then-x order. On a 3-column page that BRAIDS the columns together -- line 1 of
col 1 + line 1 of col 2 + line 1 of col 3 become ONE line:

    During a move action, if a fighter is  There are a few situations that  If a fighter suffers impact
    touching a part of a terrain feature   can cause a fighter to fall.     damage, roll a dice. On a

Three unrelated rules, braided into nonsense -- and it converts "successfully",
with no warning, producing text that still *reads* like prose. For a rules
reference or a contract that is the worst possible failure: plausible, confident
garbage.

Two things had to be right, and the first attempt got both wrong:

1. **Split into horizontal bands first.** A real page is not N columns top to
   bottom -- it is a stack of regions, each with its own column count: a
   full-width heading, then 3 columns, then a 2-column sidebar. Detecting one
   column layout for the whole page cannot represent that.

2. **Ignore column-spanning words when looking for gutters.** Projecting *every*
   word onto the x axis lets a single full-width heading ("DISENGAGE ACTIONS")
   bridge every gutter, collapsing the page to one column. Only body-width words
   vote on where the gutters are.

Coordinates come from pdfplumber (MIT, already a markitdown dependency). We
deliberately do NOT use PyMuPDF, which has the best column detection going --
it is AGPL, and this project is 0BSD with no copyleft dependencies.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

log = logging.getLogger(__name__)

_BINS = 240
# A word wider than this fraction of the page spans columns; it must not vote on gutters.
_MAX_WORD_FRAC = 0.35
# Empty x-run narrower than this is inter-word space, not a gutter.
_MIN_GUTTER_PT = 8.0
# Discard slivers: margin noise, page numbers, drop caps.
_MIN_COL_FRAC = 0.10
# Vertical whitespace taller than this starts a new horizontal band.
_MIN_BAND_GAP_PT = 10.0
# Words whose tops differ by less than this are on the same line.
_LINE_TOL = 3.0


@dataclass
class PageLayout:
    page_no: int
    n_columns: int  # the widest band on the page
    text: str


def _columns(words: list[dict], width: float) -> list[tuple[float, float]]:
    """x-bands of a region, found from a coverage histogram of body-width words."""
    body = [w for w in words if (w["x1"] - w["x0"]) < width * _MAX_WORD_FRAC] or words
    if not body:
        return []

    bin_w = width / _BINS
    cover = [0] * _BINS
    for w in body:
        lo = max(0, int(w["x0"] // bin_w))
        hi = min(_BINS - 1, int(w["x1"] // bin_w))
        for i in range(lo, hi + 1):
            cover[i] += 1

    runs: list[list[float]] = []
    start: int | None = None
    for i, c in enumerate(cover):
        if c > 0 and start is None:
            start = i
        elif c == 0 and start is not None:
            runs.append([start * bin_w, i * bin_w])
            start = None
    if start is not None:
        runs.append([start * bin_w, width])

    merged: list[list[float]] = []
    for lo, hi in runs:
        if merged and lo - merged[-1][1] < _MIN_GUTTER_PT:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])

    return [(lo, hi) for lo, hi in merged if (hi - lo) >= width * _MIN_COL_FRAC]


def _bands(words: list[dict]) -> list[list[dict]]:
    """Horizontal regions separated by full-width whitespace."""
    if not words:
        return []
    ordered = sorted(words, key=lambda w: w["top"])
    bands: list[list[dict]] = [[ordered[0]]]
    bottom = ordered[0]["bottom"]
    for w in ordered[1:]:
        if w["top"] - bottom > _MIN_BAND_GAP_PT:
            bands.append([w])
        else:
            bands[-1].append(w)
        bottom = max(bottom, w["bottom"])
    return bands


def _lines(words: list[dict]) -> list[str]:
    if not words:
        return []
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows and abs(w["top"] - rows[-1][0]["top"]) <= _LINE_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    return [
        " ".join(x["text"] for x in sorted(r, key=lambda w: w["x0"])).strip()
        for r in rows
    ]


def extract_page(page) -> PageLayout:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    width = float(page.width)

    chunks: list[str] = []
    widest = 1

    for band in _bands(words):
        cols = _columns(band, width)
        widest = max(widest, len(cols) or 1)

        if len(cols) <= 1:
            text = "\n".join(_lines(band))
            if text.strip():
                chunks.append(text)
            continue

        # Read each column of this band fully, top to bottom, before the next.
        for lo, hi in cols:
            in_col = [w for w in band if lo <= (w["x0"] + w["x1"]) / 2 <= hi]
            text = "\n".join(_lines(in_col))
            if text.strip():
                chunks.append(text)

    return PageLayout(page.page_number, widest, "\n\n".join(chunks))


def extract(path: Path) -> tuple[str, int, list[int]]:
    """Returns (text, max_columns_seen, page_numbers_that_were_multicolumn)."""
    out: list[str] = []
    multi: list[int] = []
    max_cols = 1

    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            try:
                layout = extract_page(page)
            except Exception as exc:  # noqa: BLE001 - one bad page must not sink the doc
                log.warning("layout extraction failed on page %s: %s", page.page_number, exc)
                continue
            if layout.n_columns > 1:
                multi.append(layout.page_no)
            max_cols = max(max_cols, layout.n_columns)
            if layout.text.strip():
                out.append(layout.text)

    return "\n\n".join(out), max_cols, multi


def looks_multicolumn(path: Path, sample: int = 8) -> bool:
    """Does a sample of pages have more than one column in its widest band?"""
    try:
        with pdfplumber.open(str(path)) as pdf:
            pages = pdf.pages[:sample]
            if not pages:
                return False
            counts: list[int] = []
            for page in pages:
                try:
                    counts.append(extract_page(page).n_columns)
                except Exception:  # noqa: BLE001
                    counts.append(1)
        return bool(counts) and statistics.median(counts) > 1
    except Exception as exc:  # noqa: BLE001
        log.debug("multicolumn probe failed for %s: %s", path, exc)
        return False
