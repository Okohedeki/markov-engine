"""Clustering tests against the real SqliteStore (in-memory) with embeddings
monkeypatched to a deterministic function — no network calls.

Asserts the two clustering behaviours:
  * similar summaries land on the SAME chain (cosine >= combine_threshold)
  * a distinct summary seeds a NEW chain
"""

from __future__ import annotations

import asyncio

import pytest

from markov_engine import clustering
from markov_engine.store.sqlite import SqliteStore

# A tiny deterministic "embedding" space: map known phrases to unit-ish vectors.
# "ai" and "ml" point nearly the same way (cosine ~0.997 >= 0.82 threshold);
# "cooking" is orthogonal.
_VECTORS = {
    "ai": [1.0, 0.05, 0.0],
    "ml": [1.0, 0.10, 0.0],
    "cooking": [0.0, 0.0, 1.0],
}


def _fake_embed_factory():
    async def _fake_embed(text: str, *, input_type: str = "document") -> list[float]:
        key = (text or "").strip().lower()
        for name, vec in _VECTORS.items():
            if name in key:
                return list(vec)
        return [0.0, 1.0, 0.0]

    return _fake_embed


@pytest.mark.asyncio
async def test_similar_sources_same_chain(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        monkeypatch.setattr(clustering, "embed", _fake_embed_factory())

        s1 = await store.add_source(
            url="http://a", title="AI advances", source_type="article",
            content_text="x", summary="ai breakthroughs",
        )
        chain1 = await clustering.assign_topic(
            store, s1.id, "AI advances", "ai breakthroughs", combine_threshold=0.82
        )

        s2 = await store.add_source(
            url="http://b", title="ML progress", source_type="article",
            content_text="y", summary="ml progress and ai",
        )
        chain2 = await clustering.assign_topic(
            store, s2.id, "ML progress", "ml progress and ai", combine_threshold=0.82
        )

        assert chain1 == chain2, "similar summaries should merge into one chain"
        chains = await store.list_chains()
        assert len(chains) == 1
        # Both sources are linked to the merged chain.
        members = await store.list_chain_sources(chain1)
        assert {m.source.id for m in members} == {s1.id, s2.id}
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_distinct_source_new_chain(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        monkeypatch.setattr(clustering, "embed", _fake_embed_factory())

        s1 = await store.add_source(
            url="http://a", title="AI advances", source_type="article",
            content_text="x", summary="ai breakthroughs",
        )
        chain1 = await clustering.assign_topic(
            store, s1.id, "AI advances", "ai breakthroughs", combine_threshold=0.82
        )

        s2 = await store.add_source(
            url="http://c", title="Cooking pasta", source_type="article",
            content_text="z", summary="cooking recipes",
        )
        chain2 = await clustering.assign_topic(
            store, s2.id, "Cooking pasta", "cooking recipes", combine_threshold=0.82
        )

        assert chain1 != chain2, "distinct summary should seed a new chain"
        chains = await store.list_chains()
        assert len(chains) == 2
    finally:
        await store.close()


if __name__ == "__main__":  # pragma: no cover - manual run without pytest
    class _MP:
        def setattr(self, obj, name, value):
            setattr(obj, name, value)

    asyncio.run(test_similar_sources_same_chain(_MP()))
    asyncio.run(test_distinct_source_new_chain(_MP()))
    print("clustering tests passed")
