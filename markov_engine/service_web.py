"""Same-origin QR pairing and local-console device management."""
import base64
import datetime as dt

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from markov_engine.bookmark_web import bookmark_form
from markov_engine.bookmark_views import archive_context
from markov_engine.service_auth import DEVICE_COOKIE, local_console, service_origin


def create_service_router(settings, render, owner):
    router = APIRouter()
    if not settings.local_service:
        return router
    origin = service_origin(settings)

    @router.get('/app/pair')
    async def pair_page(request: Request):
        return render(request, 'service_pair.html', service_name=settings.service_name,
                      service_url=origin, error=None)

    return router
