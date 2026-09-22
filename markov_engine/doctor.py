"""Read-only checks for the local engine and the configured phone connection."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import httpx

from markov_engine.service_auth import service_origin


def diagnose(data_dir, port=8000, *, require_phone=False, transport=None):
    """Return (level, message) checks without changing configuration or pairing."""
    checks = []
    try:
        saved = json.loads((Path(data_dir).expanduser() / 'service.json').read_text(encoding='utf-8'))
        if not isinstance(saved, dict) or not isinstance(saved.get('url', ''), str):
            raise ValueError('Invalid service configuration')
        origin = service_origin(SimpleNamespace(local_service=True, clerk_publishable_key='',
            clerk_secret_key='', service_url=saved.get('url', '')))
    except (OSError, ValueError):
        return [('FAIL', 'Cannot read a valid service.json. Start Markov once, or check --data-dir.')]
    if not 1 <= port <= 65535:
        return [('FAIL', 'Port must be between 1 and 65535.')]
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False, transport=transport) as client:
        try:
            response = client.get(f'http://127.0.0.1:{port}/app/devices')
            if response.status_code == 200 and 'Running on this computer' in response.text:
                checks.append(('PASS', 'The local Markov console is running.'))
            else:
                checks.append(('FAIL', 'This port did not return the local Markov console. Check --port.'))
        except httpx.HTTPError:
            checks.append(('FAIL', 'Cannot reach the local engine. Start Markov and check --port.'))
        if not origin:
            checks.append(('FAIL' if require_phone else 'WARN',
                'No phone address configured. Restart Markov with --url and a reachable HTTPS origin.'))
            return checks
        try:
            pairing = client.get(origin + '/app/pair')
            if pairing.status_code != 200 or 'data-pair-form' not in pairing.text:
                checks.append(('FAIL', 'The HTTPS address did not return Markov pairing. Check the proxy target.'))
            else:
                checks.append(('PASS', 'The pairing page is reachable over trusted HTTPS from this computer.'))
            console = client.get(origin + '/app/devices')
            if console.status_code == 401:
                checks.append(('PASS', 'Unpaired HTTPS requests cannot access the device console.'))
            else:
                checks.append(('FAIL', 'Unexpected device-console access over HTTPS. Check forwarding headers.'))
        except httpx.HTTPError:
            checks.append(('FAIL', 'HTTPS connection failed. Check DNS, certificate trust, private network, and proxy.'))
    checks.append(('INFO', 'Phone reachability, QR scanning, and home-screen installation still need a real phone.'))
    return checks
