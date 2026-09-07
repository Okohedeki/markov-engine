"""Authenticated API and server-rendered delivery-surface tests."""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.exports import markdown_to_safe_html
from markov_engine.store.sqlite import SqliteStore


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_pro',
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
@pytest.mark.parametrize("route", ["/v1/jobs", "/v2/jobs"])
@pytest.mark.parametrize("fail_first", [False, True])
async def test_concurrent_customers_share_capacity_not_data(monkeypatch, route, fail_first):
    import markov_engine.api as api_module

    store = await SqliteStore.open(":memory:")
    settings = _settings()
    settings.default_entitlement_profile = "cloud_pro"
    settings.job_concurrency = 2
    settings.api_keys["third-key"] = "owner-3"
    two_started, third_submitted, release = (asyncio.Event() for _ in range(3))
    active = peak = 0
    original_submit = api_module.submit_job

    async def observed_submit(*args, **kwargs):
        result = await original_submit(*args, **kwargs)
        if kwargs["owner_id"] == "owner-3":
            third_submitted.set()
        return result

    async def held_process(store, *, case_id, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 2:
            two_started.set()
        try:
            await release.wait()
            case = await store.get_research_case(case_id)
            if fail_first and case.owner_id == "owner-1":
                raise RuntimeError("fixture provider failure")
            return await _fake_process(store, case_id=case_id, **kwargs)
        finally:
            active -= 1

    monkeypatch.setattr(api_module, "submit_job", observed_submit)
    app = create_app(store=store, settings=settings, process_case=held_process)
    requests = []
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for index, key in enumerate(["customer-key", "other-key", "third-key"]):
                source = {"type": "text", "value": f"Private input from owner-{index + 1}"}
                payload = {"mode": "brief", "inputs": [source]} if route == "/v1/jobs" else {
                    "job": "Catch me up", "source": source,
                }
                requests.append(asyncio.create_task(client.post(
                    route, json=payload,
                    headers={"X-Markov-Key": key, "Idempotency-Key": "shared-key"},
                )))
                if index == 1:
                    try:
                        await asyncio.wait_for(two_started.wait(), timeout=5)
                    except TimeoutError:
                        outcomes = [
                            repr(task.exception()) if task.exception() else task.result().text
                            for task in requests if task.done()
                        ]
                        pytest.fail(f"Both customers did not start: {outcomes}")
            await asyncio.wait_for(third_submitted.wait(), timeout=5)
            assert (await store.list_jobs(owner_id="owner-3"))[0].status == "queued"
            assert active == 2
            release.set()
            responses = await asyncio.wait_for(asyncio.gather(*requests), timeout=5)
            assert [response.status_code for response in responses] == [202, 202, 202]
            jobs = [response.json()["job"] for response in responses]
            assert len({job["id"] for job in jobs}) == 3
            assert peak == 2
            for index, job in enumerate(jobs, start=1):
                saved = await store.get_job(job["id"], owner_id=f"owner-{index}")
                failed = fail_first and index == 1
                assert saved.status == ("failed" if failed else "completed"), saved.error
                assert (await store.get_credit_account(f"owner-{index}")).balance == (
                    20 if failed else 18
                )
                denied = await client.get(
                    f"/v1/research-cases/{job['research_case_id']}",
                    headers={"X-Markov-Key": "other-key" if index == 1 else "customer-key"},
                )
                assert denied.status_code == 404
    finally:
        release.set()
        await asyncio.gather(*requests, return_exceptions=True)
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
            assert "Your stories" in signed_in.text
            assert "Find connected stories" in signed_in.text
            assert 'id="queue-title"' in signed_in.text
            assert 'name="focus"' in signed_in.text
            assert "nothing is posted automatically" in signed_in.text
            assert "Why would Japanese investors sell U.S. Treasuries?" in signed_in.text
            assert f'href="/app/artifacts/{artifact.id}"' in signed_in.text
            assert "knowledge graph" not in signed_in.text.lower()
            assert "owner-1" not in signed_in.text
            assert 'href="/app/signals"' in signed_in.text
            assert 'href="/app/series"' in signed_in.text
            assert 'href="/app/plans"' in signed_in.text
            assert 'name="q"' in signed_in.text

            for path, heading in (
                ("/app/signals", "Bring in a conversation"),
                ("/app/ideas", "Explore different angles"),
                ("/app/plans", "Drafts"),
                ("/app/published", "Take a finished draft to your channel"),
                ("/app/search?q=Japanese", "Find the topic or idea"),
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
            assert "Start with a link." in landing.text
            assert 'href="/app/login"' in landing.text
            assert 'href="#how-it-works"' in landing.text
            assert 'href="/demo/"' not in landing.text
            assert 'data-source-trail' in landing.text
            assert 'data-trail-tabs' in landing.text
            assert 'data-trail-idea="beer"' in landing.text
            assert 'data-trail-idea="chips"' in landing.text
            assert "Curated example, not a live Markov run" in landing.text
            assert "Sources travel with the idea" in landing.text
            assert 'data-source-film' in landing.text
            assert 'preload="none"' in landing.text
            assert 'source-to-story.vtt" default' in landing.text
            assert landing.text.count("<h1") == 1
            assert "Skip to content" in landing.text

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
            assert "Current job credit costs" in pricing.text
            assert "paid checkout and subscription prices are not available" in pricing.text

            developers = await client.get("/developers")
            assert developers.status_code == 200
            assert "Idempotency-Key" in developers.text
            assert "POST /v2/jobs" in developers.text
            assert "structured research and drafts" in developers.text.lower()

            sample = await client.get("/sample")
            assert sample.status_code == 200
            assert "What will you post next?" in sample.text
            assert 'data-idea-playground' in sample.text
            assert 'data-idea-editor' in sample.text
            assert "Your shortlist stays in this browser" in sample.text

            css = await client.get("/static/studio.css")
            assert css.status_code == 200
            assert "prefers-reduced-motion" in css.text
            assert "--accent" in css.text

            pdf_preview = await client.get("/static/japan-nber-cover.png")
            assert pdf_preview.status_code == 200
            assert pdf_preview.headers["content-type"] == "image/png"

            javascript = await client.get("/static/markov.js")
            assert javascript.status_code == 200
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
            assert "Your ideas are ready to explore." in job.text
            artifact_match = re.search(r'href="(/app/artifacts/\d+)"', job.text)
            assert artifact_match is not None

            artifact = await client.get(artifact_match.group(1))
            assert artifact.status_code == 200
            assert "Ideas to develop" in artifact.text
            assert ">Angles<" in artifact.text
            assert ">Draft<" in artifact.text
            assert "Sources and provenance" in artifact.text
            assert "Evidence margin" in artifact.text
            assert "Claims to inspect" in artifact.text
            assert "Saving creates a new version" in artifact.text
            assert 'data-output-composer' in artifact.text
            assert 'data-composer-context' in artifact.text
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
        assert "Ideas to develop" in response.text
        assert "What makes this angle interesting" in response.text
        assert "Mixed evidence" in response.text
        assert "Dig deeper" in response.text
        assert 'data-open-composer' in response.text
        assert "Sources and provenance" in response.text
        assert "The sources behind this topic" in response.text
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


def test_github_pages_export_is_static_and_project_relative(tmp_path, monkeypatch):
    from scripts import build_pages

    monkeypatch.setattr(build_pages, "PAGES", {
        name: tmp_path / path.relative_to(build_pages.OUTPUT)
        for name, path in build_pages.PAGES.items()
    })
    monkeypatch.setattr(build_pages, "OUTPUT", tmp_path)
    build_pages.build()
    landing = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="/markov-engine/static/studio.css"' in landing
    assert 'src="/markov-engine/static/markov.js"' in landing
    assert 'href="/markov-engine/#how-it-works"' in landing
    assert 'href="/markov-engine/developers/"' in landing
    assert 'href="/app/login"' not in landing
    assert "Start with a link." in landing
    assert "Try without an account" not in landing
    assert 'href="/markov-engine/demo/"' not in landing
    assert "data-source-trail" in landing
    assert "Run locally" in landing
    assert 'href="https://github.com/Okohedeki/markov-engine#local-setup"' in landing
    assert landing.count("<h1") == 1
    assert (tmp_path / "developers" / "index.html").is_file()
    assert (tmp_path / "pricing" / "index.html").is_file()
    assert (tmp_path / "sample" / "index.html").is_file()
    assert (tmp_path / "static" / "source-trail.js").is_file()
    pricing = (tmp_path / "pricing" / "index.html").read_text(encoding="utf-8")
    assert "No full talking-point generation or series creation" in pricing
    assert "Ask about Plus access" in pricing
    assert "Credits do not unlock paid features" in pricing
    assert "Explore the studio" not in pricing
    sample = (tmp_path / "sample" / "index.html").read_text(encoding="utf-8")
    assert "read local setup instructions" in sample


def test_legal_export_identifies_operator_and_paid_boundary(tmp_path, monkeypatch):
    from scripts import build_pages

    monkeypatch.setattr(build_pages, "PAGES", {
        name: tmp_path / path.relative_to(build_pages.OUTPUT)
        for name, path in build_pages.PAGES.items()
        if name in {"privacy.html", "terms.html", "copyright.html"}
    })
    monkeypatch.setattr(build_pages, "OUTPUT", tmp_path)
    build_pages.build()
    for name in ["privacy", "terms", "copyright"]:
        page = (tmp_path / name / "index.html").read_text(encoding="utf-8")
        assert "EyeQ enterprises" in page and "Phoenix, Arizona" in page
        assert 'href="mailto:okohedeki@gmail.com"' in page
        assert 'href="/markov-engine/privacy/"' in page
        assert 'href="/markov-engine/static/public-info.css"' in page
        assert page.count("<h1") == 1
    terms = (tmp_path / "terms" / "index.html").read_text(encoding="utf-8")
    assert "Generating full talking points and creating series in Story Mode require paid access" in terms
    assert "Subscription checkout is not available" in terms
