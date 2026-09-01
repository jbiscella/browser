"""Column detection — pins the two bugs that made the first attempt useless.

The failure being prevented: pdfminer reads a 3-column page in y-then-x order and
BRAIDS the columns, so line 1 of each column becomes one line. The result still
reads like prose, converts with no warning, and is nonsense. For a rules
reference or a contract that is the worst kind of wrong.
"""

from __future__ import annotations

from webresearch.layout import _bands, _columns

W = 600.0


def word(text: str, x0: float, x1: float, top: float) -> dict:
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 10}


def _three_column_band(top: float = 100.0) -> list[dict]:
    cols = []
    for i, x in enumerate((80, 260, 440)):
        for row in range(4):
            cols.append(word(f"c{i}w{row}", x, x + 100, top + row * 12))
    return cols


def test_three_columns_are_detected():
    assert len(_columns(_three_column_band(), W)) == 3


def test_a_full_width_heading_does_not_collapse_the_columns():
    """The original bug: one spanning word bridged every gutter -> 1 column.

    A heading like "DISENGAGE ACTIONS" is a single wide word-run. If it is allowed
    to vote on where the gutters are, the whole page projects as one solid band.
    """
    words = _three_column_band()
    words.append(word("DISENGAGE ACTIONS SPANNING EVERYTHING", 80, 540, 100.0))
    assert len(_columns(words, W)) == 3, "a spanning heading collapsed the columns"


def test_single_column_page_stays_single():
    words = [word(f"w{i}", 80, 520, 100 + i * 12) for i in range(6)]
    assert len(_columns(words, W)) <= 1


def test_page_is_split_into_horizontal_bands():
    """A page is a stack of regions, not N columns top-to-bottom.

    Heading (1 col) → body (3 cols) → heading (1 col). Detecting one column count
    for the whole page cannot represent that, which is why bands come first.
    """
    words = [word("HEADING", 80, 300, 50.0)]
    words += _three_column_band(top=100.0)
    words += [word("NEXT HEADING", 80, 300, 400.0)]

    bands = _bands(words)
    assert len(bands) == 3, f"expected heading/body/heading, got {len(bands)} bands"
    assert len(_columns(bands[0], W)) == 1
    assert len(_columns(bands[1], W)) == 3
    assert len(_columns(bands[2], W)) == 1


def test_narrow_slivers_are_not_columns():
    """Page numbers and margin marks must not register as a column."""
    words = [word(f"w{i}", 80, 520, 100 + i * 12) for i in range(4)]
    words.append(word("13", 300, 310, 700.0))  # page number, far below
    for band in _bands(words):
        assert len(_columns(band, W)) <= 1


def test_visual_page_thresholds_are_ratio_based():
    """A symbol chart is many images + few words. A dense rules page is many
    images + MANY words, and must not be mistaken for one.

    Warcry p24 (the runemark reference) yields 46 words with every symbol gone --
    the Markdown reads complete and is useless. p13 (dense 3-column rules) also
    carries dozens of decorative images, but thousands of characters, and its text
    IS the content. Raw image count cannot tell them apart; the ratio can.
    """
    from webresearch.convert import _VISUAL_MAX_CHARS, _VISUAL_MIN_IMAGES

    def is_visual(images: int, chars: int) -> bool:
        return images >= _VISUAL_MIN_IMAGES and chars < _VISUAL_MAX_CHARS

    assert is_visual(images=30, chars=300), "a symbol chart must be flagged"
    assert not is_visual(images=35, chars=2400), "a dense rules page must NOT be flagged"
    assert not is_visual(images=1, chars=200), "a sparse text page is not a chart"
