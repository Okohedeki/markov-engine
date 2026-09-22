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

    @router.post('/app/pair')
    async def connect_device(request: Request):
        if not origin or str(request.base_url).rstrip('/') != origin or request.url.scheme != 'https':
            raise HTTPException(403, 'Open the pairing invitation at your service’s HTTPS address.')
        values = await bookmark_form(request)
        result = await request.app.state.store.devices.redeem(values.get('code', ''), values.get('name', ''))
        if not result or result['owner_id'] != settings.service_owner:
            response = render(request, 'service_pair.html', service_name=settings.service_name,
                service_url=origin, error='This invitation expired or was already used. Scan a fresh code from your computer.')
            response.status_code = 400
            return response
        response = RedirectResponse('/app/you?connected=1', 303)
        response.set_cookie(DEVICE_COOKIE, result['token'], secure=True, httponly=True,
                            samesite='strict', path='/', max_age=90 * 86400)
        return response

    return router
