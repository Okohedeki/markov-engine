"""Windows executable entrypoint; keep user data outside the packaged program."""
import argparse
import multiprocessing
import os
from pathlib import Path
import sys
import traceback


def launch(argv=None):
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument('--data-dir')
    parser.add_argument('--no-browser', action='store_true')
    options, remaining = parser.parse_known_args(argv)
    legacy = Path.home() / '.markov'
    default = legacy if (legacy / 'service.json').exists() else (
        Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData' / 'Local'))) / 'Markov')
    directory = Path(options.data_dir or default).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    # Never load an unrelated .env from Downloads or the executable's location.
    # Model configuration can be placed deliberately in this data directory.
    os.chdir(directory)
    sys.argv = [sys.argv[0], *remaining, '--data-dir', str(directory)]
    if not options.no_browser:
        sys.argv.append('--open-browser')
    from markov_engine.service import main
    print('Markov for Windows\nKeep this window open while using your archive. Ctrl+C stops the service.\n')
    main()
