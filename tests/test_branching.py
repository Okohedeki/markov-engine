"""Following a V2 connection forks a durable, independent Script direction."""

from __future__ import annotations

import pytest

from markov_engine.branching import follow_connection_into_script
from markov_engine.renderers import render_artifact
from markov_engine.research import generate_case_artifact, persist_rendered_artifact
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_followed_connection_becomes_the_angle_in_a_separate_script():
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="creator",
            title="Two possible stories",
            original_input="https://youtube.com/watch?v=branches",
            input_type="youtube",
            purpose="script",
            constraints={"target_minutes": 3},
        )
        source = await store.add_source(
            url=case.original_input,
            title=case.title,
            source_type="youtube",
            content_text="One. Two. Three. Four.",
            summary="",
        )
        await store.add_research_case_source(
            research_case_id=case.id, source_id=source.id, source_role="seed"
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {"ordinal": index, "text": f"Located statement {index + 1}.", "start_seconds": index * 10}
                for index in range(4)
            ],
        )
        claims = []
        for index, segment in enumerate(segments):
            claims.append(
                await store.add_claim(
                    research_case_id=case.id,
                    seed_source_id=source.id,
                    claim_text=f"Located statement {index + 1} has a measurable implication.",
                    claim_type="factual",
                    importance=1 - index / 10,
                    speaker_certainty="asserted_as_fact",
                    source_start_segment_id=segment.id,
                    source_end_segment_id=segment.id,
                    verification_status="supported",
                )
            )

        async def connection(left, right, statement, score):
            return await store.add_connection(
                research_case_id=case.id,
                source_node_type="claim",
                source_node_id=left.id,
                target_node_type="claim",
                target_node_id=right.id,
                connection_type="dependency_link",
                statement=statement,
                mechanism="One measured input changes the downstream condition.",
                why_it_matters="The downstream mechanism changes the script's conclusion.",
                supports="The two supported claims identify the endpoints.",
                weakens="The magnitude remains uncertain.",
                could_lead_to="Inspect the intermediary time series.",
                evidence_level="plausible_hypothesis",
                validation_status="validated",
                relevance=score,
                evidence_strength=score,
                novelty=score,
                explanatory_value=score,
                output_usefulness=score,
                risk=0.2,
                total_score=score,
            )

        first = await connection(
            claims[0], claims[1], "The obvious high-scoring connection is useful.", 0.9
        )
        followed = await connection(
            claims[2], claims[3], "The followed connection reveals a better branch.", 0.7
        )
        first_path = await store.add_connection_path(
            research_case_id=case.id,
            title="Obvious path",
            summary=first.statement,
            connection_ids=[first.id],
            relevance=0.9,
            evidence_strength=0.9,
            novelty=0.9,
            explanatory_value=0.9,
            output_usefulness=0.9,
            risk=0.2,
            total_score=0.9,
            status="validated",
        )
        followed_path = await store.add_connection_path(
            research_case_id=case.id,
            title="Followed path",
            summary=followed.statement,
            connection_ids=[followed.id],
            relevance=0.7,
            evidence_strength=0.7,
            novelty=0.7,
            explanatory_value=0.7,
            output_usefulness=0.7,
            risk=0.2,
            total_score=0.7,
            status="validated",
        )
        first_insight = await store.add_insight_candidate(
            research_case_id=case.id,
            title="First angle",
            thesis="The first angle starts as the recommended story.",
            connection_path_ids=[first_path.id],
            supporting_claim_ids=[claims[0].id, claims[1].id],
            novelty_basis="It links the first two claims.",
            evidence_level="plausible_hypothesis",
            evidence_strength=0.9,
            counterevidence="Magnitude is uncertain.",
            uncertainty="The mechanism still needs direct evidence.",
            next_step="Inspect the input.",
        )
        followed_insight = await store.add_insight_candidate(
            research_case_id=case.id,
            title="Followed angle",
            thesis="The followed branch becomes the revised original angle.",
            connection_path_ids=[followed_path.id],
            supporting_claim_ids=[claims[2].id, claims[3].id],
            novelty_basis="It links the overlooked claims.",
            evidence_level="plausible_hypothesis",
            evidence_strength=0.7,
            counterevidence="Magnitude is uncertain.",
            uncertainty="The mechanism still needs direct evidence.",
            next_step="Inspect the intermediary.",
        )
        rendered = await render_artifact(store, case.id, "script")
        artifact = await persist_rendered_artifact(
            store, case=case, rendered=rendered, review_level="instant"
        )
        original_angle = next(
            item["content"]
            for item in artifact.structured_content["sections"]
            if item["id"] == "recommended-angle"
        )
        assert original_angle == first_insight.thesis

        _first_decision, first_branch = await follow_connection_into_script(
            store,
            connection_id=first.id,
            owner_id="creator",
            artifact_id=artifact.id,
        )
        decision, revised = await follow_connection_into_script(
            store,
            connection_id=followed.id,
            owner_id="creator",
            artifact_id=artifact.id,
        )
        revised_angle = next(
            item["content"]
            for item in revised.structured_content["sections"]
            if item["id"] == "recommended-angle"
        )
        original = await store.get_artifact(artifact.id)
        versions = await store.list_artifact_versions(revised.id)

        assert decision.action == "follow"
        assert first_branch.branch_key == f"connection:{first.id}"
        assert revised.id != artifact.id
        assert revised.id != first_branch.id
        assert revised.parent_artifact_id == artifact.id
        assert revised.branch_key == f"connection:{followed.id}"
        assert revised_angle == followed_insight.thesis
        assert f"K{followed.id}" in revised.content
        assert original.structured_content == artifact.structured_content
        assert [item["change_kind"] for item in versions] == ["connection_followed"]
        assert len(
            [
                item
                for item in await store.list_case_artifacts(case.id)
                if item.artifact_type == "script"
            ]
        ) == 3

        insight_script = await generate_case_artifact(
            store,
            case_id=case.id,
            artifact_type="script",
            constraints={"selected_insight_id": followed_insight.id},
            branch_key=f"insight:{followed_insight.id}",
            parent_artifact_id=artifact.id,
        )
        insight_angle = next(
            item["content"]
            for item in insight_script.structured_content["sections"]
            if item["id"] == "recommended-angle"
        )
        assert insight_script.branch_key == f"insight:{followed_insight.id}"
        assert insight_script.parent_artifact_id == artifact.id
        assert insight_angle == followed_insight.thesis
    finally:
        await store.close()
