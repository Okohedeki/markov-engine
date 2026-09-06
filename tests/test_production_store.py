"""Persistent bulk workflow, series sequencing and owner isolation."""
import pytest

from markov_engine.store.sqlite import SqliteStore


async def seed(store, owner='creator', count=35):
    case = await store.create_research_case(owner_id=owner, title='A real source', original_input='https://example.com/story', input_type='url', purpose='research', constraints={})
    for index in range(count):
        await store.add_research_topic(research_case_id=case.id, title=f'Story {index}', focus=f'Investigate connection {index}', importance=1, claim_ids=[])
    return await store.production_ideas(owner)


@pytest.mark.asyncio
async def test_production_queue_supports_more_than_thirty_and_persists(tmp_path):
    path = str(tmp_path / 'production.db')
    store = await SqliteStore.open(path)
    rows = await seed(store)
    assert len(rows) == 35
    keys = [row['item_key'] for row in rows[:30]]
    await store.move_production_ideas('creator', keys, 'shortlisted')
    await store.close()
    store = await SqliteStore.open(path)
    try:
        assert sum(r['status'] == 'shortlisted' for r in await store.production_ideas('creator')) == 30
        await store.move_production_ideas('creator', keys[:3], 'recorded')
        await store.move_production_ideas('creator', keys[:1], 'ideas')
        assert sum(r['status'] == 'recorded' for r in await store.production_ideas('creator')) == 2
        assert await store.production_ideas('other') == []
        with pytest.raises(ValueError):
            await store.move_production_ideas('other', keys, 'ready')
        with pytest.raises(ValueError):
            await store.move_production_ideas('creator', keys + ['topic:999999'], 'ready')
        assert not any(r['status'] == 'ready' for r in await store.production_ideas('creator'))
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_series_sequence_and_next_episode_use_real_queue_state():
    store = await SqliteStore.open(':memory:')
    try:
        rows = await seed(store, count=3)
        keys = [row['item_key'] for row in rows]
        series_id = await store.create_story_series('creator', keys, 'The water loop', 'Follow water reuse across three different settings.')
        assert await store.story_series('other', series_id) == []
        with pytest.raises(ValueError):
            await store.reorder_story_episode('other', series_id, keys[0], 'down')
        await store.reorder_story_episode('creator', series_id, keys[0], 'down')
        series = (await store.story_series('creator', series_id))[0]
        assert [e['item_key'] for e in series['episodes']] == [keys[1], keys[0], keys[2]]
        await store.move_production_ideas('creator', [keys[1]], 'recorded')
        series = (await store.story_series('creator', series_id))[0]
        assert series['completed'] == 1 and series['next_episode']['item_key'] == keys[0]
        with pytest.raises(ValueError):
            await store.create_story_series('creator', [keys[0], keys[0]], 'Duplicate', 'A meaningful description')
    finally:
        await store.close()
