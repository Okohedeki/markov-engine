"""Production queue and paid series routes using the existing session boundary."""
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from markov_engine.billing import credit_cost
from markov_engine.entitlements import require_paid_feature, resolve_entitlements
from markov_engine.research import convert_case_artifact

STATUSES = {'all': 'All ideas', 'ideas': 'To explore', 'shortlisted': 'Shortlisted', 'ready': 'Ready to record', 'recorded': 'Recorded'}


async def queue_context(store, owner_id, request, settings):
    rows = await store.production_ideas(owner_id)
    counts = {key: sum(row['status'] == key for row in rows) for key in STATUSES}
    counts['all'] = len(rows)
    state = request.query_params.get('status', 'all')
    state = state if state in STATUSES else 'all'
    query = request.query_params.get('q', '').strip()[:200]
    filtered = [r for r in rows if (state == 'all' or r['status'] == state)
                and (not query or query.casefold() in f"{r['title']} {r['angle']} {r['source_title']}".casefold())]
    pages = max(1, (len(filtered) + 29) // 30)
    try:
        page = max(1, min(int(request.query_params.get('page', '1')), pages))
    except ValueError:
        page = 1
    for row in filtered:
        parsed = urlparse(row['original_input'])
        row['source_host'] = parsed.hostname if parsed.scheme in {'http', 'https'} else 'Your source'
        row['destination'] = f"/app/artifacts/{row['artifact_id']}" if row['artifact_id'] else '/app/signals'
    def link(**values):
        return '/app?' + urlencode({'status': state, 'q': query, **values})
    return dict(items=filtered[(page-1)*30:page*30], counts=counts, statuses=STATUSES,
        filters=[{'key': key, 'label': label, 'count': counts[key], 'url': link(status=key)} for key, label in STATUSES.items()],
        state=state, query=query, page=page, pages=pages, result_count=len(filtered),
        previous_url=link(page=page-1), next_url=link(page=page+1),
        series_count=len(await store.story_series(owner_id)), talking_point_cost=credit_cost('script', 'instant', settings),
        notice=request.query_params.get('notice', '')[:300])


def create_production_router(*, settings, owner, render):
    router = APIRouter()

    async def form(request):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Cross-origin changes are not accepted.')
        raw = await request.body()
        if len(raw) > 32_000:
            raise HTTPException(413, 'This selection is too large.')
        return parse_qs(raw.decode('utf-8', errors='replace'))

    def paid(owner_id, feature):
        require_paid_feature(owner_id, feature, settings=settings)

    def error(request, message):
        result = render(request, 'error.html', title='Could not update your production queue', message=message)
        result.status_code = 400
        return result

    async def common(request, owner_id):
        return dict(active='series', account=await request.app.state.store.get_credit_account(owner_id),
                    entitlements=resolve_entitlements(owner_id, settings=settings))

    @router.get('/app/upgrade')
    async def upgrade(request: Request):
        owner_id = owner(request)
        return render(request, 'upgrade.html', **await common(request, owner_id))

    @router.post('/app/queue/actions')
    async def queue_action(request: Request):
        owner_id = owner(request)
        values = await form(request)
        action = values.get('action', ['move'])[0]
        keys = values.get('item', [])
        store = request.app.state.store
        try:
            if action in {'series', 'talking_points'}:
                paid(owner_id, 'story_mode' if action == 'series' else 'talking_points')
            rows = await store.selected_production_ideas(owner_id, keys)
            if action == 'move':
                await store.move_production_ideas(owner_id, keys, values.get('status', ['shortlisted'])[0])
                notice = f'{len(rows)} ideas moved. You can change their status at any time.'
            elif action == 'export':
                lines = ['# Markov story shortlist', '', 'Story directions and sources, not generated talking points.']
                for row in rows:
                    lines.extend(['', f"## {row['title']}", row['angle'], '', 'Sources:'])
                    sources = await store.list_research_case_sources(row['case_id'])
                    linked = False
                    for source in sources:
                        if urlparse(source.get('url') or '').scheme in {'http', 'https'}:
                            lines.append(f"- {source.get('title') or 'Original source'}: {source['url']}")
                            linked = True
                    if not linked:
                        lines.append('- No linked source recorded yet; verify this idea before publishing.')
                return Response('\n'.join(lines), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="markov-shortlist.md"'})
            elif action == 'series':
                if not 2 <= len(rows) <= 30:
                    raise ValueError('Select 2–30 ideas to build a series.')
                return render(request, 'series.html', series=[], selected=rows, **await common(request, owner_id))
            elif action == 'talking_points':
                if len(rows) > 30:
                    raise ValueError('Develop at most 30 ideas in a batch.')
                if any(row['research_status'] != 'completed' for row in rows):
                    raise ValueError('Wait for research to finish before developing this batch. No talking points were generated.')
                completed = 0
                for row in rows:
                    try:
                        await convert_case_artifact(store, case_id=row['case_id'], owner_id=owner_id, mode='script',
                            constraints={'selected_topic_id': row['topic_id']} if row['topic_id'] else {}, settings=settings)
                        completed += 1
                    except ValueError as exc:
                        return error(request, f'{completed} of {len(rows)} outputs completed. Existing outputs are in Talking points. Remaining ideas were not developed: {exc}')
                return RedirectResponse('/app/plans', 303)
            else:
                raise ValueError('Choose a supported batch action.')
        except ValueError as exc:
            if 'paid feature' in str(exc):
                return RedirectResponse('/app/upgrade', 303)
            return error(request, str(exc))
        return RedirectResponse('/app?' + urlencode({'notice': notice}), 303)

    @router.get('/app/series')
    async def series_list(request: Request):
        owner_id = owner(request)
        return render(request, 'series.html', series=await request.app.state.store.story_series(owner_id),
                      selected=[], **await common(request, owner_id))

    @router.post('/app/series')
    async def create_series(request: Request):
        owner_id = owner(request)
        values = await form(request)
        try:
            paid(owner_id, 'story_mode')
            series_id = await request.app.state.store.create_story_series(owner_id, values.get('item', []),
                values.get('title', [''])[0], values.get('premise', [''])[0])
        except ValueError as exc:
            if 'paid feature' in str(exc):
                return RedirectResponse('/app/upgrade', 303)
            return error(request, str(exc))
        return RedirectResponse(f'/app/series/{series_id}', 303)


    return router
