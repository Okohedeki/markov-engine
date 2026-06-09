"""Chain growth — discover and ingest new Sources for a Chain.

The caller supplies the reach parameters (``hop_depth``, ``source_budget``,
``cycle_cost_cap``) — there is no tier logic here. A relevance-decay floor and a
per-cycle cost cap keep Chains from ballooning and bound LLM spend.
"""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.embeddings import embed
from markov_engine.ingest import ingest_url
from markov_engine.llm import complete_json
from markov_engine.store.base import Store
from markov_engine.vectors import cosine_similarity as _cosine
from markov_engine.search import search_web

logger = logging.getLogger(__name__)
_settings = get_settings()

_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "hop": {
                        "type": "integer",
                        "description": "0 = on-subject; 1..N = adjacency hop",
                    },
                },
                "required": ["q", "hop"],
            },
        }
    },
    "required": ["queries"],
}

_QUERY_PROMPT = """Generate web-search queries to surface NEW articles, news, and analyses
that grow a research Chain about a subject.

SUBJECT: {subject}
TOP ENTITIES IN THE CHAIN: {entities}
ADJACENT SUBJECTS (graph neighbors): {neighbors}

Rules:
- Produce {n_subject} on-subject queries (hop=0) about recent developments on the SUBJECT.
- {bridge_rule}
- Each query must be distinct and specific. Avoid repeating the subject title verbatim.
"""


async def _build_queries(
    store: Store, chain, hop_depth: int, model: str
) -> list[dict]:
    top = await store.top_entities_for_chain(chain.id, limit=6)
    entity_names = [t["name"] for t in top]
    neighbors: list[str] = []
    if hop_depth >= 1 and top:
        for t in top[:3]:
            neighbors += await store.gather_entity_neighbors(t["id"], limit=4)
    bridge_rule = (
        f"Produce {hop_depth} bridge queries (hop=1..{hop_depth}) combining the SUBJECT with an "
        "ADJACENT SUBJECT, to reach into neighboring topics."
        if hop_depth >= 1
        else "Do NOT produce any bridge/adjacent queries — stay strictly on-subject (hop=0 only)."
    )
    prompt = _QUERY_PROMPT.format(
        subject=chain.title,
        entities=", ".join(entity_names) or "(none)",
        neighbors=", ".join(dict.fromkeys(neighbors)) or "(none)",
        n_subject=3,
        bridge_rule=bridge_rule,
    )
    try:
        data, _ = await complete_json(
            prompt, schema=_QUERY_SCHEMA, model=model, max_tokens=512
        )
        queries = [
            {"q": q["q"].strip(), "hop": max(0, min(int(q.get("hop", 0)), hop_depth))}
            for q in data.get("queries", [])
            if q.get("q")
        ]
        return queries or [{"q": chain.title, "hop": 0}]
    except Exception as e:
        logger.warning("Query generation failed (%s); falling back to subject", e)
        return [{"q": chain.title, "hop": 0}]


async def grow_chain(
    store: Store,
    chain,
    *,
    hop_depth: int,
    source_budget: int,
    cycle_cost_cap: float,
    decay: float | None = None,
    floor: float | None = None,
    model: str | None = None,
) -> dict:
    """Run one growth cycle for a Chain. Returns a summary dict.

    Discovery reach and spend are controlled entirely by the caller via
    ``hop_depth`` / ``source_budget`` / ``cycle_cost_cap``. ``decay`` and
    ``floor`` default to the engine settings (relevance decay 0.7, floor 0.45).
    """
    decay = decay if decay is not None else _settings.relevance_decay
    floor = floor if floor is not None else _settings.relevance_floor
    query_model = model or _settings.model_extraction
    centroid = (
        list(chain.centroid_embedding)
        if chain.centroid_embedding is not None
        else None
    )

    queries = await _build_queries(store, chain, hop_depth, query_model)
    await store.log_event("queries", chain_id=chain.id, detail={"queries": queries})

    # Gather + pre-filter candidates (cheap snippet embedding before full ingest).
    seen: set[str] = set()
    candidates: list[dict] = []
    for item in queries:
        for r in await search_web(item["q"], max_results=max(3, source_budget)):
            url = (r.get("url") or "").strip()
            if not url or url.lower() in seen:
                continue
            seen.add(url.lower())
            if await store.get_source_by_url(url):
                continue
            sim = 1.0
            if centroid is not None:
                snippet_emb = await embed(
                    f"{r.get('title', '')} {r.get('snippet', '')}", input_type="query"
                )
                sim = _cosine(snippet_emb, centroid)
            decayed = sim * (decay ** item["hop"])
            if decayed < floor:
                await store.log_event(
                    "reject",
                    chain_id=chain.id,
                    detail={"url": url, "hop": item["hop"], "decayed": round(decayed, 4)},
                )
                continue
            candidates.append({"url": url, "hop": item["hop"], "relevance": sim})

    # Ingest up to the budget, enforcing the per-cycle cost cap.
    spent = 0.0
    added = 0
    for cand in candidates[:source_budget]:
        if spent >= cycle_cost_cap:
            await store.log_event(
                "info", chain_id=chain.id, detail={"stopped": "cost_cap"}
            )
            break
        res = await ingest_url(store, cand["url"], model=model, cluster=True)
        if not res.get("success"):
            continue
        spent += res.get("cost_usd", 0.0)
        await store.add_chain_source(
            chain_id=chain.id,
            source_id=res["source_id"],
            hop_distance=cand["hop"],
            relevance=cand["relevance"],
        )
        added += 1

    await store.touch_chain_grown(chain.id)
    await store.log_event(
        "grow",
        chain_id=chain.id,
        detail={"added": added, "spent": round(spent, 4), "candidates": len(candidates)},
    )
    return {"success": True, "chain_id": chain.id, "added": added, "cost_usd": spent}
