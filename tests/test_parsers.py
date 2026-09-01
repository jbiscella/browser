"""Offline SERP parser tests -- the regression net for selector rot.

Fixtures are real result pages captured from a live browser (query: "attention
is all you need"). When an engine changes its markup, `web_search` starts
returning nothing; re-capture the fixture, fix engines.py, and these tests tell
you whether the fix is real. No network.

Both of the bugs that broke this in practice are pinned here:
  - bing wraps every href in a bing.com/ck/a redirect (must be base64-decoded)
  - a healthy brave page contains the word "captcha" in an i18n JS blob, so
    is_blocked() must read visible text, not raw HTML
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import pytest

from webresearch.engines import ENGINES, is_blocked, parse_results

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    path = FIXTURES / f"{name}.html"
    if not path.exists():
        pytest.skip(f"fixture {path.name} not captured")
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.mark.parametrize("engine", ["bing", "brave"])
def test_parses_real_results(engine: str):
    results = parse_results(_load(engine), ENGINES[engine], max_results=10)
    assert len(results) >= 5, f"{engine}: only {len(results)} results parsed"
    for r in results:
        assert r["title"].strip(), f"{engine}: empty title"
        assert r["url"].startswith("http"), f"{engine}: bad url {r['url']}"


@pytest.mark.parametrize("engine", ["bing", "brave"])
def test_no_engine_plumbing_leaks_into_results(engine: str):
    results = parse_results(_load(engine), ENGINES[engine], max_results=10)
    for r in results:
        host = (urlparse(r["url"]).hostname or "").lower()
        assert "bing.com" not in host, f"undecoded bing redirect leaked: {r['url']}"
        assert "brave.com" not in host, f"brave internal link leaked: {r['url']}"


def test_bing_ck_a_redirects_are_decoded():
    """Bing wraps EVERY organic result; if this regresses, search returns zero."""
    results = parse_results(_load("bing"), ENGINES["bing"], max_results=10)
    assert results, "bing parsed nothing -- ck/a decoding likely broken"
    assert any("arxiv.org" in r["url"] for r in results), (
        "expected a decoded arxiv.org URL among bing results"
    )
    assert not any("/ck/a" in r["url"] for r in results)


def test_healthy_brave_page_is_not_flagged_as_blocked():
    """Regression: brave ships an i18n JS dict containing 'captcha'."""
    html = _load("brave")
    assert "captcha" in html.lower(), "fixture should contain the JS 'captcha' string"
    assert not is_blocked(html, ENGINES["brave"]), (
        "healthy page flagged as blocked -- is_blocked() is matching raw HTML "
        "instead of visible text"
    )


def test_blocked_page_is_detected():
    blocked = "<html><body><h1>Please verify you are human to continue</h1></body></html>"
    assert is_blocked(blocked, ENGINES["brave"])
