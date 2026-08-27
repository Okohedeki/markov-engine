# Markov V1 architecture and migration plan

Status: implementation baseline, 2026-08-26

## Product boundary

Markov V1 sells finished artifacts, not a knowledge graph or a generic writing
workspace. A submission creates one isolated research case. That case preserves
source locators, claims, research gaps, evidence, decisions, usage, and cost, and
can render any of these products without repeating unchanged research:

- **Markov Brief** — a source-skipping decision artifact.
- **Markov Research** — a cited, claim-organized research report.
- **Markov Script** — an evidence-linked, ready-to-record factual YouTube script.

Each artifact has an `instant` or `verified` review level. Verified work runs the
same agentic pipeline and then enters a structured reviewer queue.

## Current repository audit

This repository is the public Python engine, not the closed-source full-stack
application referenced by the old README. It has no frontend framework, HTTP API,
job worker, authentication, owner model, Stripe integration, migrations, deployment
manifest, or CI workflow. No dependency on another `markov-engine` implementation
exists in this checkout.

### Current end-to-end flow

```text
CLI command
  -> SqliteStore.open (CREATE TABLE IF NOT EXISTS schema bootstrap)
  -> ingest_url
       -> classify URL
       -> extract article/PDF/social/media text
       -> summarize and extract key points/entities/relationships
       -> persist Source and entity graph
       -> embed summary
       -> create Topic
       -> automatically merge into nearest Chain or create a Chain
  -> optional grow/walk
       -> generate broad discovery queries
       -> fan out to web/news/video/social search
       -> rank snippets by centroid similarity/freshness
       -> ingest selected URLs
       -> attach Sources to a Chain
  -> optional generate
       -> concatenate source excerpts
       -> ask one model for an article or newsletter
       -> persist Artifact
```

The current flow flattens transcripts, PDFs, and articles into `content_text`,
truncates entity extraction to the first 8,000 characters, treats broad entities
and Chains as the primary organization, and generates artifacts from one large
prompt. It therefore cannot provide claim-level provenance or stable locators.

### Current major modules

| Module | Current responsibility | V1 disposition |
| --- | --- | --- |
| `markov_engine.extract` | URL classification and source-specific extraction | Modify to preserve structured segments and locators |
| `markov_engine.transcribe` | Cached faster-whisper transcription | Modify to return timed segments and cache by model |
| `markov_engine.entities` | Summary, key points, entities, relationships | Keep for legacy flow and query support; claims become primary |
| `markov_engine.ingest` | Extract, summarize, persist, cluster | Preserve legacy API; add research-case orchestration beside it |
| `markov_engine.embeddings` / `vectors` | Embedding backends and similarity | Reuse with dimension validation |
| `markov_engine.search` | Multi-avenue discovery and rate limiting | Reuse transport/rate limits; add authority-oriented evidence queries |
| `markov_engine.growth` | Chain discovery and automatic growth | Park from primary V1 flow |
| `markov_engine.clustering` | Automatic Topic-to-Chain merging | Park from new case creation; retain for old data/API |
| `markov_engine.generate` | Article/newsletter synthesis | Park from primary UI; retain for compatibility |
| `markov_engine.llm` | Anthropic, OpenAI-compatible, llama.cpp, heuristic backends | Reuse for bounded structured tasks |
| `markov_engine.store` | Store ABC, records, single-file SQLite backend | Extend additively for research cases and migrations |
| `markov_engine.cli` | Synchronous-looking CLI over async engine calls | Preserve old commands; add V1 case/artifact commands |
| `docs/index.html` | Static engine marketing page | Remove from primary product flow later; do not delete now |

### Existing data model

The SQLite bootstrap defines `sources`, `source_key_points`, `topics`, `chains`,
`chain_sources`, `entities`, `relationships`, `entity_sources`, `artifacts`,
`artifact_sources`, and `events`. There are no foreign-key constraints, schema
version records, owners, jobs, reviews, usage ledgers, or preserved source
segments. `artifacts` is Chain-scoped.

Known migration and correctness risks:

1. `CREATE TABLE IF NOT EXISTS` does not add newly introduced columns to existing
   databases. The recently added `sources.metadata` column already breaks legacy
   databases.
