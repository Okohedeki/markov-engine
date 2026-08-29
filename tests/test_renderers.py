"""Contract tests for deterministic customer-facing artifact packages."""

from __future__ import annotations

import pytest

from markov_engine.config import Settings
from markov_engine.extract import ExtractedContent, ExtractedSegment
from markov_engine.renderers import render_artifact
from markov_engine.research import (
    convert_case_artifact,
    create_research_case,
    generate_case_artifact,
    process_research_case,
)
from markov_engine.store.sqlite import SqliteStore


async def _researched_case(store: SqliteStore):
    case = await store.create_research_case(
        owner_id="customer-1",
        title="Fixture Video",
        original_input="https://youtube.com/watch?v=fixture",
        input_type="youtube",
        purpose="brief",
        constraints={"target_minutes": 6, "audience": "working creators"},
    )
    seed = await store.add_source(
        url=case.original_input,
        title="Fixture Video",
        source_type="youtube",
        content_text="Revenue doubled. The forecast is uncertain.",
        summary="",
    )
    await store.add_research_case_source(
        research_case_id=case.id, source_id=seed.id, source_role="seed"
    )
    segments = await store.add_source_segments(
        source_id=seed.id,
        segments=[
            {
                "text": "Revenue doubled in the measured period.",
                "start_seconds": 62,
                "end_seconds": 68,
                "caption_source": "youtube_manual",
            },
            {
                "text": "The presenter predicts continued growth.",
                "start_seconds": 68,
                "end_seconds": 76,
                "caption_source": "youtube_manual",
            },
        ],
    )
    factual = await store.add_claim(
        research_case_id=case.id,
        seed_source_id=seed.id,
        claim_text="Revenue doubled in the measured period.",
        claim_type="quantitative",
        importance=0.95,
        speaker_certainty="asserted_as_fact",
        source_start_segment_id=segments[0].id,
        source_end_segment_id=segments[0].id,
    )
    prediction = await store.add_claim(
        research_case_id=case.id,
        seed_source_id=seed.id,
        claim_text="Revenue will continue to grow.",
        claim_type="predictive",
        importance=0.7,
        speaker_certainty="speculative",
        source_start_segment_id=segments[1].id,
        source_end_segment_id=segments[1].id,
    )
    evidence_source = await store.add_source(
        url="https://example.gov/revenue-report",
        title="Official Revenue Report",
        source_type="article",
        content_text="Revenue rose from 10 to 20 during the period.",
        summary="",
    )
    await store.update_source_provenance(
        evidence_source.id,
        source_role="official_data",
        source_quality="official_data",
        source_quality_rationale="Government data release.",
    )
    await store.add_research_case_source(
        research_case_id=case.id,
        source_id=evidence_source.id,
        source_role="independent_evidence",
    )
    passage = await store.add_evidence_passage(
        source_id=evidence_source.id,
        passage_text="Revenue rose from 10 to 20 during the period.",
        section_title="Results",
        source_quality="official_data",
    )
    await store.link_claim_evidence(
        claim_id=factual.id,
        evidence_passage_id=passage.id,
        stance="supports",
        strength=0.95,
        rationale="The reported values represent a doubling.",
        model_confidence=0.94,
    )
    await store.update_claim_status(factual.id, "supported")
    await store.update_claim_status(prediction.id, "unverifiable")
    await store.add_research_gap(
        research_case_id=case.id,
        claim_id=prediction.id,
        gap_type="unresolved_evidence",
        question="What evidence supports the forward-looking forecast?",
        importance=0.8,
    )
    return case, factual, prediction, passage


