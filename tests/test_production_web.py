"""Production UI exercises real persistence and paid routes without model calls."""
from urllib.parse import urlencode

import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_queue_to_series_journey_and_free_gates():
    store = await SqliteStore.open(':memory:')
    settings = Settings(MARKOV_API_KEYS={'plus-key': 'plus', 'free-key': 'free'},
        MARKOV_WEB_SESSION_SECRET='production-test-only', MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_free',
        MARKOV_OWNER_ENTITLEMENT_PROFILES={'plus': 'cloud_plus'})
    for owner in ['plus', 'free']:
        case = await store.create_research_case(owner_id=owner, title='Example seed', original_input='A test source', input_type='text', purpose='research', constraints={})
        source = await store.add_source(
            url=f'https://example.invalid/{owner}', title='Stored test source',
            source_type='article', content_text='Fixture text', summary='Fixture only')
        await store.add_research_case_source(
            research_case_id=case.id, source_id=source.id, source_role='seed')
        for index in range(32):
            await store.add_research_topic(research_case_id=case.id, title=f'Example story {index}', focus='A distinct connection to follow', importance=1, claim_ids=[])
    app = create_app(store=store, settings=settings)
    async def post(client, path, values):
        return await client.post(path, content=urlencode(values, doseq=True), headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/app')).status_code == 303
            await post(client, '/app/login', {'api_key': 'plus-key'})
            page = await client.get('/app')
            assert page.status_code == 200 and page.text.count('data-production-row') == 30
            assert (await client.get('/app?page=2')).text.count('data-production-row') == 2
            keys = [r['item_key'] for r in (await store.production_ideas('plus'))[:3]]
            moved = await post(client, '/app/queue/actions', {'item': keys, 'action': 'move', 'status': 'shortlisted'})
            assert moved.status_code == 303
            assert (await client.get('/app?status=shortlisted')).text.count('data-production-row') == 3
            assert 'No stories match this view' in (await client.get('/app?q=missing')).text
            export = await post(client, '/app/queue/actions', {'item': keys, 'action': 'export'})
            assert 'markov-shortlist.md' in export.headers['content-disposition']
            assert 'not generated talking points' in export.text
            assert 'https://example.invalid/plus' in export.text
            builder = await post(client, '/app/queue/actions', {'item': keys, 'action': 'series'})
            assert 'Create 3-episode series' in builder.text
            created = await post(client, '/app/series', {'item': keys, 'title': 'Example series', 'premise': 'Follow the connections between these ideas.'})
            location = created.headers['location']
            assert 'Episode 1' in (await client.get(location)).text
            await post(client, location + '/episodes', {'item': keys[0], 'action': 'recorded'})
            detail = await client.get(location)
            assert '1 / 3 recorded' in detail.text and 'Up next · Episode 2' in detail.text
            await post(client, location + '/episodes', {'item': keys[2], 'action': 'up'})
            assert (await store.story_series('plus'))[0]['episodes'][1]['item_key'] == keys[2]
            cross_origin = await client.post('/app/queue/actions', content='action=move', headers={'Origin': 'https://outside.example'})
            assert cross_origin.status_code == 403
            await post(client, '/app/login', {'api_key': 'free-key'})
            assert (await client.get(location)).status_code == 404
            own_keys = [r['item_key'] for r in (await store.production_ideas('free'))[:2]]
            for action in ['series', 'talking_points']:
                locked = await post(client, '/app/queue/actions', {'item': own_keys, 'action': action})
                assert locked.status_code == 303 and locked.headers['location'] == '/app/upgrade'
            locked = await post(client, '/app/series', {'item': own_keys, 'title': 'Attempted bypass', 'premise': 'These are free account ideas.'})
            assert locked.headers['location'] == '/app/upgrade'
            assert await store.story_series('free') == []
            assert (await post(client, '/app/queue/actions', {'item': keys, 'action': 'move'})).status_code == 400
    finally:
        await store.close()