2. `ingest_chosen(..., cluster=False)` attaches grown Sources without creating a
   Topic or updating the Chain centroid.
3. Normal clustering creates a Topic but does not set `sources.topic_id`.
4. Ingestion commits each small mutation independently, so a failure can leave a
   partially ingested Source that future retries treat as complete.
5. Embedding dimensions and model identity are not stored. Mismatched vectors are
   silently truncated by `zip`.
6. Existing tables and artifacts must stay readable during V1 rollout.

### Frontend structure

There is no application frontend. `docs/index.html` is a static GitHub Pages
marketing page and is not connected to engine state. The first slice will add a
minimal server-rendered FastAPI interface for intake, processing status, artifact
viewing, evidence inspection, exports, and internal review. A separate SPA is not
required to test demand.

### Existing API and worker behavior

There is no HTTP API or durable worker. All public operations are async Python
functions invoked by the CLI. The first slice will persist jobs and stage events,
then execute them as FastAPI background tasks in a single process. The job schema
is intentionally compatible with moving execution to a durable queue later.
Restart recovery and horizontally scaled workers are documented V1 limitations.

### Authentication and billing

There is no authentication, owner isolation, Stripe code, credit balance, or
entitlement system in this checkout. The first slice will add:

- API-key-to-owner configuration for HTTP access.
- owner-scoped research-case queries.
- a configurable six-variant product catalog.
- credit accounts and immutable credit/usage events.
- optional Stripe Checkout/webhook hooks configured by environment variables.

No final prices will be embedded in business logic.

### Existing engine integration

The repository *is* the engine. There is no duplicated full-stack implementation
to consolidate here. New web, API, review, and billing surfaces must call the same
research-case service used by the CLI so research logic remains single-sourced.

## Reuse, modify, park, and de-emphasize

| Category | Components | Decision |
| --- | --- | --- |
| Reuse unchanged | async public API style, LLM backend boundary, SQLite connection lifecycle, search rate limiter, record dataclasses, source metadata, event concept | Compose these into the new case pipeline |
| Modify | extraction, transcription, SQLite bootstrap, artifacts, configuration, CLI, package exports, search ranking hooks | Add locators, migrations, owner/case scope, jobs, evidence, costs, and V1 commands |
| Park | automatic Chain growth, embedding-based automatic case merging, article/newsletter generator, entity graph as the primary abstraction | Keep code and old data working, but do not route new submissions through it |
| Remove from primary UI | visual graph language, “knowledge that walks,” article/newsletter positioning, autonomous scheduled growth, static engine-first landing copy | Preserve files in the first pass; V1 pages lead with Brief/Research/Script |

## Target V1 architecture

```text
Web form / POST /v1/jobs / CLI
  -> authenticate owner and reserve configured credits
  -> create Job + isolated ResearchCase
  -> Extract
       -> Source + ordered SourceSegments with exact locators
  -> Claim
       -> overlapping segment chunks
       -> atomic Claims + ResearchGaps
       -> deduplicate and rank
  -> Research (top five claims)
       -> claim-specific query families
       -> source-role assessment
       -> full source extraction (never snippet-as-evidence)
       -> exact EvidencePassages
       -> ClaimEvidence stance and rationale
       -> claim status calculation
  -> Render
       -> BriefRenderer / ResearchReportRenderer / ScriptRenderer
       -> deterministic citations and appendices from stored IDs
  -> Deliver
       -> persisted Artifact + versions + export
       -> Instant: completed
       -> Verified: ReviewJob + structured ReviewDecisions
  -> immutable UsageEvents + CostLedger entries throughout
```

Research cases are never merged automatically. Legacy Chains remain queryable but
are not the ownership boundary for V1.

## Additive migration plan

1. Add a `schema_migrations` table and idempotent numbered migration runner.
2. Backfill missing legacy columns such as `sources.metadata` with `ALTER TABLE`
   checks before any legacy insert executes.
