"""Ingestion pipeline: extract content → extract entities → store → assign Topic
→ cluster into a Chain."""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.entities import extract_entities
from markov_engine.extract import extract_content
from markov_engine.store.base import Store

logger = logging.getLogger(__name__)
_settings = get_settings()


async def _link_extraction(
    store: Store, source_id: int, extraction: dict
) -> tuple[int, int]:
    if not extraction.get("success"):
        return 0, 0
    ent_count = rel_count = 0
    for ent in extraction["entities"]:
        eid = await store.add_entity(
            name=ent["name"],
            entity_type=ent["type"],
            description=ent.get("description", ""),
        )
        await store.link_entity_to_source(eid, source_id)
        ent_count += 1
    for rel in extraction["relationships"]:
        src = await store.get_entity_by_name(rel["source"])
        tgt = await store.get_entity_by_name(rel["target"])
        if src and tgt:
            await store.add_relationship(src_id=src.id, tgt_id=tgt.id, rel_type=rel["type"])
            rel_count += 1
    return ent_count, rel_count


async def ingest_url(
    store: Store,
    url: str,
    *,
    model: str | None = None,
    whisper_model: str | None = None,
    tmp_dir: str | None = None,
    cluster: bool = True,
) -> dict:
    """Full ingestion pipeline. Returns dict: success, source_id, title, source_type,
    summary, entity_count, rel_count, cost_usd, chain_id, reused."""
    try:
        existing = await store.get_source_by_url(url)
        if existing:
            return {
                "success": True,
                "source_id": existing.id,
                "title": existing.title,
                "source_type": existing.source_type,
                "summary": existing.summary,
                "entity_count": 0,
                "rel_count": 0,
                "cost_usd": 0.0,
                "chain_id": None,
                "reused": True,
            }

        content = await extract_content(
            url,
            tmp_dir or _settings.tmp_dir,
            whisper_model
            or (_settings.whisper_model if _settings.transcribe_media else None),
        )
        if not content.success or not (content.content_text or "").strip():
            return {"success": False, "error": content.error or "No text content found"}

        extraction = await extract_entities(
            content.content_text, content.title, content.source_type, model=model
        )
        summary = extraction.get("summary", "")

        src = await store.add_source(
            url=url,
            title=content.title,
            source_type=content.source_type,
            content_text=content.content_text,
            summary=summary,
            metadata=content.metadata or None,
        )
        ent_count, rel_count = await _link_extraction(store, src.id, extraction)

        chain_id = None
        if cluster:
            from markov_engine.clustering import assign_topic  # avoids import cycle

            chain_id = await assign_topic(
                store, src.id, content.title or url, summary
            )

        await store.log_event(
            "ingest",
            chain_id=chain_id,
            detail={"source_id": src.id, "url": url, "type": content.source_type},
        )
        return {
            "success": True,
            "source_id": src.id,
            "title": content.title,
            "source_type": content.source_type,
            "summary": summary,
            "entity_count": ent_count,
            "rel_count": rel_count,
            "cost_usd": extraction.get("cost_usd", 0.0),
            "chain_id": chain_id,
            "reused": False,
        }
    except Exception as e:
        logger.exception("Ingestion failed for %s", url)
        try:
            await store.log_event("error", detail={"url": url, "error": str(e)})
        except Exception:
            pass
        return {"success": False, "error": str(e)}
