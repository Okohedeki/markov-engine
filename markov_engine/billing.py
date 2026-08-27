"""Configurable credits and optional Stripe Checkout for Markov V1."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass

import httpx

from markov_engine.config import Settings, get_settings
from markov_engine.store.sqlite import SqliteStore

PRODUCT_VARIANTS = {
    "brief_instant",
    "brief_verified",
    "research_instant",
    "research_verified",
    "script_instant",
    "script_verified",
}


@dataclass(frozen=True)
class Product:
    variant: str
    mode: str
    review_level: str
    credit_cost: float


def product_variant(mode: str, review_level: str) -> str:
    normalized = "research" if mode == "research_report" else mode
    variant = f"{normalized}_{review_level}"
    if variant not in PRODUCT_VARIANTS:
        raise ValueError(f"Unsupported product variant: {variant}")
    return variant


def catalog(settings: Settings | None = None) -> list[Product]:
    settings = settings or get_settings()
    missing = PRODUCT_VARIANTS - settings.product_credit_costs.keys()
    if missing:
        raise ValueError(
            "Missing configured credit costs for: " + ", ".join(sorted(missing))
        )
    return [
        Product(
            variant=variant,
            mode=variant.rsplit("_", 1)[0],
            review_level=variant.rsplit("_", 1)[1],
            credit_cost=float(settings.product_credit_costs[variant]),
        )
        for variant in sorted(PRODUCT_VARIANTS)
    ]


def credit_cost(
    mode: str, review_level: str, settings: Settings | None = None
) -> float:
    settings = settings or get_settings()
    variant = product_variant(mode, review_level)
    try:
        value = float(settings.product_credit_costs[variant])
    except KeyError as exc:
        raise ValueError(f"No credit cost configured for {variant}") from exc
    if value < 0:
        raise ValueError(f"Credit cost cannot be negative for {variant}")
    return value


async def reserve_job_credits(
    store: SqliteStore,
    *,
    owner_id: str,
    job_id: str,
    mode: str,
    review_level: str,
    settings: Settings | None = None,
) -> float:
    """Reserve credits once. Idempotent retries return the same balance."""
    settings = settings or get_settings()
    variant = product_variant(mode, review_level)
    cost = credit_cost(mode, review_level, settings)
    await store.ensure_credit_account(
        owner_id, opening_balance=float(settings.opening_credits)
    )
    account = await store.apply_credit_transaction(
        owner_id=owner_id,
        amount=-cost,
        reason="job_reserved",
        product_variant=variant,
        reference=job_id,
        idempotency_key=f"reserve:{job_id}",
    )
    await store.record_usage_event(
        owner_id=owner_id,
        event_type="credits_reserved",
        metadata={
            "job_id": job_id,
            "variant": variant,
            "credits": cost,
            "balance": account.balance,
        },
    )
    return cost


async def refund_job_credits(
    store: SqliteStore,
    *,
    owner_id: str,
    job_id: str,
    mode: str,
    review_level: str,
    settings: Settings | None = None,
) -> float:
    settings = settings or get_settings()
    variant = product_variant(mode, review_level)
    cost = credit_cost(mode, review_level, settings)
    account = await store.apply_credit_transaction(
        owner_id=owner_id,
        amount=cost,
        reason="job_refunded",
        product_variant=variant,
        reference=job_id,
        idempotency_key=f"refund:{job_id}",
    )
    return account.balance


async def create_checkout_session(
    *,
    owner_id: str,
    pack_name: str,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """Create Stripe Checkout without adding an SDK dependency."""
    settings = settings or get_settings()
    if not settings.stripe_secret_key:
        raise RuntimeError("Stripe is not configured")
    price_id = settings.stripe_price_ids.get(pack_name)
    if not price_id:
        raise ValueError(f"Unknown credit pack: {pack_name}")
    credits = settings.stripe_credit_packs.get(price_id)
    if credits is None:
        raise ValueError(f"No credit grant configured for Stripe price {price_id}")
    data = {
        "mode": "payment",
        "success_url": settings.stripe_success_url,
        "cancel_url": settings.stripe_cancel_url,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "metadata[owner_id]": owner_id,
        "metadata[credits]": str(float(credits)),
        "metadata[pack_name]": pack_name,
    }
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=20)
    try:
        response = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            data=data,
            auth=(settings.stripe_secret_key, ""),
        )
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            await client.aclose()


def verify_stripe_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    *,
    now: int | None = None,
    tolerance_s: int = 300,
) -> bool:
    """Verify Stripe's timestamped webhook signature."""
    values: dict[str, list[str]] = {}
    for part in signature_header.split(","):
        key, _, value = part.partition("=")
        values.setdefault(key, []).append(value)
    try:
        timestamp = int(values["t"][0])
        signatures = values["v1"]
    except (KeyError, ValueError, IndexError):
        return False
    now = int(time.time()) if now is None else now
    if abs(now - timestamp) > tolerance_s:
        return False
    signed = str(timestamp).encode() + b"." + payload
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


async def apply_stripe_event(
    store: SqliteStore, event: dict, *, settings: Settings | None = None
) -> dict:
    settings = settings or get_settings()
    event_type = str(event.get("type") or "")
    event_id = str(event.get("id") or "")
    obj = event.get("data", {}).get("object", {})
    metadata = obj.get("metadata") or {}
    owner_id = str(metadata.get("owner_id") or "")
    if not owner_id:
        return {"handled": False, "reason": "owner_id missing"}
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        credits = float(metadata.get("credits") or 0)
        price_id = str(metadata.get("price_id") or "")
        if not credits and price_id:
            credits = float(settings.stripe_credit_packs.get(price_id) or 0)
        if credits <= 0:
            return {"handled": False, "reason": "credit grant missing"}
        idempotency_key = f"stripe:{event_id}"
        if await store.has_credit_transaction(
            owner_id=owner_id, idempotency_key=idempotency_key
        ):
            account = await store.get_credit_account(owner_id)
            return {"handled": True, "duplicate": True, "balance": account.balance}
        account = await store.apply_credit_transaction(
            owner_id=owner_id,
            amount=credits,
            reason="payment_completed",
            product_variant=str(metadata.get("pack_name") or "credit_pack"),
            reference=str(obj.get("id") or event_id),
            idempotency_key=idempotency_key,
        )
        await store.record_usage_event(
            owner_id=owner_id,
            event_type="payment_completed",
            metadata={
                "event_id": event_id,
                "credits": credits,
                "balance": account.balance,
            },
        )
        return {"handled": True, "balance": account.balance}
    if event_type in {"checkout.session.async_payment_failed", "payment_intent.payment_failed"}:
        await store.record_usage_event(
            owner_id=owner_id,
            event_type="payment_failed",
            metadata={"event_id": event_id, "object_id": obj.get("id")},
        )
        return {"handled": True}
    return {"handled": False, "event_type": event_type}


def public_catalog(settings: Settings | None = None) -> list[dict]:
    return [asdict(item) for item in catalog(settings)]


def parse_stripe_event(payload: bytes) -> dict:
    try:
        event = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid Stripe event JSON") from exc
    if not isinstance(event, dict):
        raise ValueError("Invalid Stripe event object")
    return event
