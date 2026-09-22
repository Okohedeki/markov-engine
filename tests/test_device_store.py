import asyncio

import pytest

from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_pairing_is_single_use_persistent_owner_scoped_and_revocable(tmp_path):
    path = str(tmp_path / 'service.db')
    store = await SqliteStore.open(path)
    invitation = await store.devices.invite('alice')
    results = await asyncio.gather(
        store.devices.redeem(invitation['code'], 'My phone'),
        store.devices.redeem(invitation['code'], 'Replay attempt'),
    )
    assert sum(result is not None for result in results) == 1
    session = next(result for result in results if result)
    raw = await (await store._conn.execute('SELECT code_hash, session_hash FROM paired_devices')).fetchone()
    assert raw[0] is None and raw[1] != session['token']
    assert await store.devices.authenticate(session['token'], 'bob') is None
    await store.close()
    store = await SqliteStore.open(path)
    try:
        assert (await store.devices.authenticate(session['token'], 'alice'))['id'] == session['id']
        devices = await store.devices.devices('alice')
        assert len(devices) == 1 and devices[0]['name'] == session['name']
        assert not await store.devices.revoke('bob', session['id'])
        assert await store.devices.revoke('alice', session['id'])
        assert await store.devices.authenticate(session['token'], 'alice') is None
        assert await store.devices.redeem(invitation['code'], 'Reuse after revocation') is None
        assert await store.devices.devices('alice') == []
    finally:
        await store.close()
