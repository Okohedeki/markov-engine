"""Diagnostics must be read-only and must not mistake a proxy leak for success."""
import json

import httpx
import pytest

from markov_engine.doctor import diagnose


@pytest.mark.parametrize('url,local,remote,require_phone,failed', [
    ('https://home.example.test', 'up', 'paired-only', True, False),
    ('https://home.example.test', 'down', 'paired-only', True, True),
    ('https://home.example.test', 'wrong-app', 'paired-only', True, True),
    ('https://home.example.test', 'up', 'exposed-console', True, True),
    ('https://home.example.test', 'up', 'wrong-app', True, True),
    ('https://home.example.test', 'up', 'tls-failure', True, True),
    ('https://home.example.test', 'up', 'redirect', True, True),
    ('', 'up', 'unused', False, False),
    ('', 'up', 'unused', True, True),
    ('http://192.168.1.2', 'unused', 'unused', True, True),
    (123, 'unused', 'unused', True, True),
])
def test_connection_diagnostics(tmp_path, url, local, remote, require_phone, failed):
    configuration = tmp_path / 'service.json'
    configuration.write_text(json.dumps({'url': url}), encoding='utf-8')
    original = configuration.read_bytes()
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.host == '127.0.0.1':
            if local == 'down':
                raise httpx.ConnectError('offline', request=request)
            return httpx.Response(200, text='Running on this computer' if local == 'up' else 'Other app')
        if remote == 'tls-failure':
            raise httpx.ConnectError('certificate not trusted', request=request)
        if remote == 'redirect':
            return httpx.Response(307, headers={'Location': 'https://unexpected.example.test'})
        if request.url.path == '/app/pair':
            return httpx.Response(200, text='Other app' if remote == 'wrong-app' else 'data-pair-form')
        return httpx.Response(200 if remote == 'exposed-console' else 401)

    checks = diagnose(tmp_path, require_phone=require_phone, transport=httpx.MockTransport(respond))
    assert any(level == 'FAIL' for level, _ in checks) is failed
    assert configuration.read_bytes() == original
    assert list(tmp_path.iterdir()) == [configuration]
    assert all(request.method == 'GET' and not request.headers.get('cookie') for request in requests)
    assert all(request.url.host != 'unexpected.example.test' for request in requests)


@pytest.mark.parametrize('content', [None, 'not json', '[]', '{"url": null}'])
def test_invalid_configuration_never_attempts_network(tmp_path, content):
    if content is not None:
        (tmp_path / 'service.json').write_text(content, encoding='utf-8')
    def unexpected_request(request):
        pytest.fail('Invalid configuration must fail before a network request')
    assert diagnose(tmp_path, transport=httpx.MockTransport(unexpected_request))[0][0] == 'FAIL'
