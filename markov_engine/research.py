"""One reusable research-case pipeline for Brief, Research, and Script."""

from __future__ import annotations

import inspect
import re
import uuid
from urllib.parse import urlparse

from markov_engine.claims import extract_claims
from markov_engine.connections import (
    discover_connection_candidates,
    process_connection_graph,
)
from markov_engine.config import get_settings
from markov_engine.evidence import research_claim
from markov_engine.extract import classify_url, extract_content, segment_text
from markov_engine.renderers import RenderedArtifact, render_artifact
from markov_engine.store.records import ArtifactRec, ResearchCaseRec
from markov_engine.store.sqlite import SqliteStore

_settings = get_settings()

MODE_TO_ARTIFACT = {
    "brief": "brief",
    "research": "research_report",
    "research_report": "research_report",
    "script": "script",
}
REVIEW_LEVELS = {"instant", "verified"}


def classify_input(value: str) -> str:
    clean = (value or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return classify_url(clean)
    return "topic"


def _initial_title(value: str, *, input_type: str | None = None) -> str:
    clean = re.sub(r"\s+", " ", value).strip()
    if input_type in {"text", "topic", "question"} or classify_input(clean) == "topic":
        return clean[:200] or "Untitled research case"
    host = (urlparse(clean).hostname or "Source").removeprefix("www.")
    return f"Research from {host}"[:200]


async def create_research_case(
    store: SqliteStore,
    *,
    owner_id: str,
    original_input: str,
    mode: str,
    input_type: str | None = None,
    constraints: dict | None = None,
) -> ResearchCaseRec:
    if mode not in MODE_TO_ARTIFACT:
        raise ValueError(f"Unsupported mode: {mode}")
    declared_type = (input_type or "").strip().lower()
    if declared_type == "url" or not declared_type:
        resolved_input_type = classify_input(original_input)
    elif declared_type in {"text", "topic", "question"}:
        resolved_input_type = declared_type
    else:
        raise ValueError(f"Unsupported input type: {input_type}")
    case = await store.create_research_case(
        owner_id=owner_id,
        title=_initial_title(original_input, input_type=resolved_input_type),
        original_input=original_input.strip(),
        input_type=resolved_input_type,
        purpose=mode,
        constraints=constraints or {},
    )
    await store.record_usage_event(
        owner_id=owner_id,
        event_type="source_submitted",
        research_case_id=case.id,
        metadata={"input_type": resolved_input_type},
    )
    await store.record_usage_event(
        owner_id=owner_id,
        event_type="mode_selected",
        research_case_id=case.id,
        metadata={"mode": mode},
    )
    return case


async def _ensure_seed_source(
    store: SqliteStore,
    case: ResearchCaseRec,
    *,
    extractor,
) -> tuple[object, list]:
    case_sources = await store.list_research_case_sources(case.id)
    seed_row = next(
        (row for row in case_sources if row["case_source_role"] == "seed"), None
    )
    if seed_row is not None:
        source = await store.get_source(seed_row["id"])
        segments = await store.list_source_segments(seed_row["id"])
        if source is not None and segments:
            return source, segments

    if case.input_type in {"topic", "question"}:
        section_title = "Research question"
        source = await store.add_source(
            url=None,
            title=case.title,
            source_type=case.input_type,
            content_text=case.original_input,
            summary="Customer research question",
            is_note=True,
            metadata={"input_type": case.input_type},
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {
                    "ordinal": 0,
                    "text": case.original_input,
                    "section_title": section_title,
                    "character_start": 0,
                    "character_end": len(case.original_input),
                }
            ],
        )
        await store.update_source_provenance(
            source.id,
            source_role="seed",
            source_quality="customer_prompt",
            source_quality_rationale=(
                "Customer-supplied research question; it is context, not evidence."
            ),
        )
        await store.add_research_case_source(
            research_case_id=case.id, source_id=source.id, source_role="seed"
        )
        await store.update_research_case(case.id, status="extracting_claims")
        await store.record_cost(
            research_case_id=case.id,
            provider="extraction",
            operation=f"{case.input_type}_seed",
            units=1,
            cost=0,
        )
        return source, segments

    if case.input_type == "text":
        extracted_segments = segment_text(case.original_input)
        if not extracted_segments:
            raise RuntimeError("Text source produced no stable segments")
        source = await store.add_source(
            url=None,
            title=case.title,
            source_type="text",
            content_text=case.original_input,
            summary="Customer-provided source text",
            is_note=True,
            metadata={"input_type": "text"},
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[segment.as_dict() for segment in extracted_segments],
        )
        await store.update_source_provenance(
            source.id,
            source_role="seed",
            source_quality="customer_source",
            source_quality_rationale=(
                "Customer-provided source text; its claims require independent evidence."
            ),
        )
        await store.add_research_case_source(
            research_case_id=case.id, source_id=source.id, source_role="seed"
        )
        await store.update_research_case(case.id, status="extracting_claims")
        await store.record_cost(
            research_case_id=case.id,
            provider="extraction",
            operation="text_segments",
            units=len(segments),
            cost=0,
        )
        return source, segments

    content = await extractor(
        case.original_input,
        _settings.tmp_dir,
        _settings.whisper_model if _settings.transcribe_media else None,
    )
    if not content.success:
        raise RuntimeError(content.error or "Source could not be extracted")
    if not content.segments:
        raise RuntimeError("Source extraction returned no stable segments")
    source = await store.get_source_by_url(case.original_input)
    if source is None:
        source = await store.add_source(
            url=case.original_input,
            title=content.title or case.title,
            source_type=content.source_type,
            content_text=content.content_text,
            summary="",
            metadata=content.metadata or None,
        )
    segments = await store.add_source_segments(
        source_id=source.id,
        segments=[segment.as_dict() for segment in content.segments],
    )
    metadata = content.metadata or {}
    await store.update_source_provenance(
        source.id,
        source_role="seed",
        source_quality="commentary" if content.source_type == "youtube" else "analysis",
        source_quality_rationale=(
            "Seed source supplied by the customer; its claims require independent evidence."
        ),
        publisher=metadata.get("channel") or metadata.get("uploader"),
        author=metadata.get("uploader") or metadata.get("author"),
        published_at=metadata.get("upload_date") or metadata.get("published_at"),
        retrieved_at=None,
    )
    await store.add_research_case_source(
        research_case_id=case.id, source_id=source.id, source_role="seed"
    )
    await store.update_research_case(
        case.id, title=(content.title or case.title)[:200], status="extracting_claims"
    )
    await store.record_cost(
        research_case_id=case.id,
        provider="transcription"
        if any(segment.caption_source and segment.caption_source.startswith("whisper:") for segment in segments)
        else "extraction",
        operation=f"{content.source_type}_segments",
        units=len(segments),
        cost=0,
    )
    return source, segments


