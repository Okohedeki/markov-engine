"""Conservative URL identity: remove tracking, preserve content-selecting parameters."""
import ipaddress
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def canonicalize(raw):
    if not isinstance(raw, str) or len(raw) > 8192:
        raise ValueError('Please enter a valid public URL.')
    raw = raw.strip()
    if any(ord(char) < 32 for char in raw):
        raise ValueError('The URL contains invalid characters.')
    try:
        parts = urlsplit(raw)
        port = parts.port
        host = (parts.hostname or '').encode('idna').decode().lower().rstrip('.')
    except (ValueError, UnicodeError):
        raise ValueError('Please enter a valid public URL.') from None
    if (parts.scheme not in {'http', 'https'} or not host or parts.username
            or parts.password or port not in {None, 80, 443}):
        raise ValueError('Use a public http or https link without credentials.')
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Private network links cannot be imported.')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('Private network links cannot be imported.')
    except ValueError as exc:
        if 'Private' in str(exc):
            raise
    host = host.removeprefix('www.')
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith('utm_')
             and key.lower() not in {'fbclid', 'gclid', 'mc_cid', 'mc_eid'}]
    path = parts.path or '/'
    if host in {'youtu.be', 'youtube.com', 'm.youtube.com'}:
        video = path.strip('/') if host == 'youtu.be' else dict(query).get('v')
        if path.startswith(('/shorts/', '/embed/')):
            video = path.split('/')[2]
        if video:
            host, path, query = 'youtube.com', '/watch', [('v', video)]
    if host == 'twitter.com':
        host = 'x.com'
    netloc = f'[{host}]' if ':' in host else host
    if port and port != (443 if parts.scheme == 'https' else 80):
        netloc += f':{port}'
    return urlunsplit((parts.scheme, netloc, path, urlencode(query), ''))
