"""Search with a fallback chain, cleanest source first.

Order of preference:

  1. Official API (tavily) -- ToS-clean, but needs a key and has a quota.
     Skipped silently when no key is configured.
  2. Browser scraping (brave, bing, google) -- no key, no quota, but scraping a
     SERP violates that engine's Terms of Service. Fine for low-volume personal
     use; not something to run at scale. See README.
  3. Common Crawl -- free, keyless, no ToS problem, but it indexes URLs rather
     than page text, so it can only answer domain-scoped queries.

`engine="auto"` walks the whole chain. Naming a specific engine pins it.
"""

from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import quote_plus

from playwright.async_api import TimeoutError as PWTimeout

from webresearch import commoncrawl, providers
from webresearch.browser import manager, page_semaphore
from webresearch.config import settings
from webresearch.engines import ENGINES, FALLBACK_ORDER, EngineSpec, is_blocked, parse_results

log = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """The engine served a bot/anomaly page instead of results."""


async def _fetch_serp(spec: EngineSpec, query: str, max_results: int) -> str:
    url = spec.url.format(q=quote_plus(query), n=max(max_results, 10))
    async with page_semaphore, manager.context() as ctx:
        page = await ctx.new_page()
        page.set_default_timeout(settings.nav_timeout_ms)
        await page.goto(url, wait_until="domcontentloaded", timeout=settings.nav_timeout_ms)

        # Google's consent interstitial, best effort.
        if spec.name == "google":
            for label in ("Reject all", "Accept all"):
                try:
                    btn = page.get_by_role("button", name=label)
                    if await btn.count():
                        await btn.first.click(timeout=2000)
                        await page.wait_for_load_state("domcontentloaded", timeout=5000)
                        break
                except Exception:  # noqa: BLE001 - consent wall is optional
                    pass

        try:
            await page.wait_for_selector(spec.wait_for, timeout=8000)
        except PWTimeout:
            # Still read the content -- it may be a block page we want to detect,
            # or markup that drifted from `wait_for` but still parses.
            log.warning("%s: wait_for selector timed out", spec.name)

        # Cheap politeness; materially reduces DDG anomaly pages on repeat queries.
        await asyncio.sleep(random.uniform(0.3, 0.9))
        return await page.content()


async def _via_scraper(name: str, query: str, max_results: int) -> list[dict]:
    spec = ENGINES[name]
    html = await _fetch_serp(spec, query, max_results)
    if is_blocked(html, spec):
        raise BlockedError("bot/anomaly page")
    results = parse_results(html, spec, max_results)
    if not results:
        raise RuntimeError("no results parsed (selectors may have rotted)")
    return results


ALL_ENGINES = list(providers.PROVIDERS) + list(ENGINES) + ["commoncrawl"]

# Which sources are ToS-clean, for the caller's benefit.
_LICIT = set(providers.PROVIDERS) | {"commoncrawl"}


def _chain() -> list[str]:
    """APIs (if keyed, quota-ordered) -> browser scrapers -> Common Crawl."""
    return providers.preferred_order() + FALLBACK_ORDER + ["commoncrawl"]


def chain_description() -> list[dict]:
    """The chain `engine="auto"` will actually walk, right now."""
    return [
        {
            "engine": n,
            "kind": (
                "official API" if n in providers.PROVIDERS
                else "open archive" if n == "commoncrawl"
                else "browser scrape (ToS risk)"
            ),
            "licit": n in _LICIT,
        }
        for n in _chain()
    ]


async def _dispatch(name: str, query: str, max_results: int) -> list[dict]:
    if name in providers.PROVIDERS:
        return await providers.search(name, query, max_results)
    if name == "commoncrawl":
        return await commoncrawl.search(query, max_results)
    return await _via_scraper(name, query, max_results)


async def search(query: str, engine: str = "auto", max_results: int = 10) -> dict:
    """Search, preferring ToS-clean sources. See the module docstring for the chain."""
    if engine != "auto" and engine not in ALL_ENGINES:
        raise ValueError(f"Unknown engine {engine!r}. Options: auto, {', '.join(ALL_ENGINES)}")

    order = _chain() if engine == "auto" else [engine]
    tried: list[dict] = []

    for name in order:
        try:
            results = await _dispatch(name, query, max_results)
            if not results:
                raise RuntimeError("no results")
            return {
                "engine": name,
                "licit": name in _LICIT,
                "query": query,
                "count": len(results),
                "results": results,
                "fallbacks_tried": tried,
                "quota": providers.status(),
            }
        except Exception as exc:  # noqa: BLE001 - fall through to the next source
            log.warning("search via %s failed: %s", name, exc)
            tried.append({"engine": name, "error": str(exc)[:200]})

    detail = "; ".join(f"{t['engine']}={t['error']}" for t in tried)
    raise RuntimeError(f"all search sources failed: {detail}")
