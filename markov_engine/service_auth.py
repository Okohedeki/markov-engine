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
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('MARKOV_SERVICE_URL must be a trusted HTTPS origin reachable from your phone, without a path.')
    return value


def local_console(request):
    return bool(request.client and request.client.host in LOOPBACK
        and request.url.hostname in LOOPBACK
        and not any(name in request.headers for name in (
            'forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto',
            'tailscale-user-login', 'tailscale-user-name',
        )))
