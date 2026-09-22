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

    @router.post('/app/bookmarks')
    async def capture(request: Request):
        identity = owner(request)
        values = await bookmark_form(request)
        try:
            item, created = await request.app.state.store.bookmarks.save(identity, values.get('url', ''),
                title=values.get('title', ''), note=values.get('note', ''), content=values.get('content', ''))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        destination = '/app/bookmarks/' + item['bookmark_id']
        if 'application/json' in request.headers.get('accept', ''):
            return JSONResponse({'created': created, 'url': destination, 'bookmark_id': item['bookmark_id']},
                                status_code=201 if created else 200)
        return RedirectResponse(destination + '?saved=1', 303)

    @router.get('/app/library')
    async def library(request: Request):
        identity = owner(request)
        from markov_engine.bookmark_views import filter_archive
        archive = request.app.state.store.bookmarks
        items = await archive.items(identity)
        context = archive_context(items, await archive.collections(identity), 'library')
        context.update(filtered=filter_archive(items, request.query_params, context['threads'] + context['projects']),
            sources=sorted({item['source_domain'] for item in items}),
            types=sorted({item['source_type'] for item in items}), params=request.query_params,
            view=request.query_params.get('layout') if request.query_params.get('layout') in {'cards', 'compact', 'visual'} else 'cards')
        return render(request, 'memory_library.html', **context)

    @router.get('/app/bookmarks/{bookmark_id}')
    async def detail(bookmark_id: str, request: Request):
        identity = owner(request)
        from markov_engine.bookmark_views import source_context
        archive = request.app.state.store.bookmarks
        items = await archive.items(identity)
        item = next((row for row in items if row['bookmark_id'] == bookmark_id), None)
        if item is None:
            raise HTTPException(404, 'This save was not found in your archive.')
        await archive.record_event(identity, bookmark_id, 'view_history')
        context = archive_context(items, await archive.collections(identity), 'library')
        item, export_text = source_context(item)
        context.update(item=item, export_text=export_text,
            memberships=[row for row in context['threads'] + context['projects']
                         if bookmark_id in {member['bookmark_id'] for member in row['items']}],
            notice='Saved to Markov. Your link and thought are safe.' if request.query_params.get('saved') else '',
            page_title='Saved source')
        return render(request, 'memory_detail.html', **context)

    return router
