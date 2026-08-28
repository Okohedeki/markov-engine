"""Evidence research inspects source content and links exact passages."""

from __future__ import annotations

import pytest

from markov_engine import evidence
from markov_engine.extract import ExtractedContent, ExtractedSegment
from markov_engine.store.sqlite import SqliteStore


def test_query_families_and_source_roles_are_explicit():
    families = evidence.query_families("The measured value was 42")
    assert {item["family"] for item in families} == {
        "original_source", "primary_evidence", "official_data",
        "quantitative_verification", "counterevidence", "limitations",
        "historical_context", "alternative_explanation",
    }
    assert evidence.classify_source("https://data.gov/report")[0] == "official_data"
    assert evidence.classify_source(
        "https://youtube.com/watch?v=x", source_type="youtube"
    )[0] == "commentary"


@pytest.mark.asyncio
async def test_research_uses_extracted_passage_not_search_snippet(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        case = await store.create_research_case(
            owner_id="owner", title="Fixture", original_input="seed",
            input_type="youtube", purpose="research",
        )
        seed = await store.add_source(
            url="seed", title="Seed", source_type="youtube",
            content_text="The measured value was 42.", summary="",
        )
        seed_segments = await store.add_source_segments(
            source_id=seed.id,
            segments=[{"text": "The measured value was 42.", "start_seconds": 3, "end_seconds": 7}],
        )
        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=seed.id,
            claim_text="The measured value was 42.",
            claim_type="quantitative",
            importance=1,
            speaker_certainty="asserted_as_fact",
            source_start_segment_id=seed_segments[0].id,
            source_end_segment_id=seed_segments[0].id,
        )

        async def fake_search(query, max_results=4):
            return [{
                "url": "https://data.gov/fixture",
                "title": "Official measurement",
                "snippet": "THIS SEARCH SNIPPET MUST NOT BECOME EVIDENCE",
            }]

        async def fake_extract(url, tmp_dir, whisper_model):
            return ExtractedContent(
                url=url,
                source_type="article",
                title="Official measurement",
                content_text="The official table reports a measured value of 42.",
                segments=[ExtractedSegment(
                    ordinal=0,
                    text="The official table reports a measured value of 42.",
                    section_title="Results",
                )],
            )

        async def fake_stance(prompt, *, schema, model, max_tokens):
            return {
                "stance": "supports",
                "strength": 0.95,
                "rationale": "The inspected results passage reports the same value.",
                "confidence": 0.9,
            }, 0.02

        monkeypatch.setattr(evidence, "complete_json", fake_stance)
        result = await evidence.research_claim(
            store,
            case_id=case.id,
            claim=claim,
            searcher=fake_search,
            extractor=fake_extract,
            max_sources=1,
        )

        links = await store.list_claim_evidence(claim.id)
        assert result["status"] == "supported"
        assert links[0].evidence.passage_text == (
            "The official table reports a measured value of 42."
        )
        assert "SEARCH SNIPPET" not in links[0].evidence.passage_text
        assert links[0].evidence.section_title == "Results"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_disabled_search_keeps_offline_claims_unverified(monkeypatch):
    store = await SqliteStore.open(":memory:")
    monkeypatch.setattr(evidence._settings, "search_enabled", False)
    try:
        case = await store.create_research_case(
            owner_id="owner", title="Offline fixture", original_input="seed",
            input_type="topic", purpose="brief",
        )
        seed = await store.add_source(
            url=None, title="Question", source_type="topic",
            content_text="Could this claim be true?", summary="",
        )
        segments = await store.add_source_segments(
            source_id=seed.id,
            segments=[{"text": "Could this claim be true?"}],
        )
        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=seed.id,
            claim_text="Could this claim be true",
            claim_type="inference",
            importance=1,
            speaker_certainty="research_question",
            source_start_segment_id=segments[0].id,
            source_end_segment_id=segments[0].id,
        )

        result = await evidence.research_claim(
            store, case_id=case.id, claim=claim
        )

        assert result["status"] == "opinion_or_inference"
        assert result["query_attempts"] == 0
        assert result["sources_added"] == 0
        assert await store.list_claim_evidence(claim.id) == []
    finally:
        await store.close()


def test_claim_status_preserves_conflict_and_uncertainty():
    assert evidence.status_from_stances(["supports"]) == "supported"
    assert evidence.status_from_stances(["supports", "qualifies"]) == "qualified"
    assert evidence.status_from_stances(["supports", "contradicts"]) == "disputed"
    assert evidence.status_from_stances([]) == "unverifiable"
