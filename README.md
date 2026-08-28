# Markov

**Start anywhere. Follow the idea. Make something original.**

Markov treats a source as the first node, not the answer. It checks the claims,
discovers and validates typed connections, builds paths through the strongest
ideas, and turns the shared case into one of three useful outcomes:

- **Catch me up** — bottom line, assumptions, omissions, weak points, exact
  navigation, and threads worth pulling.
- **Explore where it leads** — a connection map, hidden story, hypotheses,
  ranked research paths, counterevidence, and source packet.
- **Turn it into a script** — candidate angles, an original defensible angle,
  full narration, production and fact-check notes, and a do-not-repeat list.

Every product can be **Instant** (fully agentic) or **Verified** (the same
structured case followed by audited human review). Brief, Research, and Script
reuse one isolated research case, so converting a finished project does not
repeat unchanged extraction or research.

The original open-source Chain, growth, ingestion, and article/newsletter APIs
remain available for compatibility. New customer submissions do not
automatically merge into Chains.

## What V2 includes

- YouTube captions first, with timestamped Whisper fallback.
- Structured video/audio, PDF-page, article-section, and social segments.
- Long-source claim extraction with overlap, deduplication, types, certainty,
  importance, and research gaps.
- Claim-specific authority, data, limitation, history, counterevidence, and
  alternative-explanation searches.
- Exact inspected passages; search snippets never become evidence.
- Ten closed connection types with explicit endpoints, mechanisms, significance,
  support, weakening conditions, next steps, and evidence levels.
- Reproducible scoring across relevance, evidence strength, novelty,
  explanatory value, output usefulness, and risk.
- Connection paths, insight candidates, persistent branch decisions, and
  follow-to-revised-Script behavior.
- Deterministic citations, claim markers, evidence appendices, and source
  locators.
- Authenticated asynchronous `/v2` API with idempotency, graph resources,
  branching, stage events, errors,
  webhooks, owner isolation, and rate limits.
- Public product, pricing, finished-case, and developer pages plus a
  server-rendered SaaS workspace for intake, processing, artifact reading,
  evidence, conversion, deepening, revision, export, and review.
- Configurable Community, Cloud Free, Cloud Plus, Cloud Pro, and Verified
  entitlements. Accuracy, citations, uncertainty, and source packets are never
  premium features.
- Usage analytics, variable-cost records, artifact versions, structured review
  decisions, and review-time accounting.
- Additive SQLite migrations that preserve legacy data.

## Architecture

```text
Web / API / CLI
  -> authenticated owner + configured credit reservation
  -> durable Job + isolated ResearchCase
  -> Extract -> SourceSegments with timestamps/pages/sections
  -> Claim -> atomic Claims + ResearchGaps
  -> Research -> exact EvidencePassages + ClaimEvidence stance
  -> Connect -> typed candidates -> deterministic validation and scoring
  -> Path -> ordered Connections -> InsightCandidates
  -> Render -> Brief / Research Report / Script
  -> Branch -> follow / save / dismiss -> revised artifact versions
  -> Deliver -> exports, usage, costs
  -> Verified only -> structured ReviewJob -> final delivery
```

The V2 product contract, repository audit, domain model, trust rules, API,
entitlements, analytics, and acceptance slice are in
[`docs/markov-v2-architecture.md`](docs/markov-v2-architecture.md). The original
V1 audit remains in [`docs/markov-v1-architecture.md`](docs/markov-v1-architecture.md).

## Local setup

Requirements: Python 3.11+ and FFmpeg when Whisper transcription is needed.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

On Windows, the fastest development setup is:

```powershell
.\run-local.cmd
```

This starts the landing page, SaaS workspace, and API together at
`http://127.0.0.1:8000`. When no `.env` exists, the launcher uses safe offline
development defaults: heuristic generation, hash embeddings, 100 test credits,
disabled outbound web search, and a separate `data/local-markov.db` database.
Claims without attached evidence remain visibly unsupported in this mode. Sign
into the workspace with `local-customer-key`; the reviewer key is
`local-review-key`.

Pass `-Port 8010` to choose another port or `-NoReload` to disable automatic
reloads. If `.env` exists, the launcher leaves it in control so you can test real
Anthropic, OpenAI-compatible, or in-process local model backends.

Copy [`.env.example`](.env.example) to `.env`. At minimum, configure an API key
mapping, an opening or purchased credit balance, and one LLM/search setup.
`MARKOV_API_KEYS` maps secret keys to stable owner IDs; it must be JSON.

Cloud example:

```dotenv
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=replace-me
VOYAGE_API_KEY=replace-me
MARKOV_API_KEYS={"local-customer-key":"local-customer"}
MARKOV_INTERNAL_API_KEYS={"local-review-key":"reviewer-1"}
MARKOV_OPENING_CREDITS=20
MARKOV_WEB_SESSION_SECRET=replace-with-a-random-secret
```

Local model example:

```dotenv
LLM_BACKEND=openai
EMBED_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b-instruct
OPENAI_EMBED_MODEL=nomic-embed-text
MARKOV_API_KEYS={"local-customer-key":"local-customer"}
```

Then run:

```bash
markov-api
# Public site: http://127.0.0.1:8000/
# Pricing: http://127.0.0.1:8000/pricing
# Developer guide: http://127.0.0.1:8000/developers
# Finished-case demo: http://127.0.0.1:8000/sample
# API docs: http://127.0.0.1:8000/docs
# Customer app: http://127.0.0.1:8000/app
# Reviewer app: http://127.0.0.1:8000/app/reviewer/login
```

The V1 runner executes background tasks in the API process. That is suitable for
one-instance demand testing. See [`docs/operations.md`](docs/operations.md) for
restart behavior, backups, reviewer operation, billing, and production limits.

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

`SqliteStore.open()` applies numbered, additive migrations automatically. V1
adds the evidence-oriented case model. V2 adds connections, connection evidence,
paths, insights, and branch decisions. Neither migration deletes or rewrites
Chain-era records.

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
outputs, a followed branch, and a revised Script version. Store, API,
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
