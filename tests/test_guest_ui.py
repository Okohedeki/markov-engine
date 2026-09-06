"""The guest demo must be public without making customer routes public."""
import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_guest_dashboard_does_not_bypass_customer_auth():
    store = await SqliteStore.open(':memory:')
    app = create_app(store=store, settings=Settings(MARKOV_API_KEYS={'test': 'customer'}, MARKOV_WEB_SESSION_SECRET='guest-test-secret'))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            for path in ('/demo', '/demo/'):
                response = await client.get(path)
                assert response.status_code == 200
                assert 'data-storage-key="markov-guest-studio-v1"' in response.text
                assert 'data-save-draft' in response.text
                assert 'data-guest-reset-dialog' in response.text
                assert not response.headers.get('set-cookie')
            private = await client.get('/app', follow_redirects=False)
            assert private.status_code in (303, 307, 401)
    finally:
        await store.close()
