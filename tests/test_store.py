"""The bounded-output invariant, proved on a synthetic 1M-char document.

This is the failure mode the project exists to prevent: a converted PDF flooding
the agent's context window. If these tests fail, that guard is gone.
"""

from __future__ import annotations

import pytest

from webresearch import store
from webresearch.config import settings

BIG = "".join(f"line {i} lorem ipsum dolor sit amet\n" for i in range(30_000))


def test_big_text_is_never_returned_inline():
    payload = store.emit(BIG, stem="synthetic-big")
    assert len(BIG) > 900_000, "fixture should be ~1M chars"
    assert payload["truncated"] is True
    assert len(payload["content"]) == settings.max_inline_chars
    assert payload["total_chars"] == len(BIG)
    assert payload["next_offset"] == settings.max_inline_chars
    assert "search_document" in payload["note"]


def test_full_text_is_on_disk():
    payload = store.emit(BIG, stem="synthetic-disk")
    from pathlib import Path

    assert Path(payload["path"]).read_text() == BIG


def test_small_text_is_not_truncated():
    payload = store.emit("hello world", stem="synthetic-small")
    assert payload["truncated"] is False
    assert payload["content"] == "hello world"
    assert payload["next_offset"] is None
    assert "note" not in payload


def test_read_window_is_clamped_to_hard_max():
    payload = store.emit(BIG, stem="synthetic-window")
    window = store.read_window(payload["path"], offset=0, limit=10_000_000)
    assert len(window["content"]) <= settings.hard_max_chars


def test_read_window_paginates_to_eof():
    payload = store.emit(BIG, stem="synthetic-page")
    path, offset, seen, guard = payload["path"], 0, 0, 0
    while offset is not None and guard < 200:
        w = store.read_window(path, offset=offset, limit=100_000)
        seen += len(w["content"])
        offset = w["next_offset"]
        guard += 1
    assert seen == len(BIG)
    assert w["eof"] is True


def test_search_document_finds_offsets_and_stays_bounded():
    payload = store.emit(BIG, stem="synthetic-search")
    hits = store.search_text(payload["path"], r"line 29999\b", max_matches=5)
    assert hits["total_matches"] >= 1
    assert hits["matches"][0]["offset"] > 0
    total = sum(len(m["excerpt"]) for m in hits["matches"])
    assert total <= settings.max_inline_chars


def test_search_document_rejects_bad_regex():
    payload = store.emit("abc", stem="synthetic-regex")
    with pytest.raises(ValueError):
        store.search_text(payload["path"], "(unclosed")
