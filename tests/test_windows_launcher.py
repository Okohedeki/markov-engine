from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

from markov_engine.windows import launch


@pytest.mark.parametrize('existing_archive', [False, True])
def test_windows_launch_keeps_archive_outside_program_and_preserves_existing_data(
        tmp_path, monkeypatch, existing_archive):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', ['Markov.exe'])
    monkeypatch.setattr(Path, 'home', lambda: tmp_path / 'home')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'AppData' / 'Local'))
    legacy = tmp_path / 'home' / '.markov'
    if existing_archive:
        legacy.mkdir(parents=True)
        (legacy / 'service.json').write_text('{"name":"My existing archive"}')
    run = Mock()
    monkeypatch.setattr('markov_engine.service.main', run)
    launch(['--no-browser', '--port', '8123'])
    expected = legacy if existing_archive else tmp_path / 'AppData' / 'Local' / 'Markov'
    assert Path.cwd() == expected
    assert sys.argv == ['Markov.exe', '--port', '8123', '--data-dir', str(expected)]
    run.assert_called_once_with()
    if existing_archive:
        assert 'My existing archive' in (legacy / 'service.json').read_text()
