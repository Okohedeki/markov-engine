"""Launch a personal Markov service with a persistent archive and QR device pairing."""
import argparse
import json
import os
from pathlib import Path

from markov_engine.config import Settings, get_settings
from markov_engine.service_auth import service_origin


def prepare_service(data_dir, *, name=None, url=None, owner=None, database=None):
    directory = Path(data_dir).expanduser().resolve()
    config_path = directory / 'service.json'
    saved = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    if not isinstance(saved, dict):
        raise ValueError('The service configuration must be a JSON object.')
    configured = Settings()
    if configured.llm_backend == 'anthropic' and not configured.anthropic_api_key:
        os.environ['LLM_BACKEND'] = 'heuristic'
    if configured.embed_backend == 'voyage' and not configured.voyage_api_key:
        os.environ['EMBED_BACKEND'] = 'hash'
    get_settings.cache_clear()
    settings = Settings(MARKOV_LOCAL_SERVICE=True,
        MARKOV_SERVICE_NAME=name if name is not None else saved.get('name', 'My Markov'),
        MARKOV_SERVICE_URL=url if url is not None else saved.get('url', ''),
        MARKOV_SERVICE_OWNER=owner if owner is not None else saved.get('owner', 'local'),
        MARKOV_DATABASE_PATH=str(Path(database).expanduser().resolve()) if database else
            saved.get('database', str(directory / 'markov.db')),
        MARKOV_API_KEYS={}, MARKOV_INTERNAL_API_KEYS={}, MARKOV_LOCAL_PREVIEW_OWNER='',
        CLERK_PUBLISHABLE_KEY='', CLERK_SECRET_KEY='')
    origin = service_origin(settings)
    directory.mkdir(parents=True, exist_ok=True)
    config = {'name': settings.service_name, 'url': origin, 'owner': settings.service_owner,
              'database': settings.database_path}
    if config != saved:
        temporary = config_path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
        temporary.replace(config_path)
    return settings
