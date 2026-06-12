"""Command-line interface for the Markov engine.

Backed by the local SQLite store (default ``~/.markov/markov.db``). Agents can
shell out to these commands; each prints JSON (or markdown for ``generate``) to
stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from markov_engine.config import get_settings
from markov_engine.generate import generate_artifact
from markov_engine.growth import grow_chain
from markov_engine.ingest import ingest_url
from markov_engine.store.sqlite import SqliteStore

DEFAULT_DB = "~/.markov/markov.db"


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


async def _cmd_ingest(store: SqliteStore, args) -> int:
    res = await ingest_url(store, args.url)
    if not res.get("success"):
        _print_json({"error": res.get("error", "ingestion failed")})
        return 1
    _print_json(
        {
            "source_id": res.get("source_id"),
            "title": res.get("title"),
            "chain_id": res.get("chain_id"),
            "entities": res.get("entity_count", 0),
            "cost_usd": res.get("cost_usd", 0.0),
        }
    )
    return 0


async def _cmd_grow(store: SqliteStore, args) -> int:
    chain = await store.get_chain(args.chain_id)
    if not chain:
        _print_json({"error": f"chain {args.chain_id} not found"})
        return 1
    settings = get_settings()
    hop_depth = args.hops if args.hops is not None else chain.hop_depth
    source_budget = args.budget if args.budget is not None else chain.source_budget
    res = await grow_chain(
        store,
        chain,
        hop_depth=hop_depth,
        source_budget=source_budget,
        cycle_cost_cap=args.cost_cap,
        decay=settings.relevance_decay,
        floor=settings.relevance_floor,
    )
    _print_json(res)
    return 0 if res.get("success") else 1


async def _cmd_walk(store: SqliteStore, args) -> int:
    """Take the walk: run several growth steps over a Chain in sequence, so it
    keeps moving deeper into its subject. 'Knowledge that walks.'"""
    chain = await store.get_chain(args.chain_id)
    if not chain:
        _print_json({"error": f"chain {args.chain_id} not found"})
        return 1
    settings = get_settings()
    hop_depth = args.hops if args.hops is not None else chain.hop_depth
    source_budget = args.budget if args.budget is not None else chain.source_budget
    steps_out, total_added, total_cost = [], 0, 0.0
    for step in range(1, args.steps + 1):
        chain = await store.get_chain(args.chain_id)  # reload (centroid moved)
        res = await grow_chain(
            store, chain, hop_depth=hop_depth, source_budget=source_budget,
            cycle_cost_cap=args.cost_cap, decay=settings.relevance_decay,
            floor=settings.relevance_floor,
        )
        added = res.get("added", 0)
        total_added += added
        total_cost += res.get("cost_usd", 0.0)
        steps_out.append({"step": step, "added": added})
        print(f"  step {step}/{args.steps}: +{added} sources", file=sys.stderr)
        if added == 0:
            break  # the walk has reached the edge of what it can find this pass
    _print_json({"chain_id": args.chain_id, "steps": steps_out,
                 "total_added": total_added, "cost_usd": round(total_cost, 4)})
    return 0


async def _cmd_generate(store: SqliteStore, args) -> int:
    res = await generate_artifact(store, args.chain_id, artifact_type=args.type)
    if not res.get("success"):
        _print_json({"error": res.get("error", "generation failed")})
        return 1
    print(res.get("content", ""))
    return 0


async def _cmd_chains(store: SqliteStore, args) -> int:
    chains = await store.list_chains(limit=50)
    _print_json(
        [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "topic_count": c.topic_count,
            }
            for c in chains
        ]
    )
    return 0


async def _cmd_sources(store: SqliteStore, args) -> int:
    sources = await store.list_sources(limit=20)
    _print_json(
        [
            {
                "id": s.id,
                "title": s.title,
                "url": s.url,
                "source_type": s.source_type,
            }
            for s in sources
        ]
    )
    return 0


async def _cmd_search(store: SqliteStore, args) -> int:
    """Best-effort local search across entity names and source titles/summaries."""
    query = args.query.strip().lower()
    results: list[dict] = []
    entity = await store.get_entity_by_name(args.query)
    if entity:
        results.append(
            {"kind": "entity", "id": entity.id, "name": entity.name, "type": entity.entity_type}
        )
    for s in await store.list_sources(limit=200):
        haystack = " ".join(
            filter(None, [s.title or "", s.summary or "", s.url or ""])
        ).lower()
        if query in haystack:
            results.append(
                {"kind": "source", "id": s.id, "title": s.title, "url": s.url}
            )
    _print_json({"query": args.query, "results": results})
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="markov", description="Markov knowledge engine CLI."
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB, help=f"SQLite DB path (default {DEFAULT_DB})"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Ingest a URL and cluster it into a Chain.")
    p_ingest.add_argument("url")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_grow = sub.add_parser("grow", help="Run a growth cycle for a Chain.")
    p_grow.add_argument("chain_id", type=int)
    p_grow.add_argument("--hops", type=int, default=None, help="Override hop depth.")
    p_grow.add_argument("--budget", type=int, default=None, help="Override source budget.")
    p_grow.add_argument(
        "--cost-cap", dest="cost_cap", type=float, default=1.0,
        help="Per-cycle LLM spend cap in USD (default 1.0).",
    )
    p_grow.set_defaults(func=_cmd_grow)

    p_walk = sub.add_parser("walk", help="Take the walk: run several growth steps over a Chain.")
    p_walk.add_argument("chain_id", type=int)
    p_walk.add_argument("--steps", type=int, default=3, help="Number of growth steps (default 3).")
    p_walk.add_argument("--hops", type=int, default=None, help="Override hop depth.")
    p_walk.add_argument("--budget", type=int, default=None, help="Override per-step source budget.")
    p_walk.add_argument("--cost-cap", dest="cost_cap", type=float, default=1.0,
                        help="Per-step LLM spend cap in USD (default 1.0).")
    p_walk.set_defaults(func=_cmd_walk)

    p_gen = sub.add_parser("generate", help="Generate an artifact from a Chain.")
    p_gen.add_argument("chain_id", type=int)
    p_gen.add_argument("--type", default="article", help="article | newsletter")
    p_gen.set_defaults(func=_cmd_generate)

    p_chains = sub.add_parser("chains", help="List chains.")
    p_chains.set_defaults(func=_cmd_chains)

    p_sources = sub.add_parser("sources", help="List recent sources.")
    p_sources.set_defaults(func=_cmd_sources)

    p_search = sub.add_parser("search", help="Best-effort local entity/source search.")
    p_search.add_argument("query")
    p_search.set_defaults(func=_cmd_search)

    return parser


async def _run(args) -> int:
    store = await SqliteStore.open(args.db)
    try:
        return await args.func(store, args)
    finally:
        await store.close()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
