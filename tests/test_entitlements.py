"""Plans limit capacity, never the trust floor."""

from __future__ import annotations

import pytest

from markov_engine.billing import reserve_job_credits
from markov_engine.config import Settings
from markov_engine.entitlements import PROFILES, resolve_entitlements
from markov_engine.store.sqlite import SqliteStore


def test_every_profile_keeps_accuracy_citations_uncertainty_and_sources():
    for profile in PROFILES:
        value = resolve_entitlements(
            "owner",
            settings=Settings(MARKOV_DEFAULT_ENTITLEMENT_PROFILE=profile),
        )
        assert value.citations is True
        assert value.accuracy_controls is True
        assert value.uncertainty_labels is True
        assert value.source_packet is True


def test_deployment_cannot_override_the_trust_floor_off():
    settings = Settings(
        MARKOV_DEFAULT_ENTITLEMENT_PROFILE="cloud_free",
        MARKOV_ENTITLEMENT_OVERRIDES={"cloud_free": {"citations": False}},
    )
    with pytest.raises(ValueError, match="citations cannot be disabled"):
        resolve_entitlements("owner", settings=settings)


@pytest.mark.asyncio
async def test_community_is_unmetered_but_still_records_the_operation():
    settings = Settings(MARKOV_DEFAULT_ENTITLEMENT_PROFILE="community")
    store = await SqliteStore.open(":memory:")
    try:
        cost = await reserve_job_credits(
            store,
            owner_id="self-hosted",
            job_id="job-community",
            mode="script",
            review_level="instant",
            settings=settings,
        )
        assert cost == 0
        assert (await store.get_credit_account("self-hosted")).balance == 0
        assert [
            item.event_type
            for item in await store.list_usage_events(owner_id="self-hosted")
        ] == ["unmetered_job_reserved"]
    finally:
        await store.close()


def test_limits_are_configurable_without_changing_profile_code():
    settings = Settings(
        MARKOV_DEFAULT_ENTITLEMENT_PROFILE="cloud_free",
        MARKOV_ENTITLEMENT_OVERRIDES={
            "cloud_free": {"max_connections": 7, "retention_days": 45}
        },
    )
    value = resolve_entitlements("owner", settings=settings)
    assert value.max_connections == 7
    assert value.retention_days == 45