async def _ensure_claims(
    store: SqliteStore,
    case: ResearchCaseRec,
    *,
    seed_source,
    segments,
    claim_extractor,
) -> list:
    existing = await store.list_claims(case.id)
    if existing:
        return existing
    if case.input_type in {"topic", "question"}:
        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=seed_source.id,
            claim_text=case.original_input.rstrip("?"),
            claim_type="inference",
            importance=1.0,
            speaker_certainty="research_question",
            source_start_segment_id=segments[0].id,
            source_end_segment_id=segments[0].id,
        )
        await store.add_research_gap(
            research_case_id=case.id,
            claim_id=claim.id,
            gap_type="unresolved_evidence",
            question=case.original_input,
            importance=1.0,
        )
        return [claim]
    extracted, gaps, cost = await claim_extractor(segments)
    by_id = {segment.id: segment for segment in segments}
    records = []
    for item in extracted:
        located = [by_id[segment_id] for segment_id in item["source_segment_ids"] if segment_id in by_id]
        if not located:
            continue
        records.append(
            await store.add_claim(
                research_case_id=case.id,
                seed_source_id=seed_source.id,
                claim_text=item["claim_text"],
                claim_type=item["claim_type"],
                importance=item["importance"],
                speaker_certainty=item["speaker_certainty"],
                source_start_segment_id=located[0].id,
                source_end_segment_id=located[-1].id,
            )
        )
    if not records:
        raise RuntimeError("No located claims were persisted")
    for gap in gaps:
        related = str(gap.get("related_claim_text") or "").lower()
        claim_id = next(
            (claim.id for claim in records if related and claim.claim_text.lower() == related),
            None,
        )
        await store.add_research_gap(
            research_case_id=case.id,
            claim_id=claim_id,
            gap_type=gap["gap_type"],
            question=gap["question"],
            importance=gap["importance"],
        )
    await store.record_cost(
        research_case_id=case.id,
        provider="llm",
        operation="claim_extraction",
        units=len(records),
        cost=cost,
    )
    return await store.list_claims(case.id)


