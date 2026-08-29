"""Run a reproducible V2 Markov case from an already captured YouTube source.

The runner reuses yt-dlp metadata and captions from ``media-intake`` while
allowing Markov to retrieve fresh independent evidence for the selected core
claims. It writes the database, complete case bundle, portable SQL dump, all
artifact formats, branch-specific scripts, and a quantitative run summary.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path

from markov_engine.exports import markdown_to_safe_html
from markov_engine.extract import (
    ExtractedContent,
    _extract_metadata,
    _parse_timed_text_segments,
    extract_content,
)
from markov_engine.research import (
    create_research_case,
    generate_case_artifact,
    process_research_case,
)
from markov_engine.store.sqlite import SqliteStore

VIDEO_ID = "zX1q-ZOUAQY"
SOURCE_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}&t=2s"
OWNER_ID = "local-v2-evaluation"

DEFAULT_CONSTRAINTS = {
    "focus": (
        "Build distinct evidence-backed directions from the complete interview. "
        "Verify the status and timeline of Jason Arday, including reports about "
        "his death and the plagiarism controversy. Keep established facts about "
        "named people separate from allegations, interviewee interpretations, and "
        "the broader contested claims about race, intelligence, genetics, academia, "
        "and institutional incentives. Each surviving direction should be usable as "
        "its own brief, analysis, or script."
    ),
    "audience": "curious adults who want an evidence-led explanation",
    "tone": "clear, skeptical, humane documentary",
    "target_minutes": 10,
    "words_per_minute": 145,
    "max_connections": 8,
}


def _json_default(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "keys"):
        return dict(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "artifact"


def _find_capture(capture_dir: Path) -> tuple[Path, Path]:
    info_files = sorted(capture_dir.glob("*.info.json"))
    caption_files = sorted(capture_dir.glob("*.en.vtt"))
    if not info_files or not caption_files:
        raise FileNotFoundError(
            f"Expected one .info.json and one .en.vtt in {capture_dir}"
        )
    return info_files[0], caption_files[0]


def _cached_extractor(capture_dir: Path):
    info_path, caption_path = _find_capture(capture_dir)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    captions = caption_path.read_text(encoding="utf-8")
    segments = _parse_timed_text_segments(
        captions,
        caption_source="youtube_auto_cached",
    )
    description = str(info.get("description") or "").strip()
    transcript = " ".join(segment.text for segment in segments)
    content = (
        f"{description}\n\n--- Transcript ---\n{transcript}"
        if description
        else transcript
    )
    cached = ExtractedContent(
        url=SOURCE_URL,
        source_type="youtube",
        title=str(info.get("title") or VIDEO_ID),
        content_text=content,
        metadata={
            **_extract_metadata(info),
            "capture_info_path": str(info_path),
            "capture_caption_path": str(caption_path),
            "raw_caption_cues": captions.count("-->"),
            "collapsed_caption_passages": len(segments),
        },
        segments=segments,
    )

    async def extractor(url: str, tmp_dir: str, whisper_model: str | None = "base"):
        if VIDEO_ID in url:
            return cached
        return await extract_content(url, tmp_dir, whisper_model)

    return extractor, cached


async def _case_payload(store: SqliteStore, case_id: int) -> dict:
    case = await store.get_research_case(case_id)
    claims = await store.list_claims(case_id)
    sources = [dict(row) for row in await store.list_research_case_sources(case_id)]
    for source in sources:
        source["segments"] = await store.list_source_segments(source["id"])
    claim_payload = []
    for claim in claims:
        item = dataclasses.asdict(claim)
        item["evidence"] = await store.list_claim_evidence(claim.id)
        claim_payload.append(item)
    connections = await store.list_connections(case_id)
    connection_payload = []
    for connection in connections:
        item = dataclasses.asdict(connection)
        item["evidence"] = await store.list_connection_evidence(connection.id)
        connection_payload.append(item)
    return {
        "case": case,
        "sources": sources,
        "claims": claim_payload,
        "topics": await store.list_research_topics(case_id),
        "entities": await store.list_case_entities(case_id),
        "research_gaps": await store.list_research_gaps(case_id),
        "connections": connection_payload,
        "connection_paths": await store.list_connection_paths(case_id),
        "insights": await store.list_insight_candidates(case_id),
        "branch_decisions": await store.list_user_branch_decisions(
            case_id,
            owner_id=OWNER_ID,
        ),
        "artifacts": await store.list_case_artifacts(case_id),
        "costs": await store.list_costs(case_id),
    }


def _directions_markdown(payload: dict) -> str:
    claims = {item["id"]: item for item in payload["claims"]}
    lines = [
        "# V2 artifact directions",
        "",
        (
            "Each direction below is a branch of the same source chain. It can be "
            "opened as its own brief, analysis, or script without treating every "
            "transcript claim as one story."
        ),
    ]
    for index, topic in enumerate(payload["topics"], start=1):
        lines.extend(["", f"## {index:02d}. {topic.title}", "", topic.focus])
        for claim_id in topic.claim_ids:
            claim = claims.get(claim_id)
            if claim:
                lines.append(
                    f"- C{claim_id} · {claim['verification_status']}: "
                    f"{claim.get('canonical_claim_text') or claim['claim_text']}"
                )
    if payload["insights"]:
        lines.extend(["", "# Surviving connection-led angles"])
    for insight in payload["insights"]:
        lines.extend(
            [
                "",
                f"## I{insight.id}. {insight.title}",
                "",
                insight.thesis,
                "",
                f"- Evidence level: {insight.evidence_level}",
                f"- Novelty: {insight.novelty_basis}",
                f"- Uncertainty: {insight.uncertainty}",
                f"- Next research step: {insight.next_step}",
            ]
        )
    return "\n".join(lines).strip() + "\n"


async def _export_artifacts(store: SqliteStore, case_id: int, output_dir: Path) -> list[dict]:
    artifact_dir = output_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    artifacts = await store.list_case_artifacts(case_id)
    for index, artifact in enumerate(artifacts, start=1):
        branch = f"-{_slug(artifact.branch_key)}" if artifact.branch_key else ""
        stem = f"{index:02d}-{artifact.artifact_type}{branch}"
        markdown_path = artifact_dir / f"{stem}.md"
        html_path = artifact_dir / f"{stem}.html"
        json_path = artifact_dir / f"{stem}.json"
        markdown_path.write_text(artifact.content, encoding="utf-8")
        html_path.write_text(
            markdown_to_safe_html(artifact.content),
            encoding="utf-8",
        )
        _write_json(json_path, artifact)
        exported.append(
            {
                "id": artifact.id,
                "type": artifact.artifact_type,
                "branch_key": artifact.branch_key,
                "title": artifact.title,
                "word_count": artifact.word_count,
                "markdown": str(markdown_path.resolve()),
                "html": str(html_path.resolve()),
                "json": str(json_path.resolve()),
            }
        )
    return exported


def _database_snapshot(db_path: Path, output_dir: Path) -> dict[str, int]:
    connection = sqlite3.connect(db_path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
        dump = "\n".join(connection.iterdump()) + "\n"
        (output_dir / "markov.sql").write_text(dump, encoding="utf-8")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        connection.close()
    if integrity != "ok" or foreign_keys:
        raise RuntimeError(
            f"Database validation failed: integrity={integrity}, "
            f"foreign_key_issues={len(foreign_keys)}"
        )
    return counts


async def run(args: argparse.Namespace) -> None:
    repo = Path(__file__).resolve().parents[1]
    capture_dir = (repo.parent / "media-intake" / "downloads" / "Youtube" / VIDEO_ID)
    output_dir = (repo / args.output).resolve()
    db_path = output_dir / "markov.db"
    state_path = output_dir / "runner-state.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    if db_path.exists() and not args.resume:
        raise FileExistsError(
            f"{db_path} already exists; use --resume to continue the saved case"
        )

    extractor, cached = _cached_extractor(capture_dir)
    store = await SqliteStore.open(str(db_path))
    started_at = dt.datetime.now(dt.timezone.utc)
    try:
        if args.resume and state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            case_id = int(state["research_case_id"])
        else:
            case = await create_research_case(
                store,
                owner_id=OWNER_ID,
                original_input=SOURCE_URL,
                input_type="url",
                mode="brief",
                constraints=DEFAULT_CONSTRAINTS,
            )
            case_id = case.id
            _write_json(
                state_path,
                {
                    "research_case_id": case_id,
                    "source_url": SOURCE_URL,
                    "started_at": started_at,
                },
            )

        async def stage(name: str, detail: dict) -> None:
            timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
            print(f"[{timestamp}] {name}: {json.dumps(detail, default=_json_default)}", flush=True)

        await process_research_case(
            store,
            case_id=case_id,
            review_level="instant",
            modes=["brief", "research", "script"],
            extractor=extractor,
            max_priority_claims=args.core_claims,
            max_sources_per_claim=args.sources_per_claim,
            max_connections=args.connections,
            claim_time_budget_s=args.claim_time_budget,
            stage_handler=stage,
        )

        insights = await store.list_insight_candidates(case_id)
        for insight in insights[: args.branch_scripts]:
            await generate_case_artifact(
                store,
                case_id=case_id,
                artifact_type="script",
                review_level="instant",
                constraints={
                    **DEFAULT_CONSTRAINTS,
                    "selected_insight_id": insight.id,
                },
                branch_key=f"insight:{insight.id}",
            )

        payload = await _case_payload(store, case_id)
        _write_json(output_dir / "case.complete.json", payload)
        (output_dir / "artifact-directions.md").write_text(
            _directions_markdown(payload),
            encoding="utf-8",
        )
        artifact_files = await _export_artifacts(store, case_id, output_dir)
        claims = payload["claims"]
        core_claims = [claim for claim in claims if claim["disposition"] == "core"]
        evidence_count = sum(len(claim["evidence"]) for claim in claims)
        summary = {
            "run_id": f"{VIDEO_ID}-v2",
            "source_url": SOURCE_URL,
            "captured_source_directory": str(capture_dir.resolve()),
            "markov_database": str(db_path.resolve()),
            "research_case_id": case_id,
            "raw_caption_cues": cached.metadata["raw_caption_cues"],
            "caption_passages": len(cached.segments),
            "transcript_words": sum(len(item.text.split()) for item in cached.segments),
            "located_claim_ledger_count": len(claims),
            "core_chain_count": len(core_claims),
            "researched_core_count": sum(
                item["verification_status"] != "not_researched" for item in core_claims
            ),
            "source_count": len(payload["sources"]),
            "evidence_passage_count": evidence_count,
            "topic_count": len(payload["topics"]),
            "connection_count": len(payload["connections"]),
            "validated_connection_count": sum(
                item["validation_status"] == "validated"
                for item in payload["connections"]
            ),
            "insight_count": len(payload["insights"]),
            "estimated_cloud_cost_usd": round(
                sum(float(item.cost) for item in payload["costs"]),
                6,
            ),
            "artifact_files": artifact_files,
            "completed_at": dt.datetime.now(dt.timezone.utc),
        }
        _write_json(output_dir / "run-summary.json", summary)
    finally:
        await store.close()

    summary["database_table_counts"] = _database_snapshot(db_path, output_dir)
    _write_json(output_dir / "run-summary.json", summary)
    print(json.dumps(summary, indent=2, default=_json_default), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=f"data/runs/{VIDEO_ID}-v2")
    parser.add_argument("--core-claims", type=int, default=12)
    parser.add_argument("--sources-per-claim", type=int, default=3)
    parser.add_argument("--connections", type=int, default=8)
    parser.add_argument("--branch-scripts", type=int, default=3)
    parser.add_argument("--claim-time-budget", type=float, default=60)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
