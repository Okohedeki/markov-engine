"""Exercise an installed Markov service without network sources or model keys."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx


@contextmanager
def running_service(directory, port):
    """Start a real loopback server and always stop it, including on test failure."""
    environment = dict(os.environ, LLM_BACKEND='heuristic', EMBED_BACKEND='hash',
                       SEARCH_ENABLED='false', PYTHONUTF8='1')
    command = [sys.executable, '-m', 'markov_engine.service', '--data-dir', str(directory),
               '--port', str(port), '--url', 'https://markov.example.test']
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    log_path = directory / 'smoke.log'
    with log_path.open('a', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=directory, env=environment,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', trust_env=False,
                              timeout=2) as client:
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError(log_path.read_text(encoding='utf-8'))
                    try:
                        if client.get('/app').status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.25)
                else:
                    raise RuntimeError('Service did not become ready.\n' + log_path.read_text(encoding='utf-8'))
                yield client
        except Exception:
            # CI must preserve server-side failures before the temporary archive is removed.
            print(log_path.read_text(encoding='utf-8'), file=sys.stderr, flush=True)
            raise
        finally:
            if process.poll() is None:
                if sys.platform == 'win32':
                    # A Windows venv launcher has a child interpreter holding SQLite.
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True, check=True)
                else:
                    process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def main():
    with socket.socket() as available:
        available.bind(('127.0.0.1', 0))
        port = available.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='markov smoke ') as temporary:
        directory = Path(temporary)
        with running_service(directory, port) as client:
            for path in ['/app/devices', '/app/you', '/static/memory.css', '/static/service.js',
                         '/app/manifest.webmanifest', '/app/sw.js']:
                response = client.get(path)
                assert response.status_code == 200, (path, response.status_code)
            invite = client.post('/app/devices/invite', data={'request': 'pair'},
                                 headers={'Origin': str(client.base_url).rstrip('/')})
            assert invite.status_code == 200 and 'data:image/svg+xml;base64,' in invite.text
            saved = client.post('/app/bookmarks', data={
                'url': 'https://example.com/smoke-source', 'note': 'Persistent smoke-test bookmark',
                'content': 'Supplied text must finish processing without a model or network fetch.'},
                headers={'Accept': 'application/json'})
            assert saved.status_code == 201, saved.text
            # Observe the queue through SQLite, independently of the rendered page.
            from contextlib import closing
            import sqlite3
            with closing(sqlite3.connect(directory / 'markov.db')) as database:
                for _ in range(100):
                    row = database.execute("SELECT json_extract(payload, '$.processing_state') FROM bookmarks").fetchone()
                    if row and row[0] == 'ready':
                        break
                    time.sleep(.1)
                else:
                    raise AssertionError(f'Supplied source did not become ready: {row}')
            print('Installed pages, PWA assets, QR generation, capture, and processing passed.')
        with running_service(directory, port) as client:
            library = client.get('/app/library')
            assert library.status_code == 200 and 'Persistent smoke-test bookmark' in library.text
            print('Archive persisted after stopping and restarting the service.')


if __name__ == '__main__':
    main()
