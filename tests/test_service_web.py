import re
from urllib.parse import urlsplit, parse_qs

import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.service_auth import DEVICE_COOKIE
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_local_console_pairs_a_phone_to_its_own_archive_and_can_revoke_it():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_LOCAL_SERVICE=True, MARKOV_SERVICE_OWNER='my-archive',
        MARKOV_SERVICE_NAME='Home Markov', MARKOV_SERVICE_URL='https://home.example.test')
    app = create_app(store=store, settings=settings)
    local = httpx.ASGITransport(app=app, client=('127.0.0.1', 12345))
    remote = httpx.ASGITransport(app=app, client=('100.64.1.2', 12345))
    try:
        async with httpx.AsyncClient(transport=local, base_url='http://127.0.0.1:8000') as desktop, \
                   httpx.AsyncClient(transport=remote, base_url='https://home.example.test') as phone:
            assert (await desktop.get('/app')).status_code == 200
            assert (await phone.get('/app/login')).headers['location'] == '/app/pair'
            invitation = await desktop.post('/app/devices/invite', data={}, headers={
                'Origin': 'http://127.0.0.1:8000', 'Content-Type': 'application/x-www-form-urlencoded'})
            assert invitation.status_code == 200, invitation.text
            assert 'data:image/svg+xml;base64,' in invitation.text
            assert invitation.headers['cache-control'] == 'no-store'
            assert invitation.headers['referrer-policy'] in {'same-origin', 'no-referrer'}
            url = re.search(r'href="(https://home.example.test/app/pair#code=[^"]+)"', invitation.text)[1]
            code = parse_qs(urlsplit(url).fragment)['code'][0]
            assert not urlsplit(url).query
            connected = await phone.post('/app/pair', data={'code': code, 'name': 'My iPhone'},
                                         headers={'Origin': 'https://home.example.test'})
            assert connected.status_code == 303
            assert 'Secure' in connected.headers['set-cookie'] and 'HttpOnly' in connected.headers['set-cookie']
            assert 'SameSite=strict' in connected.headers['set-cookie']
            token = phone.cookies.get(DEVICE_COOKIE)
            assert (await phone.get('/app/library')).status_code == 200
            capture = await phone.post('/app/bookmarks', data={'url': 'https://example.com/saved-on-phone',
                'note': 'Saved from my paired device'}, headers={'Accept': 'application/json'})
            assert capture.status_code == 201
            assert (await store.bookmarks.items('my-archive'))[0]['user_note'] == 'Saved from my paired device'
            assert (await store.bookmarks.items('other-person')) == []
            assert (await phone.post('/app/pair', data={'code': code})).status_code == 400
            assert (await phone.post('/app/devices/invite', data={})).status_code == 403
            assert (await phone.get('/app/research')).status_code == 303
            assert (await phone.get('/v1/jobs', headers={'Authorization': 'Bearer ' + token})).status_code == 503
            device = (await store.devices.devices('my-archive'))[0]
            assert device['name'] == 'My iPhone'
            rejected = await desktop.post('/app/devices/revoke', data={'id': device['id']},
                                           headers={'Origin': 'https://evil.example'})
            assert rejected.status_code == 403
            assert (await desktop.post('/app/devices/revoke', data={'id': device['id']})).status_code == 303
            assert (await phone.get('/app/library')).status_code == 401
            assert (await desktop.get('/app/library')).status_code == 200
            spoofed = await desktop.post('/app/devices/invite', data={}, headers={'X-Forwarded-For': '100.64.1.2'})
            assert spoofed.status_code == 401
            assert (await phone.get('/app', headers={'Host': 'evil.example'})).status_code == 400
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_phone_can_disconnect_itself_but_cross_origin_pairing_is_rejected():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_LOCAL_SERVICE=True,
        MARKOV_SERVICE_URL='https://home.example.test')
    app = create_app(store=store, settings=settings)
    transport = httpx.ASGITransport(app=app, client=('100.64.1.2', 12345))
    try:
        invite = await store.devices.invite(settings.service_owner)
        async with httpx.AsyncClient(transport=transport, base_url=settings.service_url) as phone:
            rejected = await phone.post('/app/pair', data={'code': invite['code']},
                                        headers={'Origin': 'https://evil.example'})
            assert rejected.status_code == 403
            connected = await phone.post('/app/pair', data={'code': invite['code'], 'name': 'Travel phone'})
            assert connected.status_code == 303
            token = phone.cookies.get(DEVICE_COOKIE)
            you = await phone.get('/app/you')
            assert you.status_code == 200 and 'Your connection' in you.text
            devices = await phone.get('/app/devices')
            assert devices.status_code == 200 and 'Travel phone' in devices.text
            assert 'Create pairing code' not in devices.text
            assert (await phone.post('/app/login', data={'api_key': 'legacy'})).status_code == 410
            disconnected = await phone.post('/app/devices/disconnect', data={},
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
            assert disconnected.status_code == 303
            assert not phone.cookies.get(DEVICE_COOKIE)
            assert not await store.devices.authenticate(token, settings.service_owner)
            assert (await phone.get('/app/library')).status_code == 401
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_phone_reviews_computer_results_and_sends_corrections_back_to_engine():
    from markov_engine.bookmark_worker import process_bookmark
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_LOCAL_SERVICE=True,
        MARKOV_SERVICE_URL='https://home.example.test')
    app = create_app(store=store, settings=settings)
    desktop_transport = httpx.ASGITransport(app=app, client=('127.0.0.1', 12345))
    phone_transport = httpx.ASGITransport(app=app, client=('192.168.1.20', 12345))
    try:
        async with httpx.AsyncClient(transport=desktop_transport, base_url='http://127.0.0.1:8000') as desktop, \
                   httpx.AsyncClient(transport=phone_transport, base_url=settings.service_url) as phone:
            invite = await store.devices.invite(settings.service_owner)
            assert (await phone.post('/app/pair', data={'code': invite['code']})).status_code == 303
            created = await desktop.post('/app/bookmarks', data={
                'url': 'https://example.com/review-cycle', 'title': 'A source to review',
                'content': 'Initial source material processed by the computer for review on the phone.'},
                headers={'Accept': 'application/json'})
            assert created.status_code == 201
            pending = await store.bookmarks.claim_pending()
            bookmark_id = pending['bookmark_id']
            await process_bookmark(store.bookmarks, pending)
            path = '/app/bookmarks/' + bookmark_id
            reviewed = await phone.get(path)
            assert reviewed.status_code == 200 and 'Initial source material' in reviewed.text
            edits = [('note', {'note': 'Reviewed on my phone; useful for my project.'}),
                     ('reason', {'reason': 'My corrected interpretation.'}),
                     ('favorite', {'value': 'true'}),
                     ('content', {'content': 'Corrected source text sent from the phone for the computer to process again.'})]
            for action, values in edits:
                result = await phone.post(path + '/edit', data={'action': action, **values},
                    headers={'Origin': settings.service_url})
                assert result.status_code == 303
            queued = await store.bookmarks.claim_pending()
            assert queued['bookmark_id'] == bookmark_id
            assert queued['user_note'].startswith('Reviewed on my phone')
            assert queued['favorite_state'] is True
            await process_bookmark(store.bookmarks, queued)
            ready = (await store.bookmarks.items(settings.service_owner, bookmark_id))[0]
            assert ready['processing_state'] == 'ready'
            assert ready['inferred_save_reason'] == 'My corrected interpretation.'
            for client in (desktop, phone):
                page = await client.get(path)
                assert page.status_code == 200
                assert 'Corrected source text sent from the phone' in page.text
                assert 'Reviewed on my phone' in page.text
                assert 'My corrected interpretation.' in page.text
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_tunnelled_requests_never_act_as_the_console_or_see_the_api_map():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_LOCAL_SERVICE=True, MARKOV_SERVICE_OWNER='my-archive',
        MARKOV_SERVICE_URL='https://markov.example.test')
    app = create_app(store=store, settings=settings)
    # cloudflared connects from loopback; a tunnel that rewrites Host to localhost
    # still adds its own client headers.
    tunnel = httpx.ASGITransport(app=app, client=('127.0.0.1', 12345))
    try:
        async with httpx.AsyncClient(transport=tunnel, base_url='http://127.0.0.1:8000') as client:
            assert (await client.get('/app')).status_code == 200
            for header in ['CF-Connecting-IP', 'CF-Ray', 'X-Real-IP']:
                response = await client.get('/app/library', headers={header: '203.0.113.9'})
                assert response.status_code == 401, header
            for path in ['/docs', '/redoc', '/openapi.json']:
                assert (await client.get(path)).status_code == 404, path
    finally:
        await store.close()
