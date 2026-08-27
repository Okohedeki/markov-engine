"""Job idempotency, stage events, and terminal accounting."""

from __future__ import annotations

import pytest

from markov_engine.config import Settings
from markov_engine.jobs import run_job, submit_job
from markov_engine.store.sqlite import SqliteStore


def _settings() -> Settings:
    return Settings(
        MARKOV_OPENING_CREDITS=10,
        MARKOV_PRODUCT_CREDIT_COSTS={
            "brief_instant": 2,
            "brief_verified": 3,
            "research_instant": 2,
            "research_verified": 3,
            "script_instant": 2,
            "script_verified": 3,
        },
    )


@pytest.mark.asyncio
async def test_job_is_idempotent_and_records_stages():
    store = await SqliteStore.open(":memory:")
    settings = _settings()

    async def fake_process(store, *, case_id, review_level, modes, stage_handler, **kwargs):
        await stage_handler("extracting_sources", {})
        await stage_handler("building_artifact", {"artifact_type": "brief"})
        artifact = await store.add_case_artifact(
            research_case_id=case_id,
            artifact_type="brief",
            review_level=review_level,
            status="completed",
            title="Fixture Brief",
            content="# Fixture Brief",
            structured_content={"sections": []},
            word_count=2,
            model_used="fixture",
            generation_cost=0,
            source_ids=[],
        )
        return [artifact]

    try:
        job, created = await submit_job(
            store,
            owner_id="owner-1",
            mode="brief",
            review_level="instant",
            inputs=[{"type": "url", "value": "https://youtube.com/watch?v=x"}],
            idempotency_key="same-request",
            settings=settings,
        )
        repeated, repeated_created = await submit_job(
            store,
            owner_id="owner-1",
            mode="brief",
            review_level="instant",
            inputs=[{"type": "url", "value": "https://youtube.com/watch?v=x"}],
            idempotency_key="same-request",
            settings=settings,
        )
        completed = await run_job(
            store, job_id=job.id, settings=settings, process_case=fake_process
        )

        assert created and not repeated_created
        assert repeated.id == job.id
        assert completed.status == "completed"
        assert (await store.get_credit_account("owner-1")).balance == 8
        assert [event.stage for event in await store.list_job_events(job.id)] == [
            "queued",
            "starting",
            "extracting_sources",
            "building_artifact",
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_failed_job_is_refunded_and_exposes_error():
    store = await SqliteStore.open(":memory:")
    settings = _settings()

    async def fail_process(*args, **kwargs):
        raise RuntimeError("fixture source blocked")

    try:
        job, _ = await submit_job(
            store,
            owner_id="owner-1",
            mode="research",
            review_level="verified",
            inputs=[{"type": "text", "value": "What evidence exists?"}],
            settings=settings,
        )
        failed = await run_job(
            store, job_id=job.id, settings=settings, process_case=fail_process
        )
        assert failed.status == "failed"
        assert failed.error == "fixture source blocked"
        assert (await store.get_credit_account("owner-1")).balance == 10
    finally:
        await store.close()
