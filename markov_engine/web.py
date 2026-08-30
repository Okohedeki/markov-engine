"""Server-rendered public site, customer workspace, and reviewer desk."""

from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from markov_engine.billing import public_catalog
from markov_engine.branching import (
    follow_connection_into_script,
    record_connection_decision,
)
from markov_engine.config import Settings
from markov_engine.entitlements import resolve_entitlements
from markov_engine.exports import export_artifact
from markov_engine.jobs import run_job, submit_job
from markov_engine.research import convert_case_artifact
from markov_engine.reviews import finalize_review, record_review_decision
from markov_engine.revisions import deepen_claim, revise_script_section

_TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates")
)


def _humanize(value: object) -> str:
    return str(value or "").replace("_", " ").strip().title()


def _number(value: object) -> str:
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _credits(value: object) -> str:
    amount = _number(value)
    return f"{amount} credit" if amount == "1" else f"{amount} credits"


def _badge_class(value: object) -> str:
    status = str(value or "").lower()
    if status in {"failed", "rejected", "contradicted", "disputed"}:
        return "badge-danger"
    if status in {"qualified", "awaiting_review", "pending", "queued"}:
        return "badge-warning"
    if status in {"completed", "supported", "accepted", "delivered"}:
        return ""
    return "badge-neutral"


def _locator(evidence: object) -> str:
    start = getattr(evidence, "start_seconds", None)
    if start is not None:
        total = max(0, int(start))
        end = getattr(evidence, "end_seconds", None)
        first = f"{total // 60}:{total % 60:02d}"
        if end is None:
            return first
        last = max(0, int(end))
        return f"{first}–{last // 60}:{last % 60:02d}"
    page = getattr(evidence, "page_number", None)
    if page is not None:
        return f"p. {page}"
    return getattr(evidence, "section_title", None) or "Passage"


_TEMPLATES.env.filters.update(
    humanize=_humanize,
    number=_number,
    credits=_credits,
    badge_class=_badge_class,
    locator=_locator,
)

_PUBLIC_CONTEXT = {
    "site_base": "",
    "workspace_url": "/app/login",
    "workspace_label": "Sign in",
    "api_docs_url": "/docs",
    "repository_url": "https://github.com/Okohedeki/markov-engine",
    "static_preview": False,
}


def _render(request: Request, template: str, **context):
    return _TEMPLATES.TemplateResponse(
        request=request,
        name=template,
        context={"request": request, **_PUBLIC_CONTEXT, **context},
    )


def _safe_source(source: dict) -> dict:
    item = dict(source)
    parsed = urlparse(item.get("url") or "")
    item["safe_url"] = item.get("url") if parsed.scheme in {"http", "https"} else None
    return item


async def _form(request: Request) -> dict[str, str]:
    raw = (await request.body()).decode("utf-8", errors="replace")
    return {key: values[-1] for key, values in parse_qs(raw).items()}


