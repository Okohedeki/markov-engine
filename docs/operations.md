# Markov V1 operations

## Database and migrations

The API opens `MARKOV_DATABASE_PATH` and automatically applies every unapplied
numbered migration. Migrations are additive and idempotent. Back up the SQLite
file before each release and test the release against a restored copy.

The application enables SQLite foreign keys. Do not copy individual tables
between databases; back up the complete file so claim, evidence, version, review,
credit, and usage relationships stay intact.

## Worker model

`POST /v1/jobs` writes the credit reservation, research case, job, and queued
event before scheduling work. V1 background work runs in the FastAPI process.
Stage events are durable, but the task itself is not recovered automatically if
the process stops. A stopped `running` job must be inspected and retried by an
operator. Credit reservations are idempotent and failed jobs are refunded once.

Run one application process against a SQLite file:

```bash
markov-api
```

Do not run multiple write workers against the same SQLite file. Moving to a
durable queue should retain `jobs` and `job_events` as the public state model and
replace only the in-process scheduling adapter.

## Authentication and owner isolation

`MARKOV_API_KEYS` is a JSON map from secret key to stable owner ID. Clients may
send `X-Markov-Key` or `Authorization: Bearer ...`. Case and artifact retrieval
joins through the owner-scoped research case. Reviewer keys are separate in
`MARKOV_INTERNAL_API_KEYS`.

The browser flow exchanges a configured key for an HttpOnly, SameSite-signed
identity cookie. Change `MARKOV_WEB_SESSION_SECRET` before deployment. Terminate
TLS at the application gateway and mark cookies Secure there or in a deployment
adapter.

## Billing

All six product credit costs must be configured. A job reserves credits before
creating customer work. The reservation uses `reserve:{job_id}` as an immutable
idempotency key. Terminal processing failures use one matching refund.

Optional Stripe Checkout uses configured Price IDs only. Configure the public
Stripe webhook to send events to `/v1/billing/stripe-webhook`. The endpoint
verifies Stripe's timestamped signature and applies each event ID once.

The ledger distinguishes customer credits from actual variable costs. Record
LLM, search, transcription, storage, and review costs in `cost_ledger`; do not
represent those internal costs as credit balances.

## Review workflow

1. A Verified artifact is generated with `awaiting_review` status.
2. A `ReviewJob` appears at `/app/reviews` and `/internal/reviews`.
3. The reviewer opens seed segments, claims, exact passages, and source links.
4. Every acceptance, rejection, stance/status change, locator correction, or
   edit is written as a structured `ReviewDecision` with a reason.
5. Finalization creates an artifact version, records review minutes and cost,
   changes the case/artifact/review status to completed, and emits
   `verified_review_completed`.

Reviewers should never accept a snippet, homepage, or model judgment as evidence.
They must inspect the original passage and locator.

## Webhooks

Customer webhook URLs must be HTTPS and cannot be literal private or loopback
addresses. Markov does not follow redirects. When
`MARKOV_WEBHOOK_SIGNING_SECRET` is set, payloads include
`X-Markov-Signature: sha256=<hex digest>` calculated over the exact request body.
Consumers should verify the digest before parsing JSON.

Delivery failure is stored as a `webhook_failed` job event and does not change a
completed artifact back to failed.

## Monitoring

Monitor:

- counts and durations by job mode and review level;
- failed jobs and their last stage;
- credits reserved/refunded and payment failures;
- model, search, transcription, storage, and human-review costs;
- unverified/disputed claims and cases with no authoritative evidence;
- artifact views, exports, deepening, revisions, conversions, and repeats;
- reviewer queue age and review minutes.

V1 stores the underlying events and ledgers but does not ship a metrics exporter.

## Known operational limits

- no distributed queue, automatic retry scheduler, or dead-letter queue;
- no horizontal SQLite writer scaling;
- no upload/object-storage pipeline;
- no OAuth, password reset, team roles, or enterprise policy layer;
- no Stripe subscription lifecycle, invoicing, tax, or refund automation;
- no browser-based source archiving when a publisher later changes a page;
- no guaranteed access to blocked, private, paywalled, or deleted sources.
