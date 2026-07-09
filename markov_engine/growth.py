"""Chain growth — discover and ingest new Sources for a Chain.

The caller supplies the reach parameters (``hop_depth``, ``source_budget``,
``cycle_cost_cap``) — there is no tier logic here. A relevance-decay floor and a
per-cycle cost cap keep Chains from ballooning and bound LLM spend.
"""

from __future__ import annotations

import logging
import re
import time

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


def _seed_queries(seed: str, title: str) -> list[dict]:
    """Queries that steer discovery toward a specific key point (hop 0 — this IS
    the direction the user chose to follow)."""
    s = seed.strip()
    subj = _subject_terms(title)
    out = [{"q": s, "hop": 0}, {"q": f"{s} explained", "hop": 0}, {"q": f"{s} latest", "hop": 0}]
    if subj and subj.lower() not in s.lower():
        out.append({"q": f"{subj} {s}", "hop": 0})
    return out


async def _build_queries(
    store: Store, chain, hop_depth: int, model: str, seed: str | None = None
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

    # Seed queries first so they survive the de-dup + _MAX_QUERIES cap: when the
    # user follows a key point, discovery is steered toward it.
    queries: list[dict] = _seed_queries(seed, chain.title) if seed else []
    # LLM-generated queries (best-effort — never the sole source).
    try:
        data, _ = await complete_json(
            prompt, schema=_QUERY_SCHEMA, model=model, max_tokens=512
        )
        raw = data.get("queries") or data.get("items") or []
        for q in raw if isinstance(raw, list) else []:
            if isinstance(q, str) and q.strip():
                queries.append({"q": q.strip(), "hop": 0})
            elif isinstance(q, dict) and q.get("q"):
                try:
                    hop = max(0, min(int(q.get("hop", 0)), hop_depth))
                except (TypeError, ValueError):
                    hop = 0
                queries.append({"q": str(q["q"]).strip(), "hop": hop})
    except Exception as e:
        logger.warning("LLM query generation failed (%s); using templates only", e)

    # Deterministic expansion — backend-agnostic, so discovery stays strong even
    # offline. Freshness/follow-up intent (latest/news/explained) surfaces NEW
    # stories; entity & neighbor combos reach connecting ones.
    queries += _template_queries(chain.title, entity_names, neighbors, hop_depth)

    # De-dup (case-insensitive), keep the lowest hop for each query, and cap the
    # count so the fan-out stays fast.
    best: dict[str, dict] = {}
    for q in queries:
        text = q["q"].strip()
        if not text:
            continue
        key = text.lower()
        if key not in best or q["hop"] < best[key]["hop"]:
            best[key] = {"q": text, "hop": q["hop"]}
    out = list(best.values())[:_MAX_QUERIES]
    return out or [{"q": chain.title, "hop": 0}]


# Strip site/source suffixes so queries read like a person's, not a page title.
_SUFFIX_RE = re.compile(r"\s*[-|–·]\s*(wikipedia|youtube|reddit|tiktok|instagram|x|twitter)\b.*$", re.I)
_FRESH_TERMS = ("latest", "news", "explained", "update 2026")
_MAX_QUERIES = 6  # cap the fan-out so a growth cycle stays snappy


def _subject_terms(title: str) -> str:
    return _SUFFIX_RE.sub("", title or "").strip() or (title or "").strip()


def _template_queries(
    title: str, entities: list[str], neighbors: list[str], hop_depth: int
) -> list[dict]:
    subj = _subject_terms(title)
    out: list[dict] = []
    # On-subject freshness / follow-up queries (find NEW stories) — hop 0.
    for term in _FRESH_TERMS:
        out.append({"q": f"{subj} {term}", "hop": 0})
    # Deepen on the chain's own strongest entities — each is a step OUT from the
    # seed, so it branches the walk (hop 1). Without this, chains never wire up a
    # multi-hop structure when there are no entity-graph neighbors (the common
    # case offline / early in a chain's life).
    deepen_hop = 1 if hop_depth >= 1 else 0
    for e in entities[:3]:
        if e and e.lower() not in subj.lower():
            out.append({"q": f"{subj} {e}", "hop": deepen_hop})
    # Bridge into adjacent subjects (connecting stories) — deeper still.
    if hop_depth >= 1:
        bridge_hop = min(2, hop_depth)
        for nb in list(dict.fromkeys(neighbors))[:4]:
            out.append({"q": f"{subj} {nb}", "hop": bridge_hop})
    return out


# Avenue freshness bias — news/video/social break and carry NEW stories that
# generic web search buries.
_FRESH_BONUS = {"news": 0.12, "video": 0.10, "social": 0.08, "web": 0.0}
_STOP = {"the", "and", "for", "with", "from", "what", "how", "why", "this",
         "that", "are", "was", "your", "you", "wikipedia", "part", "explained"}


def _words(title: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (title or "").lower())
            if len(w) >= 3 and w not in _STOP}


def _too_similar(words: set, others: list[set], threshold: float = 0.7) -> bool:
    """True if `words` overlaps any of `others` past the Jaccard threshold."""
    for o in others:
        if not o:
            continue
        inter = len(words & o)
        union = len(words | o) or 1
        if inter / union >= threshold:
            return True
    return False


