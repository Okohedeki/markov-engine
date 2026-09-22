from unittest.mock import Mock

import pytest

from markov_engine.config import Settings
from markov_engine.service import prepare_service
from markov_engine.service_auth import service_origin


@pytest.mark.parametrize('url', ['http://192.168.1.5:8000', 'https://localhost',
    'https://user:secret@home.example', 'https://home.example/app', 'https://home.example?key=x',
    'https://home.example#secret', 'https://home.example:bad', 'https://home.example:0',
    'https://home. example'])
def test_service_pairing_requires_a_valid_reachable_https_origin(url):
    settings = Settings(_env_file=None, MARKOV_LOCAL_SERVICE=True, MARKOV_SERVICE_URL=url)
    with pytest.raises(ValueError):
        service_origin(settings)


def test_launcher_remembers_service_identity_and_archive_without_developer_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('LLM_BACKEND', 'heuristic')
    monkeypatch.setenv('EMBED_BACKEND', 'hash')
    monkeypatch.setenv('MARKOV_API_KEYS', '{"old-developer-key":"other-owner"}')
    # The launcher normally starts a new process. Do not invalidate settings
    # retained by already-imported model modules in this shared pytest process.
    launcher_cache = Mock()
    monkeypatch.setattr('markov_engine.service.get_settings', launcher_cache)
    directory = tmp_path / 'my-service'
    first = prepare_service(directory, name='Home workstation', url='https://home.example', owner='my-owner')
    second = prepare_service(directory)
    assert second.service_name == first.service_name == 'Home workstation'
    assert second.service_owner == first.service_owner == 'my-owner'
    assert second.service_url == 'https://home.example'
    assert second.database_path == str(directory / 'markov.db')
    assert second.local_service and not second.api_keys and not second.internal_api_keys
    assert not second.clerk_publishable_key and not second.local_preview_owner
    assert 'old-developer-key' not in (directory / 'service.json').read_text()
    assert launcher_cache.cache_clear.call_count == 2
