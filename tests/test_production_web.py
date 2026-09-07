"""Production UI exercises real persistence and paid routes without model calls."""
from urllib.parse import urlencode

import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_keyless_preview_is_explicit_and_loopback_only():
    store = await SqliteStore.open(':memory:')
    try:
        for enabled, peer, host, allowed in [
            ('', '127.0.0.1', '127.0.0.1', False),
            ('owner', '127.0.0.1', '127.0.0.1', True),
            ('owner', '127.0.0.1', 'localhost', True),
            ('owner', '192.0.2.1', '127.0.0.1', False),
            ('owner', '127.0.0.1', 'public.example', False),
        ]:
            settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'owner'},
                MARKOV_WEB_SESSION_SECRET='preview-test', MARKOV_LOCAL_PREVIEW_OWNER=enabled)
            app = create_app(store=store, settings=settings)
            transport = httpx.ASGITransport(app=app, client=(peer, 1234))
            async with httpx.AsyncClient(transport=transport, base_url=f'http://{host}') as client:
                response = await client.get('/app', headers={'X-Forwarded-For': '127.0.0.1'})
                assert response.status_code == (200 if allowed else 303)
                login = await client.get('/app/login')
                assert login.status_code == (303 if allowed else 200)
                assert (await client.get('/v1/jobs')).status_code == 401
    finally:
        await store.close()


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
            assert '1 / 3 finished' in detail.text and 'Up next · Episode 2' in detail.text
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


@pytest.mark.asyncio
async def test_pending_batch_never_starts_paid_generation(monkeypatch):
    import markov_engine.production_web as production

    async def unexpected_generation(*args, **kwargs):
        raise AssertionError('Pending research must not reach generation')

    monkeypatch.setattr(production, 'convert_case_artifact', unexpected_generation)
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'owner'},
        MARKOV_WEB_SESSION_SECRET='test-only', MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_plus')
    try:
        case = await store.create_research_case(owner_id='owner', title='Still researching',
            original_input='A test seed', input_type='text', purpose='research', status='pending')
        app = create_app(store=store, settings=settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            await client.post('/app/login', data={'api_key': 'key'})
            response = await client.post('/app/queue/actions',
                data={'action': 'talking_points', 'item': f'case:{case.id}'})
            assert response.status_code == 400
            assert 'Wait for research to finish' in response.text
            assert await store.list_case_artifacts(case.id) == []
            assert (await store.get_credit_account('owner')).balance == 0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_free_composer_and_historical_talking_points():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'owner'},
        MARKOV_WEB_SESSION_SECRET='test-only', MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_free')
    try:
        case = await store.create_research_case(owner_id='owner', title='Source trail',
            original_input='Fixture source', input_type='text', purpose='research', status='completed')
        research = None
        for kind, title in [('research', 'Research-only output'), ('script', 'Previously paid talking points')]:
            item = await store.add_case_artifact(research_case_id=case.id, artifact_type=kind,
                review_level='instant', status='draft', title=title, content='Fixture content',
                structured_content={}, word_count=2, model_used='fixture', generation_cost=0, source_ids=[])
            if kind == 'research':
                research = item
        app = create_app(store=store, settings=settings)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            await client.post('/app/login', data={'api_key': 'key'})
            library = await client.get('/app/plans')
            assert 'Previously paid talking points' in library.text
            assert 'Research-only output' not in library.text
            view = await client.get(f'/app/artifacts/{research.id}')
            options = view.text.split('<select name="mode">', 1)[1].split('</select>', 1)[0]
            assert 'value="script"' not in options
            assert 'value="research"' in options
            assert 'Full talking points and Story Mode require paid access' in view.text
    finally:
        await store.close()
