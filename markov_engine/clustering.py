"""Topic→Chain clustering. After a Source is ingested, embed its summary, create
a Topic, and either attach it to the nearest similar Chain or seed a new one.
"""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.embeddings import embed
from markov_engine.store.base import Store
from markov_engine.vectors import incremental_mean as _incremental_mean

logger = logging.getLogger(__name__)
_settings = get_settings()


async def assign_topic(
    store: Store,
    source_id: int,
    title: str,
    summary: str | None,
    *,
    combine_threshold: float | None = None,
    hop_depth: int = 0,
    source_budget: int = 25,
    cadence_hours: float = 24.0,
) -> int:
    """Embed the Source, create its Topic, and cluster into a Chain. Returns chain_id.

    A new Chain seeded here is created with the given ``hop_depth`` /
    ``source_budget`` / ``cadence_hours`` reach parameters.
    """
    threshold = (
        combine_threshold
        if combine_threshold is not None
        else _settings.combine_threshold
    )
    text = (summary or "").strip() or title
    embedding = await embed(text, input_type="document")
    topic = await store.add_topic(
        canonical_title=title[:200], summary=summary, embedding=embedding
    )
    chain_id = await _cluster_into_chain(
        store,
        topic.id,
        title,
        embedding,
        source_id,
        threshold=threshold,
        hop_depth=hop_depth,
        source_budget=source_budget,
        cadence_hours=cadence_hours,
    )
    await store.attach_topic_to_chain(topic.id, chain_id)
    return chain_id


async def _cluster_into_chain(
    store: Store,
    topic_id: int,
    title: str,
    embedding: list[float],
    source_id: int,
    *,
    threshold: float,
    hop_depth: int,
    source_budget: int,
    cadence_hours: float,
) -> int:
    near = await store.nearest_chain(embedding)
    if near and near[1] >= threshold:
        chain, sim = near
        new_centroid = (
            _incremental_mean(
                list(chain.centroid_embedding), embedding, chain.topic_count
            )
            if chain.centroid_embedding is not None
            else embedding
        )
        await store.update_chain_centroid(
            chain.id, new_centroid, chain.topic_count + 1
        )
        await store.add_chain_source(
            chain_id=chain.id, source_id=source_id, hop_distance=0, relevance=sim
        )
        await store.log_event(
            "merge",
            chain_id=chain.id,
            detail={"topic_id": topic_id, "similarity": round(sim, 4)},
        )
        return chain.id

    chain = await store.create_chain(
        title=title[:200],
        centroid=embedding,
        hop_depth=hop_depth,
        source_budget=source_budget,
        cadence_hours=cadence_hours,
    )
    await store.add_chain_source(
        chain_id=chain.id, source_id=source_id, hop_distance=0, relevance=1.0
    )
    await store.log_event(
        "new_chain", chain_id=chain.id, detail={"topic_id": topic_id}
    )
    return chain.id
