"""Paid capabilities are enforced before generating, recording or charging."""
import pytest

from markov_engine.branching import follow_connection_into_script
from markov_engine.config import Settings
from markov_engine.entitlements import require_paid_feature, resolve_entitlements
from markov_engine.jobs import submit_job
from markov_engine.research import convert_case_artifact
from markov_engine.store.sqlite import SqliteStore


def test_default_accounts_are_not_silently_pro():
    assert Settings.model_fields['default_entitlement_profile'].default == 'cloud_free'
    for profile in ['cloud_free', 'community']:
        settings = Settings(MARKOV_DEFAULT_ENTITLEMENT_PROFILE=profile)
        value = resolve_entitlements('owner', settings=settings)
        assert not value.talking_points and not value.story_mode
        for feature in ['talking_points', 'story_mode']:
            with pytest.raises(ValueError, match='paid feature'):
                require_paid_feature('owner', feature, settings=settings)
    for profile in ['cloud_plus', 'cloud_pro', 'verified_add_on']:
        settings = Settings(MARKOV_DEFAULT_ENTITLEMENT_PROFILE=profile)
        require_paid_feature('owner', 'talking_points', settings=settings)
        require_paid_feature('owner', 'story_mode', settings=settings)


@pytest.mark.asyncio
async def test_free_cannot_generate_through_any_script_entry_point():
    settings = Settings(MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_free', MARKOV_OPENING_CREDITS=1000)
    store = await SqliteStore.open(':memory:')
    try:
        with pytest.raises(ValueError, match='paid feature'):
            await submit_job(store, owner_id='free', mode='script', review_level='instant',
                             inputs=[{'type': 'text', 'value': 'A starting story'}], settings=settings)
        with pytest.raises(ValueError, match='paid feature'):
            await convert_case_artifact(store, case_id=1, owner_id='free', mode='script', settings=settings)
        with pytest.raises(ValueError, match='paid feature'):
            await follow_connection_into_script(store, connection_id=1, owner_id='free', settings=settings)
        assert await store.list_jobs(owner_id='free') == []
        assert await store.list_research_cases(owner_id='free') == []
        assert await store.list_usage_events(owner_id='free') == []
        assert (await store.get_credit_account('free')).balance == 0
        job, created = await submit_job(store, owner_id='free', mode='research', review_level='instant',
                                        inputs=[{'type': 'text', 'value': 'Find connected stories'}], settings=settings)
        assert created and job.mode == 'research'
    finally:
        await store.close()
