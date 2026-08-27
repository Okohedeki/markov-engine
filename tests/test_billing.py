"""Credit catalog, reservation, and Stripe webhook tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import pytest

from markov_engine.billing import (
    apply_stripe_event,
    catalog,
    reserve_job_credits,
    verify_stripe_signature,
)
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


def _settings(**values) -> Settings:
    defaults = {
        "MARKOV_OPENING_CREDITS": 20,
        "MARKOV_PRODUCT_CREDIT_COSTS": {
            "brief_instant": 1,
            "brief_verified": 2,
            "research_instant": 3,
            "research_verified": 4,
            "script_instant": 5,
            "script_verified": 6,
        },
    }
    defaults.update(values)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_all_six_products_and_idempotent_credit_reservation():
    settings = _settings()
    assert len(catalog(settings)) == 6
    store = await SqliteStore.open(":memory:")
    try:
        first = await reserve_job_credits(
            store,
            owner_id="owner-1",
            job_id="job-1",
            mode="script",
            review_level="verified",
            settings=settings,
        )
        second = await reserve_job_credits(
            store,
            owner_id="owner-1",
            job_id="job-1",
            mode="script",
            review_level="verified",
            settings=settings,
        )
        account = await store.get_credit_account("owner-1")
        assert first == second == 6
        assert account.balance == 14
    finally:
        await store.close()


def test_stripe_signature_verification():
    payload = b'{"id":"evt_fixture"}'
    timestamp = 1_700_000_000
    signature = hmac.new(
        b"whsec_fixture",
        str(timestamp).encode() + b"." + payload,
        hashlib.sha256,
    ).hexdigest()
    assert verify_stripe_signature(
        payload,
        f"t={timestamp},v1={signature}",
        "whsec_fixture",
        now=timestamp,
    )
    assert not verify_stripe_signature(
        payload, f"t={timestamp},v1=bad", "whsec_fixture", now=timestamp
    )


@pytest.mark.asyncio
async def test_completed_stripe_checkout_grants_credits_once():
    store = await SqliteStore.open(":memory:")
    event = {
        "id": "evt_fixture",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_fixture",
                "metadata": {
                    "owner_id": "owner-1",
                    "credits": "25",
                    "pack_name": "starter",
                },
            }
        },
    }
    try:
        await apply_stripe_event(store, json.loads(json.dumps(event)))
        await apply_stripe_event(store, json.loads(json.dumps(event)))
        assert (await store.get_credit_account("owner-1")).balance == 25
        events = await store.list_usage_events(owner_id="owner-1")
        assert [item.event_type for item in events] == ["payment_completed"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_concurrent_credit_debits_cannot_overspend():
    store = await SqliteStore.open(":memory:")
    try:
        await store.ensure_credit_account("owner-1", opening_balance=10)

        async def debit(key):
            return await store.apply_credit_transaction(
                owner_id="owner-1",
                amount=-6,
                reason="concurrent_fixture",
                idempotency_key=key,
            )

        results = await asyncio.gather(
            debit("debit-1"), debit("debit-2"), return_exceptions=True
        )
        assert sum(not isinstance(item, Exception) for item in results) == 1
        assert sum(isinstance(item, ValueError) for item in results) == 1
        assert (await store.get_credit_account("owner-1")).balance == 4
    finally:
        await store.close()
