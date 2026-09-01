"""Official search APIs -- the ToS-clean path.

Scraping a search engine's result page violates its Terms of Service. A provider
here is sanctioned by its operator, so using one avoids that entirely.

  tavily  TAVILY_API_KEY  1000 credits/MONTH, free, no credit card

Not required: with no key set, search falls back to browser scraping and behaves
exactly as before.

Quota accounting is local (.search_usage.json in docs_dir). It is a best-effort
mirror of the provider's own counter, not a source of truth -- a 429 from the
provider is always believed over it.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import httpx

from webresearch.config import settings

log = logging.getLogger(__name__)


class QuotaExhausted(RuntimeError):
    """The provider says we're out of quota (or our local counter thinks so)."""


@dataclass(frozen=True)
class Provider:
    name: str
    limit: int
    period: str  # "day" | "month"

    @property
    def enabled(self) -> bool:
        return bool(_credentials(self.name))


# Provider names must never collide with a scraped engine name in engines.py: a
# shared key would route the scraper's slot to the API and report a scraped SERP
# as ToS-clean. Pinned by tests/test_search_chain.py.
PROVIDERS = {
    "tavily": Provider("tavily", limit=1000, period="month"),
}


def _credentials(name: str) -> tuple[str, ...] | None:
    if name == "tavily":
        key = os.environ.get("TAVILY_API_KEY")
        return (key,) if key else None
    return None


# --------------------------------------------------------------------------- quota

def _usage_file() -> Path:
    return settings.docs_dir / ".search_usage.json"


def _period_key(period: str) -> str:
    today = date.today()
    return today.isoformat() if period == "day" else f"{today.year}-{today.month:02d}"


def _load() -> dict:
    try:
        return json.loads(_usage_file().read_text())
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    try:
        _usage_file().write_text(json.dumps(data, indent=2))
    except OSError as exc:  # never fail a search because bookkeeping failed
        log.debug("could not persist search usage: %s", exc)


def used(name: str) -> int:
    p = PROVIDERS[name]
    entry = _load().get(name) or {}
    if entry.get("period") != _period_key(p.period):
        return 0  # the window rolled over
    return int(entry.get("count", 0))


def remaining(name: str) -> int:
    return max(0, PROVIDERS[name].limit - used(name))


def record(name: str, n: int = 1) -> None:
    p = PROVIDERS[name]
    data = _load()
    key = _period_key(p.period)
    entry = data.get(name) or {}
    count = int(entry.get("count", 0)) if entry.get("period") == key else 0
    data[name] = {"period": key, "count": count + n}
    _save(data)


def mark_exhausted(name: str) -> None:
    """The provider returned a quota error -- trust it over our counter."""
    p = PROVIDERS[name]
    data = _load()
    data[name] = {"period": _period_key(p.period), "count": p.limit}
    _save(data)


def preferred_order() -> list[str]:
    """Configured providers with quota left, most headroom first.

    Ranking by *fraction* remaining rather than absolute count so that adding a
    provider with a different allowance and reset window still behaves sanely.
    """
    live = [n for n, p in PROVIDERS.items() if p.enabled and remaining(n) > 0]
    return sorted(live, key=lambda n: -(remaining(n) / PROVIDERS[n].limit))


# --------------------------------------------------------------------------- search

async def _tavily(query: str, max_results: int) -> list[dict]:
    (key,) = _credentials("tavily")
    payload = {"query": query, "max_results": min(max_results, 20), "search_depth": "basic"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.tavily.com/search",
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
        )
    if r.status_code in (429, 432, 433):  # 432/433 = tavily's plan-limit codes
        mark_exhausted("tavily")
        raise QuotaExhausted(f"tavily: HTTP {r.status_code} (monthly credits spent)")
    r.raise_for_status()
    return [
        {
            "title": i.get("title", ""),
            "url": i.get("url", ""),
            "snippet": (i.get("content") or "")[:300],
        }
        for i in (r.json().get("results") or [])
        if i.get("url")
    ]


_IMPL = {"tavily": _tavily}


async def search(name: str, query: str, max_results: int) -> list[dict]:
    if not PROVIDERS[name].enabled:
        raise RuntimeError(f"{name}: no API key configured")
    if remaining(name) <= 0:
        raise QuotaExhausted(f"{name}: local counter says quota is spent")

    results = await _IMPL[name](query, max_results)
    record(name)
    log.info("%s: %d results (%d/%d used)", name, len(results),
             used(name), PROVIDERS[name].limit)
    return results


def status() -> dict:
    return {
        n: {
            "configured": p.enabled,
            "used": used(n) if p.enabled else 0,
            "limit": p.limit,
            "remaining": remaining(n) if p.enabled else 0,
            "resets": p.period,
        }
        for n, p in PROVIDERS.items()
    }
