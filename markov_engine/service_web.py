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

    async def device_page(request, invitation=None):
        import qrcode
        from qrcode.image.svg import SvgPathFillImage
        identity = owner(request)
        console = local_console(request)
        devices = await request.app.state.store.devices.devices(identity) if console else []
        for device in devices:
            for field in ('created', 'expires'):
                device[field + '_label'] = dt.datetime.fromtimestamp(
                    device[field + '_at'], dt.timezone.utc).date().isoformat()
        pair_url, qr_data = '', ''
        if invitation:
            pair_url = origin + '/app/pair#code=' + invitation['code']
            svg = qrcode.make(pair_url, image_factory=SvgPathFillImage, border=4).to_string()
            qr_data = 'data:image/svg+xml;base64,' + base64.b64encode(svg).decode()
        context = archive_context([], screen='you')
        context.update(page_title='Your service', service_name=settings.service_name, service_url=origin,
            is_console=console, devices=devices, invitation=invitation, pair_url=pair_url, qr_data=qr_data,
            current_device=getattr(request.state, 'paired_device', None))
        return render(request, 'service_devices.html', **context)

    @router.get('/app/devices')
    async def devices_page(request: Request):
        return await device_page(request)

    @router.post('/app/devices/invite')
    async def invite_device(request: Request):
        identity = owner(request)
        if not local_console(request):
            raise HTTPException(403, 'Create pairing codes on the service computer.')
        await bookmark_form(request)
        if not origin:
            raise HTTPException(409, 'Configure the service HTTPS address before pairing a phone.')
        invitation = await request.app.state.store.devices.invite(identity)
        return await device_page(request, invitation)

    @router.post('/app/devices/revoke')
    async def revoke_device(request: Request):
        identity = owner(request)
        if not local_console(request):
            raise HTTPException(403, 'Manage other devices on the service computer.')
        values = await bookmark_form(request)
        if not await request.app.state.store.devices.revoke(identity, values.get('id', '')):
            raise HTTPException(404, 'Device not found.')
        return RedirectResponse('/app/devices', 303)

    return router
