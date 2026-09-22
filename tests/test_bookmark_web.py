"""Exercise capture, recovery, retrieval, and curation across real HTTP routes."""
import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.bookmark_worker import process_bookmark
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_bookmark_journey_and_cross_owner_boundary():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'alice', 'other': 'bob'},
                        MARKOV_WEB_SESSION_SECRET='bookmark-test')
    app = create_app(store=store, settings=settings)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.get('/app/memory')).status_code == 303
            await client.post('/app/login', data={'api_key': 'key'})
            save = await client.post('/app/bookmarks', data={
                'url': 'https://example.com/replay', 'title': 'Deterministic replay',
                'note': 'Checkpoint architecture', 'content': 'Deterministic replay preserves state for reproducible debugging.'},
                headers={'Accept': 'application/json'})
            assert save.status_code == 201
            path = save.json()['url']
            item = (await store.bookmarks.items('alice'))[0]
            await process_bookmark(store.bookmarks, item)
            for route in ['/app/memory', '/app/library', '/app/threads', '/app/projects', '/app/you', path]:
                response = await client.get(route)
                assert response.status_code == 200, response.text
            page = await client.get('/app/memory/search?q=Checkpoint')
            assert 'Checkpoint architecture' in page.text
            assert 'Contains your exact phrase.' in page.text
            edit = await client.post(path + '/edit', data={'action': 'note', 'note': '<script>alert(1)</script>'})
            assert edit.status_code == 303
            assert '&lt;script&gt;' in (await client.get(path)).text
            exported = await client.get(path + '/export')
            assert 'Source: https://example.com/replay' in exported.text
            assert (await client.post(path + '/edit', data={'action': 'favorite', 'value': 'true'},
                headers={'Origin': 'https://evil.example'})).status_code == 403
            project = await client.post('/app/collections', data={'action': 'create', 'kind': 'project', 'title': 'Workstation'})
            project_id = project.headers['location'].split('/')[-1]
            added = await client.post('/app/collections', data={'action': 'add', 'id': project_id,
                'bookmark_id': item['bookmark_id']})
            assert added.status_code == 303
            project_page = await client.get(project.headers['location'])
            assert project_page.status_code == 200 and 'Deterministic replay' in project_page.text
            await client.post('/app/login', data={'api_key': 'other'})
            assert (await client.get(path)).status_code == 404
            assert (await client.get(path + '/export')).status_code == 404
            assert (await client.post(path + '/edit', data={'action': 'note', 'note': 'stolen'})).status_code == 404
            assert (await client.get(project.headers['location'])).status_code == 404
            assert (await client.get('/app/archive/export')).json()['bookmarks'] == []
    finally:
        await store.close()
