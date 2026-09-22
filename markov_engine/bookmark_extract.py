"""Bounded public-source extraction with pinned public addresses on every redirect."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from markov_engine.bookmark_urls import canonicalize


async def fetch_public(url, *, limit=8_000_000):
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
        for _ in range(6):
            url = canonicalize(url)
            parsed = urlsplit(url)
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            addresses = await asyncio.get_running_loop().getaddrinfo(
                parsed.hostname, port, type=socket.SOCK_STREAM,
            )
            ips = list(dict.fromkeys(address[4][0] for address in addresses))
            if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
                raise ValueError('This source resolves to a private network address.')
            # Connect to the validated IP, retaining TLS verification for the source host.
            pinned = httpx.URL(url).copy_with(host=ips[0])
            headers = {'Host': parsed.netloc, 'User-Agent': 'MarkovBookmark/1.0',
                       'Accept': 'text/html,application/pdf,text/plain,application/json'}
            async with client.stream('GET', pinned, headers=headers,
                    extensions={'sni_hostname': parsed.hostname}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > limit:
                        raise ValueError('This source is too large to extract automatically.')
                return bytes(body), response.headers.get('content-type', ''), url
    raise ValueError('This source redirects too many times.')
