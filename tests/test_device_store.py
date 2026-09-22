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


@pytest.mark.asyncio
async def test_new_invitations_replace_old_codes_and_expiry_is_enforced(monkeypatch):
    import time
    store = await SqliteStore.open(':memory:')
    try:
        first = await store.devices.invite('alice')
        second = await store.devices.invite('alice')
        assert await store.devices.redeem(first['code'], 'Old QR') is None
        stamp = int(time.time())
        monkeypatch.setattr('markov_engine.device_store.time.time', lambda: stamp + 301)
        assert await store.devices.redeem(second['code'], 'Expired QR') is None
        third = await store.devices.invite('alice')
        session = await store.devices.redeem(third['code'], 'Connected')
        assert session is not None
        monkeypatch.setattr('markov_engine.device_store.time.time', lambda: stamp + 91 * 86400)
        assert await store.devices.authenticate(session['token'], 'alice') is None
        assert await store.devices.devices('alice') == []
    finally:
        await store.close()
