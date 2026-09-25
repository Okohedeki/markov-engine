"""Bounded public-source extraction with pinned public addresses on every redirect."""
import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx

from markov_engine.bookmark_urls import public_url


async def resolve(host, port):
    addresses = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(address[4][0] for address in addresses))


async def fetch_public(url, *, limit=8_000_000, transport=None):
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False,
                                 transport=transport) as client:
        for _ in range(6):
            # Validate each hop without canonical identity rewrites: a site that
            # redirects youtube.com to www.youtube.com must not loop.
            url = public_url(url)
            parsed = urlsplit(url)
            port = parsed.port or (443 if parsed.scheme == 'https' else 80)
            ips = await resolve(parsed.hostname, port)
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


async def read_source(item):
    import re
    import trafilatura
    from markov_engine.extract import classify_url
    url = item['canonical_url']
    kind = classify_url(url)
    host = urlsplit(url).hostname
    if host == 'github.com':
        kind = 'github'
    if host.endswith('substack.com'):
        kind = 'newsletter'
    base = {'source_type': kind, 'metadata': {'extracted_from': url}, 'important_passages': []}
    if item.get('supplied_content'):
        text = item['content']
        base['metadata']['content_origin'] = 'User-supplied text; not independently fetched'
        if kind in {'youtube', 'audio', 'media'}:
            base['transcript'] = text
            for match in re.finditer(r'(?m)^(?:(\d+):)?(\d{1,2}):(\d{2})\s+(.+)$', text):
                hours, minutes, seconds, passage = match.groups()
                start = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
                base['important_passages'].append({'text': passage, 'start_seconds': start,
                    'locator': match.group(0).split()[0], 'source_url': url, 'origin': 'supplied'})
        return {**base, 'content': text}
    if kind == 'youtube':
        from markov_engine.bookmark_youtube import read_youtube
        return {**base, **await read_youtube(url, fetch_public)}
    if kind in {'audio', 'media', 'tiktok', 'instagram', 'twitter', 'reddit'}:
        # A landing-page description is not the video, podcast, or conversation.
        return {**base, 'content': '', 'processing_error':
            'The link is saved. Add text or a transcript to make its contents searchable.'}
    body, mime, final_url = await fetch_public(url)
    base['metadata']['extracted_from'] = final_url
    if 'application/pdf' in mime or body.startswith(b'%PDF'):
        import pymupdf
        with pymupdf.open(stream=body, filetype='pdf') as document:
            pages = [page.get_text() for page in list(document)[:300]]
            base.update(source_type='pdf', title=document.metadata.get('title') or item['title'],
                        author=document.metadata.get('author') or '')
        base['important_passages'] = [{'text': text[:1200], 'page_number': index + 1,
            'locator': f'Page {index + 1}', 'source_url': url, 'origin': 'source'}
            for index, text in enumerate(pages) if text.strip()][:12]
        return {**base, 'content': '\n\n'.join(pages)[:500_000]}
    if not any(value in mime for value in ('html', 'text/plain', 'json', 'xml')):
        return {**base, 'content': '', 'processing_error':
            'The link is saved. This file needs text supplied by you before it can be indexed.'}
    document = await asyncio.to_thread(trafilatura.bare_extraction, body, url=final_url,
                                      with_metadata=True, include_comments=False, as_dict=True)
    if not document or not document.get('text'):
        return {**base, 'content': '', 'processing_error':
            "Article text couldn't be extracted. The URL and your note were still saved."}
    image = document.get('image') or ''
    if image:
        try:
            image = public_url(urljoin(final_url, image))
        except ValueError:
            image = ''
    return {**base, 'content': document['text'][:500_000],
            'title': document.get('title') or item['title'], 'author': document.get('author') or '',
            'published_at': document.get('date'), 'thumbnail': image}
