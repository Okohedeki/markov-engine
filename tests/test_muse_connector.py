"""Protocol, isolation, and read-only contract checks for the Muse adapter."""
import httpx
import pytest

from markov_engine.api import create_app
from markov_engine.config import Settings
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_muse_mcp_authentication_retrieval_and_read_only_scope():
    store = await SqliteStore.open(':memory:')
    settings = Settings(_env_file=None, MARKOV_API_KEYS={'full-key': 'alice'},
        MARKOV_MUSE_API_KEYS={'connector-alice': 'alice', 'connector-bob': 'bob'})
    app = create_app(store=store, settings=settings)
    item, _ = await store.bookmarks.save('alice', 'https://example.com/replay',
        title='Deterministic replay', note='Checkpointing', content='Preserved source text. ' * 1200)
    before = await store.bookmarks.items('alice')
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            async def rpc(method, params=None, token='connector-alice', **kwargs):
                return await client.post('/mcp/muse', json={'jsonrpc': '2.0', 'id': 1,
                    'method': method, 'params': params or {}}, headers={
                    'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream', **kwargs})
            assert (await rpc('tools/list', token='full-key')).status_code == 401
            assert (await rpc('tools/list', Origin='https://evil.example')).status_code == 403
            init = (await rpc('initialize', {'protocolVersion': '2025-11-25'})).json()['result']
            assert init['protocolVersion'] == '2025-11-25'
            tools = (await rpc('tools/list')).json()['result']['tools']
            assert {tool['name'] for tool in tools} == {'search', 'fetch', 'list_threads', 'get_thread', 'rediscover'}
            assert all(tool['annotations']['readOnlyHint'] for tool in tools)
            search = (await rpc('tools/call', {'name': 'search', 'arguments': {'query': 'Checkpointing'}})).json()['result']
            found = search['structuredContent']['results'][0]
            assert found['id'] == item['bookmark_id'] and found['user_note'] == 'Checkpointing'
            assert 'user_id' not in found and 'embeddings' not in found
            fetched = (await rpc('tools/call', {'name': 'fetch', 'arguments': {'id': item['bookmark_id']}})).json()['result']
            assert fetched['structuredContent']['next_offset'] == 20000
            assert len(fetched['structuredContent']['source_text']) == 20000
            foreign = (await rpc('tools/call', {'name': 'fetch', 'arguments': {'id': item['bookmark_id']}},
                                 token='connector-bob')).json()['result']
            assert foreign['isError'] and 'Preserved source text' not in str(foreign)
            invalid = (await rpc('tools/call', {'name': 'search', 'arguments': {'query': 'x', 'limit': -1}})).json()['result']
            assert invalid['isError']
            write = (await rpc('tools/call', {'name': 'delete_save', 'arguments': {'id': item['bookmark_id']}})).json()['result']
            assert write['isError']
            notification = await client.post('/mcp/muse', json={'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                headers={'Authorization': 'Bearer connector-alice'})
            assert notification.status_code == 202 and not notification.content
            assert (await client.get('/mcp/muse', headers={'Authorization': 'Bearer connector-alice'})).status_code == 405
            assert await store.bookmarks.items('alice') == before
            assert (await client.get('/v1/jobs', headers={'Authorization': 'Bearer connector-alice'})).status_code == 401
    finally:
        await store.close()
