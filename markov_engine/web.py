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
from markupsafe import Markup

from markov_engine.billing import public_catalog
from markov_engine.config import Settings
from markov_engine.exports import export_artifact, markdown_to_safe_html
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


def _markdown_body(markdown: str) -> Markup:
    rendered = markdown_to_safe_html(markdown)
    body = rendered.split("<body>", 1)[-1].rsplit("</body>", 1)[0]
    return Markup(body)


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
        return (
            f"Your {_humanize(job.mode).lower()} is ready.",
            "The finished artifact and its evidence trail are ready to inspect.",
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
        "building_artifact": "Writing the finished artifact.",
    }
    return (
        stage_titles.get(job.stage, "Building an inspectable research case."),
        "Markov records each stage so you can see what is happening and return later.",
    )


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
        return _render(
            request,
            "dashboard.html",
            active="overview",
            owner_id=owner_id,
            account=account,
            jobs=await store.list_jobs(owner_id=owner_id, limit=12),
            products=public_catalog(settings),
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
            active="projects",
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
            artifact=artifact,
            artifact_body=_markdown_body(artifact.content),
            case=case,
            sections=structured.get("sections", []),
            claim_rows=claim_rows,
            gaps=await store.list_research_gaps(case.id),
            sources=[
                _safe_source(source)
                for source in await store.list_research_case_sources(case.id)
            ],
        )

    @router.get("/app/artifacts/{artifact_id}/export")
    async def artifact_export(
        artifact_id: int, request: Request, format: str = "markdown"
    ):
        owner_id = owner(request)
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
        try:
            artifact, _ = await convert_case_artifact(
                request.app.state.store,
                case_id=case_id,
                owner_id=owner_id,
                mode=values.get("mode", "brief"),
                review_level=values.get("review_level", "instant"),
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
