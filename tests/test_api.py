"""Authenticated API and server-rendered delivery-surface tests."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.exports import markdown_to_safe_html
from markov_engine.store.sqlite import SqliteStore


def _settings() -> Settings:
    return Settings(
        MARKOV_API_KEYS={"customer-key": "owner-1", "other-key": "owner-2"},
        MARKOV_INTERNAL_API_KEYS={"review-key": "reviewer-1"},
        MARKOV_WEB_SESSION_SECRET="fixture-session-secret",
        MARKOV_OPENING_CREDITS=20,
        MARKOV_PRODUCT_CREDIT_COSTS={
            "brief_instant": 2,
            "brief_verified": 4,
            "research_instant": 3,
            "research_verified": 5,
            "script_instant": 3,
            "script_verified": 6,
        },
    )


async def _fake_process(
    store, *, case_id, review_level, modes, stage_handler, **kwargs
):
    await stage_handler("extracting_sources", {})
    await stage_handler("building_artifact", {"artifact_type": modes[0]})
    artifact_type = "research_report" if modes[0] == "research" else modes[0]
    artifact = await store.add_case_artifact(
        research_case_id=case_id,
        artifact_type=artifact_type,
        review_level=review_level,
        status="awaiting_review" if review_level == "verified" else "completed",
        title=f"Fixture {artifact_type}",
        content="# Fixture\n\n<script>alert('unsafe')</script>",
        structured_content={
            "artifact_type": artifact_type,
            "sections": [
                {
                    "id": "narration" if artifact_type == "script" else "bottom-line",
                    "title": "Narration" if artifact_type == "script" else "Bottom line",
                    "content": "Fixture content.",
                    "claim_ids": [],
                    "evidence_ids": [],
                }
            ],
            "citations": [],
        },
        word_count=3,
        model_used="fixture",
        generation_cost=0,
        source_ids=[],
    )
    if review_level == "verified":
        await store.create_review_job(artifact.id)
    return [artifact]


@pytest.mark.asyncio
async def test_api_job_idempotency_auth_status_and_safe_export():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            unauthenticated = await client.get("/v1/jobs")
            assert unauthenticated.status_code == 401
            headers = {
                "X-Markov-Key": "customer-key",
                "Idempotency-Key": "fixture-request",
            }
            payload = {
                "mode": "brief",
                "review_level": "instant",
                "inputs": [
                    {"type": "url", "value": "https://youtube.com/watch?v=fixture"}
                ],
                "constraints": {"focus": "economic claims"},
            }
            created = await client.post("/v1/jobs", headers=headers, json=payload)
            repeated = await client.post("/v1/jobs", headers=headers, json=payload)
            assert created.status_code == 202
            assert repeated.status_code == 200
            assert repeated.json()["created"] is False
            job_id = created.json()["job"]["id"]

            status = await client.get(
                f"/v1/jobs/{job_id}", headers={"X-Markov-Key": "customer-key"}
            )
            assert status.json()["job"]["status"] == "completed"
            artifact = status.json()["artifacts"][0]
            case_id = status.json()["job"]["research_case_id"]
            denied = await client.get(
                f"/v1/research-cases/{case_id}",
                headers={"X-Markov-Key": "other-key"},
            )
            assert denied.status_code == 404

            exported = await client.get(
                f"/v1/artifacts/{artifact['id']}/export?format=html",
                headers={"X-Markov-Key": "customer-key"},
            )
            assert exported.status_code == 200
            assert "&lt;script&gt;" in exported.text
            assert "<script>" not in exported.text
            account = await client.get(
                "/v1/account", headers={"X-Markov-Key": "customer-key"}
            )
            assert account.json()["account"]["balance"] == 18
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_v2_job_and_graph_resources_use_customer_language():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/v2/jobs",
                headers={"X-Markov-Key": "customer-key"},
                json={
                    "job": "Explore where it leads",
                    "source": {
                        "type": "url",
                        "value": "https://youtube.com/watch?v=v2-api",
                    },
                    "options": {"max_connections": 3},
                },
            )
            assert created.status_code == 202
            body = created.json()
            assert body["job"]["mode"] == "research"
            assert body["links"]["case"].startswith("/v2/cases/")

            case = await client.get(
                body["links"]["case"],
                headers={"X-Markov-Key": "customer-key"},
            )
            assert case.status_code == 200
            assert {
                "connections",
                "connection_paths",
                "insights",
                "branch_decisions",
            } <= set(case.json())
            entitlements = await client.get(
                "/v2/entitlements",
                headers={"X-Markov-Key": "customer-key"},
            )
            assert entitlements.json()["entitlements"]["citations"] is True
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_v2_api_access_is_an_entitlement():
    store = await SqliteStore.open(":memory:")
    settings = _settings()
    settings.owner_entitlement_profiles = {"owner-1": "cloud_free"}
    app = create_app(store=store, settings=settings, process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/v2/entitlements",
                headers={"X-Markov-Key": "customer-key"},
            )
            assert response.status_code == 403
            assert "api access" in response.json()["detail"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_verified_job_enters_internal_review_and_finalizes():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/v1/jobs",
                headers={"X-Markov-Key": "customer-key"},
                json={
                    "mode": "script",
                    "review_level": "verified",
                    "inputs": [{"type": "text", "value": "What evidence exists?"}],
                    "constraints": {"target_minutes": 8},
                },
            )
            assert created.status_code == 202
            queue = await client.get(
                "/internal/reviews", headers={"X-Markov-Key": "review-key"}
            )
            assert queue.status_code == 200
            review_id = queue.json()["reviews"][0]["id"]
            detail = await client.get(
                f"/internal/reviews/{review_id}",
                headers={"X-Markov-Key": "review-key"},
            )
            assert detail.status_code == 200
            finalized = await client.post(
                f"/internal/reviews/{review_id}/finalize",
                headers={"X-Markov-Key": "review-key"},
                json={"review_minutes": 7.5},
            )
            assert finalized.json()["review"]["status"] == "completed"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_web_login_and_focused_intake_page():
    store = await SqliteStore.open(":memory:")
    research_case = await store.create_research_case(
        owner_id="owner-1",
        title="Why would Japanese investors sell U.S. Treasuries?",
        original_input="https://www.youtube.com/watch?v=nmdujC0MUKA",
        input_type="url",
        purpose="research",
        status="completed",
    )
    artifact = await store.add_case_artifact(
        research_case_id=research_case.id,
        artifact_type="research_report",
        review_level="instant",
        status="completed",
        title="Japan capital flows",
        content="# Japan capital flows",
        structured_content={"artifact_type": "research_report", "sections": []},
        word_count=3,
        model_used="fixture",
        generation_cost=0,
        source_ids=[],
    )
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as client:
            redirected = await client.get("/app")
            assert "Workspace access key" in redirected.text
            assert "This build uses an access key" in redirected.text
            assert "Email and social sign-in are not enabled" in redirected.text
            signed_in = await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert signed_in.status_code == 200
            assert "Pick up the thread" in signed_in.text
            assert "Add a source or question" in signed_in.text
            assert "Needs your attention" in signed_in.text
            assert "No decision is waiting" in signed_in.text
            assert "Why would Japanese investors sell U.S. Treasuries?" in signed_in.text
            assert f'href="/app/artifacts/{artifact.id}"' in signed_in.text
            assert "knowledge graph" not in signed_in.text.lower()
            assert "owner-1" not in signed_in.text
            assert 'href="/app/signals"' in signed_in.text
            assert 'href="/app/ideas"' in signed_in.text
            assert 'href="/app/plans"' in signed_in.text
            assert 'href="/app/search"' in signed_in.text

            for path, heading in (
                ("/app/signals", "Sources, notes, and questions that can begin"),
                ("/app/ideas", "Research trails you can inspect"),
                ("/app/plans", "Briefs, reports, and factual scripts"),
                ("/app/published", "Reconnect live work to the Chain"),
                ("/app/search?q=Japanese", "Search sources, Chains, open questions"),
            ):
                page = await client.get(path)
                assert page.status_code == 200
                assert heading in page.text

            for old_path, new_path in (
                ("/app/inbox", "/app/signals"),
                ("/app/chains", "/app/ideas"),
                ("/app/outputs", "/app/plans"),
            ):
                legacy = await client.get(old_path, follow_redirects=False)
                assert legacy.status_code == 307
                assert legacy.headers["location"] == new_path
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_public_site_demonstrates_markov_before_asking_for_an_input():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            landing = await client.get("/")
            assert landing.status_code == 200
            assert "A source is where" in landing.text
            assert "Give Markov a video, article, paper, podcast, post, or question" in landing.text
            assert "The useful part is often what the source leaves out" in landing.text
            assert "A question can lead somewhere. Or just make more noise." in landing.text
            assert "The research changes shape" in landing.text
            assert landing.text.count("Open the workspace") == 2
            assert "Research-led creators, analysts, strategists, and consultants" in landing.text
            assert "High-volume filler, unconstrained fiction, or passive read-later archives" in landing.text
            assert "The source trail is part of the product" in landing.text
            assert "Demand can weaken before holdings are sold" in landing.text
            assert "Compare the mechanism, the evidence, and the weak point" in landing.text
            assert landing.text.count("data-source-choice=") == 5
            assert landing.text.count("data-route-choice=") == 3
            assert landing.text.count("data-output-choice=") == 3
            for stage in ("Starting source", "Separate the claim", "Expose the skipped step", "Follow the connection"):
                assert stage in landing.text
            assert "Japan’s pension pivot puts overseas capital in play" in landing.text
            assert "buyer who never arrives" in landing.text
            assert "High information gain" in landing.text
            assert "A slower buyer can change financing conditions" in landing.text
            assert "The evidence stays attached" in landing.text
            assert "Markov does not replace the human decision to publish" in landing.text
            assert "Skip to content" in landing.text
            assert landing.text.count("<h1") == 1
            for disallowed in ("ai-powered", "open source", "github", "free trial", "customer logos"):
                assert disallowed not in landing.text.lower()

            narrative = await client.get("/story")
            assert narrative.status_code == 307
            assert narrative.headers["location"] == "/"

            narrative_alias = await client.get("/landing-v2", follow_redirects=False)
            assert narrative_alias.status_code == 307
            assert narrative_alias.headers["location"] == "/"

            pricing = await client.get("/pricing")
            assert pricing.status_code == 200
            assert "Hosted workspace pricing" in pricing.text
            assert "2 credits" in pricing.text
            assert "Job credits from the live catalog" in pricing.text

            developers = await client.get("/developers")
            assert developers.status_code == 200
            assert "Idempotency-Key" in developers.text
            assert "POST /v2/jobs" in developers.text
            assert "typed connections" in developers.text.lower()

            sample = await client.get("/sample")
            assert sample.status_code == 200
            assert "One Japan source, followed all the way through" in sample.text
            assert "The missing mechanism" in sample.text
            assert "U.S. Treasuries" in sample.text
            assert "Source packet" in sample.text
            assert "Japan’s pension pivot" in sample.text
            assert "child-free creator" not in sample.text
            assert "CASE MKV" not in sample.text

            css = await client.get("/static/markov.css")
            assert css.status_code == 200
            assert "prefers-reduced-motion" in css.text
            assert "--fog" in css.text
            assert "--cobalt" in css.text
            assert "--ember" in css.text
            assert ".mk-thread-story" in css.text
            assert ".mk-app-nav" in css.text

            pdf_preview = await client.get("/static/japan-nber-cover.png")
            assert pdf_preview.status_code == 200
            assert pdf_preview.headers["content-type"] == "image/png"

            javascript = await client.get("/static/markov.js")
            assert javascript.status_code == 200
            assert "data-source-choice" in javascript.text
            assert "data-route-choice" in javascript.text
            assert "data-output-choice" in javascript.text
            assert "data-case-view-tab" in javascript.text
            assert "ArrowLeft" in javascript.text
            assert "aria-expanded" in javascript.text
            assert 'event.key === "Escape"' in javascript.text
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_job_and_artifact_reader_form_one_flow():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as client:
            await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            job = await client.post(
                "/app/jobs",
                content=(
                    "mode=brief&review_level=instant&"
                    "value=What+evidence+holds+up%3F&focus=priority+claims"
                ),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert job.status_code == 200
            assert "Your next decision is ready." in job.text
            artifact_match = re.search(r'href="(/app/artifacts/\d+)"', job.text)
            assert artifact_match is not None

            artifact = await client.get(artifact_match.group(1))
            assert artifact.status_code == 200
            assert "Routes worth inspecting" in artifact.text
            assert ">Explore<" in artifact.text
            assert ">Output<" in artifact.text
            assert "Sources and provenance" in artifact.text
            assert "Evidence margin" in artifact.text
            assert "Claims to inspect" in artifact.text
            assert "Saving creates a new version" in artifact.text
            assert "Shape an output" in artifact.text
            assert "Give this route a job" in artifact.text
            assert "Export JSON" in artifact.text
            assert "<script>alert('unsafe')</script>" not in artifact.text

            artifact_id = int(artifact_match.group(1).rsplit("/", 1)[-1])
            edited = await client.post(
                f"/app/artifacts/{artifact_id}/edit",
                content="content=%23+Revised+output%0A%0AA+saved+manual+revision.&action=save",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert edited.status_code == 200
            assert "A saved manual revision." in edited.text
            saved_artifact = await store.get_artifact(artifact_id, owner_id="owner-1")
            assert saved_artifact is not None
            assert saved_artifact.status == "draft"
            assert saved_artifact.content == "# Revised output\n\nA saved manual revision."
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_case_workspace_exposes_topics_gaps_and_supplemental_sources():
    store = await SqliteStore.open(":memory:")
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        case = await store.create_research_case(
            owner_id="owner-1",
            title="A starting video with more than one story",
            original_input="https://youtube.com/watch?v=branches",
            input_type="youtube",
            purpose="brief",
        )
        seed = await store.add_source(
            url=case.original_input,
            title="The original interview",
            source_type="youtube",
            content_text="A located claim.",
            summary="",
        )
        await store.add_research_case_source(
            research_case_id=case.id, source_id=seed.id, source_role="seed"
        )
        supplemental = await store.add_source(
            url="https://example.com/news/context",
            title="Supplemental reporting that changes the question",
            source_type="article",
            content_text="Additional context.",
            summary="",
        )
        await store.update_source_provenance(
            supplemental.id,
            source_role="independent_evidence",
            source_quality="analysis",
            source_quality_rationale="A reported analysis with additional context.",
            publisher="Example News",
        )
        await store.add_research_case_source(
            research_case_id=case.id,
            source_id=supplemental.id,
            source_role="independent_evidence",
        )
        claim = await store.add_claim(
            research_case_id=case.id,
            seed_source_id=seed.id,
            claim_text="The original claim depends on an omitted mechanism.",
            claim_type="causal",
            importance=0.95,
            speaker_certainty="asserted_as_fact",
            source_start_segment_id=None,
            source_end_segment_id=None,
            verification_status="partially_supported",
        )
        passage = await store.add_evidence_passage(
            source_id=supplemental.id,
            passage_text="The additional reporting identifies the omitted mechanism.",
            section_title="Analysis",
            source_quality="analysis",
        )
        await store.link_claim_evidence(
            claim_id=claim.id,
            evidence_passage_id=passage.id,
            stance="partially_supports",
            strength=0.8,
            rationale="It establishes one step but not the entire causal path.",
            model_confidence=0.85,
        )
        topic = await store.add_research_topic(
            research_case_id=case.id,
            title="The mechanism the interview skipped",
            focus="Find the intermediary and test the competing explanation.",
            importance=0.9,
            claim_ids=[claim.id],
        )
        await store.update_claim_plan(
            claim.id,
            canonical_claim_text=claim.claim_text,
            research_topic_id=topic.id,
            research_priority=0.95,
            disposition="core",
        )
        await store.add_research_gap(
            research_case_id=case.id,
            claim_id=claim.id,
            gap_type="missing_mechanism",
            question="Which intermediary turns the premise into the claimed outcome?",
            importance=0.9,
        )
        artifact = await store.add_case_artifact(
            research_case_id=case.id,
            artifact_type="brief",
            review_level="instant",
            status="completed",
            title="Fixture branch brief",
            content="# Fixture branch brief\n\nThe output remains inspectable.",
            structured_content={"sections": []},
            word_count=8,
            model_used="fixture",
            generation_cost=0.0,
            source_ids=[seed.id, supplemental.id],
        )

        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as client:
            await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = await client.get(f"/app/artifacts/{artifact.id}")

        assert response.status_code == 200
        assert topic.title in response.text
        assert "Which intermediary turns the premise" in response.text
        assert "Supplemental reporting that changes the question" in response.text
        assert f'data-topic-id="{topic.id}"' in response.text
        assert "Routes worth inspecting" in response.text
        assert "Why this route exists" in response.text
        assert "Mixed evidence" in response.text
        assert "Research this route" in response.text
        assert "Shape an output" in response.text
        assert "Sources and provenance" in response.text
        assert "Everything Markov analyzed for this Chain" in response.text
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_workspace_only_shows_and_serves_entitled_exports():
    store = await SqliteStore.open(":memory:")
    settings = _settings()
    settings.owner_entitlement_profiles = {"owner-1": "cloud_free"}
    app = create_app(store=store, settings=settings, process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as client:
            await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            job = await client.post(
                "/app/jobs",
                content="mode=brief&review_level=instant&value=Test",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            artifact_match = re.search(r'href="(/app/artifacts/\d+)"', job.text)
            assert artifact_match is not None
            artifact_path = artifact_match.group(1)
            artifact = await client.get(artifact_path)
            assert "Export MD" in artifact.text
            assert "Export JSON" in artifact.text
            assert "Export HTML" not in artifact.text

            blocked = await client.get(f"{artifact_path}/export?format=html")
            assert blocked.status_code == 200
            assert "Export is not available" in blocked.text
            assert "cloud_free profile" in blocked.text

            api_blocked = await client.get(
                f"/v1/artifacts/{artifact_path.rsplit('/', 1)[-1]}/export?format=html",
                headers={"X-Markov-Key": "customer-key"},
            )
            assert api_blocked.status_code == 403
            assert "cloud_free profile" in api_blocked.json()["detail"]
    finally:
        await store.close()


def test_html_export_escapes_source_markup():
    rendered = markdown_to_safe_html("# Test\n\n<img src=x onerror=alert(1)>")
    assert "&lt;img" in rendered
    assert "<img" not in rendered


def test_github_pages_export_is_static_and_project_relative():
    root = Path(__file__).resolve().parents[1]
    landing = (root / "docs" / "index.html").read_text(encoding="utf-8")
    assert 'href="/markov-engine/static/markov.css"' in landing
    assert 'src="/markov-engine/static/markov.js"' in landing
    assert 'href="/markov-engine/sample/"' in landing
    assert 'href="/markov-engine/developers/"' in landing
    assert 'href="/app/login"' not in landing
    assert "A source is where" in landing
    assert "The useful part is often what the source leaves out" in landing
    assert landing.count("Open the workspace") == 2
    assert landing.count("data-output-choice=") == 3
    assert "Run locally" not in landing
    assert "open-source" not in landing.lower()
    assert "github.com" not in landing.lower()
    assert landing.count("<h1") == 1
    assert (root / "docs" / "developers" / "index.html").is_file()
    assert (root / "docs" / "pricing" / "index.html").is_file()
    assert (root / "docs" / "sample" / "index.html").is_file()
