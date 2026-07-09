"""Video/media metadata (creator, thumbnail, duration) survives ingestion.

``_extract_media`` builds a ``metadata`` dict from yt-dlp info, but it used to be
dropped before persistence. These tests pin the thread:

  * the store round-trips ``metadata`` through ``add_source`` → ``get_source``.
  * ``ingest_url`` forwards ``ExtractedContent.metadata`` into ``add_source``.

No network: extraction + entity steps are monkeypatched.
"""

from __future__ import annotations

from markov_engine import ingest as ingest_mod
from markov_engine.extract import ExtractedContent
from markov_engine.store.sqlite import SqliteStore


async def test_store_roundtrips_metadata():
    store = await SqliteStore.open(":memory:")
    src = await store.add_source(
        url="https://tiktok.com/@creator/video/1",
        title="Dense clip",
        source_type="tiktok",
        content_text="transcript...",
        summary="a summary",
        metadata={"uploader": "@creator", "thumbnail": "https://img/1.jpg", "duration": 42},
    )
    fetched = await store.get_source(src.id)
    assert fetched is not None
    assert fetched.metadata == {
        "uploader": "@creator",
        "thumbnail": "https://img/1.jpg",
        "duration": 42,
    }


async def test_store_null_metadata_stays_none():
    store = await SqliteStore.open(":memory:")
    src = await store.add_source(
        url="https://example.com/article",
        title="Just an article",
        source_type="article",
        content_text="body",
        summary="s",
    )
    fetched = await store.get_source(src.id)
    assert fetched is not None
    assert fetched.metadata is None


async def test_ingest_url_forwards_metadata(monkeypatch):
    store = await SqliteStore.open(":memory:")
    meta = {"uploader": "@creator", "channel": "Creator", "thumbnail": "t.jpg", "duration": 30}

    async def _fake_extract(url, tmp_dir, whisper_model):
        return ExtractedContent(
            url=url, source_type="tiktok", title="Clip",
            content_text="hello world transcript", metadata=meta,
        )

    async def _fake_entities(text, title, source_type, model=None):
        return {"success": True, "entities": [], "relationships": [],
                "summary": "sum", "cost_usd": 0.0}

    monkeypatch.setattr(ingest_mod, "extract_content", _fake_extract)
    monkeypatch.setattr(ingest_mod, "extract_entities", _fake_entities)

    res = await ingest_mod.ingest_url(store, "https://tiktok.com/@creator/video/2", cluster=False)
    assert res["success"] is True
    stored = await store.get_source(res["source_id"])
    assert stored.metadata == meta
