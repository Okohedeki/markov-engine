"""Local, single-user SQLite implementation of :class:`Store`.

Single DB file, no owner_id, no tenancy. Embeddings are stored as JSON text;
``nearest_chain`` loads all chains and computes cosine similarity in Python —
local scale is tiny, so this is fine and keeps the dependency surface minimal.

Open with ``store = await SqliteStore.open("~/.markov/markov.db")`` and close
with ``await store.close()``.
"""

from __future__ import annotations

import datetime as dt
import json
import os

import aiosqlite

from markov_engine.store.base import Store
from markov_engine.store.records import (
    ArtifactRec,
    ChainRec,
    ChainSourceRec,
    EntityRec,
    SourceRec,
    TopicRec,
)
from markov_engine.vectors import cosine_similarity

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT,
    title TEXT,
    source_type TEXT,
    content_text TEXT,
    summary TEXT,
    topic_id INTEGER,
    is_note INTEGER NOT NULL DEFAULT 0,
    metadata TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_sources_url ON sources(url) WHERE url IS NOT NULL;

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_title TEXT NOT NULL,
    summary TEXT,
    embedding TEXT,
    chain_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    centroid_embedding TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    hop_depth INTEGER NOT NULL DEFAULT 0,
    source_budget INTEGER NOT NULL DEFAULT 5,
    cadence_hours REAL NOT NULL DEFAULT 24,
    topic_count INTEGER NOT NULL DEFAULT 0,
    last_grown_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chain_sources (
    chain_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    hop_distance INTEGER NOT NULL DEFAULT 0,
    relevance REAL NOT NULL DEFAULT 1.0,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (chain_id, source_id)
);

CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT,
    UNIQUE (name, entity_type)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity_id INTEGER NOT NULL,
    target_entity_id INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    UNIQUE (source_entity_id, target_entity_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS entity_sources (
    entity_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    PRIMARY KEY (entity_id, source_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id INTEGER,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    parameters TEXT,
    model_used TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS artifact_sources (
    artifact_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    PRIMARY KEY (artifact_id, source_id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id INTEGER,
    kind TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _loads(raw: str | None) -> list[float] | None:
    return json.loads(raw) if raw else None


def _ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


class SqliteStore(Store):
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    @classmethod
    async def open(cls, path: str) -> "SqliteStore":
        """Connect to (creating if needed) a SQLite DB file and ensure tables."""
        if path != ":memory:":
            path = os.path.expanduser(path)
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.executescript(_SCHEMA)
        await conn.commit()
        return cls(conn)

    async def close(self) -> None:
        await self._conn.close()

    # ── row → record mappers ──────────────────────────────────────
    @staticmethod
    def _source(row: aiosqlite.Row) -> SourceRec:
        return SourceRec(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            source_type=row["source_type"],
            content_text=row["content_text"],
            summary=row["summary"],
            is_note=bool(row["is_note"]),
            topic_id=row["topic_id"],
            ingested_at=_ts(row["ingested_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )

    @staticmethod
    def _chain(row: aiosqlite.Row) -> ChainRec:
        return ChainRec(
            id=row["id"],
            title=row["title"],
            centroid_embedding=_loads(row["centroid_embedding"]),
            status=row["status"],
            hop_depth=row["hop_depth"],
            source_budget=row["source_budget"],
            cadence_hours=float(row["cadence_hours"]),
            topic_count=row["topic_count"],
            last_grown_at=_ts(row["last_grown_at"]),
            created_at=_ts(row["created_at"]),
        )

    # ── sources ───────────────────────────────────────────────────
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
    ) -> SourceRec:
        cur = await self._conn.execute(
            "INSERT INTO sources (url, title, source_type, content_text, summary, is_note, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (url, title, source_type, content_text, summary, int(is_note),
             json.dumps(metadata) if metadata else None),
        )
        await self._conn.commit()
        rec = await self.get_source(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_source(self, source_id: int) -> SourceRec | None:
        async with self._conn.execute(
            "SELECT * FROM sources WHERE id = ?", (source_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._source(row) if row else None

    async def get_source_by_url(self, url: str) -> SourceRec | None:
        async with self._conn.execute(
            "SELECT * FROM sources WHERE url = ?", (url,)
        ) as cur:
            row = await cur.fetchone()
        return self._source(row) if row else None

    async def list_sources(self, limit: int = 20) -> list[SourceRec]:
        async with self._conn.execute(
            "SELECT * FROM sources ORDER BY ingested_at DESC, id DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._source(r) for r in rows]

    async def set_source_topic(self, source_id: int, topic_id: int) -> None:
        await self._conn.execute(
            "UPDATE sources SET topic_id = ? WHERE id = ?", (topic_id, source_id)
        )
        await self._conn.commit()

    # ── topics ────────────────────────────────────────────────────
    async def add_topic(
        self, *, canonical_title: str, summary: str | None, embedding: list[float]
    ) -> TopicRec:
        cur = await self._conn.execute(
            "INSERT INTO topics (canonical_title, summary, embedding) VALUES (?, ?, ?)",
            (canonical_title, summary, json.dumps(embedding)),
        )
        await self._conn.commit()
        return TopicRec(
            id=cur.lastrowid,
            canonical_title=canonical_title,
            summary=summary,
            embedding=embedding,
        )

    async def attach_topic_to_chain(self, topic_id: int, chain_id: int) -> None:
        await self._conn.execute(
            "UPDATE topics SET chain_id = ? WHERE id = ?", (chain_id, topic_id)
        )
        await self._conn.commit()

    # ── chains ────────────────────────────────────────────────────
    async def create_chain(
        self,
        *,
        title: str,
        centroid: list[float] | None,
        hop_depth: int,
        source_budget: int,
        cadence_hours: float,
    ) -> ChainRec:
        cur = await self._conn.execute(
            "INSERT INTO chains (title, centroid_embedding, hop_depth, source_budget, "
            "cadence_hours, topic_count) VALUES (?, ?, ?, ?, ?, 1)",
            (
                title,
                json.dumps(centroid) if centroid is not None else None,
                hop_depth,
                source_budget,
                cadence_hours,
            ),
        )
        await self._conn.commit()
        rec = await self.get_chain(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_chain(self, chain_id: int) -> ChainRec | None:
        async with self._conn.execute(
            "SELECT * FROM chains WHERE id = ?", (chain_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._chain(row) if row else None

    async def list_chains(self, limit: int = 50) -> list[ChainRec]:
        async with self._conn.execute(
            "SELECT * FROM chains ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ) as cur:
            rows = await cur.fetchall()
        return [self._chain(r) for r in rows]

    async def nearest_chain(
        self, embedding: list[float]
    ) -> tuple[ChainRec, float] | None:
        async with self._conn.execute(
            "SELECT * FROM chains WHERE status != 'archived' "
            "AND centroid_embedding IS NOT NULL"
        ) as cur:
            rows = await cur.fetchall()
        best: tuple[ChainRec, float] | None = None
        for row in rows:
            chain = self._chain(row)
            if chain.centroid_embedding is None:
                continue
            sim = cosine_similarity(embedding, chain.centroid_embedding)
            if best is None or sim > best[1]:
                best = (chain, sim)
        return best

    async def update_chain_centroid(
        self, chain_id: int, centroid: list[float], topic_count: int
    ) -> None:
        await self._conn.execute(
            "UPDATE chains SET centroid_embedding = ?, topic_count = ? WHERE id = ?",
            (json.dumps(centroid), topic_count, chain_id),
        )
        await self._conn.commit()

    async def touch_chain_grown(self, chain_id: int) -> None:
        await self._conn.execute(
            "UPDATE chains SET last_grown_at = datetime('now') WHERE id = ?",
            (chain_id,),
        )
        await self._conn.commit()

    async def update_chain(self, chain_id: int, **fields) -> None:
        if not fields:
            return
        # `centroid` maps to the centroid_embedding column (JSON-encoded).
        cols, vals = [], []
        for key, value in fields.items():
            if key == "centroid":
                key = "centroid_embedding"
            if key == "centroid_embedding" and value is not None:
                value = json.dumps(value)
            cols.append(f"{key} = ?")
            vals.append(value)
        vals.append(chain_id)
        await self._conn.execute(
            f"UPDATE chains SET {', '.join(cols)} WHERE id = ?", vals
        )
        await self._conn.commit()

    # ── chain_sources ─────────────────────────────────────────────
    async def add_chain_source(
        self, *, chain_id: int, source_id: int, hop_distance: int, relevance: float
    ) -> bool:
        cur = await self._conn.execute(
            "INSERT OR IGNORE INTO chain_sources (chain_id, source_id, hop_distance, relevance) "
            "VALUES (?, ?, ?, ?)",
            (chain_id, source_id, hop_distance, relevance),
        )
        await self._conn.commit()
        return cur.rowcount > 0

    async def list_chain_sources(
        self, chain_id: int, limit: int = 50
    ) -> list[ChainSourceRec]:
        async with self._conn.execute(
            "SELECT s.*, cs.hop_distance AS cs_hop, cs.relevance AS cs_rel, "
            "cs.added_at AS cs_added "
            "FROM chain_sources cs JOIN sources s ON s.id = cs.source_id "
            "WHERE cs.chain_id = ? ORDER BY cs.added_at DESC LIMIT ?",
            (chain_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [
            ChainSourceRec(
                source=self._source(r),
                hop_distance=r["cs_hop"],
                relevance=r["cs_rel"],
                added_at=_ts(r["cs_added"]),
            )
            for r in rows
        ]

    # ── entities / relationships ──────────────────────────────────
    async def add_entity(
        self, *, name: str, entity_type: str, description: str | None
    ) -> int:
        async with self._conn.execute(
            "SELECT id, description FROM entities WHERE name = ? AND entity_type = ?",
            (name, entity_type),
        ) as cur:
            row = await cur.fetchone()
        if row:
            # Backfill an empty description if we now have one.
            if description and not row["description"]:
                await self._conn.execute(
                    "UPDATE entities SET description = ? WHERE id = ?",
                    (description, row["id"]),
                )
                await self._conn.commit()
            return row["id"]
        cur = await self._conn.execute(
            "INSERT INTO entities (name, entity_type, description) VALUES (?, ?, ?)",
            (name, entity_type, description),
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_entity_by_name(self, name: str) -> EntityRec | None:
        async with self._conn.execute(
            "SELECT * FROM entities WHERE name = ?", (name,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            async with self._conn.execute(
                "SELECT * FROM entities WHERE name LIKE ? LIMIT 1", (f"%{name}%",)
            ) as cur:
                row = await cur.fetchone()
        if not row:
            return None
        return EntityRec(
            id=row["id"],
            name=row["name"],
            entity_type=row["entity_type"],
            description=row["description"],
        )

    async def add_relationship(
        self, *, src_id: int, tgt_id: int, rel_type: str
    ) -> None:
        await self._conn.execute(
            "INSERT INTO relationships (source_entity_id, target_entity_id, relationship_type) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT (source_entity_id, target_entity_id, relationship_type) "
            "DO UPDATE SET weight = weight + 1",
            (src_id, tgt_id, rel_type),
        )
        await self._conn.commit()

    async def link_entity_to_source(self, entity_id: int, source_id: int) -> None:
        await self._conn.execute(
            "INSERT OR IGNORE INTO entity_sources (entity_id, source_id) VALUES (?, ?)",
            (entity_id, source_id),
        )
        await self._conn.commit()

    async def gather_entity_neighbors(
        self, entity_id: int, limit: int = 8
    ) -> list[str]:
        async with self._conn.execute(
            """
            SELECT e.name, COUNT(DISTINCT es2.source_id) AS shared
            FROM entity_sources es1
            JOIN entity_sources es2
              ON es2.source_id = es1.source_id AND es2.entity_id != es1.entity_id
            JOIN entities e ON e.id = es2.entity_id
            WHERE es1.entity_id = ?
            GROUP BY e.id ORDER BY shared DESC LIMIT ?
            """,
            (entity_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [r["name"] for r in rows]

    async def top_entities_for_chain(
        self, chain_id: int, limit: int = 8
    ) -> list[dict]:
        async with self._conn.execute(
            """
            SELECT e.id AS id, e.name AS name, COUNT(*) AS freq
            FROM chain_sources cs
            JOIN entity_sources es ON es.source_id = cs.source_id
            JOIN entities e ON e.id = es.entity_id
            WHERE cs.chain_id = ?
            GROUP BY e.id, e.name ORDER BY freq DESC LIMIT ?
            """,
            (chain_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [{"id": r["id"], "name": r["name"]} for r in rows]

    # ── artifacts ─────────────────────────────────────────────────
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
    ) -> ArtifactRec:
        cur = await self._conn.execute(
            "INSERT INTO artifacts (chain_id, artifact_type, title, content, parameters, "
            "model_used, cost_usd) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                chain_id,
                artifact_type,
                title,
                content,
                json.dumps(parameters) if parameters is not None else None,
                model_used,
                cost_usd,
            ),
        )
        artifact_id = cur.lastrowid
        for sid in source_ids:
            await self._conn.execute(
                "INSERT OR IGNORE INTO artifact_sources (artifact_id, source_id) VALUES (?, ?)",
                (artifact_id, sid),
            )
        await self._conn.commit()
        return ArtifactRec(
            id=artifact_id,
            chain_id=chain_id,
            artifact_type=artifact_type,
            title=title,
            content=content,
            parameters=parameters,
            model_used=model_used,
            cost_usd=cost_usd,
        )

    async def list_artifacts(
        self, chain_id: int | None = None, limit: int = 20
    ) -> list[ArtifactRec]:
        if chain_id is not None:
            query = (
                "SELECT * FROM artifacts WHERE chain_id = ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?"
            )
            params: tuple = (chain_id, limit)
        else:
            query = "SELECT * FROM artifacts ORDER BY created_at DESC, id DESC LIMIT ?"
            params = (limit,)
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [
            ArtifactRec(
                id=r["id"],
                chain_id=r["chain_id"],
                artifact_type=r["artifact_type"],
                title=r["title"],
                content=r["content"],
                parameters=json.loads(r["parameters"]) if r["parameters"] else None,
                model_used=r["model_used"],
                cost_usd=float(r["cost_usd"]),
                created_at=_ts(r["created_at"]),
            )
            for r in rows
        ]

    # ── events ────────────────────────────────────────────────────
    async def log_event(
        self, kind: str, *, chain_id: int | None = None, detail: dict | None = None
    ) -> None:
        await self._conn.execute(
            "INSERT INTO events (chain_id, kind, detail) VALUES (?, ?, ?)",
            (chain_id, kind, json.dumps(detail) if detail is not None else None),
        )
        await self._conn.commit()
