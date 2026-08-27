"""Round-trip the V1 research, review, usage, cost, and credit records."""

from __future__ import annotations

import pytest

from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_research_case_round_trip():
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="owner-1",
            title="A researched video",
            original_input="https://youtube.com/watch?v=fixture",
            input_type="youtube",
            purpose="brief",
            constraints={"focus": "economic claims"},
        )
        assert (await store.get_research_case(case.id, owner_id="other")) is None

        source = await store.add_source(
            url=case.original_input,
            title="Fixture",
            source_type="youtube",
            content_text="First claim. Second claim.",
            summary="Two claims",
            metadata={"channel": "Fixture channel"},
        )
        await store.add_research_case_source(
            research_case_id=case.id, source_id=source.id, source_role="seed"
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {"text": "First claim.", "start_seconds": 1.25, "end_seconds": 3.5,
                 "caption_source": "youtube_manual"},
                {"text": "Second claim.", "start_seconds": 3.5, "end_seconds": 7.0,
                 "caption_source": "youtube_manual"},
            ],
        )
        assert segments[0].locator == "0:01"

        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=source.id,
            claim_text="The first claim is measurable.",
            claim_type="factual",
            importance=0.9,
            speaker_certainty="asserted_as_fact",
            source_start_segment_id=segments[0].id,
            source_end_segment_id=segments[0].id,
        )
        gap = await store.add_research_gap(
            research_case_id=case.id,
            claim_id=claim.id,
            gap_type="missing_data",
            question="Which dataset supports it?",
            importance=0.8,
        )
        passage = await store.add_evidence_passage(
            source_id=source.id,
            passage_text="The measured value was 42.",
            start_seconds=1.25,
            end_seconds=3.5,
            source_quality="primary_evidence",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="supports",
            strength=0.88,
            rationale="The passage states the measured value.",
            model_confidence=0.91,
        )
        await store.update_claim_status(claim.id, "supported")

        artifact = await store.add_case_artifact(
            research_case_id=case.id,
            artifact_type="brief",
            review_level="verified",
            status="awaiting_review",
            title="Markov Brief: Fixture",
            content="# Brief\n\nSupported claim [C1].",
            structured_content={"sections": [{"id": "bottom-line", "claim_ids": [claim.id]}]},
            word_count=4,
            model_used="deterministic",
            generation_cost=0,
            source_ids=[source.id],
        )
        assert (await store.get_artifact(artifact.id, owner_id="other")) is None
        assert len(await store.list_artifact_versions(artifact.id)) == 1

        job = await store.create_job(
            job_id="job-1",
            owner_id="owner-1",
            research_case_id=case.id,
            mode="brief",
            review_level="verified",
            constraints={},
            webhook_url=None,
            idempotency_key="idem-1",
        )
        await store.update_job(job.id, status="running", stage="researching")
        await store.add_job_event(job_id=job.id, stage="researching", detail={"claim": claim.id})
        assert (await store.get_job_by_idempotency(
            owner_id="owner-1", idempotency_key="idem-1"
        )).id == job.id

        review = await store.create_review_job(artifact.id)
        decision = await store.add_review_decision(
            review_job_id=review.id,
            entity_type="claim",
            entity_id=str(claim.id),
            decision_type="claim_status_changed",
            previous_value="not_researched",
            new_value="supported",
            reason="Checked the cited passage.",
        )
        await store.update_review_job(
            review.id, status="completed", assigned_reviewer="reviewer-1", review_minutes=6.5
        )

        await store.record_usage_event(
            owner_id="owner-1",
            event_type="job_completed",
            research_case_id=case.id,
            artifact_id=artifact.id,
            metadata={"mode": "brief"},
        )
        await store.record_cost(
            research_case_id=case.id,
            artifact_id=artifact.id,
            provider="fixture",
            operation="claim_extraction",
            units=2,
            cost=0.02,
        )
        await store.ensure_credit_account("owner-1", opening_balance=10)
        account = await store.apply_credit_transaction(
            owner_id="owner-1",
            amount=-2,
            reason="job",
            product_variant="brief_verified",
            idempotency_key="charge-job-1",
        )
        repeated = await store.apply_credit_transaction(
            owner_id="owner-1",
            amount=-2,
            reason="job",
            product_variant="brief_verified",
            idempotency_key="charge-job-1",
        )

        assert (await store.list_claims(case.id))[0].verification_status == "supported"
        assert (await store.list_research_gaps(case.id))[0].id == gap.id
        assert (await store.list_claim_evidence(claim.id))[0].evidence.id == passage.id
        assert (await store.list_job_events(job.id))[0].stage == "researching"
        assert (await store.list_review_decisions(review.id))[0].id == decision.id
        assert (await store.list_usage_events(owner_id="owner-1"))[0].event_type == "job_completed"
        assert (await store.list_costs(case.id))[0].cost == pytest.approx(0.02)
        assert account.balance == repeated.balance == pytest.approx(8)
    finally:
        await store.close()
