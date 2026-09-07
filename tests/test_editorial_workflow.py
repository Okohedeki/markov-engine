"""Stable story identities and owner-isolated selection from stored discovery."""
import pytest

from markov_engine.store.sqlite import SqliteStore


async def seed_angles(store, owner='creator'):
    case = await store.create_research_case(
        owner_id=owner, title='Seed source', original_input='https://example.invalid/seed',
        input_type='url', purpose='research', status='completed',
    )
    findings = [{'evidence_id': i, 'source_id': i, 'claim_id': 1,
                 'url': f'https://example.invalid/{i}', 'title': f'Source {i}',
                 'passage': f'A retained passage for story {i}.', 'locator': 'Paragraph 1'}
                for i in (1, 2)]
    angles = [{'title': f'Distinct story {i}', 'question': f'What changed in story {i}?',
               'new_information': f'New context for story {i}.', 'uncertainty': 'Needs review.',
               'novelty_basis': 'Goes beyond the starting account.', 'why_it_matters': 'Explains a consequence.',
               'support': [{'evidence_id': i, 'quote': f'A retained passage for story {i}.'}],
               'challenge_evidence_ids': [], 'evidence_status': 'single_source_lead'} for i in (1, 2)]
    event = await store.record_usage_event(owner_id=owner, research_case_id=case.id,
        event_type='editorial_discovery', metadata={'status': 'complete', 'angles': angles, 'findings': findings})
    return case, event


@pytest.mark.asyncio
async def test_stories_keep_identity_progress_and_series_across_discovery(tmp_path):
    path = str(tmp_path / 'stories.db')
    store = await SqliteStore.open(path)
    try:
        case, event = await seed_angles(store)
        rows = await store.production_ideas('creator')
        keys = [row['item_key'] for row in rows]
        assert keys == [f'angle:{event.id}:0', f'angle:{event.id}:1']
        assert [r['source_count'] for r in rows] == [1, 1]
        assert rows[0]['story_packet']['findings'][0]['evidence_id'] == 1
        await store.move_production_ideas('creator', keys[:1], 'ready')
        series_id = await store.create_story_series('creator', keys, 'Connected stories', 'Two related but distinct episodes.')
        await store.record_usage_event(owner_id='creator', research_case_id=case.id,
            event_type='editorial_discovery', metadata={'angles': [], 'findings': []})
        assert await store.editorial_ideas('other', keys[0]) == []
        with pytest.raises(ValueError):
            await store.move_production_ideas('other', keys, 'recorded')
        await store.close()
        store = await SqliteStore.open(path)
        assert (await store.selected_production_ideas('creator', keys[:1]))[0]['status'] == 'ready'
        assert [e['item_key'] for e in (await store.story_series('creator', series_id))[0]['episodes']] == keys
    finally:
        await store.close()
