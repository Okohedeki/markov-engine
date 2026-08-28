"""Additive schema upgrades preserve and repair legacy SQLite databases."""

from __future__ import annotations

import sqlite3

import pytest

from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_legacy_database_gains_new_columns_and_remains_writable(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE sources ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT, title TEXT, source_type TEXT, "
        "content_text TEXT, summary TEXT, topic_id INTEGER, "
        "is_note INTEGER NOT NULL DEFAULT 0, ingested_at TEXT)"
    )
    conn.commit()
    conn.close()

    store = await SqliteStore.open(str(path))
    try:
        source = await store.add_source(
            url="https://example.com/video",
            title="Legacy-safe",
            source_type="youtube",
            content_text="Transcript",
            summary="Summary",
            metadata={"duration": 42},
        )
        assert source.metadata == {"duration": 42}
        async with store._conn.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ) as cur:
            assert [tuple(row) for row in await cur.fetchall()] == [
                (1, "research_case_v1"),
                    (2, "connection_graph_v2"),
                    (3, "focused_research_plan_v2"),
                    (4, "branched_artifacts_v2"),
                ]
    finally:
        await store.close()

    # Reopening is idempotent and does not duplicate migration records.
    reopened = await SqliteStore.open(str(path))
    try:
        assert (await reopened.get_source_by_url("https://example.com/video")) is not None
        async with reopened._conn.execute(
            "SELECT COUNT(*) FROM schema_migrations"
        ) as cur:
            assert (await cur.fetchone())[0] == 4
    finally:
        await reopened.close()
