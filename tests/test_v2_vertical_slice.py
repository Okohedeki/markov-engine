"""The smallest complete Markov V2 journey, from source to followed idea."""

from __future__ import annotations

import pytest

from markov_engine.branching import follow_connection_into_script
from markov_engine.extract import ExtractedContent, ExtractedSegment
from markov_engine.research import create_research_case, process_research_case
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_youtube_to_three_connections_insight_outputs_and_revised_script():
    store = await SqliteStore.open(":memory:")
    stages = []

    async def extractor(url, tmp_dir, whisper_model):
        return ExtractedContent(
            url=url,
            source_type="youtube",
            title="A source that starts an idea",
            content_text="A constraint changed. A downstream outcome moved later.",
            metadata={"channel": "Fixture channel"},
            segments=[
                ExtractedSegment(
                    ordinal=0,
                    text="The policy constraint changed in the measured period.",
                    start_seconds=12,
                    end_seconds=18,
                    caption_source="youtube_manual",
                ),
                ExtractedSegment(
                    ordinal=1,
                    text="The downstream outcome moved after that period.",
                    start_seconds=28,
                    end_seconds=34,
                    caption_source="youtube_manual",
                ),
            ],
        )

    async def claims(segments):
        return (
            [
                {
                    "claim_text": "The policy constraint changed in the measured period.",
                    "claim_type": "factual",
                    "importance": 1,
                    "speaker_certainty": "asserted_as_fact",
                    "source_segment_ids": [segments[0].id],
                },
                {
                    "claim_text": "The downstream outcome moved after that period.",
                    "claim_type": "causal",
                    "importance": 0.9,
                    "speaker_certainty": "asserted_as_fact",
                    "source_segment_ids": [segments[1].id],
                },
            ],
            [
                {
                    "gap_type": "missing_mechanism",
                    "question": "Which intermediary transmits the constraint?",
                    "importance": 0.95,
                    "related_claim_text": "The downstream outcome moved after that period.",
                }
            ],
            0,
        )

    async def research(store, *, case_id, claim, **kwargs):
        evidence_source = await store.add_source(
            url=f"https://example.gov/series/{claim.id}",
            title=f"Official series {claim.id}",
            source_type="article",
            content_text=f"The official series measures: {claim.claim_text}",
            summary="",
        )
        await store.update_source_provenance(
            evidence_source.id,
            source_role="official_data",
            source_quality="official_data",
            source_quality_rationale="Fixture public series.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=evidence_source.id,
            source_role="independent_evidence",
        )
        passage = await store.add_evidence_passage(
            source_id=evidence_source.id,
            passage_text=f"The official series measures: {claim.claim_text}",
            section_title="Series",
            source_quality="official_data",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="supports",
            strength=0.9,
            rationale="The inspected series measures the atomic claim.",
            model_confidence=0.9,
        )
        await store.update_claim_status(claim.id, "supported")
        return {"claim_id": claim.id, "status": "supported"}

    async def discover(store, *, case_id):
        case_claims = await store.list_claims(case_id)
        gap = (await store.list_research_gaps(case_id))[0]
        source = next(
            row
            for row in await store.list_research_case_sources(case_id)
            if row["case_source_role"] == "seed"
        )
        evidence = (await store.list_claim_evidence(case_claims[0].id))[0]

        def candidate(left_type, left_id, right_type, right_id, kind):
            return {
                "source_node_type": left_type,
                "source_node_id": left_id,
                "target_node_type": right_type,
                "target_node_id": right_id,
                "connection_type": kind,
                "statement": "The upstream constraint changes the downstream interpretation.",
                "mechanism": "An intermediary transmits the changed input to the later outcome.",
                "why_it_matters": "The hidden intermediary is more useful than repeating the source.",
                "supports": "An inspected official series bears on the connected claims.",
                "weakens": "The current passage does not establish the magnitude of the effect.",
                "could_lead_to": "Inspect the intermediary and compare its timing.",
                "evidence_level": "evidence_backed_interpretation",
                "relevance": 0.9,
                "evidence_strength": 0.8,
                "novelty": 0.8,
                "explanatory_value": 0.9,
                "output_usefulness": 0.9,
                "risk": 0.2,
                "evidence": [
                    {
                        "evidence_passage_id": evidence.evidence_passage_id,
                        "stance": "supports",
                        "strength": 0.8,
                        "rationale": "The inspected series bears on the proposed mechanism.",
                    }
                ],
            }

        candidates = [
            candidate(
                "claim",
                case_claims[0].id,
                "claim",
                case_claims[1].id,
                "dependency_link",
            ),
            candidate(
                "claim",
                case_claims[1].id,
                "gap",
                gap.id,
                "hidden_intermediary",
            ),
            candidate(
                "gap", gap.id, "source", source["id"], "constraint_link"
            ),
        ]
        unsupported = candidate(
            "claim", case_claims[0].id, "source", 99_999, "historical_analogue"
        )
        unsupported["mechanism"] = ""
        candidates.append(unsupported)
        return candidates, 0

    async def stage(name, detail):
        stages.append(name)

    try:
        case = await create_research_case(
            store,
            owner_id="creator",
            original_input="https://youtube.com/watch?v=v2",
            mode="script",
            constraints={"target_minutes": 4},
        )
        artifacts = await process_research_case(
            store,
            case_id=case.id,
            modes=["brief", "research", "script"],
            extractor=extractor,
            claim_extractor=claims,
            claim_researcher=research,
            connection_discoverer=discover,
            stage_handler=stage,
        )
        connections = await store.list_connections(case.id)
        validated = [item for item in connections if item.validation_status == "validated"]
        rejected = [item for item in connections if item.validation_status == "rejected"]
        paths = await store.list_connection_paths(case.id)
        insights = await store.list_insight_candidates(case.id)
        by_type = {item.artifact_type: item for item in artifacts}

        assert len(await store.list_source_segments(1)) == 2
        assert len(await store.list_claims(case.id)) == 2
        assert len(await store.list_research_gaps(case.id)) == 1
        assert {item.connection_type for item in validated} == {
            "dependency_link",
            "hidden_intermediary",
            "constraint_link",
        }
        assert len(rejected) == 1
        assert len(paths) == 1
        assert len(insights) == 1
        assert set(by_type) == {"brief", "research_report", "script"}
        assert "## Threads worth pulling" in by_type["brief"].content
        assert "## Connection map" in by_type["research_report"].content
        assert "## Original, defensible angle" in by_type["script"].content
        assert {
            "discovering_connections",
            "validating_connections",
            "building_paths",
            "synthesizing_insights",
        } <= set(stages)

        followed = validated[0]
        _decision, revised = await follow_connection_into_script(
            store,
            connection_id=followed.id,
            owner_id="creator",
            artifact_id=by_type["script"].id,
        )
        assert f"K{followed.id}" in revised.content
        assert (await store.list_artifact_versions(revised.id))[-1][
            "change_kind"
        ] == "connection_followed"
    finally:
        await store.close()
