"""The V2 graph persists without weakening V1 evidence provenance."""

from __future__ import annotations

import pytest

from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_connection_graph_round_trip_and_owner_scope():
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="owner-1",
            title="Connection case",
            original_input="https://youtube.com/watch?v=graph",
            input_type="youtube",
            purpose="research",
        )
        source = await store.add_source(
            url="https://example.gov/data",
            title="Official data",
            source_type="article",
            content_text="The measured dependency changed.",
            summary="",
        )
        await store.add_research_case_source(
            research_case_id=case.id,
            source_id=source.id,
            source_role="independent_evidence",
        )
        evidence = await store.add_evidence_passage(
            source_id=source.id,
            passage_text="The measured dependency changed.",
            section_title="Results",
            source_quality="primary_evidence",
        )
        first = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=source.id,
            claim_text="A policy constraint changed.",
            claim_type="factual",
            importance=1,
            speaker_certainty="asserted",
            source_start_segment_id=None,
            source_end_segment_id=None,
        )
        second = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=source.id,
            claim_text="A downstream dependency changed.",
            claim_type="factual",
            importance=0.8,
            speaker_certainty="asserted",
            source_start_segment_id=None,
            source_end_segment_id=None,
        )
        connection = await store.add_connection(
            research_case_id=case.id,
            source_node_type="claim",
            source_node_id=first.id,
            target_node_type="claim",
            target_node_id=second.id,
            connection_type="dependency_link",
            statement="The policy change alters the downstream dependency.",
            mechanism="The dependency consumes the constrained input.",
            why_it_matters="The second outcome cannot be evaluated in isolation.",
            supports="The inspected results describe the changed dependency.",
            weakens="The timing is not fully resolved.",
            could_lead_to="Compare the dependency before and after the policy change.",
            evidence_level="evidence_backed_interpretation",
            validation_status="validated",
            relevance=0.9,
            evidence_strength=0.8,
            novelty=0.7,
            explanatory_value=0.9,
            output_usefulness=0.8,
            risk=0.2,
            total_score=0.79,
        )
        await store.link_connection_evidence(
            connection_id=connection.id,
            evidence_passage_id=evidence.id,
            stance="supports",
            strength=0.8,
            rationale="The inspected passage bears on the stated mechanism.",
        )
        path = await store.add_connection_path(
            research_case_id=case.id,
            title="Constraint to dependency",
            summary="A policy constraint reaches a downstream result.",
            connection_ids=[connection.id],
            relevance=0.9,
            evidence_strength=0.8,
            novelty=0.7,
            explanatory_value=0.9,
            output_usefulness=0.8,
            risk=0.2,
            total_score=0.79,
            status="validated",
        )
        insight = await store.add_insight_candidate(
            research_case_id=case.id,
            title="The dependency is the story",
            thesis="The visible result is downstream of the overlooked constraint.",
            connection_path_ids=[path.id],
            supporting_claim_ids=[first.id, second.id],
            novelty_basis="The seed treats the outcomes separately.",
            evidence_level="evidence_backed_interpretation",
            evidence_strength=0.8,
            counterevidence="Timing remains unresolved.",
            uncertainty="Direction is supported; magnitude is not.",
            next_step="Inspect the time series.",
        )
        decision = await store.add_user_branch_decision(
            research_case_id=case.id,
            owner_id=case.owner_id,
            connection_id=connection.id,
            action="follow",
            metadata={"insight_id": insight.id},
        )

        assert await store.get_connection(connection.id, owner_id="other") is None
        assert (await store.get_connection(connection.id)).mechanism.startswith("The")
        assert (await store.list_connection_evidence(connection.id))[0].evidence.id == evidence.id
        assert (await store.list_connection_paths(case.id))[0].connection_ids == [connection.id]
        assert (await store.list_insight_candidates(case.id))[0].supporting_claim_ids == [
            first.id,
            second.id,
        ]
        assert decision.metadata == {"insight_id": insight.id}
        assert (await store.list_user_branch_decisions(case.id))[0].action == "follow"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_connection_upsert_preserves_one_addressable_edge():
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="owner-1",
            title="Upsert",
            original_input="question",
            input_type="topic",
            purpose="brief",
        )
        base = dict(
            research_case_id=case.id,
            source_node_type="claim",
            source_node_id=1,
            target_node_type="claim",
            target_node_id=2,
            connection_type="contradiction",
            mechanism="The claims make incompatible predictions under the same condition.",
            why_it_matters="Only one framing can guide the output.",
            supports="The statements conflict.",
            weakens="They may use different time horizons.",
            could_lead_to="Normalize the time horizons.",
            evidence_level="plausible_hypothesis",
        )
        original = await store.add_connection(
            **base,
            statement="The claims may conflict.",
            total_score=0.4,
        )
        updated = await store.add_connection(
            **base,
            statement="The claims conflict under a shared horizon.",
            total_score=0.7,
        )

        assert original.id == updated.id
        assert len(await store.list_connections(case.id)) == 1
        assert updated.total_score == 0.7
    finally:
        await store.close()
