"""Key points: the deep-dive units. extract_entities returns explained key
points; ingest_url persists them per source (the seeds for chain branches).

No network: extraction is monkeypatched; storage is the bundled SqliteStore.
"""

from __future__ import annotations

from markov_engine import ingest as ingest_mod
from markov_engine.entities import _coerce_key_points
from markov_engine.extract import ExtractedContent
from markov_engine.store.sqlite import SqliteStore


def test_coerce_key_points_shapes():
    # bare strings become title-only; dicts keep detail; blanks dropped.
    out = _coerce_key_points([
        "A lone claim",
        {"title": "Explained", "detail": "Because of X, Y follows."},
        {"point": "alt key name", "explanation": "alt detail key"},
        "",
        123,
    ])
    assert out == [
        {"title": "A lone claim", "detail": ""},
        {"title": "Explained", "detail": "Because of X, Y follows."},
        {"title": "alt key name", "detail": "alt detail key"},
    ]


async def test_ingest_persists_key_points(monkeypatch):
    store = await SqliteStore.open(":memory:")
    kps = [
        {"title": "Point one", "detail": "The first thing explained in depth."},
        {"title": "Point two", "detail": "The second thing explained in depth."},
    ]

    async def _fake_extract(url, tmp_dir, whisper_model):
        return ExtractedContent(url=url, source_type="youtube", title="Clip",
                                content_text="a transcript body", metadata={})

    async def _fake_entities(text, title, source_type, model=None):
        return {"success": True, "summary": "sum", "key_points": kps,
                "entities": [], "relationships": [], "cost_usd": 0.0}

    monkeypatch.setattr(ingest_mod, "extract_content", _fake_extract)
    monkeypatch.setattr(ingest_mod, "extract_entities", _fake_entities)

    res = await ingest_mod.ingest_url(store, "https://youtube.com/watch?v=x", cluster=False)
    assert res["success"] is True

    rows = await (await store._conn.execute(
        "SELECT ordinal, title, detail FROM source_key_points WHERE source_id=? ORDER BY ordinal",
        (res["source_id"],),
    )).fetchall()
    assert [(r[0], r[1]) for r in rows] == [(0, "Point one"), (1, "Point two")]
    assert rows[0][2] == "The first thing explained in depth."
