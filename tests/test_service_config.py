import pytest

from markov_engine.config import Settings, get_settings
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
