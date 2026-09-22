"""Personal-service identity: local console administration and paired device sessions."""
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse

DEVICE_COOKIE = '__Host-markov_device'
LOOPBACK = {'127.0.0.1', '::1', 'localhost'}


def service_origin(settings):
    if settings.local_service and (settings.clerk_publishable_key or settings.clerk_secret_key):
        raise ValueError('Personal service mode uses device pairing; remove Clerk configuration for this process.')
    value = settings.service_url.rstrip('/')
    if not value:
        return ''
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.hostname in LOOPBACK
            or parsed.username or parsed.password or '*' in value
            or parsed.path or parsed.query or parsed.fragment or parsed.port == 0
            or any(character.isspace() for character in value)):
        raise ValueError('MARKOV_SERVICE_URL must be a trusted HTTPS origin reachable from your phone, without a path.')
    return value


def local_console(request):
    return bool(request.client and request.client.host in LOOPBACK
        and request.url.hostname in LOOPBACK
        and not any(name in request.headers for name in (
            'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto',
            'tailscale-user-login', 'tailscale-user-name',
        )))


def install_service_auth(app, settings):
    if not settings.local_service:
        return
    origin = service_origin(settings)
    allowed = LOOPBACK | ({urlsplit(origin).hostname} if origin else set())

    @app.middleware('http')
    async def device_session(request, call_next):
        if request.url.hostname not in allowed:
            return JSONResponse({'detail': 'This hostname is not configured for your Markov service.'}, 400)
        request.state.local_console = local_console(request)
        request.state.paired_device = None
        app_page = request.url.path == '/app' or request.url.path.startswith('/app/')
        if app_page and not request.state.local_console and str(request.base_url).rstrip('/') == origin:
            token = request.cookies.get(DEVICE_COOKIE)
            if token:
                request.state.paired_device = await request.app.state.store.devices.authenticate(
                    token, settings.service_owner)
        response = await call_next(request)
        if app_page:
            # Keep the Origin on same-site form POSTs; no-referrer makes it null.
            response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'same-origin',
                                     'X-Frame-Options': 'DENY'})
        return response
