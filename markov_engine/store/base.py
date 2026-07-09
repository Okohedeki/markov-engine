"""The Store contract.

A ``Store`` is the single persistence boundary for the engine. All engine code
(clustering, growth, generation, ingestion) talks ONLY to a ``Store`` — never to
a database directly. Implement this ABC to back the engine with any storage you
like (Postgres, a vector DB, an in-memory dict for tests). The bundled
:class:`~markov_engine.store.sqlite.SqliteStore` is the default local backend.

All methods are async. Records returned must expose the attributes used by the
engine — see :mod:`markov_engine.store.records`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from markov_engine.store.records import (
    ArtifactRec,
    ChainRec,
    ChainSourceRec,
    EntityRec,
    SourceRec,
    TopicRec,
)


class Store(ABC):
    # ── sources ───────────────────────────────────────────────────
    @abstractmethod
    async def add_source(
        self,
        *,
        url: str | None,
        title: str | None,
        source_type: str | None,
        content_text: str | None,
        summary: str | None,
        is_note: bool = False,
        metadata: dict | None = None,
    ) -> SourceRec: ...

    @abstractmethod
    async def get_source(self, source_id: int) -> SourceRec | None: ...

    @abstractmethod
    async def get_source_by_url(self, url: str) -> SourceRec | None: ...

    @abstractmethod
    async def list_sources(self, limit: int = 20) -> list[SourceRec]: ...

    @abstractmethod
    async def set_source_topic(self, source_id: int, topic_id: int) -> None: ...

    # ── topics ────────────────────────────────────────────────────
    @abstractmethod
    async def add_topic(
        self, *, canonical_title: str, summary: str | None, embedding: list[float]
    ) -> TopicRec: ...

    @abstractmethod
    async def attach_topic_to_chain(self, topic_id: int, chain_id: int) -> None: ...

    # ── chains ────────────────────────────────────────────────────
    @abstractmethod
    async def create_chain(
        self,
        *,
        title: str,
        centroid: list[float] | None,
        hop_depth: int,
        source_budget: int,
        cadence_hours: float,
    ) -> ChainRec: ...

    @abstractmethod
    async def get_chain(self, chain_id: int) -> ChainRec | None: ...

    @abstractmethod
    async def list_chains(self, limit: int = 50) -> list[ChainRec]: ...

    @abstractmethod
    async def nearest_chain(
        self, embedding: list[float]
    ) -> tuple[ChainRec, float] | None:
        """Return (nearest_chain, cosine_similarity) or None if no chains exist."""
        ...

    @abstractmethod
    async def update_chain_centroid(
        self, chain_id: int, centroid: list[float], topic_count: int
    ) -> None: ...

    @abstractmethod
    async def touch_chain_grown(self, chain_id: int) -> None: ...

    @abstractmethod
    async def update_chain(self, chain_id: int, **fields) -> None: ...

    # ── chain_sources ─────────────────────────────────────────────
    @abstractmethod
    async def add_chain_source(
        self, *, chain_id: int, source_id: int, hop_distance: int, relevance: float
    ) -> bool:
        """Link a Source to a Chain. Return False if already linked."""
        ...

    @abstractmethod
    async def list_chain_sources(
        self, chain_id: int, limit: int = 50
    ) -> list[ChainSourceRec]: ...

    # ── entities / relationships ──────────────────────────────────
    @abstractmethod
    async def add_entity(
        self, *, name: str, entity_type: str, description: str | None
    ) -> int: ...

    @abstractmethod
    async def get_entity_by_name(self, name: str) -> EntityRec | None: ...

    @abstractmethod
    async def add_relationship(self, *, src_id: int, tgt_id: int, rel_type: str) -> None: ...

    @abstractmethod
    async def link_entity_to_source(self, entity_id: int, source_id: int) -> None: ...

    @abstractmethod
    async def gather_entity_neighbors(
        self, entity_id: int, limit: int = 8
    ) -> list[str]: ...

    @abstractmethod
    async def top_entities_for_chain(
        self, chain_id: int, limit: int = 8
    ) -> list[dict]:
        """Return [{"id": .., "name": ..}] most-frequent entities for a Chain."""
        ...

    # ── artifacts ─────────────────────────────────────────────────
    @abstractmethod
    async def add_artifact(
        self,
        *,
        chain_id: int | None,
        artifact_type: str,
        title: str,
        content: str,
        parameters: dict | None,
        model_used: str,
        cost_usd: float,
        source_ids: list[int],
    ) -> ArtifactRec: ...

    @abstractmethod
    async def list_artifacts(
        self, chain_id: int | None = None, limit: int = 20
    ) -> list[ArtifactRec]: ...

    # ── events ────────────────────────────────────────────────────
    @abstractmethod
    async def log_event(
        self, kind: str, *, chain_id: int | None = None, detail: dict | None = None
    ) -> None: ...
