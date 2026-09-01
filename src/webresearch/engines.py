"""SERP selectors -- the one file that rots.

Everything breakage-prone lives in ENGINES. When an engine changes its markup,
re-save a fixture into tests/fixtures/ and fix the dict here; nothing else moves.

Parsing runs on the HTML string with BeautifulSoup rather than Playwright
locators, which keeps `parse_results` a pure function testable offline against
saved fixtures with zero network.

Engine choice is empirical, not aspirational (checked 2026-07):
  - brave  : primary. Direct hrefs, no redirect wrapping, stable markup, and it
             kept working under repeated hits from one IP.
  - bing    : secondary. Works, but wraps EVERY result in a bing.com/ck/a
             redirect whose `u` param is the base64url'd real URL (must be
             decoded), and it degrades to a JS shell with no results at all when
             hit repeatedly from the same IP. Fine as a fallback, flaky as a
             primary.
  - google : bot-walls a headless browser almost immediately. Last resort only.
  - duckduckgo: DROPPED. html.duckduckgo.com/html/ and /lite/ now return 403,
             and the SPA renders nothing for a headless client. Every "DDG
             scraper" recipe you'll find online is dead; don't reinstate it
             without checking that a real request actually returns results.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

_SNIPPET_MAX = 300


def _bing_unwrap(href: str) -> str | None:
    """Bing routes every organic result through bing.com/ck/a?...&u=a1<base64url>."""
    if not href:
        return None
    if "bing.com/ck/a" not in href:
        return href
    raw = parse_qs(urlparse(href).query).get("u", [None])[0]
    if not raw:
        return None
    if raw.startswith("a1"):
        raw = raw[2:]
    try:
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (binascii.Error, ValueError):
        return None
    url = decoded.decode("utf-8", "replace")
    return url if url.startswith("http") else None


@dataclass(frozen=True)
class EngineSpec:
    name: str
    url: str  # {q} = quoted query, {n} = max results
    wait_for: str
    result: str
    title: str
    link: str
    snippet: str
    href_fix: Callable[[str], str | None] | None = None
    blocked_markers: tuple[str, ...] = field(default_factory=tuple)


ENGINES: dict[str, EngineSpec] = {
    "bing": EngineSpec(
        name="bing",
        url="https://www.bing.com/search?q={q}&count={n}&setlang=en",
        wait_for="li.b_algo",
        result="li.b_algo",
        title="h2 a",
        link="h2 a",
        snippet="div.b_caption p, p.b_lineclamp2, div.b_snippet, p",
        href_fix=_bing_unwrap,
        blocked_markers=(),
    ),
    "brave": EngineSpec(
        name="brave",
        url="https://search.brave.com/search?q={q}",
        wait_for="div.snippet[data-type='web']",
        result="div.snippet[data-type='web']",
        title="div.title",
        link="a[href^='http']",
        snippet="div.snippet-description, div.snippet-content",
        href_fix=None,
        # NB: a healthy Brave page ships an i18n JS dictionary containing the
        # word "captcha". Markers are matched against VISIBLE TEXT only (see
        # is_blocked) and must be specific enough not to fire on it.
        blocked_markers=("verify you are human", "unusual activity from your"),
    ),
    # Bot-walls headless browsers aggressively. Kept only as a last resort.
    "google": EngineSpec(
        name="google",
        url="https://www.google.com/search?q={q}&num={n}&hl=en&gl=us",
        wait_for="div#search, div#rso",
        result="div#rso div.g, div#rso div[data-hveid] div[data-ved]",
        title="h3",
        link="a[href^='http']",
        snippet="div[data-sncf], div.VwiC3b",
        href_fix=None,
        blocked_markers=(
            "our systems have detected unusual traffic",
            "/sorry/index",
        ),
    ),
}

FALLBACK_ORDER = ["brave", "bing", "google"]

# Never surface a search engine's own plumbing as a result.
_JUNK_HOSTS = (
    "bing.com",
    "microsoft.com",
    "microsofttranslator.com",
    "search.brave.com",
    "brave.com",
    "google.com",
    "googleusercontent.com",
    "duckduckgo.com",
)


def is_blocked(html: str, spec: EngineSpec) -> bool:
    """Detect a bot/anomaly page.

    Matches VISIBLE TEXT, not raw HTML: search pages embed big i18n JS
    dictionaries, and a healthy Brave result page contains the string "captcha"
    inside one. Grepping the raw markup flags every good page as blocked.
    """
    if not spec.blocked_markers:
        return False
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(("script", "style", "noscript")):
        tag.decompose()
    text = soup.get_text(" ", strip=True).lower()
    return any(marker in text for marker in spec.blocked_markers)


def _normalize(url: str) -> str:
    return url.rstrip("/").split("#", 1)[0]


def parse_results(html: str, spec: EngineSpec, max_results: int = 10) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    seen: set[str] = set()

    for node in soup.select(spec.result):
        link_el = node.select_one(spec.link)
        if not link_el:
            continue
        href = link_el.get("href", "")
        if spec.href_fix:
            href = spec.href_fix(href)
        if not href or not href.startswith("http"):
            continue

        host = (urlparse(href).hostname or "").lower()
        if any(host == j or host.endswith("." + j) for j in _JUNK_HOSTS):
            continue

        key = _normalize(href)
        if key in seen:
            continue

        title_el = node.select_one(spec.title) or link_el
        title = title_el.get_text(" ", strip=True)
        if not title:
            continue

        snippet_el = node.select_one(spec.snippet)
        snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rsplit(" ", 1)[0] + "…"

        seen.add(key)
        out.append({"title": title, "url": href, "snippet": snippet})
        if len(out) >= max_results:
            break

    return out
