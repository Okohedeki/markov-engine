"""Authenticated asynchronous HTTP API and application entrypoint for Markov V1."""

import asyncio
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import httpx
import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from markov_engine.billing import (
    apply_stripe_event,
    create_checkout_session,
    parse_stripe_event,
    public_catalog,
    verify_stripe_signature,
)
from markov_engine.config import Settings, get_settings
from markov_engine.exports import export_artifact
from markov_engine.jobs import run_job, submit_job
from markov_engine.research import convert_case_artifact, process_research_case
from markov_engine.reviews import finalize_review, record_review_decision
from markov_engine.revisions import deepen_claim, revise_script_section
from markov_engine.store.sqlite import SqliteStore


class InputItem(BaseModel):
    type: str
    value: str


class JobCreate(BaseModel):
    mode: str
    review_level: str = "instant"
    inputs: list[InputItem]
    constraints: dict[str, Any] = Field(default_factory=dict)
    webhook_url: str | None = None


class ArtifactCreate(BaseModel):
    mode: str
    review_level: str = "instant"
    constraints: dict[str, Any] = Field(default_factory=dict)


class RevisionCreate(BaseModel):
    section_id: str
    replacement: str


class DeepenCreate(BaseModel):
    max_sources: int = Field(5, ge=1, le=12)
    time_budget_s: float = Field(90, ge=5, le=300)


class ReviewDecisionCreate(BaseModel):
    entity_type: str
    entity_id: str
    decision_type: str
    new_value: Any = None
    reason: str


class ReviewFinalizeCreate(BaseModel):
    review_minutes: float = Field(ge=0)


class CheckoutCreate(BaseModel):
    pack_name: str


class _RateLimiter:
    def __init__(self, requests_per_minute: int):
        self.limit = max(1, requests_per_minute)
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = asyncio.Lock()

    async def check(self, identity: str) -> None:
        now = time.monotonic()
        async with self.lock:
            hits = self.hits[identity]
            while hits and hits[0] <= now - 60:
                hits.popleft()
            if len(hits) >= self.limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            hits.append(now)


def _bearer_or_key(authorization: str | None, x_markov_key: str | None) -> str:
    if x_markov_key:
        return x_markov_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return ""


def _as_json(value):
    return jsonable_encoder(asdict(value) if hasattr(value, "__dataclass_fields__") else value)


