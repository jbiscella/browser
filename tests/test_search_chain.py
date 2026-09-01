"""Chain composition and the ToS-honesty invariant. No network.

The bug these pin: `google` named both the official API provider and the scraped
engine. The shared key routed the scraper's slot to the API *and* reported a
scraped result as `licit: true` — i.e. the system would have told you a
ToS-violating source was ToS-clean. That must never regress.
"""

from __future__ import annotations

import pytest

from webresearch import commoncrawl, providers, search


def test_api_and_scraper_namespaces_do_not_collide():
    from webresearch.engines import ENGINES

    overlap = set(providers.PROVIDERS) & set(ENGINES)
    assert not overlap, f"provider/engine name collision: {overlap}"


def test_scraped_engines_are_never_reported_as_licit():
    from webresearch.engines import ENGINES

    for step in search.chain_description():
        if step["engine"] in ENGINES:
            assert step["licit"] is False, (
                f"{step['engine']} is a scraped SERP but was reported as ToS-clean"
            )


def test_licit_sources_are_apis_and_the_open_archive():
    for step in search.chain_description():
        if step["licit"]:
            assert step["engine"] in set(providers.PROVIDERS) | {"commoncrawl"}


def test_commoncrawl_is_last_in_the_chain():
    """It's the free, always-legal fallback — it must not pre-empt better sources."""
    assert search.chain_description()[-1]["engine"] == "commoncrawl"


def test_unkeyed_providers_are_skipped_not_attempted(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert providers.preferred_order() == []


def test_keyed_provider_leads_the_chain(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "z")
    monkeypatch.setattr(providers, "used", lambda name: 0)
    assert providers.preferred_order() == ["tavily"]
    assert search._chain()[0] == "tavily"


def test_exhausted_provider_drops_out_of_the_chain(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "z")
    monkeypatch.setattr(providers, "used", lambda name: providers.PROVIDERS[name].limit)
    assert providers.preferred_order() == []


@pytest.mark.parametrize(
    "query,expected",
    [
        ("site:swica.ch completa pdf", "swica.ch"),
        ("axa.ch cga economia domestica", "axa.ch"),
        ("https://www4.swica.ch/p/030_i_AVB.pdf", "www4.swica.ch"),
        ("what is a transformer", None),
        ("version 1.2 release notes", None),  # must not read "1.2" as a domain
    ],
)
def test_commoncrawl_domain_extraction(query, expected):
    assert commoncrawl.extract_domain(query) == expected


async def test_commoncrawl_refuses_a_general_query_rather_than_guessing():
    with pytest.raises(commoncrawl.NoDomainInQuery):
        await commoncrawl.search("what is a transformer")