async def persist_rendered_artifact(
    store: SqliteStore,
    *,
    case: ResearchCaseRec,
    rendered: RenderedArtifact,
    review_level: str,
) -> ArtifactRec:
    status = "awaiting_review" if review_level == "verified" else "completed"
    artifact = await store.add_case_artifact(
        research_case_id=case.id,
        artifact_type=rendered.artifact_type,
        review_level=review_level,
        status=status,
        title=rendered.title,
        content=rendered.content,
        structured_content=rendered.structured_content,
        word_count=rendered.word_count,
        model_used="deterministic-v1",
        generation_cost=0,
        source_ids=rendered.source_ids,
    )
    if review_level == "verified":
        await store.create_review_job(artifact.id)
    await store.record_usage_event(
        owner_id=case.owner_id,
        event_type="artifact_generated",
        research_case_id=case.id,
        artifact_id=artifact.id,
        metadata={
            "mode": rendered.artifact_type,
            "review_level": review_level,
            "word_count": rendered.word_count,
        },
    )
    await store.record_cost(
        research_case_id=case.id,
        artifact_id=artifact.id,
        provider="deterministic",
        operation=f"render_{rendered.artifact_type}",
        units=rendered.word_count,
        cost=rendered.word_count * 0,
    )
    return artifact


async def generate_case_artifact(
    store: SqliteStore,
    *,
    case_id: int,
    artifact_type: str,
    review_level: str = "instant",
    constraints: dict | None = None,
    force: bool = False,
) -> ArtifactRec:
    if artifact_type not in {"brief", "research_report", "script"}:
        raise ValueError(f"Unsupported artifact type: {artifact_type}")
    if review_level not in REVIEW_LEVELS:
        raise ValueError(f"Unsupported review level: {review_level}")
    case = await store.get_research_case(case_id)
    if case is None:
        raise ValueError("Research case not found")
    if not force:
        existing = next(
            (
                artifact
                for artifact in await store.list_case_artifacts(case_id)
                if artifact.artifact_type == artifact_type
                and artifact.review_level == review_level
            ),
            None,
        )
        if existing is not None:
            return existing
    rendered = await render_artifact(
        store, case_id, artifact_type, constraints=constraints
    )
    artifact = await persist_rendered_artifact(
        store, case=case, rendered=rendered, review_level=review_level
    )
    purposes = set(filter(None, case.purpose.split(",")))
    purposes.add("research" if artifact_type == "research_report" else artifact_type)
    await store.update_research_case(case_id, purpose=",".join(sorted(purposes)))
    return artifact


async def convert_case_artifact(
    store: SqliteStore,
    *,
    case_id: int,
    owner_id: str,
    mode: str,
    review_level: str = "instant",
    constraints: dict | None = None,
    settings=None,
) -> tuple[ArtifactRec, bool]:
    """Create another sellable output from existing research without rerunning it."""
    from markov_engine.billing import refund_job_credits, reserve_job_credits

    if mode not in MODE_TO_ARTIFACT:
        raise ValueError(f"Unsupported mode: {mode}")
    case = await store.get_research_case(case_id, owner_id=owner_id)
    if case is None:
        raise ValueError("Research case not found")
    artifact_type = MODE_TO_ARTIFACT[mode]
    existing = next(
        (
            artifact
            for artifact in await store.list_case_artifacts(case.id)
            if artifact.artifact_type == artifact_type
            and artifact.review_level == review_level
        ),
        None,
    )
    if existing is not None:
        return existing, False
    reference = f"conversion:{case.id}:{artifact_type}:{uuid.uuid4()}"
    await reserve_job_credits(
        store,
        owner_id=owner_id,
        job_id=reference,
        mode=mode,
        review_level=review_level,
        settings=settings,
    )
    try:
        artifact = await generate_case_artifact(
            store,
            case_id=case.id,
            artifact_type=artifact_type,
            review_level=review_level,
            constraints=constraints,
        )
    except Exception:
        await refund_job_credits(
            store,
            owner_id=owner_id,
            job_id=reference,
            mode=mode,
            review_level=review_level,
            settings=settings,
        )
        raise
    event_mode = "research" if artifact_type == "research_report" else artifact_type
    await store.record_usage_event(
        owner_id=owner_id,
        event_type=f"converted_to_{event_mode}",
        research_case_id=case.id,
        artifact_id=artifact.id,
        metadata={"review_level": review_level},
    )
    return artifact, True


