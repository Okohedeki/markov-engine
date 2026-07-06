"""Growth split (guided walk): discovery is separable from ingestion.

  * ``discover_candidates`` ranks NEW candidates and ingests NOTHING (so it is
    cheap/safe to run on demand for a "pick where this goes next" UI), and it
    carries title/snippet through for rendering cards.
  * ``ingest_chosen`` commits only the subset it is handed.

No network: search + ingest are monkeypatched; the chain has no centroid so the
snippet-embedding path is skipped (relevance defaults to 1.0).
"""

from __future__ import annotations

import pytest

from markov_engine import growth
from markov_engine.store.sqlite import SqliteStore


async def _fixed_queries(store, chain, hop_depth, model):
    return [{"q": "q1", "hop": 0}]


def _fake_search_factory(url_titles):
    async def _fake_search(q, *, max_results=5):
        return [
            {"url": u, "title": t, "snippet": "snip",
             "kind": "web", "platform": "web"}
            for u, t in url_titles
        ]
    return _fake_search


async def _seed_chain(store):
    s = await store.add_source(
        url="http://seed", title="Seed", source_type="article",
        content_text="x", summary="seed subject",
    )
    chain = await store.create_chain(
        title="Seed subject", centroid=None,
        hop_depth=1, source_budget=5, cadence_hours=24,
    )
    await store.add_chain_source(
        chain_id=chain.id, source_id=s.id, hop_distance=0, relevance=1.0
    )
    return await store.get_chain(chain.id)


@pytest.mark.asyncio
async def test_discover_ranks_without_ingesting(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        chain = await _seed_chain(store)
        monkeypatch.setattr(growth, "_build_queries", _fixed_queries)
        monkeypatch.setattr(growth, "search_web", _fake_search_factory(
            [("http://a", "Quantum computing milestone"),
             ("http://b", "Ocean acidification report")]))

        ingest_calls = {"n": 0}

        async def _boom(*a, **k):  # discovery must never ingest
            ingest_calls["n"] += 1
            return {"success": False}

        monkeypatch.setattr(growth, "ingest_url", _boom)

        cands = await growth.discover_candidates(
            store, chain, hop_depth=1, source_budget=5
        )

        assert ingest_calls["n"] == 0
        assert {c["url"] for c in cands} == {"http://a", "http://b"}
        # UI fields carried through for candidate cards.
        assert all(c.get("title") and "snippet" in c for c in cands)
        # Only the seed source exists — nothing was added.
        assert len(await store.list_chain_sources(chain.id)) == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_ingest_chosen_commits_only_the_subset(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        chain = await _seed_chain(store)

        async def _fake_ingest(store, url, *, model=None, cluster=True):
            s = await store.add_source(
                url=url, title=f"T {url}", source_type="article",
                content_text="x", summary="s",
            )
            return {"success": True, "source_id": s.id, "cost_usd": 0.0}

        monkeypatch.setattr(growth, "ingest_url", _fake_ingest)

        chosen = [
            {"url": "http://a", "hop": 0, "relevance": 1.0, "platform": "web"},
            {"url": "http://b", "hop": 0, "relevance": 1.0, "platform": "web"},
        ]
        res = await growth.ingest_chosen(store, chain, chosen, cycle_cost_cap=1.0)

        assert res["added"] == 2
        # seed (1) + the two chosen = 3
        assert len(await store.list_chain_sources(chain.id)) == 3
    finally:
        await store.close()
