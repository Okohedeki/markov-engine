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

Start `.\run-service.cmd` to run the processing engine on your computer and open
the local web app at `http://127.0.0.1:8000/app`. Your phone uses the same web app
through a reachable private HTTPS address, paired from **You → Your service**.
The computer owns the archive and processing queue; the phone is the review
interface for that same archive.

The connection works both ways: processed sources and interpretations are
available on the phone, while notes, corrected interpretations, favorites,
source-text edits, and retry requests go back to the engine. Pages read the
latest server state when opened or refreshed. `localhost` on a phone refers to
the phone itself, so use the computer's configured address there.

The [Windows executable](docs/windows-app.md) remains an optional launcher for
the same service; browser-based review does not depend on native app packaging.

Device access survives restarts and can be revoked individually. No central
Markov account is required in this mode. The computer must remain running and
reachable; HTTPS networking and automatic startup are separate setup steps.
See [local service setup and pairing](docs/local-service.md).

Legacy research remains at `/app/research`; its APIs and stored cases remain
compatible. See the [research architecture reference](docs/markov-v2-architecture.md).

## Windows setup

Install **64-bit Python 3.11**, clone this repository, and run from its folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
.\run-service.cmd
```

The setup creates an isolated environment and installs tested dependency versions.
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

## API quick start

```bash
curl -X POST http://127.0.0.1:8000/v2/jobs \
  -H "X-Markov-Key: local-customer-key" \
  -H "Idempotency-Key: demo-brief-1" \
  -H "Content-Type: application/json" \
  -d '{
    "job": "Explore where it leads",
    "review_level": "instant",
    "source": {"type":"url","value":"https://www.youtube.com/watch?v=..."},
    "options": {"focus":"economic claims","max_connections":8}
  }'
```

Poll `GET /v2/jobs/{job_id}` or inspect ordered events at
`GET /v2/jobs/{job_id}/events`. Fetch connections, paths, and insights under
`/v2/cases/{case_id}`; follow a branch with
`POST /v2/connections/{connection_id}/follow`. Full requests are in
[`docs/api-examples.md`](docs/api-examples.md).

## Entitlements and billing configuration

Owners resolve to `community`, `cloud_free`, `cloud_plus`, `cloud_pro`, or
`verified_add_on`. Configure the default with
`MARKOV_DEFAULT_ENTITLEMENT_PROFILE`, owner mappings with
`MARKOV_OWNER_ENTITLEMENT_PROFILES`, and deployment-specific limits with
`MARKOV_ENTITLEMENT_OVERRIDES`. Trust-floor capabilities cannot be switched off.

Cloud credit pricing still has six job variants:

```text
brief_instant        brief_verified
research_instant     research_verified
script_instant       script_verified
```

Credit costs are configuration, not business-logic constants. Override all six
with `MARKOV_PRODUCT_CREDIT_COSTS`. To sell credit packs through Stripe,
configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_IDS`, and
`STRIPE_CREDIT_PACKS`. The webhook grants credits idempotently and records
`payment_completed` or `payment_failed` usage events.

## Database migrations

`SqliteStore.open()` applies numbered, additive migrations automatically. The
sequence adds the evidence-oriented case model, connection graph, focused
research plans, entity aliases, and independently addressable artifact branches.
No migration deletes or rewrites Chain-era records.

Back up the SQLite file before deploying a new release:

```bash
python -c "import sqlite3; src=sqlite3.connect('data/markov.db'); dst=sqlite3.connect('data/markov.backup.db'); src.backup(dst); dst.close(); src.close()"
```

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

## Tests

```bash
python -m pytest -q
python -m ruff check markov_engine tests
```

The suite includes a full network-free V2 vertical slice covering timestamped
YouTube extraction, claims and gaps, evidence research, three typed validated
connections, an explicitly rejected candidate, one path and insight, all three
outputs, and a followed branch preserved as a separate Script. Store, API,
entitlement, export, review, cost, and analytics contracts are also tested.

## Samples

- [`samples/markov-brief.md`](samples/markov-brief.md)
- [`samples/markov-research.md`](samples/markov-research.md)
- [`samples/markov-script.md`](samples/markov-script.md)

These are compact fixtures demonstrating structure and provenance, not claims
about a real company or event.

## Known V1 limits

- Background execution is single-process; there is no distributed queue or
  automatic restart recovery yet.
- SQLite is intended for one API instance, not horizontally scaled writes.
- URL intake is public-source only. Upload transport and signed object storage
  are not included in this repository.
- Authentication is configured API-key ownership, not a full identity provider.
- Stripe supports configurable one-time credit packs; subscriptions, invoicing,
  tax, refunds, and enterprise contracts are intentionally deferred.
- Human review is a queue and audit workflow, not workforce scheduling.
- Evidence quality is conservative metadata plus inspectable rationale; reviewers
  remain responsible for final editorial and legal judgment.

## License

MIT — see [LICENSE](LICENSE).