async def discover_candidates(
    store: Store,
    chain,
    *,
    hop_depth: int,
    source_budget: int,
    decay: float | None = None,
    floor: float | None = None,
    model: str | None = None,
    seed: str | None = None,
) -> list[dict]:
    """Discover + rank NEW candidate Sources for a Chain WITHOUT ingesting them.

    ``seed`` (optional) steers discovery toward a specific key point the user
    chose to follow — its queries take priority so the walk branches that way.

    The first half of a growth cycle: build queries, search every avenue, filter
    for novelty + relevance, and return the ranked candidates (each a dict with
    ``url/title/snippet/hop/relevance/kind/platform/score``, best first).

    Discovery is cheap — query generation + snippet embeddings only; it never
    fetches or LLM-parses a full page — so it is safe to run on demand to power a
    "pick where this Chain goes next" UI. Feed the chosen subset to
    ``ingest_chosen`` to actually grow the Chain.
    """
    decay = decay if decay is not None else _settings.relevance_decay
    floor = floor if floor is not None else _settings.relevance_floor
    query_model = model or _settings.model_extraction
    centroid = (
        list(chain.centroid_embedding)
        if chain.centroid_embedding is not None
        else None
    )

    queries = await _build_queries(store, chain, hop_depth, query_model, seed=seed)
    await store.log_event("queries", chain_id=chain.id, detail={"queries": queries})

    # Titles already in the chain — for novelty (skip near-duplicate stories,
    # not just identical URLs).
    existing = await store.list_chain_sources(chain.id, limit=500)
    existing_words = [_words(cs.source.title) for cs in existing if cs.source.title]

    # Fan out every query across every avenue concurrently — the network round
    # trips dominate, so run them all at once instead of query-by-query.
    import asyncio
    per_query = await asyncio.gather(
        *(search_web(item["q"], max_results=max(3, source_budget)) for item in queries),
        return_exceptions=True,
    )

    # Gather + pre-filter candidates (cheap snippet embedding before full ingest).
    seen: set[str] = set()
    accepted_words: list[set] = []
    candidates: list[dict] = []
    for item, results in zip(queries, per_query):
        if isinstance(results, Exception):
            continue
        for r in results:
            url = (r.get("url") or "").strip()
            if not url or url.lower() in seen:
                continue
            seen.add(url.lower())
            if await store.get_source_by_url(url):
                continue
            title = r.get("title") or ""
            tw = _words(title)
            # Novelty: drop near-duplicate stories (same headline, different URL).
            if tw and (_too_similar(tw, existing_words) or _too_similar(tw, accepted_words)):
                continue
            sim = 1.0
            if centroid is not None:
                snippet_emb = await embed(
                    f"{title} {r.get('snippet', '')}", input_type="query"
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
            if tw:
                accepted_words.append(tw)
            kind = r.get("kind", "web")
            # Freshness/novelty bias: news & video break NEW stories; the social
            # avenues are exactly what generic web search buries — surface them.
            fresh = _FRESH_BONUS.get(kind, 0.0) + (0.05 if r.get("date") else 0.0)
            candidates.append({
                "url": url, "hop": item["hop"], "relevance": sim,
                # title/snippet carried through so a guided-walk UI can render
                # candidate cards without re-fetching.
                "title": title, "snippet": r.get("snippet", ""),
                "kind": kind, "platform": r.get("platform", "web"),
                "score": decayed + fresh,
            })

    # Best stories first: relevance + freshness, newest/most-novel surfaced.
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


async def ingest_chosen(
    store: Store,
    chain,
    candidates: list[dict],
    *,
    cycle_cost_cap: float,
    model: str | None = None,
) -> dict:
    """Ingest an already-chosen, ranked list of candidates into a Chain.

    The second half of a growth cycle. ``candidates`` is whatever the caller
    decided to commit: the top-``source_budget`` slice of ``discover_candidates``
    for auto-grow, or the user's hand-picked subset for a guided walk. Enforces
    the per-cycle cost + wall-clock caps. Returns a summary dict.
    """
    spent = 0.0
    added = 0
    deadline = time.monotonic() + _settings.grow_time_budget_s
    for cand in candidates:
        if spent >= cycle_cost_cap:
            await store.log_event(
                "info", chain_id=chain.id, detail={"stopped": "cost_cap"}
            )
            break
        if time.monotonic() > deadline:
            await store.log_event(
                "info", chain_id=chain.id, detail={"stopped": "time_cap", "added": added}
            )
            break
        # Ingest WITHOUT clustering: the walk is explicitly attaching this find to
        # *this* chain at the hop it was discovered. Letting clustering run would
        # attach it at hop 0 first, and the INSERT-OR-IGNORE below would then be a
        # no-op — collapsing every discovery to hop 0 (no graph structure).
        res = await ingest_url(store, cand["url"], model=model, cluster=False)
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

    from collections import Counter
    avenues = dict(Counter(c["platform"] for c in candidates))
    await store.touch_chain_grown(chain.id)
    await store.log_event(
        "grow",
        chain_id=chain.id,
        detail={"added": added, "spent": round(spent, 4),
                "candidates": len(candidates), "avenues": avenues},
    )
    return {"success": True, "chain_id": chain.id, "added": added,
            "cost_usd": spent, "avenues": avenues}


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
    """Run one automatic growth cycle: discover candidates, then ingest the top
    ``source_budget`` of them.

    Equivalent to ``discover_candidates`` followed by ``ingest_chosen`` on the
    highest-scoring slice — kept as one call for the auto-grow cron. Guided
    ("pick your own hop") growth calls the two halves separately. Discovery
    reach and spend are controlled entirely by the caller via ``hop_depth`` /
    ``source_budget`` / ``cycle_cost_cap``; ``decay`` and ``floor`` default to
    the engine settings (relevance decay 0.7, floor 0.45).
    """
    candidates = await discover_candidates(
        store, chain, hop_depth=hop_depth, source_budget=source_budget,
        decay=decay, floor=floor, model=model,
    )
    return await ingest_chosen(
        store, chain, candidates[:source_budget],
        cycle_cost_cap=cycle_cost_cap, model=model,
    )
