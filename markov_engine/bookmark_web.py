"""Authenticated bookmark routes using Markov's existing identity boundary."""
import datetime as dt
import json
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from markov_engine.bookmark_views import archive_context


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
