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
