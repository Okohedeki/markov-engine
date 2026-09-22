# Markov

**A bookmark app that remembers what you forgot.**

Save anything worth remembering. Markov keeps your note, preserves available
source text, and brings older saves back with a reason grounded in your archive.
The mobile-first PWA centers Home, Library, Threads, Search, and You.

- Save a URL immediately; extract articles, PDFs, and available YouTube captions
  in a durable background queue.
- Keep user notes, source passages, and generated interpretations distinct.
- Find saves through exact, semantic, or hybrid search with explained matches.
- Follow automatic topic threads, curate them, and optionally organize projects.
- Rediscover up to five older saves based on recent interests and revisit history.
- Ask questions of saved sources, compare items, and copy or export their context.
- Install the PWA and receive shared links in browsers supporting Web Share Target.
- Expose read-only archive retrieval through the [Muse connector](docs/muse-connector.md).

Open `/app` for your archive or `/demo` for a clearly labeled example archive.
Configure a semantic embedding provider for meaning-based retrieval; hash mode
uses an explicitly labeled keyword fallback. Model enrichment and source-grounded
answers require a configured LLM; capture and lexical search work without one.

Blocked sources and media without accessible transcripts remain saved with a clear
partial state. Paste text or a timestamped transcript to index their contents.
Native share extensions, screenshot uploads/OCR, source-change monitoring, and
automatic contradiction detection are not implemented. Offline capture is not
queued: the installed app explains when a connection is required. Muse directory
submission and live integration testing remain pending its account-gated review.

The implementation direction is [documented here](docs/bookmark-direction.md).

## Your own service and paired PWA

Start `markov-service --open-browser` to run the processing engine on your computer and open
the local web app at `http://127.0.0.1:8000/app`. Your phone uses the same web app
through a reachable private HTTPS address, paired from **You → Your service**.
The computer owns the archive and processing queue; the phone is the review
interface for that same archive.

The connection works both ways: processed sources and interpretations are
available on the phone, while notes, corrected interpretations, favorites,
source-text edits, and retry requests go back to the engine. Pages read the
latest server state when opened or refreshed. `localhost` on a phone refers to
the phone itself, so use the computer's configured address there.

Markov is a Python local service for Linux, Windows, and macOS. The browser and
phone PWA connect to that same service; no native desktop application is required.

Device access survives restarts and can be revoked individually. No central
Markov account is required in this mode. The computer must remain running and
reachable; HTTPS networking and automatic startup are separate setup steps.
See [local service setup and pairing](docs/local-service.md).

Legacy research remains at `/app/research`; its APIs and stored cases remain
compatible. See the [research architecture reference](docs/markov-v2-architecture.md).

## Local service setup

Install **Python 3.11 or newer**, clone this repository, and open its folder.
Create and activate a virtual environment for your operating system:

Linux / macOS:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Then use the same install and start commands on every platform:

```sh
python -m pip install -c requirements/constraints.txt -e .
python -m pip check
markov-service --open-browser
```

The virtual environment isolates dependencies; shared constraints pin their versions.
Markov opens at `http://127.0.0.1:8000/app`. No account or model key is needed for
capture and keyword search. Phone access adds a private HTTPS address and QR
pairing; follow [the connection guide](docs/local-service.md#run-and-pair).

Your archive lives in `~/.markov/markov.db`; `service.json` remembers its setup.
An existing `.env` still controls model providers. With no provider configured,
processing uses heuristic interpretation and keyword indexing. See
[legacy model configuration](docs/legacy-setup.md) for optional model backends.
For environment conflicts and development, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Public landing-page build

The GitHub Pages site is generated from the same Jinja templates used by the
FastAPI app. Rebuild the committed `docs/` output after changing a public
template or static asset:

```bash
python scripts/build_pages.py
```

GitHub Pages publishes the `docs/` directory from `main`. The static build links
the workspace and API calls to the repository setup instructions because Pages
does not run the FastAPI service.

## Legacy research API

For the retained research API, see [request examples](docs/api-examples.md) and
[authentication and model setup](docs/legacy-setup.md). Phone pairing grants
bookmark access; it does not authorize these developer APIs.

Hosted research billing and reviewer operations are described in the
[operations reference](docs/operations.md). They are not needed for the personal
bookmark service.

## Updates and backups

Stop Markov with Ctrl+C before copying the personal archive. Back up the database
named in `~/.markov/service.json` (normally `~/.markov/markov.db`) and keep that
configuration file with it. Protect backups: they contain private saved material
and paired-device records. See [archive handling](docs/local-service.md#keep-an-existing-archive).

Before updating, make a backup, pull the new code, rerun the pip install command, and
restart Markov. Additive database migrations run automatically. Restore a backup
with its matching code version when testing a rollback; do not assume an older
version understands a newer database.

## CLI

The V1 CLI is useful for local, unmetered operation:

```bash
markov create "https://www.youtube.com/watch?v=..." --mode brief
markov case 1
markov convert 1 --mode script
markov deepen 3
```

Legacy engine commands remain available:

```bash
markov ingest https://example.com/article
markov grow 1 --hops 2 --budget 10
markov walk 1 --steps 3
markov generate 1 --type article
markov chains
```

## Contributing and checks

Use [CONTRIBUTING.md](CONTRIBUTING.md) for the isolated development setup:

```powershell
python -m pytest -q
python scripts/smoke_service.py
```

[Service CI](https://github.com/Okohedeki/markov-engine/actions/workflows/service.yml)
checks installation, regressions, a built wheel, and the real service on Linux,
Windows, and macOS (Intel and Apple Silicon).
See [release notes](CHANGELOG.md) and [private security reporting](SECURITY.md).

## Samples

- [`samples/markov-brief.md`](samples/markov-brief.md)
- [`samples/markov-research.md`](samples/markov-research.md)
- [`samples/markov-script.md`](samples/markov-script.md)

These are compact fixtures demonstrating structure and provenance, not claims
about a real company or event.

## Current status and limits

Markov is **alpha**, with Windows x64 / Python 3.11 as the validation target.
It is ready for development and local evaluation; a stable public release still
needs the physical-phone acceptance checks on a trusted HTTPS deployment.

- The computer must stay running and reachable. Private networking and automatic
  startup are separate setup steps.
- Pages update on opening or refresh. Live push updates and offline capture
  queues are not implemented.
- SQLite and the background queue serve one engine instance. Multi-user hosted
  deployment is outside the personal-service contract.
- QR pairing and revocation have automated coverage; physical phone scanning,
  home-screen installation, and reconnect still need device verification.
- Local storage does not prevent configured cloud model providers from receiving
  source text. Choose local providers when that is a requirement.

## License

MIT — see [LICENSE](LICENSE).
