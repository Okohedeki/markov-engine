"""Retrieval must be explained and interpretation must preserve source evidence."""
import datetime as dt

import pytest

from markov_engine.bookmark_intelligence import archive_threads, rediscover, search_archive
from markov_engine.bookmark_worker import process_bookmark
from markov_engine.store.sqlite import SqliteStore


@pytest.mark.asyncio
async def test_saved_text_is_searchable_without_models_and_forms_threads():
    store = await SqliteStore.open(':memory:')
    try:
        first, _ = await store.bookmarks.save('a', 'https://example.com/first',
            title='Deterministic replay', note='Checkpointing architecture',
            content='Deterministic replay preserves runtime state and makes failures reproducible.')
        await process_bookmark(store.bookmarks, first)
        second, _ = await store.bookmarks.save('a', 'https://example.com/second',
            title='Replay', content='Deterministic replay makes debugging reproducible.')
        await process_bookmark(store.bookmarks, second)
        items = await store.bookmarks.items('a')
        result, mode = await search_archive(items, 'checkpointing architecture')
        assert len(result) == 1 and result[0]['bookmark_id'] == first['bookmark_id']
        assert mode == 'Keyword search'
        assert result[0]['content'] == first['content']
        assert result[0]['user_note'] == first['user_note']
        assert result[0]['inferred_save_reason'] == ''
        threads = archive_threads(items)
        assert any(thread['count'] == 2 for thread in threads)
        hidden = {**threads[0], 'hidden': True}
        assert hidden['id'] not in {thread['id'] for thread in archive_threads(items, [hidden])}
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_rediscovery_requires_a_reason_and_is_bounded():
    store = await SqliteStore.open(':memory:')
    try:
        old, _ = await store.bookmarks.save('a', 'https://example.com/old')
        current = dt.datetime.now(dt.timezone.utc)
        old['saved_at'] = (current - dt.timedelta(days=240)).isoformat()
        assert rediscover([old], current=current) == []
        old['favorite_state'] = True
        assert rediscover([old], current=current)[0]['resurface_label'] == 'You forgot this'
        newer = {**old, 'bookmark_id': 'new', 'saved_at': current.isoformat(), 'concepts': ['Evaluation']}
        old['concepts'] = ['Evaluation']
        resurfaced = rediscover([old, newer], current=current)
        assert resurfaced[0]['related_ids'] == ['new']
        assert '1 item about evaluation this week' in resurfaced[0]['resurface_reason']
        old['view_history'] = [{'at': current.isoformat()}]
        assert rediscover([old, newer], current=current) == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_failed_extraction_never_discards_capture(monkeypatch):
    async def fail(item):
        raise RuntimeError('offline')
    monkeypatch.setattr('markov_engine.bookmark_worker.read_source', fail)
    store = await SqliteStore.open(':memory:')
    try:
        item, _ = await store.bookmarks.save('a', 'https://example.com', note='Keep this')
        await process_bookmark(store.bookmarks, item)
        saved = (await store.bookmarks.items('a'))[0]
        assert saved['processing_state'] == 'partial'
        assert saved['user_note'] == 'Keep this'
        assert 'still saved' in saved['processing_error']
    finally:
        await store.close()
