"""Long-source claim extraction preserves locators and deduplicates overlap."""

from __future__ import annotations

import re

import pytest

from markov_engine import claims
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_claim_extraction_processes_all_chunks_and_merges_overlap(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        source = await store.add_source(
            url="fixture", title="Long fixture", source_type="youtube",
            content_text="long", summary="",
        )
        segments = await store.add_source_segments(
            source_id=source.id,
            segments=[
                {"text": f"Segment {index} states measurable result {index}. " + "detail " * 12}
                for index in range(8)
            ],
        )
        calls = []

        async def fake_complete(prompt, *, schema, model, max_tokens, task):
            assert task == "claim_extraction"
            segment_ids = [int(value) for value in re.findall(r"\[S(\d+)\]", prompt)]
            calls.append(segment_ids)
            return {
                "claims": [
                    {
                        "claim_text": f"Result {segment_id} was measured.",
                        "claim_type": "quantitative",
                        "importance": 0.8,
                        "speaker_certainty": "asserted_as_fact",
                        "source_segment_ids": [segment_id],
                    }
                    for segment_id in segment_ids
                ],
                "research_gaps": [
                    {
                        "gap_type": "missing_data",
                        "question": "Which dataset contains these measurements?",
                        "importance": 0.7,
                    }
                ],
            }, 0.01

        monkeypatch.setattr(claims, "complete_json", fake_complete)
        extracted, gaps, cost = await claims.extract_claims(
            segments, max_chars=300, overlap=1
        )

        assert len(calls) > 1
        assert {segment_id for call in calls for segment_id in call} == {
            segment.id for segment in segments
        }
        assert len(extracted) == len(segments)
        assert len(gaps) == 1
        assert cost == pytest.approx(0.01 * len(calls))
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_claim_extraction_rejects_invented_segment_ids(monkeypatch):
    store = await SqliteStore.open(":memory:")
    try:
        source = await store.add_source(
            url="fixture", title="Fixture", source_type="youtube",
            content_text="text", summary="",
        )
        segments = await store.add_source_segments(
            source_id=source.id, segments=[{"text": "A sufficiently long factual statement."}]
        )

        async def fake_complete(*args, **kwargs):
            return {
                "claims": [{
                    "claim_text": "This locator was invented by the model.",
                    "claim_type": "factual",
                    "importance": 1,
                    "speaker_certainty": "asserted_as_fact",
                    "source_segment_ids": [999999],
                }],
                "research_gaps": [],
            }, 0

        monkeypatch.setattr(claims, "complete_json", fake_complete)
        with pytest.raises(ValueError, match="no valid, located claims"):
            await claims.extract_claims(segments)
    finally:
        await store.close()