@pytest.mark.asyncio
async def test_all_renderers_preserve_claims_evidence_and_locators():
    store = await SqliteStore.open(":memory:")
    try:
        case, factual, prediction, passage = await _researched_case(store)
        brief = await render_artifact(store, case.id, "brief")
        report = await render_artifact(store, case.id, "research_report")
        script = await render_artifact(store, case.id, "script")

        assert "## Bottom line" in brief.content
        assert "## What can be skipped" in brief.content
        assert "1:02–1:08" in brief.content
        assert "## Source navigation" in brief.content
        assert "## Assumptions" in brief.content
        assert "## What the source leaves out" in brief.content
        assert "## What may be wrong" in brief.content
        assert "## Threads worth pulling" in brief.content

        assert "## Direct answer" in report.content
        assert "## Counterevidence and qualifications" in report.content
        assert "## Source-quality classifications" in report.content
        assert "## Connection map" in report.content
        assert "## Hidden story" in report.content
        assert "## Novel hypotheses" in report.content
        assert "## Research paths" in report.content

        assert "## Complete spoken narration" in script.content
        assert "## Fact-check appendix" in script.content
        assert "## Do not repeat" in script.content
        assert "## Premise check" in script.content
        assert "## Candidate angles" in script.content
        assert "## Original, defensible angle" in script.content
        assert script.structured_content["target_minutes"] == 6
        assert script.structured_content["actual_narration_word_count"] > 0

        for rendered in (brief, report, script):
            assert f"C{factual.id}" in rendered.content
            assert f"C{prediction.id}" in rendered.content
            assert f"E{passage.id}" in rendered.content
            assert "https://example.gov/revenue-report" in rendered.content
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_topic_guidance_creates_a_scoped_artifact_branch():
    store = await SqliteStore.open(":memory:")
    try:
        case, factual, prediction, _passage = await _researched_case(store)
        topic = await store.add_research_topic(
            research_case_id=case.id,
            title="What the measured growth changes",
            focus="Explain the measured result without inheriting the forecast.",
            importance=0.9,
            claim_ids=[factual.id],
        )
        await store.add_research_topic(
            research_case_id=case.id,
            title="Whether the forecast holds",
            focus="Test the forward-looking claim separately.",
            importance=0.8,
            claim_ids=[prediction.id],
        )
        settings = Settings(
            MARKOV_OPENING_CREDITS=20,
            MARKOV_PRODUCT_CREDIT_COSTS={"script_instant": 1},
        )

        script, created = await convert_case_artifact(
            store,
            case_id=case.id,
            owner_id="customer-1",
            mode="script",
            constraints={
                "selected_topic_id": topic.id,
                "angle": "The result matters, but the forecast remains a separate bet.",
                "audience": "independent video creators",
                "target_minutes": 4,
                "tone": "skeptical documentary",
                "delivery_format": "YouTube essay",
                "desired_takeaway": "Separate measured performance from prediction.",
                "evidence_boundary": "block_on_gaps",
            },
            settings=settings,
        )

        assert created is True
        assert script.branch_key == f"topic:{topic.id}"
        assert script.structured_content["selected_topic_id"] == topic.id
        assert script.structured_content["guidance"] == {
            "angle": "The result matters, but the forecast remains a separate bet.",
            "audience": "independent video creators",
            "tone": "skeptical documentary",
            "delivery_format": "YouTube essay",
            "desired_takeaway": "Separate measured performance from prediction.",
            "evidence_boundary": "block_on_gaps",
        }
        assert f"C{factual.id}" in script.content
        assert f"C{prediction.id}" not in script.content
        assert topic.title in script.title
        assert "Stop the draft where an essential open question is unresolved." in script.content
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_youtube_brief_converts_without_repeating_research():
    store = await SqliteStore.open(":memory:")
    extraction_calls = 0
    researched_claim_ids: list[int] = []

    async def fake_extractor(url, tmp_dir, whisper_model):
        nonlocal extraction_calls
        extraction_calls += 1
        return ExtractedContent(
            url=url,
            source_type="youtube",
            title="One Shared Research Case",
            content_text="Claim one. Claim two. Claim three. Claim four. Claim five. Claim six.",
            metadata={"channel": "Fixture Channel"},
            segments=[
                ExtractedSegment(
                    ordinal=0,
                    text="Six independently testable claims are presented.",
                    start_seconds=12,
                    end_seconds=20,
                    caption_source="youtube_manual",
                )
            ],
        )

    async def fake_claim_extractor(segments):
        return (
            [
                {
                    "claim_text": f"Priority claim {index} is testable.",
                    "claim_type": "factual",
                    "importance": 1 - index / 20,
                    "speaker_certainty": "asserted_as_fact",
                    "source_segment_ids": [segments[0].id],
                }
                for index in range(1, 7)
            ],
            [],
            0.01,
        )

    async def fake_claim_researcher(store, *, case_id, claim, **kwargs):
        researched_claim_ids.append(claim.id)
        source = await store.add_source(
            url=f"https://example.gov/evidence/{claim.id}",
            title=f"Evidence {claim.id}",
            source_type="article",
            content_text=f"Independent evidence for {claim.claim_text}",
            summary="",
        )
        await store.update_source_provenance(
            source.id,
            source_role="official_data",
            source_quality="official_data",
            source_quality_rationale="Fixture authority.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=source.id,
            source_role="independent_evidence",
        )
        passage = await store.add_evidence_passage(
            source_id=source.id,
            passage_text=f"Independent evidence for {claim.claim_text}",
            section_title="Finding",
            source_quality="official_data",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="supports",
            strength=0.9,
            rationale="Direct fixture support.",
            model_confidence=0.9,
        )
        await store.update_claim_status(claim.id, "supported")

    try:
        case = await create_research_case(
            store,
            owner_id="customer-1",
            original_input="https://youtube.com/watch?v=shared",
            mode="brief",
            constraints={"target_minutes": 5},
        )
        brief = (
            await process_research_case(
                store,
                case_id=case.id,
                extractor=fake_extractor,
                claim_extractor=fake_claim_extractor,
                claim_researcher=fake_claim_researcher,
            )
        )[0]
        report = await generate_case_artifact(
            store, case_id=case.id, artifact_type="research_report"
        )
        script = await generate_case_artifact(
            store, case_id=case.id, artifact_type="script"
        )

        assert extraction_calls == 1
        assert len(researched_claim_ids) == 6
        assert [brief.artifact_type, report.artifact_type, script.artifact_type] == [
            "brief",
            "research_report",
            "script",
        ]
        assert len(await store.list_claims(case.id)) == 6
        assert len(await store.list_case_artifacts(case.id)) == 3
        assert (await store.get_research_case(case.id)).purpose == "brief,research,script"
        low, high = script.structured_content["target_word_range"]
        assert low <= script.structured_content["actual_narration_word_count"] <= high
    finally:
        await store.close()
