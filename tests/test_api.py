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
    app = create_app(store=store, settings=_settings(), process_case=_fake_process)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=True
        ) as client:
            redirected = await client.get("/app")
            assert "API key" in redirected.text
            signed_in = await client.post(
                "/app/login",
                content="api_key=customer-key",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert signed_in.status_code == 200
            assert "What did you find?" in signed_in.text
            assert "Catch me up" in signed_in.text
            assert "Explore where it leads" in signed_in.text
            assert "Turn it into a script" in signed_in.text
            assert "knowledge graph" not in signed_in.text.lower()
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
            assert "The research workspace between finding information and using it." not in landing.text
            assert "Open your workspace" not in landing.text
            assert 'href="/app/login"' in landing.text
            assert ">Sign in</a>" in landing.text
            assert "Why would" in landing.text
            assert ">Japanese investors</button>" in landing.text
            assert ">sell</button>" in landing.text
            assert ">U.S. Treasuries</button>" in landing.text
            assert landing.text.count('aria-controls="idea-route"') == 3
            assert "Hover or focus a phrase to follow the idea." in landing.text
            assert "The missing steps will unfold here." in landing.text
            assert "The stronger idea appears after you inspect two paths." not in landing.text
            assert "New angle" not in landing.text
            assert "Markov does not jump from a provocative sentence" not in landing.text
            assert "Save any video, article, PDF, podcast, post, or question." not in landing.text
            assert "You started with an article." in landing.text
            assert "Current thread" not in landing.text
            assert "Starting artifact" in landing.text
            assert "Japan’s pension pivot puts overseas capital in play" in landing.text
            assert "https://www.reuters.com/world/asia-pacific/" in landing.text
            assert "Open original ↗" in landing.text
            assert "data-story-source-packet" not in landing.text
            assert "Markov started a chain." in landing.text
            assert "Markov found the missing mechanism." not in landing.text
            assert "Mechanism artifact" in landing.text
            assert "data-story-mechanism-nodes" in landing.text
            assert "Markov absorbed the chains." in landing.text
            assert "Markov compared competing paths." not in landing.text
            assert "Comparison artifact" in landing.text
            assert "data-story-comparison-rows" in landing.text
            assert "Markov produced a stronger idea." in landing.text
            assert "Finished artifacts" in landing.text
            assert "data-story-angle" in landing.text
            assert "data-story-report" in landing.text
            assert "data-story-script" in landing.text
            assert "One living chain, from first source to original work." in landing.text
            assert landing.text.count("Made for original work") == 1
            assert "Do not start the next piece" not in landing.text
            assert "saved TikToks, YouTube videos, podcasts, posts, and articles" in landing.text
            assert "AEO pages, reports, and editorial briefs" in landing.text
            assert "One workspace for the whole trail" in landing.text
            assert "Capture and parse" in landing.text
            assert "Store and connect" in landing.text
            assert "Review and decide" in landing.text
            assert "Edit and create" in landing.text
            assert "The chain ends in work you can actually use." in landing.text
            assert "MARKOV BRIEF" in landing.text
            assert "MARKOV RESEARCH REPORT" in landing.text
            assert "MARKOV SCRIPT" in landing.text
            assert "5 COLLECTED SOURCES" in landing.text
            assert "A coordinated Treasury dump is not established" in landing.text
            assert "What would change the conclusion" in landing.text
            assert "READY TO RECORD" in landing.text
            assert "Open the full evidence-linked sample" in landing.text
            assert landing.text.index('id="artifact-proof-title"') < landing.text.index(
                'id="intake-title"'
            )
            assert "For people" in landing.text
            assert "For agents" in landing.text
            assert "It syncs into your web workspace" in landing.text
            assert "What do you want to understand—or make?" in landing.text
            assert landing.text.index('id="intake-title"') < landing.text.index(
                'class="post-intake-section"'
            )
            for source_story in ("article", "japan", "tiktok", "pdf", "podcast", "question"):
                assert f'data-source="{source_story}"' in landing.text
            assert landing.text.count("data-source=") == 6
            for source_label in ("Article", "YouTube", "TikTok", "PDF", "Podcast", "Question"):
                assert f">{source_label}</button>" in landing.text
            assert 'data-source="nuclear"' not in landing.text
            assert 'data-source="glp1"' not in landing.text
            assert "Skip to content" in landing.text
            assert landing.text.count("<h1") == 1
            assert "dashboard screenshot" not in landing.text.lower()
            assert "feature card" not in landing.text.lower()
            assert "customer logos" not in landing.text.lower()
            assert "free trial" not in landing.text.lower()
            assert "run markov locally" not in landing.text.lower()
            assert "open source" not in landing.text.lower()
            assert "github" not in landing.text.lower()

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
            assert "CASE MKV" not in sample.text

            css = await client.get("/static/markov.css")
            assert css.status_code == 200
            assert "prefers-reduced-motion" in css.text
            assert "@media (hover: none), (pointer: coarse)" in css.text
            assert "#f5f4ef" in css.text
            assert "#e9502c" in css.text
            assert ":focus-visible" in css.text

            pdf_preview = await client.get("/static/japan-nber-cover.png")
            assert pdf_preview.status_code == 200
            assert pdf_preview.headers["content-type"] == "image/png"

            javascript = await client.get("/static/markov.js")
            assert javascript.status_code == 200
            assert "window.setTimeout(() => renderRoute(trigger.dataset.route), 120)" in javascript.text
            assert "event.key !== 'Escape'" in javascript.text
            assert "aria-expanded" in javascript.text
            assert "markov.pendingSource" in javascript.text
            assert "You started with a YouTube video." in javascript.text
            assert "You started with a TikTok." in javascript.text
            assert "You started with an article." in javascript.text
            assert "You started with a paper." in javascript.text
            assert "You started with a podcast." in javascript.text
            assert "You started with a question." in javascript.text
            assert "https://www.tiktok.com/player/v1/7664551582888971542" in javascript.text
            assert "static/japan-nber-cover.png" in javascript.text
            assert "Japan’s pension pivot puts overseas capital in play" in javascript.text
            assert "delete examples.nuclear" in javascript.text
            assert "delete examples.glp1" in javascript.text
            assert "storyFields.start.textContent = example.startCopy" in javascript.text
            assert "renderSourceArtifact(example.media)" in javascript.text
            assert "renderSourcePacket" not in javascript.text
            assert "renderMechanismArtifact(resolved)" in javascript.text
            assert "renderComparisonArtifact(resolved)" in javascript.text
            assert "storyFields.report.textContent = resolved.comparison" in javascript.text
            assert "storyFields.sources.replaceChildren()" not in javascript.text
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
            assert "Your brief is ready." in job.text
            artifact_match = re.search(r'href="(/app/artifacts/\d+)"', job.text)
            assert artifact_match is not None

            artifact = await client.get(artifact_match.group(1))
            assert artifact.status_code == 200
            assert "Continue this case" in artifact.text
            assert "Connections" in artifact.text
            assert "Claim ledger" in artifact.text
            assert "Export JSON" in artifact.text
            assert "&lt;script&gt;" in artifact.text
            assert "<script>alert('unsafe')</script>" not in artifact.text
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
            assert "Export Markdown" in artifact.text
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
    assert 'href="/markov-engine/sample/"' in landing
    assert 'href="/markov-engine/developers/"' in landing
    assert 'href="/app/login"' not in landing
    assert "Product demo" in landing
    assert "Run locally" not in landing
    assert "open-source" not in landing.lower()
    assert "github.com" not in landing.lower()
    assert 'data-idea-demo' in landing
    assert 'aria-controls="idea-route"' in landing
    assert 'data-landing-intake' in landing
    assert landing.count("<h1") == 1
    assert (root / "docs" / "developers" / "index.html").is_file()
    assert (root / "docs" / "pricing" / "index.html").is_file()
    assert (root / "docs" / "sample" / "index.html").is_file()
