"""V2 connection validation is typed, scored, path-aware, and honest."""

from __future__ import annotations

import pytest

from markov_engine.connections import (
    CONNECTION_TYPES,
    build_connection_paths,
    derive_insight_candidates,
    process_connection_graph,
    score_connection,
    validate_and_persist_connection,
    validate_path_order,
)
from markov_engine.store.sqlite import SqliteStore


async def _case_graph_inputs(store: SqliteStore):
    case = await store.create_research_case(
        owner_id="reader",
        title="A source with a downstream story",
        original_input="https://youtube.com/watch?v=connections",
        input_type="youtube",
        purpose="research",
    )
    source = await store.add_source(
        url="https://example.gov/series",
        title="Official series",
        source_type="article",
        content_text="The official series records the mechanism over time.",
        summary="",
    )
    await store.add_research_case_source(
        research_case_id=case.id,
        source_id=source.id,
        source_role="independent_evidence",
    )
    first = await store.add_claim(
        research_case_id=case.id,
        seed_source_id=source.id,
        claim_text="The first constraint changed.",
        claim_type="factual",
        importance=1,
        speaker_certainty="asserted",
        source_start_segment_id=None,
        source_end_segment_id=None,
        verification_status="supported",
    )
    second = await store.add_claim(
        research_case_id=case.id,
        seed_source_id=source.id,
        claim_text="The second outcome moved later.",
        claim_type="factual",
        importance=0.9,
        speaker_certainty="asserted",
        source_start_segment_id=None,
        source_end_segment_id=None,
        verification_status="supported",
    )
    gap = await store.add_research_gap(
        research_case_id=case.id,
        claim_id=second.id,
        gap_type="missing_mechanism",
        question="Which intermediary transmits the constraint?",
        importance=0.9,
    )
    evidence = await store.add_evidence_passage(
        source_id=source.id,
        passage_text="The official series records the mechanism over time.",
        section_title="Series notes",
        source_quality="official_data",
    )
    await store.link_claim_evidence(
        claim_id=first.id,
        evidence_passage_id=evidence.id,
        stance="supports",
        strength=0.85,
        rationale="The series directly measures the first constraint.",
        model_confidence=0.8,
    )
    return case, source, first, second, gap, evidence


def _candidate(source_type, source_id, target_type, target_id, kind, evidence_id):
    return {
        "source_node_type": source_type,
        "source_node_id": source_id,
        "target_node_type": target_type,
        "target_node_id": target_id,
        "connection_type": kind,
        "statement": "The first node changes how the second node should be interpreted.",
        "mechanism": "The first node changes an input consumed by the second node.",
        "why_it_matters": "The visible outcome is downstream rather than independent.",
        "supports": "An inspected official series bears on the proposed mechanism.",
        "weakens": "The observed timing does not establish the full magnitude.",
        "could_lead_to": "Compare the lag structure against an alternative explanation.",
        "evidence_level": "established",
        "relevance": 0.9,
        "evidence_strength": 0.85,
        "novelty": 0.75,
        "explanatory_value": 0.9,
        "output_usefulness": 0.85,
        "risk": 0.15,
        "evidence": [
            {
                "evidence_passage_id": evidence_id,
                "stance": "supports",
                "strength": 0.85,
                "rationale": "The inspected series bears on the proposed mechanism.",
            }
        ],
    }


def test_score_is_reproducible_and_penalizes_risk():
    dimensions = {
        "relevance": 0.9,
        "evidence_strength": 0.8,
        "novelty": 0.7,
        "explanatory_value": 0.8,
        "output_usefulness": 0.9,
        "risk": 0.1,
    }
    low_risk = score_connection(dimensions)
    assert low_risk == score_connection(dimensions)
    assert score_connection({**dimensions, "risk": 0.9}) < low_risk
    assert 0 <= low_risk <= 1


