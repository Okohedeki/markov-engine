"""The public-source fetcher: redirect handling, address pinning, and private-network refusal."""
import httpx
import pytest

from markov_engine import bookmark_extract
from markov_engine.bookmark_extract import fetch_public
from markov_engine.bookmark_urls import canonicalize, public_url

ADDRESSES = {'youtube.com': ['142.250.1.1'], 'www.youtube.com': ['142.250.1.2'],
             'example.com': ['93.184.215.14'], 'intranet.example': ['10.0.0.5'],
             'mixed.example': ['93.184.215.15', '127.0.0.1']}


@pytest.fixture
def seen(monkeypatch):
    async def resolve(host, port):
        return ADDRESSES.get(host, [])
    monkeypatch.setattr(bookmark_extract, 'resolve', resolve)
    return []


def serve(seen, routes):
    def handler(request):
        seen.append((request.url.host, request.headers['host'], request.url.raw_path.decode()))
        return routes[request.headers['host']](request)
    return httpx.MockTransport(handler)


def moved(location, status=301):
    return lambda request: httpx.Response(status, headers={'location': location})


def page(body=b'<html>ok</html>', mime='text/html'):
    return lambda request: httpx.Response(200, headers={'content-type': mime}, content=body)


@pytest.mark.asyncio
async def test_follows_a_redirect_to_the_host_that_canonical_identity_removes(seen):
    # youtube.com canonicalizes without www, and the site redirects back to www.
    start = canonicalize('https://www.youtube.com/watch?v=abc')
    assert start == 'https://youtube.com/watch?v=abc'
    transport = serve(seen, {'youtube.com': moved('https://www.youtube.com/watch?v=abc'),
                             'www.youtube.com': page(b'<html>video</html>')})
    body, mime, final = await fetch_public(start, transport=transport)
    assert body == b'<html>video</html>' and mime == 'text/html'
    assert final == 'https://www.youtube.com/watch?v=abc'
    assert [host for _, host, _ in seen] == ['youtube.com', 'www.youtube.com']


@pytest.mark.asyncio
async def test_connects_to_the_validated_address_and_keeps_the_host_name(seen):
    await fetch_public('https://example.com/a?utm_source=x', transport=serve(seen, {'example.com': page()}))
    assert seen == [('93.184.215.14', 'example.com', '/a?utm_source=x')]


@pytest.mark.asyncio
@pytest.mark.parametrize('location, message', [
    ('https://intranet.example/admin', 'private network address'),
    ('http://169.254.169.254/latest/meta-data/', 'Private network links'),
    ('https://mixed.example/', 'private network address'),
    ('http://localhost:8000/app', 'Use a public http or https link'),
])
async def test_refuses_redirects_into_private_networks(seen, location, message):
    transport = serve(seen, {'example.com': moved(location, 302), 'intranet.example': page(b'secret'),
                             'mixed.example': page(b'secret')})
    with pytest.raises(ValueError, match=message):
        await fetch_public('https://example.com/', transport=transport)
    assert [host for _, host, _ in seen] == ['example.com']


@pytest.mark.asyncio
async def test_redirect_loops_and_oversized_sources_fail_without_a_partial_result(seen):
    looping = serve(seen, {'example.com': moved('https://example.com/')})
    with pytest.raises(ValueError, match='redirects too many times'):
        await fetch_public('https://example.com/', transport=looping)
    with pytest.raises(ValueError, match='too large'):
        await fetch_public('https://example.com/', limit=10,
                           transport=serve(seen, {'example.com': page(b'x' * 11)}))


def test_public_url_validates_without_rewriting_identity():
    assert public_url('https://www.youtube.com/watch?v=abc&utm_source=x#t') == \
        'https://www.youtube.com/watch?v=abc&utm_source=x'
    assert public_url('HTTPS://Example.COM') == 'https://example.com/'
    for private in ['http://10.1.2.3/', 'http://printer.local/', 'https://user:pw@example.com/']:
        with pytest.raises(ValueError):
            public_url(private)
