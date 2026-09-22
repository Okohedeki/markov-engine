"""Authenticated bookmark routes using Markov's existing identity boundary."""
import datetime as dt
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from markov_engine.bookmark_views import archive_context


async def bookmark_form(request):
    origin = request.headers.get('origin')
    if ((origin and origin.rstrip('/') != str(request.base_url).rstrip('/'))
            or request.headers.get('sec-fetch-site') == 'cross-site'):
        raise HTTPException(403, 'Cross-origin changes are not accepted.')
    if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        raise HTTPException(415, 'Submit this form using URL-encoded fields.')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 2_000_000:
            raise HTTPException(413, 'This source is too large. Save the link first, then add a shorter excerpt.')
    values = parse_qs(raw.decode('utf-8', errors='replace'), keep_blank_values=True)
    return {key: values[-1] for key, values in values.items()}


def create_bookmark_router(*, owner, render):
    router = APIRouter()

    @router.get('/app/memory')
    async def home(request: Request):
        try:
            identity = owner(request)
        except HTTPException:
            return RedirectResponse('/app/login', 303)
        archive = request.app.state.store.bookmarks
        context = archive_context(await archive.items(identity), await archive.collections(identity))
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        for item in context['resurfaced']:
            if not any(event['at'].startswith(today) for event in item['resurface_history']):
                await archive.record_event(identity, item['bookmark_id'], 'resurface_history', item['resurface_reason'])
        response = render(request, 'memory_home.html', **context)
        response.headers['Cache-Control'] = 'no-store'
        return response

    return router
