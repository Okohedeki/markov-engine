"""Lightweight dataclass records returned by a :class:`~markov_engine.store.base.Store`.

The engine accesses results by ATTRIBUTE (e.g. ``chain.id``,
``chain.centroid_embedding``, ``source.content_text``). Any Store backend must
return objects that expose these attributes — these dataclasses are the
canonical shape used by the bundled SQLite store.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class SourceRec:
    id: int
    url: str | None
    title: str | None
    source_type: str | None
    content_text: str | None
    summary: str | None
    is_note: bool = False
    topic_id: int | None = None
    ingested_at: dt.datetime | None = None
    metadata: dict | None = None


@dataclass
class TopicRec:
    id: int
    canonical_title: str
    summary: str | None
    embedding: list[float] | None = None
    chain_id: int | None = None


@dataclass
class ChainRec:
    id: int
    title: str
    centroid_embedding: list[float] | None
    status: str = "active"
    hop_depth: int = 0
    source_budget: int = 5
    cadence_hours: float = 24.0
    topic_count: int = 0
    last_grown_at: dt.datetime | None = None
    created_at: dt.datetime | None = None


@dataclass
class ChainSourceRec:
    """A Source joined with its membership metadata for a given Chain."""

    source: SourceRec
    hop_distance: int = 0
    relevance: float = 1.0
    added_at: dt.datetime | None = None


@dataclass
class EntityRec:
    id: int
    name: str
    entity_type: str
    description: str | None = None


@dataclass
class ArtifactRec:
    id: int
    chain_id: int | None
    artifact_type: str
    title: str
    content: str
    parameters: dict | None = field(default=None)
    model_used: str | None = None
    cost_usd: float = 0.0
    created_at: dt.datetime | None = None
