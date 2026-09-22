# Contributing to Markov

Markov is an intelligent bookmark app with a local computer engine and a paired
phone interface. Start with [the product direction](docs/bookmark-direction.md)
and [the service contract](docs/local-service.md). Legacy research APIs remain
supported, but they are not the primary product.

## Development setup

The supported validation target is Windows x64 with Python 3.11. Clone the
repository, create a branch for your contribution, and run from its root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1 -Development
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts/smoke_service.py
```

The setup uses `packaging/windows-constraints.txt` for the tested runtime versions.
It needs internet access for installation. Tests use heuristic processing and
hash indexing; they do not need paid model keys. Do not copy a personal `.env`
or archive into a bug report. Use a temporary `--data-dir` for manual testing.

If an existing `.venv` inherits global packages or uses a different Python,
choose `-EnvironmentPath build/dev-env` and use that environment's Python in
the commands above. The setup does not delete or replace existing environments.

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

The Windows CI workflow tests a clean setup, runs the suite, builds and installs
the wheel, then checks real service startup, capture, processing, bundled PWA
assets, QR generation, and persistence after restart. Mac and Linux validation
and native packaging are future work, not supported release targets yet.

Dependency updates must pass these same checks. Update version constraints
deliberately; do not replace them with an unreviewed freeze of a global environment.
The constraints are tested version pins, not a hash-locked supply-chain guarantee.
Update the release notes when preparing a release.
