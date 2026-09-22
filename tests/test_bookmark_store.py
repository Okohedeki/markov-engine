"""Persistence regressions for the personal archive."""
import asyncio

import pytest

from markov_engine.bookmark_urls import canonicalize
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_capture_deduplicates_without_losing_notes_or_owner_isolation():
    store = await SqliteStore.open(':memory:')
    try:
        archive = store.bookmarks
        item, created = await archive.save('alice', 'https://example.com/a?utm_source=x', note='My thought')
        duplicate, repeated = await archive.save('alice', 'https://example.com/a', note='replacement')
        other, _ = await archive.save('bob', 'https://example.com/a')
        assert created and not repeated
        assert duplicate['bookmark_id'] == item['bookmark_id']
        assert duplicate['user_note'] == 'My thought'
        assert other['bookmark_id'] != item['bookmark_id']
        assert await archive.items('bob', item['bookmark_id']) == []
        assert not await archive.update('bob', item['bookmark_id'], {'title': 'stolen'})
        await asyncio.gather(
            archive.update('alice', item['bookmark_id'], {'user_note': 'Edited'}),
            archive.update('alice', item['bookmark_id'], {'summary': 'Interpretation'}),
        )
        updated = (await archive.items('alice', item['bookmark_id']))[0]
        assert updated['user_note'] == 'Edited' and updated['summary'] == 'Interpretation'
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_claim_is_exclusive_and_history_survives_reopen(tmp_path):
    path = str(tmp_path / 'archive.db')
    store = await SqliteStore.open(path)
    item, _ = await store.bookmarks.save('alice', 'https://example.com')
    claims = await asyncio.gather(store.bookmarks.claim_pending(), store.bookmarks.claim_pending())
    assert sum(claim is not None for claim in claims) == 1
    await store.bookmarks.record_event('alice', item['bookmark_id'], 'view_history')
    await store.close()
    store = await SqliteStore.open(path)
    try:
        loaded = (await store.bookmarks.items('alice'))[0]
        assert len(loaded['view_history']) == 1
        assert loaded['processing_state'] == 'processing'
    finally:
        await store.close()


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'javascript:alert(1)',
    'http://127.0.0.1/a', 'http://[::1]/', 'https://user:secret@example.com', 'https://localhost'])
def test_private_and_nonweb_urls_are_rejected(url):
    with pytest.raises(ValueError):
        canonicalize(url)


def test_video_identity_and_content_parameters():
    assert canonicalize('https://youtu.be/abc?t=23') == 'https://youtube.com/watch?v=abc'
    assert canonicalize('https://example.com/a?id=3&utm_medium=x') == 'https://example.com/a?id=3'


@pytest.mark.asyncio
async def test_same_automatic_topic_can_be_curated_independently_by_two_owners():
    import json
    store = await SqliteStore.open(':memory:')
    thread = {'id': 'auto-replay', 'kind': 'thread', 'title': 'Replay', 'bookmark_ids': []}
    try:
        # Cover an existing unnamespaced row from the first archive schema.
        await store.bookmarks.conn.execute('INSERT INTO bookmark_collections VALUES (?, ?, ?, ?)',
            (thread['id'], 'alice', 'thread', json.dumps(thread)))
        await store.bookmarks.conn.commit()
        await store.bookmarks.collections('alice', collection={**thread, 'title': 'Alice’s replay notes'})
        await store.bookmarks.collections('bob', collection={**thread, 'title': 'Bob’s replay notes'})
        await store.bookmarks.collections('bob', collection={**thread, 'title': 'Bob renamed it', 'pinned': True})
        alice = await store.bookmarks.collections('alice')
        bob = await store.bookmarks.collections('bob')
        assert len(alice) == len(bob) == 1
        assert alice[0]['title'] == 'Alice’s replay notes'
        assert bob[0]['title'] == 'Bob renamed it' and bob[0]['pinned']
        assert alice[0]['id'] == bob[0]['id'] == 'auto-replay'
    finally:
        await store.close()
