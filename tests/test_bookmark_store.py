"""Persistence regressions for the personal archive."""
import asyncio

import pytest

from markov_engine.bookmark_store import CLAIM_SQL
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
        assert duplicate['user_note'] == 'My thought\n\nreplacement'
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
async def test_saving_again_adds_a_new_thought_and_fills_missing_text_only():
    store = await SqliteStore.open(':memory:')
    try:
        archive = store.bookmarks
        item, _ = await archive.save('alice', 'https://www.tiktok.com/@a/video/1')
        await archive.update('alice', item['bookmark_id'], {'processing_state': 'partial'})
        # First thought on an empty note, then a repeated tap and an empty re-save change nothing.
        for note in ['Watch the ending', 'Watch the ending', '']:
            again, created = await archive.save('alice', 'https://www.tiktok.com/@a/video/1', note=note)
            assert not created and again['user_note'] == 'Watch the ending'
        again, _ = await archive.save('alice', 'https://www.tiktok.com/@a/video/1', note='Relevant to onboarding',
                                      content='0:03 The pitch starts here')
        assert again['user_note'] == 'Watch the ending\n\nRelevant to onboarding'
        assert again['content'] == '0:03 The pitch starts here' and again['supplied_content']
        assert again['processing_state'] == 'pending'
        # Existing source text is never replaced by a later paste.
        await archive.update('alice', item['bookmark_id'], {'processing_state': 'ready'})
        again, _ = await archive.save('alice', 'https://www.tiktok.com/@a/video/1', content='Different text')
        assert again['content'] == '0:03 The pitch starts here' and again['processing_state'] == 'ready'
        # Another owner's re-save never touches this archive.
        await archive.save('bob', 'https://www.tiktok.com/@a/video/1', note='Bob only')
        assert 'Bob' not in (await archive.items('alice'))[0]['user_note']
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
async def test_capture_can_commit_while_worker_claims_a_bookmark(monkeypatch):
    store = await SqliteStore.open(':memory:')
    try:
        archive = store.bookmarks
        first, _ = await archive.save('alice', 'https://example.com/queued')
        execute = archive.conn._execute
        captured = []

        async def concurrent_request(function, *args, **kwargs):
            result = await execute(function, *args, **kwargs)
            # Force a request into the gap after the worker's database call,
            # before its coroutine resumes. A live RETURNING cursor breaks commit.
            if args and isinstance(args[0], str) and 'RETURNING payload' in args[0]:
                item, created = await archive.save('alice', 'https://example.com/concurrent')
                assert created
                captured.append(item)
            return result

        monkeypatch.setattr(archive.conn, '_execute', concurrent_request)
        claimed = await archive.claim_pending()
        assert claimed['bookmark_id'] == first['bookmark_id']
        assert claimed['processing_state'] == 'processing'
        assert len(captured) == 1
        items = await archive.items('alice')
        assert len(items) == 2
        assert next(item for item in items if item['bookmark_id'] == captured[0]['bookmark_id'])['processing_state'] == 'pending'
    finally:
        await store.close()


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


@pytest.mark.asyncio
async def test_idle_queue_poll_reads_the_state_index_not_every_payload():
    store = await SqliteStore.open(':memory:')
    try:
        plan = ' '.join(row[-1] for row in await store.bookmarks.conn.execute_fetchall(
            'EXPLAIN QUERY PLAN ' + CLAIM_SQL, ('now',)))
        assert 'bookmarks_processing_state' in plan
        assert 'SCAN bookmarks' not in plan
    finally:
        await store.close()