def _signed(identity: str, secret: str) -> str:
    encoded = base64.urlsafe_b64encode(identity.encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _unsigned(value: str | None, secret: str) -> str | None:
    if not value or "." not in value:
        return None
    encoded, signature = value.rsplit(".", 1)
    expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def _job_language(job) -> tuple[str, str]:
    if job.status == "completed":
        result_name = {
            "brief": "brief",
            "research": "exploration",
            "script": "script",
        }.get(job.mode, _humanize(job.mode).lower())
        return (
            f"Your {result_name} is ready.",
            "The artifact, connections, and source trail are ready to inspect.",
        )
    if job.status == "awaiting_review":
        return (
            "A reviewer is checking the evidence.",
            "The structured case is complete. Delivery waits for the Verified review decision.",
        )
    if job.status == "failed":
        return (
            "This case needs attention.",
            "The job stopped safely. Review the recorded error before trying another approach.",
        )
    stage_titles = {
        "accepted": "Your case is in the queue.",
        "extracting_sources": "Reading the source material.",
        "extracting_claims": "Finding the claims that matter.",
        "researching_claims": "Testing claims against evidence.",
        "discovering_connections": "Looking for useful connections.",
        "validating_connections": "Testing each connection.",
        "building_paths": "Building paths through the idea.",
        "synthesizing_insights": "Turning the strongest path into an insight.",
        "building_artifact": "Writing the finished artifact.",
    }
    return (
        stage_titles.get(job.stage, "Building an inspectable research case."),
        "Markov records each stage so you can see what is happening and return later.",
    )


_WORKSPACE_STAGES = (
    ("extracting_sources", "Reading source"),
    ("extracting_claims", "Mapping claims"),
    ("researching_claims", "Checking evidence"),
    ("discovering_connections", "Finding connections"),
    ("building_artifact", "Directions ready"),
)


def _source_label(research_case) -> str:
    parsed_source = urlparse(research_case.original_input)
    if parsed_source.scheme in {"http", "https"}:
        host = parsed_source.netloc.removeprefix("www.")
        return f"{_humanize(research_case.input_type)} · {host}"
    return "Question or note"


async def _workspace_snapshot(store, *, owner_id: str, limit: int = 50) -> dict:
    jobs = await store.list_jobs(owner_id=owner_id, limit=max(limit, 50))
    jobs_by_case = {}
    for job in jobs:
        jobs_by_case.setdefault(job.research_case_id, job)

    case_rows = []
    output_rows = []
    connection_rows = []
    for research_case in await store.list_research_cases(
        owner_id=owner_id, limit=limit
    ):
        artifacts = await store.list_case_artifacts(research_case.id)
        sources = await store.list_research_case_sources(research_case.id)
        topics = await store.list_research_topics(research_case.id)
        insights = await store.list_insight_candidates(research_case.id)
        connections = await store.list_connections(research_case.id)
        latest_artifact = artifacts[-1] if artifacts else None
        latest_job = jobs_by_case.get(research_case.id)
        is_processing = bool(
            latest_job
            and latest_job.status not in {"completed", "failed", "awaiting_review"}
        )

        destination = None
        action_label = "Open Chain"
        status = research_case.status
        updated_at = research_case.updated_at or research_case.created_at
        if latest_artifact is not None:
            destination = f"/app/artifacts/{latest_artifact.id}"
            action_label = "Review and continue"
            status = latest_artifact.status
            updated_at = latest_artifact.updated_at or latest_artifact.created_at
        elif latest_job is not None:
            destination = f"/app/jobs/{latest_job.id}"
            action_label = "See what Markov is doing"
            status = latest_job.status
            updated_at = latest_job.updated_at or latest_job.created_at

        if is_processing:
            finding = _job_language(latest_job)[0]
            next_action = "Markov will ask for a decision when the directions are ready."
        elif insights:
            finding = insights[0].thesis or insights[0].title
            next_action = "Choose which direction should become the next piece of work."
        elif topics:
            finding = f"Markov found {len(topics)} directions worth a closer look."
            next_action = "Review the strongest direction and decide what to investigate."
        elif connections:
            finding = connections[0].why_it_matters or connections[0].statement
            next_action = "Inspect the connection before carrying it into an output."
        elif latest_artifact is not None:
            finding = f"A {_humanize(latest_artifact.artifact_type).lower()} is ready."
            next_action = "Review the work, its sources, and any unresolved claims."
        else:
            finding = "The source is saved and ready for its first research pass."
            next_action = "Open the Chain and choose what Markov should follow."

        stage_index = 0
        if latest_job is not None:
            stage_names = [stage for stage, _ in _WORKSPACE_STAGES]
            if latest_job.status in {"completed", "awaiting_review"}:
                stage_index = len(_WORKSPACE_STAGES)
            elif latest_job.stage in stage_names:
                stage_index = stage_names.index(latest_job.stage) + 1

        row = {
            "case": research_case,
            "latest_artifact": latest_artifact,
            "latest_job": latest_job,
            "destination": destination,
            "action_label": action_label,
            "status": status,
            "updated_at": updated_at,
            "source_label": _source_label(research_case),
            "source_count": len(sources),
            "topic_count": len(topics),
            "connection_count": len(connections),
            "finding": finding,
            "next_action": next_action,
            "is_processing": is_processing,
            "stage_index": stage_index,
            "first_connection": connections[0] if connections else None,
            "information_gain": (
                round(max(item.novelty for item in connections) * 100)
                if connections and max(item.novelty for item in connections) > 0
                else None
            ),
            "audience_relevance": (
                round(max(item.relevance for item in connections) * 100)
                if connections and max(item.relevance for item in connections) > 0
                else None
            ),
            "opportunity_thesis": (
                insights[0].thesis
                if insights
                else topics[0].focus
                if topics
                else finding
            ),
            "opportunity_basis": (
                insights[0].novelty_basis
                if insights and insights[0].novelty_basis
                else connections[0].why_it_matters
                if connections
                else "A landscape scan is still needed before Markov can explain what appears underdeveloped."
            ),
            "opportunity_weakness": (
                insights[0].uncertainty
                if insights and insights[0].uncertainty
                else connections[0].weakens
                if connections and connections[0].weakens
                else "No explicit weakness has been recorded yet."
            ),
        }
        case_rows.append(row)
        for artifact in reversed(artifacts):
            output_rows.append({"artifact": artifact, "case": research_case})
        for connection in connections[:1]:
            connection_rows.append(
                {"connection": connection, "case": research_case, "row": row}
            )

    return {
        "jobs": jobs,
        "cases": case_rows,
        "outputs": output_rows,
        "connections": connection_rows,
        "in_progress": [row for row in case_rows if row["is_processing"]],
        "ready": [
            row
            for row in case_rows
            if not row["is_processing"]
            and (row["topic_count"] or row["connection_count"])
        ],
        "stages": _WORKSPACE_STAGES,
    }


def create_web_router(*, settings: Settings) -> APIRouter:
    router = APIRouter()

    def owner(request: Request) -> str:
        identity = _unsigned(
            request.cookies.get("markov_session"), settings.web_session_secret
        )
        if not identity or identity not in set(settings.api_keys.values()):
            raise HTTPException(status_code=401, detail="Sign in at /app/login")
        return identity

    def reviewer(request: Request) -> str:
        identity = _unsigned(
            request.cookies.get("markov_reviewer"), settings.web_session_secret
        )
        if not identity or identity not in set(settings.internal_api_keys.values()):
            raise HTTPException(status_code=401, detail="Sign in at /app/reviewer/login")
        return identity

    @router.get("/")
    async def landing(request: Request):
        return _render(request, "landing.html")

    @router.get("/story")
    async def narrative_landing(request: Request):
        return RedirectResponse("/", status_code=307)

    @router.get("/landing-v2")
    async def narrative_landing_alias():
        return RedirectResponse("/", status_code=307)

    @router.get("/product")
    async def product():
        return RedirectResponse("/#product", status_code=307)

    @router.get("/pricing")
    async def pricing(request: Request):
        return _render(request, "pricing.html", products=public_catalog(settings))

    @router.get("/developers")
    async def developers(request: Request):
        return _render(request, "developers.html")

    @router.get("/sample")
    async def sample(request: Request):
        return _render(request, "sample.html")

    @router.get("/app/login")
    async def login_page(request: Request):
        return _render(request, "login.html", error=None)

    @router.post("/app/login")
    async def login(request: Request):
        values = await _form(request)
        owner_id = settings.api_keys.get(values.get("api_key", ""))
        if not owner_id:
            return _render(request, "login.html", error="That API key is not valid.")
        response = RedirectResponse("/app", status_code=303)
        response.set_cookie(
            "markov_session",
            _signed(owner_id, settings.web_session_secret),
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 24 * 30,
        )
        return response

    @router.get("/app")
    async def intake(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        account = await store.get_credit_account(owner_id)
        snapshot = await _workspace_snapshot(store, owner_id=owner_id, limit=12)
        return _render(
            request,
            "dashboard.html",
            active="home",
            owner_id=owner_id,
            account=account,
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.get("/app/signals")
    async def signals_page(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        snapshot = await _workspace_snapshot(store, owner_id=owner_id)
        return _render(
            request,
            "workspace_page.html",
            active="signals",
            page_kind="signals",
            page_title="Signals",
            page_description="Raw material that may change what your audience needs next.",
            account=await store.get_credit_account(owner_id),
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.get("/app/inbox")
    async def inbox_page_alias():
        return RedirectResponse("/app/signals", status_code=307)

    @router.get("/app/ideas")
    async def ideas_page(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        snapshot = await _workspace_snapshot(store, owner_id=owner_id)
        return _render(
            request,
            "workspace_page.html",
            active="ideas",
            page_kind="ideas",
            page_title="Ideas",
            page_description="Opportunities Markov can explain, you can challenge, and your audience may value.",
            account=await store.get_credit_account(owner_id),
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.get("/app/chains")
    async def chains_page_alias():
        return RedirectResponse("/app/ideas", status_code=307)

    @router.get("/app/plans")
    async def plans_page(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        snapshot = await _workspace_snapshot(store, owner_id=owner_id)
        return _render(
            request,
            "workspace_page.html",
            active="plans",
            page_kind="plans",
            page_title="Campaign Plans",
            page_description="Development briefs and channel treatments that preserve the idea's distinctive core.",
            account=await store.get_credit_account(owner_id),
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.get("/app/outputs")
    async def outputs_page_alias():
        return RedirectResponse("/app/plans", status_code=307)

    @router.get("/app/published")
    async def published_page(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        snapshot = await _workspace_snapshot(store, owner_id=owner_id)
        return _render(
            request,
            "workspace_page.html",
            active="published",
            page_kind="published",
            page_title="Published",
            page_description="Connect finished work to the idea that produced it and learn from the response.",
            account=await store.get_credit_account(owner_id),
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.get("/app/onboarding")
    async def onboarding_page(request: Request):
        try:
            owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        return _render(request, "onboarding.html", active="onboarding")

    @router.get("/app/search")
    async def search_page(request: Request):
        try:
            owner_id = owner(request)
        except HTTPException:
            return RedirectResponse("/app/login", status_code=303)
        store = request.app.state.store
        snapshot = await _workspace_snapshot(store, owner_id=owner_id)
        query = request.query_params.get("q", "").strip()
        if query:
            needle = query.casefold()
            snapshot["cases"] = [
                row
                for row in snapshot["cases"]
                if needle in row["case"].title.casefold()
                or needle in row["case"].original_input.casefold()
                or needle in row["finding"].casefold()
            ]
        return _render(
            request,
            "workspace_page.html",
            active="search",
            page_kind="search",
            page_title="Search",
            page_description="Search signals, ideas, audience questions, coverage, and campaign plans.",
            query=query,
            account=await store.get_credit_account(owner_id),
            entitlements=resolve_entitlements(owner_id, settings=settings),
            **snapshot,
        )

    @router.post("/app/jobs")
    async def create_job_page(request: Request, background_tasks: BackgroundTasks):
        owner_id = owner(request)
        values = await _form(request)
        value = values.get("value", "").strip()
        input_type = "url" if urlparse(value).scheme in {"http", "https"} else "text"
        constraints = {
            key: values[key]
            for key in ("focus", "audience", "tone")
            if values.get(key)
        }
        if values.get("target_minutes"):
            constraints["target_minutes"] = float(values["target_minutes"])
        try:
            job, created = await submit_job(
                request.app.state.store,
                owner_id=owner_id,
                mode=values.get("mode", "brief"),
                review_level=values.get("review_level", "instant"),
                inputs=[{"type": input_type, "value": value}],
                constraints=constraints,
                settings=settings,
            )
        except ValueError as exc:
            return _render(
                request,
                "error.html",
                title="Could not create the case",
                message=str(exc),
            )
        if created:
            background_tasks.add_task(
                run_job,
                request.app.state.store,
                job_id=job.id,
                settings=settings,
                process_case=request.app.state.process_case,
            )
        return RedirectResponse(f"/app/jobs/{job.id}", status_code=303)

    @router.get("/app/jobs/{job_id}")
    async def job_page(job_id: str, request: Request):
        owner_id = owner(request)
        store = request.app.state.store
        job = await store.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        stage_title, stage_description = _job_language(job)
        return _render(
            request,
            "job.html",
            active="ideas",
            account=await store.get_credit_account(owner_id),
            job=job,
            events=await store.list_job_events(job.id),
            artifacts=await store.list_case_artifacts(job.research_case_id),
            stage_title=stage_title,
            stage_description=stage_description,
            refresh=None
            if job.status in {"completed", "failed", "awaiting_review"}
            else 4,
        )

    @router.get("/app/artifacts/{artifact_id}")
    async def artifact_page(artifact_id: int, request: Request):
        owner_id = owner(request)
        store = request.app.state.store
        artifact = await store.get_artifact(artifact_id, owner_id=owner_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        case = await store.get_research_case(
            artifact.research_case_id, owner_id=owner_id
        )
        if case is None:
            raise HTTPException(status_code=404, detail="Research case not found")
        claims = await store.list_claims(case.id)
        claim_rows = [
            {"claim": claim, "evidence": await store.list_claim_evidence(claim.id)}
            for claim in claims
        ]
        claim_rows_by_id = {row["claim"].id: row for row in claim_rows}
        decisions = await store.list_user_branch_decisions(
            case.id, owner_id=owner_id
        )
        latest_decision = {item.connection_id: item for item in decisions}
        connections = await store.list_connections(case.id)
        connection_rows = [
            {
                "connection": connection,
                "evidence": await store.list_connection_evidence(connection.id),
                "decision": latest_decision.get(connection.id),
            }
            for connection in connections
        ]
        gaps = await store.list_research_gaps(case.id)
        source_rows = [
            _safe_source(source)
            for source in await store.list_research_case_sources(case.id)
        ]
        source_rows_by_id = {source["id"]: source for source in source_rows}
        topics = await store.list_research_topics(case.id)
        insights = await store.list_insight_candidates(case.id)
        planned_topic_rows = []
        for topic in topics:
            topic_claim_rows = [
                claim_rows_by_id[claim_id]
                for claim_id in topic.claim_ids
                if claim_id in claim_rows_by_id
            ]
            evidence_source_ids = {
                link.evidence.source_id
                for row in topic_claim_rows
                for link in row["evidence"]
                if link.evidence is not None
            }
            planned_topic_rows.append(
                {
                    "topic": topic,
                    "claims": topic_claim_rows,
                    "gaps": [gap for gap in gaps if gap.claim_id in topic.claim_ids],
                    "sources": [
                        source_rows_by_id[source_id]
                        for source_id in evidence_source_ids
                        if source_id in source_rows_by_id
                    ],
                    "insights": [
                        insight
                        for insight in insights
                        if set(insight.supporting_claim_ids) & set(topic.claim_ids)
                    ],
                }
            )
        topic_rows = planned_topic_rows
        for index, row in enumerate(topic_rows):
            statuses = {
                claim_row["claim"].verification_status
                for claim_row in row["claims"]
            }
            if statuses & {"supported", "completed"}:
                evidence_label = "Independently supported"
                evidence_class = "is-supported"
            elif statuses & {"partially_supported", "qualified"}:
                evidence_label = "Mixed evidence"
                evidence_class = "is-mixed"
            elif statuses & {"disputed", "contradicted"}:
                evidence_label = "Competing evidence"
                evidence_class = "is-competing"
            elif statuses & {"unverifiable", "not_researched"}:
                evidence_label = "Needs verification"
                evidence_class = "needs-evidence"
            elif statuses & {"opinion_or_inference"}:
                evidence_label = "Claim from the source"
                evidence_class = "source-claim"
            else:
                evidence_label = "Open question"
                evidence_class = "is-open"

            if index == 0 and evidence_class == "is-supported":
                rank_label = "Strongest supported direction"
            elif row["insights"]:
                rank_label = "Most original direction"
            elif (
                row["topic"].importance >= 0.8
                and evidence_class in {"is-supported", "is-mixed"}
            ):
                rank_label = "Most consequential direction"
            elif evidence_class in {"needs-evidence", "source-claim"}:
                rank_label = "Needs more evidence"
            elif evidence_class == "is-competing":
                rank_label = "Competing explanations"
            else:
                rank_label = "Ready to explore"

            row["evidence_label"] = evidence_label
            row["evidence_class"] = evidence_class
            row["rank_label"] = rank_label
        core_claim_rows = [
            row for row in claim_rows if row["claim"].disposition == "core"
        ] or claim_rows
        seed_source = next(
            (
                source
                for source in source_rows
                if source.get("case_source_role") == "seed"
            ),
            source_rows[0] if source_rows else None,
        )
        supplemental_sources = [
            source for source in source_rows if source is not seed_source
        ]
        await store.record_usage_event(
            owner_id=owner_id,
            event_type="artifact_viewed",
            research_case_id=case.id,
            artifact_id=artifact.id,
        )
        structured = artifact.structured_content or {}
        return _render(
            request,
            "artifact.html",
            active="ideas",
            artifact=artifact,
            case=case,
            entitlements=resolve_entitlements(owner_id, settings=settings),
            sections=structured.get("sections", []),
            claim_rows=core_claim_rows,
            connection_rows=connection_rows,
            gaps=gaps,
            topics=topics,
            topic_rows=topic_rows,
            insights=insights,
            sources=source_rows,
            seed_source=seed_source,
            supplemental_sources=supplemental_sources,
            case_artifacts=await store.list_case_artifacts(case.id),
            artifact_versions=await store.list_artifact_versions(artifact.id),
        )

    @router.get("/app/artifacts/{artifact_id}/export")
    async def artifact_export(
        artifact_id: int, request: Request, format: str = "markdown"
    ):
        owner_id = owner(request)
        entitlements = resolve_entitlements(owner_id, settings=settings)
        if format not in entitlements.export_formats:
            return _render(
                request,
                "error.html",
                title="Export is not available",
                message=(
                    f"The {entitlements.profile} profile does not include "
                    f"{format} export."
                ),
            )
        try:
            content, media_type, filename = await export_artifact(
                request.app.state.store,
                artifact_id=artifact_id,
                owner_id=owner_id,
                export_format=format,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.post("/app/cases/{case_id}/convert")
    async def convert_page(case_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        constraint_fields = (
            "selected_topic_id",
            "selected_insight_id",
            "angle",
            "focus",
            "audience",
            "target_minutes",
            "tone",
            "delivery_format",
            "desired_takeaway",
            "evidence_boundary",
        )
        constraints = {
            field: values[field]
            for field in constraint_fields
            if str(values.get(field) or "").strip()
        }
        try:
            artifact, _ = await convert_case_artifact(
                request.app.state.store,
                case_id=case_id,
                owner_id=owner_id,
                mode=values.get("mode", "brief"),
                review_level=values.get("review_level", "instant"),
                constraints=constraints,
                settings=settings,
            )
        except ValueError as exc:
            return _render(
                request,
                "error.html",
                title="Could not convert the case",
                message=str(exc),
            )
        return RedirectResponse(f"/app/artifacts/{artifact.id}", status_code=303)

    @router.post("/app/claims/{claim_id}/deepen")
    async def deepen_page(claim_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        return_artifact = int(values.get("return_artifact") or 0)
        try:
            await deepen_claim(
                request.app.state.store, claim_id=claim_id, owner_id=owner_id
            )
        except ValueError as exc:
            return _render(
                request,
                "error.html",
                title="Could not deepen the claim",
                message=str(exc),
            )
        return RedirectResponse(f"/app/artifacts/{return_artifact}", status_code=303)

    @router.post("/app/connections/{connection_id}/actions")
    async def connection_action_page(connection_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        action = values.get("action", "open")
        return_artifact = int(values.get("return_artifact") or 0)
        return_to = values.get("return_to", "")
        try:
            if action == "follow":
                current = await request.app.state.store.get_artifact(
                    return_artifact, owner_id=owner_id
                )
                script_id = (
                    current.id
                    if current is not None and current.artifact_type == "script"
                    else None
                )
                _decision, artifact = await follow_connection_into_script(
                    request.app.state.store,
                    connection_id=connection_id,
                    owner_id=owner_id,
                    artifact_id=script_id,
                )
                return RedirectResponse(
                    f"/app/artifacts/{artifact.id}", status_code=303
                )
            await record_connection_decision(
                request.app.state.store,
                connection_id=connection_id,
                owner_id=owner_id,
                action=action,
                metadata={"reason": values["reason"]} if values.get("reason") else None,
            )
        except ValueError as exc:
            return _render(
                request,
                "error.html",
                title="Could not update the connection",
                message=str(exc),
            )
        destination = (
            return_to
            if return_to.startswith("/app")
            else f"/app/artifacts/{return_artifact}"
        )
        return RedirectResponse(destination, status_code=303)

    @router.post("/app/artifacts/{artifact_id}/revisions")
    async def revise_page(artifact_id: int, request: Request):
        owner_id = owner(request)
        values = await _form(request)
        try:
            await revise_script_section(
                request.app.state.store,
                artifact_id=artifact_id,
                section_id=values.get("section_id", ""),
                replacement=values.get("replacement", ""),
                owner_id=owner_id,
            )
        except ValueError as exc:
            return _render(
                request,
                "error.html",
                title="Could not revise the section",
                message=str(exc),
            )
        return RedirectResponse(f"/app/artifacts/{artifact_id}", status_code=303)

    @router.post("/app/artifacts/{artifact_id}/edit")
    async def edit_artifact_page(artifact_id: int, request: Request):
        owner_id = owner(request)
        store = request.app.state.store
        artifact = await store.get_artifact(artifact_id, owner_id=owner_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        values = await _form(request)
        content = values.get("content", "").strip()
        structured_content = dict(artifact.structured_content or {})
        section_keys = sorted(
            (key for key in values if key.startswith("section_") and key[8:].isdigit()),
            key=lambda key: int(key[8:]),
        )
        if section_keys:
            updated_sections = []
            markdown_sections = []
            existing_sections = list(structured_content.get("sections", []))
            for key in section_keys:
                index = int(key[8:])
                existing = (
                    dict(existing_sections[index])
                    if index < len(existing_sections)
                    else {}
                )
                title = values.get(f"section_title_{index}", "").strip() or str(
                    existing.get("title") or f"Section {index + 1}"
                )
                section_content = values[key].strip()
                existing.update({"title": title, "content": section_content})
                updated_sections.append(existing)
                markdown_sections.append(f"## {title}\n\n{section_content}")
            structured_content["sections"] = updated_sections
            content = "\n\n".join(markdown_sections).strip()
        elif content:
            structured_content["sections"] = [
                {"title": "Working brief", "content": content}
            ]
        if not content:
            return _render(
                request,
                "error.html",
                title="The document cannot be empty",
                message="Keep at least one line in the output before saving it.",
            )
        await store.update_case_artifact(
            artifact_id,
            content=content,
            structured_content=structured_content,
            status="completed"
            if values.get("action") == "finish"
            else "draft",
            change_kind="manual_edit",
            changed_section="full_document",
        )
        return RedirectResponse(
            f"/app/artifacts/{artifact_id}#brief", status_code=303
        )

    @router.get("/app/reviewer/login")
    async def reviewer_login_page(request: Request):
        return _render(request, "review_login.html", error=None)

    @router.post("/app/reviewer/login")
    async def reviewer_login(request: Request):
        values = await _form(request)
        reviewer_id = settings.internal_api_keys.get(values.get("api_key", ""))
        if not reviewer_id:
            return _render(
                request, "review_login.html", error="Invalid reviewer key."
            )
        response = RedirectResponse("/app/reviews", status_code=303)
        response.set_cookie(
            "markov_reviewer",
            _signed(reviewer_id, settings.web_session_secret),
            httponly=True,
            samesite="strict",
            max_age=60 * 60 * 12,
        )
        return response

    @router.get("/app/reviews")
    async def review_queue(request: Request):
        try:
            reviewer(request)
        except HTTPException:
            return RedirectResponse("/app/reviewer/login", status_code=303)
        return _render(
            request,
            "review_queue.html",
            reviews=await request.app.state.store.list_review_jobs(),
        )

    @router.get("/app/reviews/{review_id}")
    async def review_page(review_id: int, request: Request):
        reviewer(request)
        store = request.app.state.store
        review_job = await store.get_review_job(review_id)
        if review_job is None:
            raise HTTPException(status_code=404, detail="Review not found")
        artifact = await store.get_artifact(review_job.artifact_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Reviewed artifact not found")
        case = await store.get_research_case(artifact.research_case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Research case not found")
        claims = await store.list_claims(case.id)
        claim_rows = [
            {"claim": claim, "evidence": await store.list_claim_evidence(claim.id)}
            for claim in claims
        ]
        return _render(
            request,
            "review_detail.html",
            review_job=review_job,
            artifact=artifact,
            case=case,
            claim_rows=claim_rows,
        )

    @router.post("/app/reviews/{review_id}/claims")
    async def review_claim(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await record_review_decision(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            entity_type="claim",
            entity_id=values.get("claim_id", ""),
            decision_type="claim_status_changed",
            new_value=values.get("status"),
            reason=values.get("reason", ""),
        )
        return RedirectResponse(f"/app/reviews/{review_id}", status_code=303)

    @router.post("/app/reviews/{review_id}/evidence")
    async def review_evidence(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await record_review_decision(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            entity_type="evidence",
            entity_id=values.get("evidence_id", ""),
            decision_type=values.get("decision", "evidence_rejected"),
            new_value={"claim_id": values.get("claim_id")},
            reason=values.get("reason", ""),
        )
        return RedirectResponse(f"/app/reviews/{review_id}", status_code=303)

    @router.post("/app/reviews/{review_id}/finalize")
    async def finalize_page(review_id: int, request: Request):
        reviewer_id = reviewer(request)
        values = await _form(request)
        await finalize_review(
            request.app.state.store,
            review_id=review_id,
            reviewer_id=reviewer_id,
            review_minutes=float(values.get("review_minutes") or 0),
            settings=settings,
        )
        return RedirectResponse("/app/reviews", status_code=303)

    return router