async def process_research_case(
    store: SqliteStore,
    *,
    case_id: int,
    review_level: str = "instant",
    modes: list[str] | None = None,
    extractor=extract_content,
    claim_extractor=extract_claims,
    claim_researcher=research_claim,
    connection_discoverer=discover_connection_candidates,
    searcher=None,
    max_priority_claims: int = 5,
    max_sources_per_claim: int = 3,
    max_connections: int | None = None,
    claim_time_budget_s: float = 60,
    stage_handler=None,
) -> list[ArtifactRec]:
    """Run or resume one case without repeating completed extraction/research."""
    case = await store.get_research_case(case_id)
    if case is None:
        raise ValueError("Research case not found")
    if review_level not in REVIEW_LEVELS:
        raise ValueError(f"Unsupported review level: {review_level}")
    selected_modes = modes or [case.purpose.split(",")[0]]
    unsupported = [mode for mode in selected_modes if mode not in MODE_TO_ARTIFACT]
    if unsupported:
        raise ValueError(f"Unsupported mode: {unsupported[0]}")
    artifact_types = [MODE_TO_ARTIFACT[mode] for mode in selected_modes]

    async def stage(name: str, detail: dict | None = None) -> None:
        if stage_handler is None:
            return
        result = stage_handler(name, detail or {})
        if inspect.isawaitable(result):
            await result

    await store.update_research_case(case.id, status="extracting")
    await store.record_usage_event(
        owner_id=case.owner_id,
        event_type="job_started",
        research_case_id=case.id,
        metadata={"modes": selected_modes, "review_level": review_level},
    )
    try:
        await stage("extracting_sources", {"input_type": case.input_type})
        seed_source, segments = await _ensure_seed_source(
            store, case, extractor=extractor
        )
        await stage("preserving_locators", {"segments": len(segments)})
        await stage("identifying_claims")
        claims = await _ensure_claims(
            store,
            case,
            seed_source=seed_source,
            segments=segments,
            claim_extractor=claim_extractor,
        )
        await stage("planning_research", {"claims": len(claims)})
        await store.update_research_case(case.id, status="researching")
        for claim in [
            item
            for item in claims
            if item.verification_status == "not_researched"
        ][:max_priority_claims]:
            await stage("finding_evidence", {"claim_id": claim.id})
            kwargs = {
                "case_id": case.id,
                "claim": claim,
                "extractor": extractor,
                "max_sources": max_sources_per_claim,
                "time_budget_s": claim_time_budget_s,
            }
            if searcher is not None:
                kwargs["searcher"] = searcher
            await claim_researcher(store, **kwargs)
        claims = await store.list_claims(case.id)
        await stage("comparing_sources")
        await stage("discovering_connections")
        graph = await process_connection_graph(
            store,
            case_id=case.id,
            discoverer=connection_discoverer,
            max_connections=max(
                1,
                int(
                    max_connections
                    or case.constraints.get("max_connections")
                    or 8
                ),
            ),
        )
        await stage(
            "validating_connections",
            {
                "validated": len(graph["validated"]),
                "rejected": len(graph["rejected"]),
            },
        )
        await stage("building_paths", {"paths": len(graph["paths"])})
        await stage("synthesizing_insights", {"insights": len(graph["insights"])})
        await store.update_research_case(case.id, status="rendering")
        refreshed = await store.get_research_case(case.id)
        assert refreshed is not None
        artifacts = []
        for artifact_type in artifact_types:
            await stage("building_artifact", {"artifact_type": artifact_type})
            rendered = await render_artifact(
                store,
                case.id,
                artifact_type,
                constraints=refreshed.constraints,
            )
            artifacts.append(
                await persist_rendered_artifact(
                    store,
                    case=refreshed,
                    rendered=rendered,
                    review_level=review_level,
                )
            )
        final_status = "awaiting_review" if review_level == "verified" else "completed"
        await stage(final_status, {"artifact_ids": [item.id for item in artifacts]})
        await store.update_research_case(case.id, status=final_status)
        source_rows = await store.list_research_case_sources(case.id)
        evidence_count = 0
        for claim in claims:
            evidence_count += len(await store.list_claim_evidence(claim.id))
        await store.record_usage_event(
            owner_id=case.owner_id,
            event_type="job_completed",
            research_case_id=case.id,
            metadata={
                "modes": artifact_types,
                "review_level": review_level,
                "input_type": case.input_type,
                "claim_count": len(claims),
                "researched_claim_count": sum(
                    claim.verification_status != "not_researched" for claim in claims
                ),
                "source_count": len(source_rows),
                "evidence_passage_count": evidence_count,
                "connection_count": len(graph["connections"]),
                "validated_connection_count": len(graph["validated"]),
                "connection_path_count": len(graph["paths"]),
                "insight_count": len(graph["insights"]),
                "artifact_word_counts": {
                    artifact.artifact_type: artifact.word_count for artifact in artifacts
                },
            },
        )
        return artifacts
    except Exception as exc:
        await store.update_research_case(case.id, status="failed")
        await store.record_usage_event(
            owner_id=case.owner_id,
            event_type="job_failed",
            research_case_id=case.id,
            metadata={"error": str(exc)},
        )
        raise
