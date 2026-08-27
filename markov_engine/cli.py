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
from markov_engine.research import (
    MODE_TO_ARTIFACT,
    create_research_case,
    generate_case_artifact,
    process_research_case,
)
from markov_engine.revisions import deepen_claim
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


async def _cmd_create(store: SqliteStore, args) -> int:
    constraints = {
        key: value
        for key, value in {
            "focus": args.focus,
            "audience": args.audience,
            "tone": args.tone,
            "target_minutes": args.target_minutes,
        }.items()
        if value is not None
    }
    case = await create_research_case(
        store,
        owner_id=args.owner,
        original_input=args.input,
        mode=args.mode,
        constraints=constraints,
    )
    artifacts = await process_research_case(
        store,
        case_id=case.id,
        review_level=args.review_level,
        modes=[args.mode],
    )
    _print_json(
        {
            "research_case_id": case.id,
            "artifact_ids": [artifact.id for artifact in artifacts],
            "status": "awaiting_review"
            if args.review_level == "verified"
            else "completed",
        }
    )
    return 0


async def _cmd_case(store: SqliteStore, args) -> int:
    case = await store.get_research_case(args.case_id, owner_id=args.owner)
    if case is None:
        _print_json({"error": f"research case {args.case_id} not found"})
        return 1
    _print_json(
        {
            "case": case.__dict__,
            "claims": [item.__dict__ for item in await store.list_claims(case.id)],
            "research_gaps": [
                item.__dict__ for item in await store.list_research_gaps(case.id)
            ],
            "artifacts": [
                item.__dict__ for item in await store.list_case_artifacts(case.id)
            ],
        }
    )
    return 0


async def _cmd_convert(store: SqliteStore, args) -> int:
    case = await store.get_research_case(args.case_id, owner_id=args.owner)
    if case is None:
        _print_json({"error": f"research case {args.case_id} not found"})
        return 1
    existing_ids = {item.id for item in await store.list_case_artifacts(case.id)}
    artifact = await generate_case_artifact(
        store,
        case_id=args.case_id,
        artifact_type=MODE_TO_ARTIFACT[args.mode],
        review_level=args.review_level,
    )
    _print_json({"artifact_id": artifact.id, "created": artifact.id not in existing_ids})
    return 0


async def _cmd_deepen(store: SqliteStore, args) -> int:
    result = await deepen_claim(
        store,
        claim_id=args.claim_id,
        owner_id=args.owner,
        max_sources=args.max_sources,
    )
    _print_json(result)
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

    p_create = sub.add_parser(
        "create", help="Create a Brief, Research report, or Script research case."
    )
    p_create.add_argument("input", help="Public URL, topic, or research question.")
    p_create.add_argument("--owner", default="local-cli")
    p_create.add_argument("--mode", choices=["brief", "research", "script"], default="brief")
    p_create.add_argument(
        "--review-level", choices=["instant", "verified"], default="instant"
    )
    p_create.add_argument("--focus")
    p_create.add_argument("--audience")
    p_create.add_argument("--tone")
    p_create.add_argument("--target-minutes", type=float)
    p_create.set_defaults(func=_cmd_create)

    p_case = sub.add_parser("case", help="Inspect one research case.")
    p_case.add_argument("case_id", type=int)
    p_case.add_argument("--owner", default="local-cli")
    p_case.set_defaults(func=_cmd_case)

    p_convert = sub.add_parser(
        "convert", help="Render another product from an existing research case."
    )
    p_convert.add_argument("case_id", type=int)
    p_convert.add_argument("--owner", default="local-cli")
    p_convert.add_argument("--mode", choices=["brief", "research", "script"], required=True)
    p_convert.add_argument(
        "--review-level", choices=["instant", "verified"], default="instant"
    )
    p_convert.set_defaults(func=_cmd_convert)

    p_deepen = sub.add_parser("deepen", help="Research one claim more deeply.")
    p_deepen.add_argument("claim_id", type=int)
    p_deepen.add_argument("--owner", default="local-cli")
    p_deepen.add_argument("--max-sources", type=int, default=5)
    p_deepen.set_defaults(func=_cmd_deepen)

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
