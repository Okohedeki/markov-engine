"""Run editorial discovery without the GUI or a user-supplied story angle."""

# ruff: noqa: E402 -- allow direct execution from the repository checkout.

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from markov_engine.claims import extract_claims
from markov_engine.editorial import discover_story_angles
from markov_engine.extract import extract_content
from markov_engine.research import (
    _ensure_claims, _ensure_seed_source, create_research_case,
)
from markov_engine.store.sqlite import SqliteStore


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Starting source URL; no editorial hint required")
    parser.add_argument("--database", help="Optional separate SQLite output path")
    args = parser.parse_args()
    database = args.database or f"data/editorial-{uuid.uuid4().hex[:12]}.db"
    store = await SqliteStore.open(database)
    case = None
    try:
        case = await create_research_case(
            store, owner_id="editorial-local", original_input=args.url,
            mode="research", input_type="url",
        )
        print(f"Extracting source into {database}", file=sys.stderr, flush=True)
        source, segments = await _ensure_seed_source(store, case, extractor=extract_content)
        print("Extracting located claims", file=sys.stderr, flush=True)
        await _ensure_claims(
            store, case, seed_source=source, segments=segments,
            claim_extractor=extract_claims,
        )
        print("Discovering editorial questions and inspecting sources", file=sys.stderr, flush=True)
        result = await discover_story_angles(store, case_id=case.id)
        await store.update_research_case(case.id, status=(
            "completed" if result["status"] == "complete" else "partial"
        ))
        summary = {key: value for key, value in result.items() if key != "findings"}
        summary["sources"] = [
            {key: item[key] for key in ("evidence_id", "url", "title", "locator")}
            for item in result.get("findings", [])
        ]
        print(json.dumps({"database": database, "case_id": case.id, **summary}, indent=2))
    except Exception:
        if case is not None:
            await store.update_research_case(case.id, status="failed")
        raise
    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
