"""One complete paid-product lifecycle over a shared YouTube research case."""

from __future__ import annotations

import pytest

from markov_engine.config import Settings
from markov_engine.exports import export_artifact
from markov_engine.extract import ExtractedContent, ExtractedSegment
from markov_engine.research import (
    create_research_case,
    generate_case_artifact,
    process_research_case,
)
from markov_engine.reviews import finalize_review, record_review_decision
from markov_engine.revisions import deepen_claim, revise_script_section
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_complete_youtube_to_delivery_and_verified_review():
    store = await SqliteStore.open(":memory:")
    extraction_count = 0

    async def extract_youtube(url, tmp_dir, whisper_model):
        nonlocal extraction_count
        extraction_count += 1
        return ExtractedContent(
            url=url,
            source_type="youtube",
            title="Fixture: Housing and Rates",
            content_text=(
                "The policy rate increased by two points. "
                "The presenter predicts housing prices will fall."
            ),
            metadata={"channel": "Fixture Economics"},
            segments=[
                ExtractedSegment(
                    ordinal=0,
                    text="The policy rate increased by two percentage points.",
                    start_seconds=61.5,
                    end_seconds=68.2,
                    caption_source="youtube_manual",
                ),
                ExtractedSegment(
                    ordinal=1,
                    text="The presenter predicts housing prices will fall next year.",
                    start_seconds=68.2,
                    end_seconds=75.8,
                    caption_source="youtube_manual",
                ),
            ],
        )

    async def extract_claims(segments):
        return (
            [
                {
                    "claim_text": "The policy rate increased by two percentage points.",
                    "claim_type": "quantitative",
                    "importance": 1,
                    "speaker_certainty": "asserted_as_fact",
                    "source_segment_ids": [segments[0].id],
                },
                {
                    "claim_text": "Housing prices will fall next year.",
                    "claim_type": "predictive",
                    "importance": 0.8,
                    "speaker_certainty": "speculative",
                    "source_segment_ids": [segments[1].id],
                },
            ],
            [
                {
                    "gap_type": "alternative_explanation",
                    "question": "Which non-rate factors could affect housing prices?",
                    "importance": 0.8,
                    "related_claim_text": "Housing prices will fall next year.",
                }
            ],
            0.03,
        )

    async def research_priority_claim(store, *, case_id, claim, **kwargs):
        source = await store.add_source(
            url=f"https://example.gov/official/{claim.id}",
            title=f"Official evidence for claim {claim.id}",
            source_type="article",
            content_text=f"Inspected evidence concerning: {claim.claim_text}",
            summary="",
        )
        await store.update_source_provenance(
            source.id,
            source_role="official_data",
            source_quality="official_data",
            source_quality_rationale="Direct public-sector release.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=source.id,
            source_role="independent_evidence",
        )
        passage = await store.add_evidence_passage(
            source_id=source.id,
            passage_text=f"Inspected evidence concerning: {claim.claim_text}",
            section_title="Finding",
            source_quality="official_data",
        )
        stance = "supports" if claim.claim_type == "quantitative" else "qualifies"
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance=stance,
            strength=0.9,
            rationale="The exact inspected passage bears directly on the atomic claim.",
            model_confidence=0.9,
        )
        status = "supported" if stance == "supports" else "qualified"
        await store.update_claim_status(claim.id, status)
        await store.record_cost(
            research_case_id=case_id,
            provider="fixture",
            operation="evidence_research",
            units=1,
            cost=0.02,
        )
        return {"claim_id": claim.id, "status": status, "sources_added": 1}

    async def deepen_research(store, *, case_id, claim, **kwargs):
        source = await store.add_source(
            url="https://example.edu/counterevidence",
            title="Counterevidence study",
            source_type="article",
            content_text="Other market factors can offset rate changes.",
            summary="",
        )
        await store.update_source_provenance(
            source.id,
            source_role="academic_research",
            source_quality="academic_research",
            source_quality_rationale="Inspectably published study.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=source.id,
            source_role="counterevidence",
        )
        passage = await store.add_evidence_passage(
            source_id=source.id,
            passage_text="Other market factors can offset rate changes.",
            section_title="Limitations",
            source_quality="academic_research",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="qualifies",
            strength=0.8,
            rationale="The study limits a single-cause interpretation.",
            model_confidence=0.9,
        )
        await store.update_claim_status(claim.id, "qualified")
        await store.record_cost(
            research_case_id=case_id,
            provider="fixture",
            operation="claim_deepening",
            units=1,
            cost=0.01,
        )
        return {"claim_id": claim.id, "status": "qualified", "sources_added": 1}

    try:
        case = await create_research_case(
            store,
            owner_id="customer-1",
            original_input="https://youtube.com/watch?v=vertical",
            mode="brief",
            constraints={"target_minutes": 6, "audience": "general"},
        )
        artifacts = await process_research_case(
            store,
            case_id=case.id,
            modes=["brief", "research", "script"],
            extractor=extract_youtube,
            claim_extractor=extract_claims,
            claim_researcher=research_priority_claim,
        )
        brief, report, script = artifacts
        segments = await store.list_source_segments(
            (await store.list_research_case_sources(case.id))[0]["id"]
        )
        claims = await store.list_claims(case.id)

        assert extraction_count == 1
        assert [(item.start_seconds, item.end_seconds) for item in segments] == [
            (61.5, 68.2),
            (68.2, 75.8),
        ]
        assert [item.artifact_type for item in artifacts] == [
            "brief",
            "research_report",
            "script",
        ]
        assert "1:01–1:08" in brief.content
        assert "## Source packet" in report.content
        assert "## Complete spoken narration" in script.content

        deepened = await deepen_claim(
            store,
            claim_id=claims[0].id,
            owner_id="customer-1",
            claim_researcher=deepen_research,
        )
        assert set(deepened["updated_artifact_ids"]) == {
            brief.id,
            report.id,
            script.id,
        }

        revised = await revise_script_section(
            store,
            artifact_id=script.id,
            section_id="narration",
            replacement=(
                f"The measured rate change is documented [C{claims[0].id}], "
                "but its downstream effects remain qualified."
            ),
            owner_id="customer-1",
        )
        assert "downstream effects remain qualified" in revised.content
        exported, media_type, filename = await export_artifact(
            store,
            artifact_id=script.id,
            owner_id="customer-1",
            export_format="markdown",
        )
        assert exported.startswith("# Markov Script")
        assert media_type.startswith("text/markdown")
        assert filename.endswith(".md")

        verified = await generate_case_artifact(
            store,
            case_id=case.id,
            artifact_type="script",
            review_level="verified",
        )
        review = (await store.list_review_jobs(status="queued"))[0]
        evidence = (await store.list_claim_evidence(claims[0].id))[0]
        await record_review_decision(
            store,
            review_id=review.id,
            reviewer_id="reviewer-1",
            entity_type="evidence",
            entity_id=str(evidence.evidence_passage_id),
            decision_type="evidence_accepted",
            new_value={"claim_id": claims[0].id},
            reason="Opened the original source and confirmed the exact passage.",
        )
        finalized = await finalize_review(
            store,
            review_id=review.id,
            reviewer_id="reviewer-1",
            review_minutes=9,
            settings=Settings(MARKOV_HUMAN_REVIEW_HOURLY_COST=40),
        )

        assert verified.status == "awaiting_review"
        assert finalized.status == "completed"
        assert (await store.get_artifact(verified.id)).status == "completed"
        assert len(await store.list_review_decisions(review.id)) == 1
        assert len(await store.list_costs(case.id)) >= 4
        event_types = {
            item.event_type
            for item in await store.list_usage_events(owner_id="customer-1")
        }
        assert {
            "artifact_generated",
            "claim_deepened",
            "artifact_revised",
            "artifact_exported",
            "verified_review_started",
            "verified_review_completed",
        } <= event_types
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_topic_question_becomes_an_isolated_research_case_without_url_extraction():
    store = await SqliteStore.open(":memory:")

    async def fail_extractor(*args, **kwargs):
        raise AssertionError("topic-only cases should not run URL extraction")

    async def research_question(store, *, case_id, claim, **kwargs):
        source = await store.add_source(
            url="https://example.gov/topic-evidence",
            title="Topic evidence",
            source_type="article",
            content_text="The inspected record provides relevant context.",
            summary="",
        )
        await store.update_source_provenance(
            source.id,
            source_role="official_data",
            source_quality="official_data",
            source_quality_rationale="Official fixture record.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=source.id,
            source_role="independent_evidence",
        )
        passage = await store.add_evidence_passage(
            source_id=source.id,
            passage_text="The inspected record provides relevant context.",
            section_title="Overview",
            source_quality="official_data",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="context_only",
            strength=0.6,
            rationale="Relevant context without a conclusive answer.",
            model_confidence=0.8,
        )
        await store.update_claim_status(claim.id, "unverifiable")
        return {"claim_id": claim.id, "status": "unverifiable"}

    try:
        case = await create_research_case(
            store,
            owner_id="customer-1",
            original_input="Could demographic change affect borrowing costs?",
            mode="research",
        )
        artifacts = await process_research_case(
            store,
            case_id=case.id,
            extractor=fail_extractor,
            claim_researcher=research_question,
        )
        sources = await store.list_research_case_sources(case.id)
        seed_segments = await store.list_source_segments(sources[0]["id"])
        assert case.input_type == "topic"
        assert seed_segments[0].section_title == "Research question"
        assert artifacts[0].artifact_type == "research_report"
        assert "Could demographic change affect borrowing costs" in artifacts[0].content
    finally:
        await store.close()
