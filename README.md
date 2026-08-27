# Markov

Markov turns a source, topic, or question into one of three finished,
evidence-linked products:

- **Markov Brief** — the bottom line, important points, what can be skipped,
  missing context, claim status, and exact source navigation.
- **Markov Research** — a professional research report organized around atomic
  claims, exact evidence passages, counterevidence, gaps, and source quality.
- **Markov Script** — a ready-to-record factual YouTube package with a production
  verdict, thesis, complete narration, production notes, evidence markers,
  fact-check appendix, and do-not-repeat list.

Every product can be **Instant** (fully agentic) or **Verified** (the same
structured case followed by audited human review). Brief, Research, and Script
reuse one isolated research case, so converting a finished project does not
repeat unchanged extraction or research.

The original open-source Chain, growth, ingestion, and article/newsletter APIs
remain available for compatibility. New customer submissions do not
automatically merge into Chains.

## What V1 includes

- YouTube captions first, with timestamped Whisper fallback.
- Structured video/audio, PDF-page, article-section, and social segments.
- Long-source claim extraction with overlap, deduplication, types, certainty,
  importance, and research gaps.
- Claim-specific authority, data, limitation, history, counterevidence, and
  alternative-explanation searches.
- Exact inspected passages; search snippets never become evidence.
- Deterministic citations, claim markers, evidence appendices, and source
  locators.
- Authenticated asynchronous API with idempotency, stage events, errors,
  webhooks, owner isolation, and rate limits.
- Focused server-rendered intake, processing, artifact, evidence, conversion,
  deepening, revision, export, and reviewer pages.
- Six configurable credit products and optional Stripe Checkout/webhooks.
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
  -> Render -> Brief / Research Report / Script
  -> Deliver -> versions, exports, usage, costs
  -> Verified only -> structured ReviewJob -> final delivery
```

The detailed repository audit, migration plan, module decisions, risks, and
vertical-slice map are in
[`docs/markov-v1-architecture.md`](docs/markov-v1-architecture.md).

## Local setup

Requirements: Python 3.11+ and FFmpeg when Whisper transcription is needed.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

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
# API docs: http://127.0.0.1:8000/docs
# Customer app: http://127.0.0.1:8000/app
# Reviewer app: http://127.0.0.1:8000/app/reviewer/login
```

The V1 runner executes background tasks in the API process. That is suitable for
one-instance demand testing. See [`docs/operations.md`](docs/operations.md) for
restart behavior, backups, reviewer operation, billing, and production limits.

## API quick start

```bash
curl -X POST http://127.0.0.1:8000/v1/jobs \
  -H "X-Markov-Key: local-customer-key" \
  -H "Idempotency-Key: demo-brief-1" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "brief",
    "review_level": "instant",
    "inputs": [{"type":"url","value":"https://www.youtube.com/watch?v=..."}],
    "constraints": {"focus":"economic claims","depth":"standard"}
  }'
```

Poll `GET /v1/jobs/{job_id}` or inspect ordered events at
`GET /v1/jobs/{job_id}/events`. Full requests for all three modes, conversion,
deepening, revision, export, review, and checkout are in
[`docs/api-examples.md`](docs/api-examples.md).

## Product and billing configuration

The product catalog has exactly six variants:

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
adds research cases, segments, claims, gaps, evidence, jobs, versions, reviews,
usage, cost, and credit tables and only nullable/defaulted columns to legacy
tables. It does not delete or rewrite Chain-era records.

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

The suite includes a full network-free vertical slice covering timestamped
YouTube extraction, claims, priority evidence research, all three outputs,
deepening, targeted regeneration, section revision, export, Verified review,
structured correction, costs, and analytics.

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
