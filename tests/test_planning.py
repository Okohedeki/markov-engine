"""V2 planning turns a large transcript ledger into focused research directions."""

from __future__ import annotations

import pytest

from markov_engine import planning
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_model_plan_canonicalizes_entities_and_focuses_the_full_source(monkeypatch):
    store = await SqliteStore.open(":memory:")
    monkeypatch.setattr(planning._settings, "llm_backend", "anthropic")
    monkeypatch.setattr(planning._settings, "anthropic_api_key", "test-key")
    try:
        case = await store.create_research_case(
            owner_id="owner",
            title="Long interview",
            original_input="https://youtube.com/watch?v=long",
            input_type="youtube",
            purpose="research",
        )
        source = await store.add_source(
            url=case.original_input,
            title=case.title,
            source_type="youtube",
            content_text="A complete long interview.",
            summary="",
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {"ordinal": index, "text": f"Located segment {index}."}
                for index in range(6)
            ],
        )
        claims = []
        for index, segment in enumerate(segments):
            claims.append(
                await store.add_claim(
                    research_case_id=case.id,
                    seed_source_id=source.id,
                    claim_text=(
                        "Jason Arde died after an illness."
                        if index == 5
                        else f"Transcript claim {index} describes a different point."
                    ),
                    claim_type="factual",
                    importance=0.9 - index * 0.05,
                    speaker_certainty="asserted_as_fact",
                    source_start_segment_id=segment.id,
                    source_end_segment_id=segment.id,
                )
            )

        async def fake_plan(prompt, *, schema, model, max_tokens, task):
            assert task == "planning_review"
            assert f"[C{claims[-1].id}]" in prompt
            return {
                "entities": [
                    {
                        "canonical_name": "Jason Arday",
                        "aliases": ["Jason Arde"],
                        "entity_type": "person",
                        "rationale": "The surrounding discussion identifies the academic.",
                    }
                ],
                "topics": [
                    {
                        "title": "Main argument",
                        "focus": "Test the interview's central mechanism.",
                        "importance": 1,
                        "claim_ids": [claims[0].id],
                    },
                    {
                        "title": "Consequential factual claims",
                        "focus": "Verify high-stakes claims from later in the interview.",
                        "importance": 0.95,
                        "claim_ids": [claims[-1].id],
                    },
                ],
                "selected_claims": [
                    {
                        "claim_id": claims[0].id,
                        "canonical_claim_text": claims[0].claim_text,
                        "topic_title": "Main argument",
                        "research_priority": 1,
                        "selection_reason": "Central mechanism.",
                    },
                    {
                        "claim_id": claims[-1].id,
                        "canonical_claim_text": "Jason Arday died after an illness.",
                        "topic_title": "Consequential factual claims",
                        "research_priority": 0.95,
                        "selection_reason": "Consequential late-source factual claim.",
                    },
                ],
            }, 0.004

        monkeypatch.setattr(planning, "complete_json", fake_plan)
        core = await planning.plan_research_case(
            store, case_id=case.id, max_core_claims=4
        )

        assert [item.id for item in core] == [claims[0].id, claims[-1].id]
        corrected = next(item for item in core if item.id == claims[-1].id)
        assert corrected.claim_text == "Jason Arde died after an illness."
        assert corrected.research_text == "Jason Arday died after an illness."
        assert len(await store.list_research_topics(case.id)) == 2
        entities = await store.list_case_entities(case.id)
        assert entities[0].canonical_name == "Jason Arday"
        assert entities[0].aliases == ["Jason Arde"]
        ledger = await store.list_claims(case.id)
        assert sum(item.disposition == "core" for item in ledger) == 2
        assert sum(item.disposition == "background" for item in ledger) == 4
        assert (await store.list_costs(case.id))[0].operation == "research_planning"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_offline_plan_samples_across_the_source_not_just_the_first_claims(
    monkeypatch,
):
    store = await SqliteStore.open(":memory:")
    monkeypatch.setattr(planning._settings, "llm_backend", "heuristic")
    try:
        case = await store.create_research_case(
            owner_id="owner",
            title="Timeline",
            original_input="source",
            input_type="text",
            purpose="brief",
        )
        source = await store.add_source(
            url=None,
            title=case.title,
            source_type="text",
            content_text="Timeline",
            summary="",
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[{"ordinal": index, "text": f"Segment {index}."} for index in range(20)],
        )
        for index, segment in enumerate(segments):
            await store.add_claim(
                research_case_id=case.id,
                seed_source_id=source.id,
                claim_text=f"Researchable claim number {index}.",
                claim_type="factual",
                importance=1 - index / 100,
                speaker_certainty="asserted_as_fact",
                source_start_segment_id=segment.id,
                source_end_segment_id=segment.id,
            )

        core = await planning.plan_research_case(
            store, case_id=case.id, max_core_claims=5
        )

        located_ids = sorted(item.source_start_segment_id for item in core)
        assert len(core) == 5
        assert located_ids[0] == segments[0].id
        assert located_ids[-1] >= segments[16].id
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_hybrid_reduces_full_ledger_locally_before_cloud_review(monkeypatch):
    store = await SqliteStore.open(":memory:")
    monkeypatch.setattr(planning._settings, "llm_backend", "hybrid")
    monkeypatch.setattr(planning._settings, "hybrid_cloud_backend", "openai")
    monkeypatch.setattr(planning._settings, "local_llm_model", "llama3.1:8b")
    monkeypatch.setattr(planning._settings, "openai_api_key", "test-key")
    try:
        case = await store.create_research_case(
            owner_id="owner",
            title="Long source",
            original_input="https://youtube.com/watch?v=long-hybrid",
            input_type="youtube",
            purpose="research",
        )
        source = await store.add_source(
            url=case.original_input,
            title=case.title,
            source_type="youtube",
            content_text="A complete source.",
            summary="",
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {"ordinal": index, "text": f"Located segment {index}."}
                for index in range(12)
            ],
        )
        claims = []
        for index, segment in enumerate(segments):
            claims.append(
                await store.add_claim(
                    research_case_id=case.id,
                    seed_source_id=source.id,
                    claim_text=f"Distinct researchable claim number {index}.",
                    claim_type="factual",
                    importance=1 - index / 100,
                    speaker_certainty="asserted_as_fact",
                    source_start_segment_id=segment.id,
                    source_end_segment_id=segment.id,
                )
            )

        calls = []

        async def fake_plan(
            prompt, *, schema, model, max_tokens, task, route="auto"
        ):
            calls.append((task, route, prompt))
            if route == "local":
                assert all(f"[C{claim.id}]" in prompt for claim in claims)
                selected_claims = claims[:4]
            else:
                candidate_ids = [
                    claim.id for claim in claims if f"[C{claim.id}]" in prompt
                ]
                assert len(candidate_ids) <= 4
                assert claims[-1].id in candidate_ids
                selected_claims = [
                    claim for claim in claims if claim.id in candidate_ids
                ]
            return {
                "entities": [],
                "topics": [
                    {
                        "title": "Bounded directions",
                        "focus": "Review only the reduced candidate ledger.",
                        "importance": 1,
                        "claim_ids": [claim.id for claim in selected_claims],
                    }
                ],
                "selected_claims": [
                    {
                        "claim_id": claim.id,
                        "canonical_claim_text": claim.claim_text,
                        "topic_title": "Bounded directions",
                        "research_priority": claim.importance,
                        "selection_reason": "Bounded candidate.",
                    }
                    for claim in selected_claims
                ],
            }, 0.002 if route == "cloud" else 0

        monkeypatch.setattr(planning, "complete_json", fake_plan)
        core = await planning.plan_research_case(
            store, case_id=case.id, max_core_claims=4
        )

        assert [item[0:2] for item in calls] == [
            ("planning_reduction", "local"),
            ("planning_review", "cloud"),
        ]
        assert len(core) == 4
        assert claims[-1].id in {item.id for item in core}
    finally:
        await store.close()
