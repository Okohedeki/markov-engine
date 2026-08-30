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
            assert "QA access" in redirected.text
            assert "Production email and Google sign-in are coming next" in redirected.text
            signed_in = await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert signed_in.status_code == 200
            assert "Find what should be published next" in signed_in.text
            assert "Add a signal" in signed_in.text
            assert "New opportunities for your audience" in signed_in.text
            assert "Information gain" in signed_in.text
            assert "Audience relevance" in signed_in.text
            assert "Why would Japanese investors sell U.S. Treasuries?" in signed_in.text
            assert f'href="/app/artifacts/{artifact.id}"' in signed_in.text
            assert "youtube.com" in signed_in.text
            assert "knowledge graph" not in signed_in.text.lower()
            assert "owner-1" not in signed_in.text
            assert 'href="/app/signals"' in signed_in.text
            assert 'href="/app/ideas"' in signed_in.text
            assert 'href="/app/plans"' in signed_in.text
            assert 'href="/app/published"' in signed_in.text
            assert 'href="/app/search"' in signed_in.text

            for path, heading in (
                ("/app/signals", "Raw material that may change what your audience needs next"),
                ("/app/ideas", "Opportunities Markov can explain"),
                ("/app/plans", "Development briefs and channel treatments"),
                ("/app/published", "Connect finished work to the idea that produced it"),
                ("/app/search?q=Japanese", "Search signals, ideas, audience questions"),
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
            assert "Find what should be published next." in landing.text
            assert "current search results, AI answers, competitor coverage" in landing.text
            assert "You write the final piece" in landing.text
            assert landing.text.count("Find my next idea") == 2
            assert "Lean company content teams" in landing.text
            assert "Research-led creators" in landing.text
            assert "Editorial studios and agencies" in landing.text
            assert "What everyone already says" in landing.text
            assert "What has not been connected" in landing.text
            assert "Competing research directions" in landing.text
            assert landing.text.count("data-explorer-tab=") == 4
            assert landing.text.count("data-story-tab=") == 3
            assert landing.text.count("data-direction=") == 3
            for stage in ("01 / Signal", "02 / Existing answers", "03 / Missing connection", "04 / Idea opportunity"):
                assert stage in landing.text
            assert "Japan’s pension pivot puts overseas capital in play" in landing.text
            assert "https://www.reuters.com/world/asia-pacific/" in landing.text
            assert "Japan need not dump Treasuries" in landing.text
            assert "Information gain" in landing.text
            assert "Audience relevance" in landing.text
            assert "A campaign is not the same post cut five ways" in landing.text
            assert landing.text.count("data-campaign-tab=") == 4
            assert "Markov plans. You publish." in landing.text
            assert "Give future answers something worth including" in landing.text
            assert "Not a read-later app, fact checker, or one-click AI writer" in landing.text
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
            assert "Brief Instant" in pricing.text
            assert "2 credits" in pricing.text
            assert "live product catalog" in pricing.text

            developers = await client.get("/developers")
            assert developers.status_code == 200
            assert "Idempotency-Key" in developers.text
            assert "POST /v2/jobs" in developers.text
            assert "typed connections" in developers.text

            sample = await client.get("/sample")
            assert sample.status_code == 200
            assert "From a Japan source packet" in sample.text
            assert "Resulting insight" in sample.text
            assert "U.S. Treasuries" in sample.text
            assert "published sources" in sample.text
            assert "Japan’s pension pivot" in sample.text
            assert "What about Japan?" in sample.text
            assert "The Wolf Of All Streets" in sample.text
            assert "7677675462264409357" in sample.text
            assert "child-free creator" not in sample.text
            assert "CASE MKV" not in sample.text

            css = await client.get("/static/markov-v3.css")
            assert css.status_code == 200
            assert "prefers-reduced-motion" in css.text
            assert "--v3-paper" in css.text
            assert "--v3-accent" in css.text
            assert "--v3-connection" in css.text
            assert "--v3-audience" in css.text
            assert ".v5-explorer" in css.text
            assert ".v5-story-stage" in css.text
            assert ".v3-app-nav" in css.text

            pdf_preview = await client.get("/static/japan-nber-cover.png")
            assert pdf_preview.status_code == 200
            assert pdf_preview.headers["content-type"] == "image/png"

            javascript = await client.get("/static/markov-v3.js")
            assert javascript.status_code == 200
            assert "data-explorer-tab" in javascript.text
            assert "data-story-tab" in javascript.text
            assert "data-direction-title" in javascript.text
            assert "data-campaign-tab" in javascript.text
            assert "ArrowLeft" in javascript.text
            assert "aria-expanded" in javascript.text
            assert "event.key === 'Escape'" in javascript.text
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
            assert "Your idea landscape is ready." in job.text
            artifact_match = re.search(r'href="(/app/artifacts/\d+)"', job.text)
            assert artifact_match is not None

            artifact = await client.get(artifact_match.group(1))
            assert artifact.status_code == 200
            assert "Existing landscape" in artifact.text
            assert "Idea opportunities" in artifact.text
            assert "Development brief" in artifact.text
            assert "Distribution plan" in artifact.text
            assert "Sources and provenance" in artifact.text
            assert "Review margin" in artifact.text
            assert "Claims to check" in artifact.text
            assert "Editable creative scaffolding" in artifact.text
            assert "Turn the direction into creative scaffolding" in artifact.text
            assert "not finished posts or scripts" in artifact.text
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
        assert "Idea opportunities" in response.text
        assert "Proposed thesis" in response.text
        assert "Mixed evidence" in response.text
        assert "Investigate claim" in response.text
        assert "Develop this idea" in response.text
        assert "Sources and provenance" in response.text
        assert "Everything Markov analyzed for this idea" in response.text
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
    assert 'href="/markov-engine/static/markov-v3.css"' in landing
    assert 'src="/markov-engine/static/markov-v3.js"' in landing
    assert 'href="/markov-engine/sample/"' in landing
    assert 'href="/markov-engine/developers/"' in landing
    assert 'href="/app/login"' not in landing
    assert "Product demo" in landing
    assert "Find what should be published next." in landing
    assert landing.count("Find my next idea") == 2
    assert landing.count("data-campaign-tab=") == 4
    assert "Run locally" not in landing
    assert "open-source" not in landing.lower()
    assert "github.com" not in landing.lower()
    assert landing.count("<h1") == 1
    assert (root / "docs" / "developers" / "index.html").is_file()
    assert (root / "docs" / "pricing" / "index.html").is_file()
    assert (root / "docs" / "sample" / "index.html").is_file()
