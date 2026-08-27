"""Targeted deepening and script-section versioning."""

from __future__ import annotations

import pytest

from markov_engine.renderers import render_artifact
from markov_engine.research import persist_rendered_artifact
from markov_engine.revisions import deepen_claim, revise_script_section
from markov_engine.store.sqlite import SqliteStore


async def _case_with_claim(store: SqliteStore):
    case = await store.create_research_case(
        owner_id="owner-1",
        title="Revision fixture",
        original_input="https://youtube.com/watch?v=revision",
        input_type="youtube",
        purpose="script",
        constraints={"target_minutes": 4},
    )
    source = await store.add_source(
        url=case.original_input,
        title="Revision fixture",
        source_type="youtube",
        content_text="The measurable result increased.",
        summary="",
    )
    await store.add_research_case_source(
        research_case_id=case.id, source_id=source.id, source_role="seed"
    )
    segments = await store.add_source_segments(
        source_id=source.id,
        segments=[
            {
                "text": "The measurable result increased.",
                "start_seconds": 10,
                "end_seconds": 15,
            }
        ],
    )
    claim = await store.add_claim(
        research_case_id=case.id,
        seed_source_id=source.id,
        claim_text="The measurable result increased.",
        claim_type="factual",
        importance=1,
        speaker_certainty="asserted_as_fact",
        source_start_segment_id=segments[0].id,
        source_end_segment_id=segments[0].id,
    )
    rendered = await render_artifact(store, case.id, "script")
    artifact = await persist_rendered_artifact(
        store, case=case, rendered=rendered, review_level="instant"
    )
    return case, claim, artifact


@pytest.mark.asyncio
async def test_script_section_revision_preserves_provenance_and_version():
    store = await SqliteStore.open(":memory:")
    try:
        _case, claim, artifact = await _case_with_claim(store)
        revised = await revise_script_section(
            store,
            artifact_id=artifact.id,
            section_id="narration",
            replacement=f"A tighter, qualified narration based on claim [C{claim.id}].",
            owner_id="owner-1",
        )
        versions = await store.list_artifact_versions(artifact.id)
        narration = next(
            section
            for section in revised.structured_content["sections"]
            if section["id"] == "narration"
        )
        assert narration["reviewer_or_user_revised"] is True
        assert narration["claim_ids"] == [claim.id]
        assert [item["change_kind"] for item in versions] == [
            "generated",
            "section_revised",
        ]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_deepen_claim_updates_only_claim_dependent_artifact_sections():
    store = await SqliteStore.open(":memory:")

    async def fake_research(store, *, case_id, claim, **kwargs):
        source = await store.add_source(
            url="https://example.gov/deeper",
            title="Stronger evidence",
            source_type="article",
            content_text="The measured value increased from 5 to 9.",
            summary="",
        )
        await store.update_source_provenance(
            source.id,
            source_role="official_data",
            source_quality="official_data",
            source_quality_rationale="Direct public dataset.",
        )
        await store.add_research_case_source(
            research_case_id=case_id,
            source_id=source.id,
            source_role="independent_evidence",
        )
        evidence = await store.add_evidence_passage(
            source_id=source.id,
            passage_text="The measured value increased from 5 to 9.",
            section_title="Table 1",
            source_quality="official_data",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=evidence.id,
            stance="supports",
            strength=0.9,
            rationale="Directly reports the increase.",
            model_confidence=0.9,
        )
        await store.update_claim_status(claim.id, "supported")
        return {"claim_id": claim.id, "status": "supported", "sources_added": 1}

    try:
        _case, claim, artifact = await _case_with_claim(store)
        before = artifact.structured_content["sections"]
        title_options_before = next(
            item["content"] for item in before if item["id"] == "title-options"
        )
        result = await deepen_claim(
            store,
            claim_id=claim.id,
            owner_id="owner-1",
            claim_researcher=fake_research,
        )
        updated = await store.get_artifact(artifact.id)
        assert updated is not None
        title_options_after = next(
            item["content"]
            for item in updated.structured_content["sections"]
            if item["id"] == "title-options"
        )
        assert result["updated_artifact_ids"] == [artifact.id]
        assert "https://example.gov/deeper" in updated.content
        assert title_options_after == title_options_before
        assert (await store.list_artifact_versions(artifact.id))[-1][
            "change_kind"
        ] == "claim_deepened"
    finally:
        await store.close()
