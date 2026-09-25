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


@pytest.mark.asyncio
async def test_public_example_and_pwa_do_not_modify_private_archives():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'alice'}, MARKOV_WEB_SESSION_SECRET='test')
    app = create_app(store=store, settings=settings)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            page = await client.get('/')
            assert 'Your bookmarks should' in page.text and 'when they matter.' in page.text
            assert page.text.count('<h1') == 1 and 'Illustrative example' in page.text
            for suffix in ['', '?view=library', '?view=threads', '?view=projects', '?view=you',
                           '?view=search&q=tools', '?item=reward-hacking']:
                page = await client.get('/demo' + suffix)
                assert page.status_code == 200
                assert 'notes and activity below are illustrative' in page.text
                assert not page.headers.get('set-cookie')
            manifest = (await client.get('/app/manifest.webmanifest')).json()
            assert manifest['start_url'] == '/app'
            assert manifest['share_target']['action'] == '/app/share'
            png_sizes = {icon['sizes'] for icon in manifest['icons'] if icon['type'] == 'image/png'}
            assert {'192x192', '512x512'} <= png_sizes
            assert any(icon['purpose'] == 'maskable' for icon in manifest['icons'])
            for icon in manifest['icons']:
                assert (await client.get(icon['src'])).status_code == 200, icon['src']
            worker = await client.get('/app/sw.js')
            assert worker.status_code == 200 and worker.headers['service-worker-allowed'] == '/app'
            shared = await client.get('/app/share?url=https://example.com')
            assert 'Sign in to save' in shared.text
            assert await store.bookmarks.items('alice') == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_merge_transfers_visible_saves_and_split_preserves_exclusions():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'alice'}, MARKOV_WEB_SESSION_SECRET='test')
    app = create_app(store=store, settings=settings)
    try:
        first, _ = await store.bookmarks.save('alice', 'https://example.com/first')
        removed, _ = await store.bookmarks.save('alice', 'https://example.com/removed')
        keep, exclude = first['bookmark_id'], removed['bookmark_id']
        await store.bookmarks.collections('alice', collection={'id': 'source', 'kind': 'thread',
            'title': 'Source', 'bookmark_ids': [keep, exclude], 'excluded_ids': [exclude]})
        await store.bookmarks.collections('alice', collection={'id': 'target', 'kind': 'thread',
            'title': 'Target', 'bookmark_ids': [], 'excluded_ids': [keep]})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            await client.post('/app/login', data={'api_key': 'key'})
            merged = await client.post('/app/collections', data={'action': 'merge', 'id': 'source', 'target': 'target'})
            assert merged.status_code == 303
            rows = {row['id']: row for row in await store.bookmarks.collections('alice')}
            assert rows['source']['hidden']
            assert rows['target']['bookmark_ids'] == [keep] and rows['target']['excluded_ids'] == []
            split = await client.post('/app/collections', data={'action': 'split', 'id': 'target',
                'title': 'Checkpoint notes', 'pick_' + keep: 'on', 'pick_' + exclude: 'on'})
            assert split.status_code == 303
            rows = await store.bookmarks.collections('alice')
            new = next(row for row in rows if row['title'] == 'Checkpoint notes')
            target = next(row for row in rows if row['id'] == 'target')
            assert new['bookmark_ids'] == [keep]
            assert target['bookmark_ids'] == [] and target['excluded_ids'] == [keep]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_saving_a_link_again_reports_whether_the_new_thought_was_added():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'key': 'alice'}, MARKOV_WEB_SESSION_SECRET='test')
    app = create_app(store=store, settings=settings)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            await client.post('/app/login', data={'api_key': 'key'})
            json_accept = {'Accept': 'application/json'}
            first = await client.post('/app/bookmarks', data={'url': 'https://example.com/a', 'note': 'First'},
                                      headers=json_accept)
            assert first.status_code == 201 and first.json()['next'].endswith('?saved=1')
            again = await client.post('/app/bookmarks', data={'url': 'https://example.com/a?utm_source=x',
                                      'note': 'Second'}, headers=json_accept)
            assert again.status_code == 200 and again.json()['note_added']
            page = await client.get(again.json()['next'])
            assert 'Your new thought was added' in page.text
            plain = await client.post('/app/bookmarks', data={'url': 'https://example.com/a', 'note': ''})
            assert plain.status_code == 303 and plain.headers['location'].endswith('?saved=again')
            page = await client.get(plain.headers['location'])
            assert 'Already in your library.' in page.text and 'link and thought are safe' not in page.text
            assert (await store.bookmarks.items('alice'))[0]['user_note'] == 'First\n\nSecond'
    finally:
        await store.close()