3. Add source provenance columns without rewriting existing Source rows.
4. Add new tables: `research_cases`, `research_case_sources`,
   `source_segments`, `claims`, `research_gaps`, `evidence_passages`,
   `claim_evidence`, `jobs`, `job_events`, `artifact_versions`, `review_jobs`,
   `review_decisions`, `usage_events`, `cost_ledger`, `credit_accounts`, and
   `credit_transactions`.
5. Add nullable research-case/review fields to `artifacts`. Existing Chain-scoped
   artifacts remain valid.
6. Add indexes and uniqueness constraints needed for idempotent jobs, stable
   segment ordinals, claim/evidence joins, and owner-scoped reads.
7. Never delete or rewrite legacy tables in the V1 migration.

## Smallest complete vertical slice

1. Accept one public YouTube URL with mode, review level, and constraints.
2. Persist caption or Whisper segments with start/end seconds and caption source.
3. Extract claims from overlapping segment chunks and preserve segment IDs.
4. Persist research gaps and research the five highest-priority claims.
5. Ingest discovered sources before treating passages as evidence.
6. Store evidence stance, rationale, source classification, and claim status.
7. Render all three products from the same case; converting modes performs no new
   extraction or unchanged research.
8. Expose job progress, case state, artifacts, evidence, Markdown/HTML export,
   claim deepening, and script-section revision.
9. Route Verified artifacts into the same structured reviewer queue.
10. Record usage, variable cost, configured credit consumption, artifact views,
    exports, revisions, deepening, conversion, and review completion.

The vertical slice uses mocked extraction/search/model calls in its end-to-end
test and real adapters in production code. This makes provenance behavior fully
testable without depending on network availability.

## Exact files expected to change

Initial audit checkpoint:

- `docs/markov-v1-architecture.md`

Research domain and persistence:

- `markov_engine/store/migrations.py` (new)
- `markov_engine/store/records.py`
- `markov_engine/store/base.py`
- `markov_engine/store/sqlite.py`
- `markov_engine/store/__init__.py`
- `tests/test_migrations.py` (new)
- `tests/test_research_store.py` (new)

Structured extraction and research:

- `markov_engine/extract.py`
- `markov_engine/transcribe.py`
- `markov_engine/claims.py` (new)
- `markov_engine/research.py` (new)
- `markov_engine/evidence.py` (new)
- `markov_engine/llm.py`
- `markov_engine/vectors.py`
- `tests/fixtures/youtube_transcript.json` (new)
- `tests/test_segments.py` (new)
- `tests/test_claims.py` (new)
- `tests/test_evidence.py` (new)

Artifacts and operations:

- `markov_engine/renderers.py` (new)
- `markov_engine/revisions.py` (new)
- `markov_engine/reviews.py` (new)
- `markov_engine/billing.py` (new)
- `markov_engine/jobs.py` (new)
- `tests/test_renderers.py` (new)
- `tests/test_revisions.py` (new)
- `tests/test_reviews.py` (new)
- `tests/test_billing.py` (new)

Delivery surfaces:

- `markov_engine/api.py` (new)
- `markov_engine/web.py` (new)
- `markov_engine/cli.py`
- `markov_engine/config.py`
- `markov_engine/__init__.py`
- `pyproject.toml`
- `tests/test_api.py` (new)
- `tests/test_vertical_slice.py` (new)

Documentation and commercial fixtures:

- `README.md`
- `docs/api-examples.md` (new)
- `samples/markov-brief.md` (new)
- `samples/markov-research.md` (new)
- `samples/markov-script.md` (new)

## Deferred after the first slice

- Article heading and PDF page extraction are implemented immediately after the
  YouTube slice proves the shared domain model.
- Durable distributed workers, sophisticated retry scheduling, a standalone SPA,
  enterprise authorization, team workspaces, native mobile clients, and complex
  invoicing are not required for the commercial test.
- A visual knowledge graph, autonomous Chain schedules, article/newsletter-first
  generation, publishing integrations, and generic chat remain parked.

## Acceptance evidence

Each implementation checkpoint must include focused tests and a clean staged diff.
The final end-to-end fixture must demonstrate one case producing all three artifact
types, exact timestamp citations, claim deepening, one script-section revision, a
Verified review decision/finalization, export, usage events, and cost records while
all legacy tests continue to pass.
