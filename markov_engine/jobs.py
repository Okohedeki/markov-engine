"""Durable job records and single-process V1 execution orchestration."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import uuid
from dataclasses import asdict
from urllib.parse import urlparse

import httpx

from markov_engine.billing import refund_job_credits, reserve_job_credits
from markov_engine.config import Settings, get_settings
from markov_engine.entitlements import require_capability, resolve_entitlements
from markov_engine.research import create_research_case, process_research_case
from markov_engine.store.records import JobRec
from markov_engine.store.sqlite import SqliteStore

JOB_MODES = {"brief", "research", "script"}
JOB_REVIEW_LEVELS = {"instant", "verified"}


def validate_webhook_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Webhook URLs must use HTTPS")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local):
        raise ValueError("Webhook URL cannot target a private address")
    return value


async def submit_job(
    store: SqliteStore,
    *,
    owner_id: str,
    mode: str,
    review_level: str,
    inputs: list[dict],
    constraints: dict | None = None,
    webhook_url: str | None = None,
    idempotency_key: str | None = None,
    settings: Settings | None = None,
) -> tuple[JobRec, bool]:
    """Create a billed, isolated job. Returns ``(job, created)``."""
    settings = settings or get_settings()
    if idempotency_key:
        existing = await store.get_job_by_idempotency(
            owner_id=owner_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            return existing, False
    if mode not in JOB_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    if review_level not in JOB_REVIEW_LEVELS:
        raise ValueError(f"Unsupported review level: {review_level}")
    entitlements = resolve_entitlements(owner_id, settings=settings)
    if review_level == "verified":
        require_capability(entitlements, "human_review")
    if len(inputs) != 1:
        raise ValueError("V1 accepts exactly one input per research case")
    input_item = inputs[0]
    input_type = str(input_item.get("type") or "").lower()
    value = str(input_item.get("value") or "").strip()
    if input_type not in {"url", "text", "topic", "question"} or not value:
        raise ValueError("Input must be one non-empty URL, text, topic, or question")
    if input_type == "url":
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("URL input must be a public HTTP(S) URL")
    webhook_url = validate_webhook_url(webhook_url)
    job_id = str(uuid.uuid4())
    prior_jobs = await store.list_jobs(owner_id=owner_id, limit=1)
    if entitlements.concurrent_jobs is not None:
        active = [
            item
            for item in await store.list_jobs(owner_id=owner_id)
            if item.status in {"queued", "running"}
        ]
        if len(active) >= entitlements.concurrent_jobs:
            raise ValueError("Concurrent job limit reached for this entitlement profile")
    constraints = dict(constraints or {})
    if entitlements.max_connections is not None:
        requested = int(
            constraints.get("max_connections") or entitlements.max_connections
        )
        constraints["max_connections"] = min(
            max(1, requested), entitlements.max_connections
        )
    if entitlements.max_connection_depth is not None:
        requested_depth = int(
            constraints.get("max_connection_depth")
            or entitlements.max_connection_depth
        )
        constraints["max_connection_depth"] = min(
            max(1, requested_depth), entitlements.max_connection_depth
        )
    constraints["entitlement_profile"] = entitlements.profile
    await reserve_job_credits(
        store,
        owner_id=owner_id,
        job_id=job_id,
        mode=mode,
        review_level=review_level,
        settings=settings,
    )
    try:
        case = await create_research_case(
            store,
            owner_id=owner_id,
            original_input=value,
            mode=mode,
            input_type=input_type,
            constraints=constraints,
        )
        job = await store.create_job(
            job_id=job_id,
            owner_id=owner_id,
            research_case_id=case.id,
            mode=mode,
            review_level=review_level,
            constraints=constraints,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
        )
        await store.add_job_event(
            job_id=job.id,
            stage="queued",
            detail={"mode": mode, "review_level": review_level},
        )
        await store.record_usage_event(
            owner_id=owner_id,
            event_type="job_created",
            research_case_id=case.id,
            metadata={
                "job_id": job.id,
                "mode": mode,
                "review_level": review_level,
                "input_type": case.input_type,
            },
        )
        if prior_jobs:
            await store.record_usage_event(
                owner_id=owner_id,
                event_type="repeat_project",
                research_case_id=case.id,
                metadata={"previous_job_id": prior_jobs[0].id},
            )
        return job, True
    except Exception:
        await refund_job_credits(
            store,
            owner_id=owner_id,
            job_id=job_id,
            mode=mode,
            review_level=review_level,
            settings=settings,
        )
        raise


async def _send_webhook(
    job: JobRec,
    payload: dict,
    *,
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> None:
    if not job.webhook_url:
        return
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json"}
    if settings.webhook_signing_secret:
        signature = hmac.new(
            settings.webhook_signing_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        headers["X-Markov-Signature"] = f"sha256={signature}"
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=10, follow_redirects=False)
    try:
        response = await client.post(job.webhook_url, content=body, headers=headers)
        response.raise_for_status()
    finally:
        if owns_client:
            await client.aclose()


async def run_job(
    store: SqliteStore,
    *,
    job_id: str,
    settings: Settings | None = None,
    process_case=process_research_case,
    webhook_client: httpx.AsyncClient | None = None,
    **process_overrides,
) -> JobRec:
    """Run a queued job and persist every visible stage and terminal failure."""
    settings = settings or get_settings()
    job = await store.get_job(job_id)
    if job is None:
        raise ValueError("Job not found")
    if job.status != "queued":
        return job
    await store.update_job(job.id, status="running", stage="starting", error=None)
    await store.add_job_event(job_id=job.id, stage="starting")

    async def stage_handler(stage: str, detail: dict) -> None:
        await store.update_job(job.id, status="running", stage=stage, error=None)
        await store.add_job_event(job_id=job.id, stage=stage, detail=detail)

    try:
        artifacts = await process_case(
            store,
            case_id=job.research_case_id,
            review_level=job.review_level,
            modes=[job.mode],
            stage_handler=stage_handler,
            **process_overrides,
        )
        terminal = "awaiting_review" if job.review_level == "verified" else "completed"
        await store.update_job(job.id, status=terminal, stage=terminal, error=None)
        completed = await store.get_job(job.id)
        assert completed is not None
        payload = {
            "event": f"job.{terminal}",
            "job": asdict(completed),
            "artifact_ids": [artifact.id for artifact in artifacts],
        }
        try:
            await _send_webhook(
                completed, payload, settings=settings, client=webhook_client
            )
            if completed.webhook_url:
                await store.add_job_event(job_id=job.id, stage="webhook_delivered")
        except Exception as exc:
            await store.add_job_event(
                job_id=job.id,
                stage="webhook_failed",
                detail={"error": str(exc)},
            )
        return completed
    except Exception as exc:
        await store.update_job(job.id, status="failed", stage="failed", error=str(exc))
        await store.add_job_event(
            job_id=job.id, stage="failed", detail={"error": str(exc)}
        )
        await refund_job_credits(
            store,
            owner_id=job.owner_id,
            job_id=job.id,
            mode=job.mode,
            review_level=job.review_level,
            settings=settings,
        )
        failed = await store.get_job(job.id)
        assert failed is not None
        try:
            await _send_webhook(
                failed,
                {"event": "job.failed", "job": asdict(failed)},
                settings=settings,
                client=webhook_client,
            )
        except Exception:
            pass
        return failed
