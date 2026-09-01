"""Common Crawl -- the free, keyless, always-legal last resort.

An open non-profit archive of the web with a public URL index (CDX). No API key,
no quota, no Terms-of-Service problem: it exists to be queried programmatically.

Be honest about what it is: **a URL index, not a text search engine.** You cannot
ask it "what is the transformer architecture". You *can* ask it "every PDF ever
archived under swica.ch" -- which is precisely the shape of this repo's real job,
finding a publisher's official documents. That's why it's a useful last link in
the chain rather than a token gesture.

It answers a query only when a domain can be inferred from it:
    "site:swica.ch pdf"                    -> *.swica.ch/*
    "www4.swica.ch/p/ conditions"          -> www4.swica.ch/*
    "axa.ch cga economia domestica"        -> *.axa.ch/*
Otherwise it says so plainly instead of returning junk.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import urlparse

import httpx

from webresearch.config import settings

log = logging.getLogger(__name__)

INDEX_LIST = "https://index.commoncrawl.org/collinfo.json"

# The CDX index is slow (seconds per query). Three crawls x this many rows keeps a
# lookup under ~30s while still covering a publisher's document tree.
#
# Coverage is genuinely PARTIAL, and that is inherent, not a tuning problem:
# Common Crawl is a sample of the web, not a mirror of it. Measured against
# swica.ch across six crawls -- "hospita" and "supplementa" return 60+ archived
# URLs each, while "infortuna" returns ZERO: that PDF has simply never been
# crawled. Treat a miss here as "not archived", never as "does not exist".
_ROWS_PER_INDEX = 150
_N_INDEXES = 3

# Words that name a filetype rather than a topic.
_FILETYPES = {"pdf", "docx", "doc", "pptx", "xlsx", "xls", "epub", "csv", "json", "xml"}

_SITE_OP = re.compile(r"\bsite:([\w.-]+\.\w{2,})", re.I)
_BARE_DOMAIN = re.compile(
    r"\b((?:[\w-]+\.)+(?:com|org|net|ch|io|edu|gov|co\.uk|de|fr|it|eu|info))\b", re.I
)
# Words that look like domains but are file extensions / noise.
_NOT_A_DOMAIN = re.compile(r"^\d+\.\d+$")

_indexes_cache: list[str] | None = None


class NoDomainInQuery(RuntimeError):
    """Common Crawl can only answer domain-scoped queries."""


def extract_domain(query: str) -> str | None:
    m = _SITE_OP.search(query)
    if m:
        return m.group(1).lower()
    for cand in _BARE_DOMAIN.findall(query):
        if not _NOT_A_DOMAIN.match(cand):
            return cand.lower()
    # A bare URL?
    for tok in query.split():
        if tok.startswith("http"):
            host = urlparse(tok).hostname
            if host:
                return host.lower()
    return None


async def _latest_indexes(client: httpx.AsyncClient, n: int = _N_INDEXES) -> list[str]:
    """The newest N crawl indexes. Cached -- collinfo.json is stable for weeks."""
    global _indexes_cache
    if _indexes_cache is None:
        r = await client.get(INDEX_LIST)
        r.raise_for_status()
        _indexes_cache = [c["cdx-api"] for c in r.json()]
    return _indexes_cache[:n]


async def _query_index(
    client: httpx.AsyncClient,
    index: str,
    pattern: str,
    limit: int,
    filters: list[str],
) -> list[dict]:
    """One CDX lookup.

    Filters are applied SERVER-SIDE. Post-filtering a `limit`-sized sample looks
    like it works and doesn't: the index holds tens of thousands of URLs per
    domain in sort order, so a 150-row slice almost never contains the document
    you asked for. Push the regex down to CDX instead.
    """
    params: list[tuple[str, str]] = [
        ("url", pattern),
        ("output", "json"),
        ("limit", str(limit)),
        ("filter", "=status:200"),
        *[("filter", f) for f in filters],
    ]
    r = await client.get(index, params=params)
    if r.status_code == 404 or not r.text.strip():
        return []
    r.raise_for_status()

    rows = []
    for line in r.text.strip().split("\n"):
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


async def search(query: str, max_results: int = 10) -> list[dict]:
    """Domain-scoped URL lookup against the Common Crawl archive."""
    domain = extract_domain(query)
    if not domain:
        raise NoDomainInQuery(
            "Common Crawl searches URLs, not page text. It needs a domain -- "
            "e.g. 'site:swica.ch conditions pdf'. It cannot answer a general query."
        )

    # Split the remaining words into a filetype hint and real content terms, and
    # turn both into server-side CDX regex filters.
    words = [
        t.lower()
        for t in re.findall(r"[\w-]{3,}", _SITE_OP.sub("", query))
        if domain.split(".")[0] not in t.lower() and not t.lower().startswith("http")
    ]
    exts = [w for w in words if w in _FILETYPES]
    terms = [w for w in words if w not in _FILETYPES]

    filters = [f"~url:(?i).*{re.escape(t)}.*" for t in terms]
    if exts:
        alt = "|".join(re.escape(e) for e in exts)
        filters.append(f"~url:(?i).*\\.({alt})$")

    pattern = f"*.{domain}/*" if domain.count(".") < 3 else f"{domain}/*"
    headers = {"User-Agent": settings.user_agent}

    async with httpx.AsyncClient(timeout=45, follow_redirects=True, headers=headers) as c:
        indexes = await _latest_indexes(c)
        batches = await asyncio.gather(
            *(_query_index(c, ix, pattern, _ROWS_PER_INDEX, filters) for ix in indexes),
            return_exceptions=True,
        )

    seen: set[str] = set()
    out: list[dict] = []
    for batch in batches:
        if isinstance(batch, Exception):
            log.warning("commoncrawl index query failed: %s", batch)
            continue
        for row in batch:
            url = row.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                {
                    "title": url.rsplit("/", 1)[-1] or url,
                    "url": url,
                    "snippet": (
                        f"Archived by Common Crawl "
                        f"({row.get('mime', '?')}, {row.get('timestamp', '?')[:8]})"
                    ),
                }
            )
            if len(out) >= max_results:
                return out
    return out
