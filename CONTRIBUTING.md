# Contributing to Markov

Markov is an intelligent bookmark app with a local computer engine and a paired
phone interface. Start with [the product direction](docs/bookmark-direction.md)
and [the service contract](docs/local-service.md). Legacy research APIs remain
supported, but they are not the primary product.

## Development setup

Markov runs as a Python local service on Linux, Windows, and macOS. CI validates
Python 3.11 on Linux and Windows x64 and both Intel and Apple Silicon Macs.
Clone the repository, create a branch, and create and activate an isolated
environment using the [platform-specific setup commands](README.md#local-service-setup).
Then run from the repository root on every platform:

```sh
python -m pip install -c requirements/constraints.txt -e '.[dev]'
python -m pip check
python -m pytest -q
python scripts/smoke_service.py
```

The setup uses `requirements/constraints.txt` for shared runtime versions.
It needs internet access for installation. Tests use heuristic processing and
hash indexing; they do not need paid model keys. Do not copy a personal `.env`
or archive into a bug report. Use a temporary `--data-dir` for manual testing.

If an existing `.venv` inherits global packages or uses an unsuitable Python,
create a fresh environment at `build/dev-env` and activate it instead. Avoid
`--system-site-packages`: globally installed dependencies can hide missing ones.
On Linux, install your distribution's Python venv package if venv is unavailable.

## Changes and review

- Describe the user-visible problem and keep a pull request focused on one fix
  or behavior. Include the checks you ran and any limitations.
- Preserve immediate saving, source provenance, user notes, and human corrections.
  Extraction or model failure must not discard a bookmark.
- Add regression coverage for changed behavior. Pairing, authorization, queue,
  and persistence changes need meaningful failure-case tests.
- For interface changes, follow `AGENTS.md` and include desktop and mobile
  screenshots. Browser emulation does not replace physical-phone verification.
- Never commit `.env`, databases, pairing links, cookies, tokens, build output,
  or personal saved material. Report vulnerabilities through [SECURITY.md](SECURITY.md).

The service CI matrix tests a clean setup, runs the suite, builds and installs
the wheel, then checks real service startup, capture, processing, bundled PWA
assets, QR generation, and persistence after restart on each supported platform.
Keep runtime paths and process handling portable; distribution is a Python
service wheel with bundled web assets.

Dependency updates must pass these same checks. Update version constraints
deliberately; do not replace them with an unreviewed freeze of a global environment.
The constraints are tested version pins, not a hash-locked supply-chain guarantee.
Update the release notes when preparing a release.
