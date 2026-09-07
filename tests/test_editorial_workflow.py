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


def test_draft_requires_retained_citations():
    from copy import deepcopy
    from markov_engine.story_drafts import validate_story_draft

    passage = 'A retained passage that explains the labor dispute.'
    packet = {'findings': [{'evidence_id': 1, 'passage': passage,
                            'url': 'https://example.invalid/labor'}]}
    result = {'beats': [{'heading': heading, 'text': 'Draft text needs editorial review.',
                        'citations': [{'evidence_id': 1, 'quote': passage}]}
                       for heading in ('Opening', 'Development', 'Close')]}
    sections = validate_story_draft(result, packet)
    assert len(sections) == 3
    assert all(s['statement_type'] == 'unreviewed_draft' for s in sections)
    assert all(s['evidence_ids'] == [1] and passage in s['source_notes'] for s in sections)
    for field, invalid in [('evidence_id', 99), ('quote', 'An invented quotation not in the source.')]:
        broken = deepcopy(result)
        broken['beats'][0]['citations'][0][field] = invalid
        with pytest.raises(ValueError):
            validate_story_draft(broken, packet)
    with pytest.raises(ValueError):
        validate_story_draft({'beats': []}, packet)


@pytest.mark.asyncio
async def test_paid_drafts_keep_selected_evidence_and_deduplicate_requests(monkeypatch):
    import asyncio
    import markov_engine.story_drafts as drafts
    from markov_engine.config import Settings
    from markov_engine.research import convert_case_artifact

    calls = []
    async def writer(store, case_id, story, constraints):
        calls.append(story['item_key'])
        await asyncio.sleep(0.01)
        finding = story['story_packet']['findings'][0]
        return {'beats': [{'heading': heading, 'text': story['title'], 'citations': [
            {'evidence_id': finding['evidence_id'], 'quote': finding['passage']}]
        } for heading in ('Opening', 'Development', 'Close')]}

    monkeypatch.setattr(drafts, 'request_story_draft', writer)
    settings = Settings(_env_file=None, MARKOV_DEFAULT_ENTITLEMENT_PROFILE='cloud_plus', MARKOV_OPENING_CREDITS=100)
    store = await SqliteStore.open(':memory:')
    try:
        case, event = await seed_angles(store)
        async def develop(index):
            return await convert_case_artifact(store, case_id=case.id, owner_id='creator',
                mode='script', constraints={'selected_story_key': f'angle:{event.id}:{index}'}, settings=settings)
        first, duplicate = await asyncio.gather(develop(0), develop(0))
        assert first[1] and not duplicate[1] and first[0].id == duplicate[0].id
        balance = (await store.get_credit_account('creator')).balance
        second, created = await develop(1)
        assert created and second.id != first[0].id and len(calls) == 2
        assert second.title == 'Distinct story 2' and second.status == 'draft'
        assert second.branch_key == f'angle:{event.id}:1'
        assert second.structured_content['story_packet']['findings'][0]['evidence_id'] == 2
        assert all(s.get('evidence_ids', [2]) == [2] for s in second.structured_content['sections'])
        assert (await store.get_credit_account('creator')).balance < balance
        for owner, key in [('other', f'angle:{event.id}:0'), ('creator', 'angle:999:0')]:
            with pytest.raises(ValueError):
                await convert_case_artifact(store, case_id=case.id, owner_id=owner, mode='script',
                    constraints={'selected_story_key': key}, settings=settings)
        assert len(calls) == 2
    finally:
        await store.close()