@pytest.mark.asyncio
async def test_evidence_level_is_capped_and_unsupported_candidate_is_rejected():
    store = await SqliteStore.open(":memory:")
    try:
        case, _source, first, second, _gap, evidence = await _case_graph_inputs(store)
        candidate = _candidate(
            "claim", first.id, "claim", second.id, "dependency_link", evidence.id
        )
        validated = await validate_and_persist_connection(
            store, case_id=case.id, candidate=candidate
        )
        assert validated.validation_status == "validated"
        assert validated.evidence_level == "evidence_backed_interpretation"

        unsupported = await validate_and_persist_connection(
            store,
            case_id=case.id,
            candidate={
                **candidate,
                "target_node_id": 99_999,
                "connection_type": "historical_analogue",
                "mechanism": "",
                "supports": "",
                "evidence": [],
            },
        )
        assert unsupported.validation_status == "rejected"
        assert "Endpoint does not belong" in unsupported.rejection_reason
        assert "Missing substantive mechanism" in unsupported.rejection_reason

        no_evidence = await validate_and_persist_connection(
            store,
            case_id=case.id,
            candidate={**candidate, "connection_type": "constraint_link", "evidence": []},
        )
        assert no_evidence.validation_status == "rejected"
        assert "No independent evidence passage" in no_evidence.rejection_reason
    finally:
        await store.close()


def test_path_order_requires_direction_and_rejects_cycles():
    from markov_engine.store.records import ConnectionRec

    def edge(edge_id, source, target):
        return ConnectionRec(
            id=edge_id,
            research_case_id=1,
            source_node_type="claim",
            source_node_id=source,
            target_node_type="claim",
            target_node_id=target,
            connection_type="dependency_link",
            statement="A substantive directed relationship exists.",
            mechanism="The first condition changes the next condition.",
            why_it_matters="Direction changes how the result is interpreted.",
            supports="An inspected passage supports this direction.",
            weakens="Magnitude remains uncertain.",
            could_lead_to="Inspect the downstream measurement.",
            evidence_level="evidence_backed_interpretation",
        )

    assert validate_path_order([edge(1, 1, 2), edge(2, 2, 3)])
    assert not validate_path_order([edge(1, 1, 2), edge(2, 3, 2)])
    assert not validate_path_order([edge(1, 1, 2), edge(2, 2, 1)])


@pytest.mark.asyncio
async def test_three_typed_connections_form_a_path_and_one_insight():
    store = await SqliteStore.open(":memory:")
    try:
        case, source, first, second, gap, evidence = await _case_graph_inputs(store)
        candidates = [
            _candidate(
                "claim", first.id, "claim", second.id, "dependency_link", evidence.id
            ),
            _candidate(
                "claim", second.id, "gap", gap.id, "hidden_intermediary", evidence.id
            ),
            _candidate(
                "gap", gap.id, "source", source.id, "constraint_link", evidence.id
            ),
        ]
        for candidate in candidates:
            await validate_and_persist_connection(
                store, case_id=case.id, candidate=candidate
            )
        connections = await store.list_connections(case.id, status="validated")
        paths = await build_connection_paths(store, case_id=case.id)
        insights = await derive_insight_candidates(store, case_id=case.id, paths=paths)

        assert {item.connection_type for item in connections} <= CONNECTION_TYPES
        assert len(connections) == 3
        assert len(paths) == 1
        ordered = [await store.get_connection(item) for item in paths[0].connection_ids]
        assert validate_path_order([item for item in ordered if item is not None])
        assert len(insights) == 1
        assert insights[0].connection_path_ids == [paths[0].id]
        assert insights[0].evidence_level == "evidence_backed_interpretation"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_graph_processor_persists_validated_and_rejected_candidates():
    store = await SqliteStore.open(":memory:")
    try:
        case, _source, first, second, gap, evidence = await _case_graph_inputs(store)

        async def discoverer(_store, *, case_id):
            assert case_id == case.id
            valid = _candidate(
                "claim", first.id, "claim", second.id, "shared_mechanism", evidence.id
            )
            rejected = _candidate(
                "claim", second.id, "gap", gap.id, "cross_domain_transfer", evidence.id
            )
            rejected["why_it_matters"] = ""
            return [valid, rejected], 0.012

        result = await process_connection_graph(
            store, case_id=case.id, discoverer=discoverer
        )
        assert len(result["validated"]) == 1
        assert len(result["rejected"]) == 1
        assert len(result["paths"]) == 1
        assert len(result["insights"]) == 1
        assert result["cost"] == 0.012
    finally:
        await store.close()