async def _case_payload(store: SqliteStore, case_id: int, owner_id: str) -> dict:
    case = await store.get_research_case(case_id, owner_id=owner_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Research case not found")
    claims = await store.list_claims(case.id)
    claim_payload = []
    for claim in claims:
        item = _as_json(claim)
        item["evidence"] = [_as_json(link) for link in await store.list_claim_evidence(claim.id)]
        claim_payload.append(item)
    sources = await store.list_research_case_sources(case.id)
    for source in sources:
        source["segments"] = [
            _as_json(segment) for segment in await store.list_source_segments(source["id"])
        ]
    return {
        "case": _as_json(case),
        "sources": _as_json(sources),
        "claims": claim_payload,
        "research_gaps": _as_json(await store.list_research_gaps(case.id)),
        "artifacts": _as_json(await store.list_case_artifacts(case.id)),
        "costs": _as_json(await store.list_costs(case.id)),
    }


def create_app(
    *,
    store: SqliteStore | None = None,
    settings: Settings | None = None,
    process_case=process_research_case,
) -> FastAPI:
    settings = settings or get_settings()
    supplied_store = store

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if supplied_store is None:
            path = Path(settings.database_path).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            app.state.store = await SqliteStore.open(str(path))
        else:
            app.state.store = supplied_store
        yield
        if supplied_store is None:
            await app.state.store.close()

    app = FastAPI(
        title="Markov API",
        version="1.0.0",
        description="Brief, Research, and Script from one inspectable research case.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.store = store
    app.state.process_case = process_case
    limiter = _RateLimiter(settings.api_rate_limit_per_minute)

    async def owner_auth(
        authorization: Annotated[str | None, Header()] = None,
        x_markov_key: Annotated[str | None, Header()] = None,
    ) -> str:
        if not settings.api_keys:
            raise HTTPException(status_code=503, detail="No API keys are configured")
        key = _bearer_or_key(authorization, x_markov_key)
        owner_id = settings.api_keys.get(key)
        if not owner_id:
            raise HTTPException(status_code=401, detail="Invalid API key")
        await limiter.check(f"owner:{owner_id}")
        return owner_id

    async def reviewer_auth(
        authorization: Annotated[str | None, Header()] = None,
        x_markov_key: Annotated[str | None, Header()] = None,
    ) -> str:
        key = _bearer_or_key(authorization, x_markov_key)
        reviewer_id = settings.internal_api_keys.get(key)
        if not reviewer_id:
            raise HTTPException(status_code=401, detail="Invalid reviewer API key")
        await limiter.check(f"reviewer:{reviewer_id}")
        return reviewer_id

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/v1/catalog")
    async def get_catalog(owner_id: Annotated[str, Depends(owner_auth)]):
        return {"products": public_catalog(settings)}

    @app.get("/v1/account")
    async def get_account(
        request: Request, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        account = await request.app.state.store.get_credit_account(owner_id)
        jobs = await request.app.state.store.list_jobs(owner_id=owner_id)
        return {"account": _as_json(account), "jobs": _as_json(jobs)}

    @app.post("/v1/jobs")
    async def post_job(
        payload: JobCreate,
        request: Request,
        background_tasks: BackgroundTasks,
        owner_id: Annotated[str, Depends(owner_auth)],
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ):
        try:
            job, created = await submit_job(
                request.app.state.store,
                owner_id=owner_id,
                mode=payload.mode,
                review_level=payload.review_level,
                inputs=[item.model_dump() for item in payload.inputs],
                constraints=payload.constraints,
                webhook_url=payload.webhook_url,
                idempotency_key=idempotency_key,
                settings=settings,
            )
        except ValueError as exc:
            status = 402 if "Insufficient credits" in str(exc) else 422
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        if created:
            background_tasks.add_task(
                run_job,
                request.app.state.store,
                job_id=job.id,
                settings=settings,
                process_case=request.app.state.process_case,
            )
        return JSONResponse(
            status_code=202 if created else 200,
            content=jsonable_encoder({"job": _as_json(job), "created": created}),
        )

    @app.get("/v1/jobs")
    async def get_jobs(
        request: Request, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        return {"jobs": _as_json(await request.app.state.store.list_jobs(owner_id=owner_id))}

    @app.get("/v1/jobs/{job_id}")
    async def get_job(
        job_id: str, request: Request, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        job = await request.app.state.store.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        artifacts = await request.app.state.store.list_case_artifacts(job.research_case_id)
        return {"job": _as_json(job), "artifacts": _as_json(artifacts)}

    @app.get("/v1/jobs/{job_id}/events")
    async def get_job_events(
        job_id: str, request: Request, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        job = await request.app.state.store.get_job(job_id, owner_id=owner_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"events": _as_json(await request.app.state.store.list_job_events(job.id))}

    @app.get("/v1/research-cases/{case_id}")
    async def get_case(
        case_id: int, request: Request, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        return await _case_payload(request.app.state.store, case_id, owner_id)

    @app.get("/v1/artifacts/{artifact_id}")
    async def get_artifact(
        artifact_id: int,
        request: Request,
        owner_id: Annotated[str, Depends(owner_auth)],
    ):
        artifact = await request.app.state.store.get_artifact(
            artifact_id, owner_id=owner_id
        )
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        await request.app.state.store.record_usage_event(
            owner_id=owner_id,
            event_type="artifact_viewed",
            research_case_id=artifact.research_case_id,
            artifact_id=artifact.id,
        )
        return {"artifact": _as_json(artifact)}

    @app.post("/v1/research-cases/{case_id}/artifacts")
    async def post_artifact(
        case_id: int,
        payload: ArtifactCreate,
        request: Request,
        owner_id: Annotated[str, Depends(owner_auth)],
    ):
        try:
            artifact, created = await convert_case_artifact(
                request.app.state.store,
                case_id=case_id,
                owner_id=owner_id,
                mode=payload.mode,
                review_level=payload.review_level,
                constraints=payload.constraints,
                settings=settings,
            )
        except ValueError as exc:
            status = 402 if "Insufficient credits" in str(exc) else 422
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        return {"artifact": _as_json(artifact), "created": created}

    @app.post("/v1/claims/{claim_id}/deepen")
    async def post_deepen(
        claim_id: int,
        payload: DeepenCreate,
        request: Request,
        owner_id: Annotated[str, Depends(owner_auth)],
    ):
        try:
            return await deepen_claim(
                request.app.state.store,
                claim_id=claim_id,
                owner_id=owner_id,
                max_sources=payload.max_sources,
                time_budget_s=payload.time_budget_s,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/artifacts/{artifact_id}/revisions")
    async def post_revision(
        artifact_id: int,
        payload: RevisionCreate,
        request: Request,
        owner_id: Annotated[str, Depends(owner_auth)],
    ):
        try:
            artifact = await revise_script_section(
                request.app.state.store,
                artifact_id=artifact_id,
                section_id=payload.section_id,
                replacement=payload.replacement,
                owner_id=owner_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"artifact": _as_json(artifact)}

    @app.get("/v1/artifacts/{artifact_id}/export")
    async def get_export(
        artifact_id: int,
        request: Request,
        owner_id: Annotated[str, Depends(owner_auth)],
        export_format: Annotated[str, Query(alias="format")] = "markdown",
    ):
        try:
            content, media_type, filename = await export_artifact(
                request.app.state.store,
                artifact_id=artifact_id,
                owner_id=owner_id,
                export_format=export_format,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/v1/billing/checkout")
    async def post_checkout(
        payload: CheckoutCreate, owner_id: Annotated[str, Depends(owner_auth)]
    ):
        try:
            session = await create_checkout_session(
                owner_id=owner_id, pack_name=payload.pack_name, settings=settings
            )
        except (ValueError, RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"id": session.get("id"), "url": session.get("url")}

    @app.post("/v1/billing/stripe-webhook")
    async def stripe_webhook(
        request: Request,
        stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
    ):
        body = await request.body()
        if not settings.stripe_webhook_secret:
            raise HTTPException(status_code=503, detail="Stripe webhook is not configured")
        if not stripe_signature or not verify_stripe_signature(
            body, stripe_signature, settings.stripe_webhook_secret
        ):
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
        try:
            event = parse_stripe_event(body)
            return await apply_stripe_event(
                request.app.state.store, event, settings=settings
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/internal/reviews")
    async def get_reviews(
        request: Request,
        reviewer_id: Annotated[str, Depends(reviewer_auth)],
        status: str | None = None,
    ):
        return {
            "reviewer_id": reviewer_id,
            "reviews": _as_json(
                await request.app.state.store.list_review_jobs(status=status)
            ),
        }

    @app.get("/internal/reviews/{review_id}")
    async def get_review(
        review_id: int,
        request: Request,
        reviewer_id: Annotated[str, Depends(reviewer_auth)],
    ):
        review = await request.app.state.store.get_review_job(review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review job not found")
        artifact = await request.app.state.store.get_artifact(review.artifact_id)
        if artifact is None or artifact.research_case_id is None:
            raise HTTPException(status_code=404, detail="Reviewed artifact not found")
        case_payload = await _case_payload(
            request.app.state.store,
            artifact.research_case_id,
            (await request.app.state.store.get_research_case(artifact.research_case_id)).owner_id,
        )
        return {
            "reviewer_id": reviewer_id,
            "review": _as_json(review),
            "decisions": _as_json(
                await request.app.state.store.list_review_decisions(review.id)
            ),
            **case_payload,
        }

    @app.post("/internal/reviews/{review_id}/decisions")
    async def post_review_decision(
        review_id: int,
        payload: ReviewDecisionCreate,
        request: Request,
        reviewer_id: Annotated[str, Depends(reviewer_auth)],
    ):
        try:
            decision = await record_review_decision(
                request.app.state.store,
                review_id=review_id,
                reviewer_id=reviewer_id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                decision_type=payload.decision_type,
                new_value=payload.new_value,
                reason=payload.reason,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"decision": _as_json(decision)}

    @app.post("/internal/reviews/{review_id}/finalize")
    async def post_finalize_review(
        review_id: int,
        payload: ReviewFinalizeCreate,
        request: Request,
        reviewer_id: Annotated[str, Depends(reviewer_auth)],
    ):
        try:
            review = await finalize_review(
                request.app.state.store,
                review_id=review_id,
                reviewer_id=reviewer_id,
                review_minutes=payload.review_minutes,
                settings=settings,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"review": _as_json(review)}

    from markov_engine.web import create_web_router

    app.include_router(create_web_router(settings=settings))
    return app


app = create_app()


def main() -> None:
    uvicorn.run("markov_engine.api:app", host="127.0.0.1", port=8000, reload=False)
