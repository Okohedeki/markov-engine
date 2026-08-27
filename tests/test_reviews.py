"""Structured review decisions and verified delivery finalization."""

from __future__ import annotations

import pytest

from markov_engine.config import Settings
from markov_engine.reviews import finalize_review, record_review_decision
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_reviewer_correction_is_applied_audited_and_finalized():
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="owner-1",
            title="Review fixture",
            original_input="https://example.com/fixture",
            input_type="article",
            purpose="brief",
            constraints={},
        )
        source = await store.add_source(
            url=case.original_input,
            title="Fixture",
            source_type="article",
            content_text="A reviewed claim.",
            summary="",
        )
        segment = (
            await store.add_source_segments(
                source_id=source.id, segments=[{"text": "A reviewed claim."}]
            )
        )[0]
        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=source.id,
            claim_text="A reviewed claim.",
            claim_type="factual",
            importance=1,
            speaker_certainty="asserted_as_fact",
            source_start_segment_id=segment.id,
            source_end_segment_id=segment.id,
        )
        artifact = await store.add_case_artifact(
            research_case_id=case.id,
            artifact_type="brief",
            review_level="verified",
            status="awaiting_review",
            title="Verified Brief",
            content="# Verified Brief\n\n## Bottom line\n\nA reviewed claim.",
            structured_content={
                "sections": [
                    {
                        "id": "bottom-line",
                        "title": "Bottom line",
                        "content": "A reviewed claim.",
                        "claim_ids": [claim.id],
                    }
                ]
            },
            word_count=6,
            model_used="fixture",
            generation_cost=0,
            source_ids=[source.id],
        )
        review = await store.create_review_job(artifact.id)
        decision = await record_review_decision(
            store,
            review_id=review.id,
            reviewer_id="reviewer-1",
            entity_type="claim",
            entity_id=str(claim.id),
            decision_type="claim_status_changed",
            new_value="qualified",
            reason="The source supports a narrower formulation.",
        )
        completed = await finalize_review(
            store,
            review_id=review.id,
            reviewer_id="reviewer-1",
            review_minutes=12,
            settings=Settings(MARKOV_HUMAN_REVIEW_HOURLY_COST=60),
        )

        assert decision.previous_value == "not_researched"
        assert (await store.get_claim(claim.id)).verification_status == "qualified"
        assert completed.status == "completed"
        assert completed.review_minutes == 12
        assert (await store.get_artifact(artifact.id)).status == "completed"
        assert (await store.list_costs(case.id))[-1].cost == pytest.approx(12)
        assert [
            item.event_type for item in await store.list_usage_events(owner_id="owner-1")
        ] == ["verified_review_started", "verified_review_completed"]
        assert [
            item["change_kind"] for item in await store.list_artifact_versions(artifact.id)
        ] == ["generated", "review_finalized"]
    finally:
        await store.close()
