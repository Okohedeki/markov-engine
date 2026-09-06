"""Production queue and paid series routes using the existing session boundary."""
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi import APIRouter, HTTPException

from markov_engine.billing import credit_cost
from markov_engine.entitlements import require_paid_feature

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


    return router
