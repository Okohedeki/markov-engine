"""Product proof through Markov's public API and real processing pipeline."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from markov_engine import connections, evidence, llm
from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_source_becomes_inspectable_research_without_invented_paths(monkeypatch):
    """Exercise the shipped engine, not a substituted processor or stored case."""
    monkeypatch.setattr(llm._settings, "llm_backend", "heuristic")
    monkeypatch.setattr(connections._settings, "llm_backend", "heuristic")
    monkeypatch.setattr(evidence._settings, "search_enabled", False)

    settings = Settings(
        LLM_BACKEND="heuristic",
        EMBED_BACKEND="hash",
        SEARCH_ENABLED=False,
        MARKOV_API_KEYS={"journey-key": "journey-owner"},
        MARKOV_OPENING_CREDITS=100,
    )
    source_text = (
        Path(__file__).parents[1] / "docs" / "markov-v2-architecture.md"
    ).read_text(encoding="utf-8")
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=settings)
    transport = httpx.ASGITransport(app=app)
    headers = {"X-Markov-Key": "journey-key"}

    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://markov.test"
        ) as client:
            submitted = await client.post(
                "/v2/jobs",
                headers=headers,
                json={
                    "job": "Catch me up",
                    "source": {"type": "text", "value": source_text},
                    "options": {"max_connections": 3},
                },
            )
            assert submitted.status_code == 202
            job_id = submitted.json()["job"]["id"]
            case_url = submitted.json()["links"]["case"]

            job = await client.get(f"/v2/jobs/{job_id}", headers=headers)
            assert job.json()["job"]["status"] == "completed"
            assert [item["artifact_type"] for item in job.json()["artifacts"]] == [
                "brief"
            ]

            response = await client.get(case_url, headers=headers)
            assert response.status_code == 200
            case = response.json()
            assert case["case"]["input_type"] == "text"
            assert case["case"]["status"] == "completed"

            seed = next(
                item
                for item in case["sources"]
                if item["case_source_role"] == "seed"
            )
            assert seed["source_type"] == "text"
            assert len(seed["segments"]) >= 8
            assert all(
                segment["character_start"] is not None
                and segment["character_end"] > segment["character_start"]
                for segment in seed["segments"]
            )
            assert all(
                re.sub(
                    r"\s+",
                    " ",
                    source_text[
                        segment["character_start"] : segment["character_end"]
                    ],
                ).strip()
                == segment["text"]
                for segment in seed["segments"]
            )

            segment_ids = {segment["id"] for segment in seed["segments"]}
            assert len(case["claims"]) >= 6
            assert all(
                claim["source_start_segment_id"] in segment_ids
                and claim["source_end_segment_id"] in segment_ids
                for claim in case["claims"]
            )
            assert case["research_gaps"]
            assert {
                claim["verification_status"] for claim in case["claims"][:5]
            } <= {"unverifiable", "opinion_or_inference"}
            assert all(not claim["evidence"] for claim in case["claims"])

            assert len(case["connections"]) == 3
            assert all(
                connection["validation_status"] == "rejected"
                and connection["evidence_level"] == "plausible_hypothesis"
                and not connection["evidence"]
                and "No independent evidence passage"
                in connection["rejection_reason"]
                for connection in case["connections"]
            )
            assert case["connection_paths"] == []
            assert case["insights"] == []

            brief = case["artifacts"][0]
            research = await client.post(
                f"/v2/artifacts/{brief['id']}/convert",
                headers=headers,
                json={"mode": "Explore where it leads"},
            )
            assert research.status_code == 200
            assert research.json()["artifact"]["artifact_type"] == "research_report"

            script = await client.post(
                f"/v2/artifacts/{brief['id']}/convert",
                headers=headers,
                json={"mode": "Turn it into a script"},
            )
            assert script.status_code == 200
            script_id = script.json()["artifact"]["id"]

            followed_connection = case["connections"][0]
            followed = await client.post(
                f"/v2/connections/{followed_connection['id']}/follow",
                headers=headers,
                json={"artifact_id": script_id},
            )
            assert followed.status_code == 422
            assert "Validated connection not found" in followed.json()["detail"]

            final_case = (await client.get(case_url, headers=headers)).json()
            assert {item["artifact_type"] for item in final_case["artifacts"]} == {
                "brief",
                "research_report",
                "script",
            }
            assert final_case["branch_decisions"] == []
    finally:
        await store.close()
