# Markov API examples

All customer requests use `X-Markov-Key` or a Bearer token. Mutating job creation
should include a stable `Idempotency-Key` unique to the customer's logical
request.

## Create an Instant Brief

```http
POST /v1/jobs
X-Markov-Key: customer-key
Idempotency-Key: youtube-brief-2026-08-26
Content-Type: application/json

{
  "mode": "brief",
  "review_level": "instant",
  "inputs": [
    {"type": "url", "value": "https://www.youtube.com/watch?v=..."}
  ],
  "constraints": {"focus": "economic claims", "depth": "standard"},
  "webhook_url": "https://customer.example/hooks/markov"
}
```

## Create a Verified Script from a question

```http
POST /v1/jobs
X-Markov-Key: customer-key
Idempotency-Key: japan-rates-script-v1
Content-Type: application/json

{
  "mode": "script",
  "review_level": "verified",
  "inputs": [
    {"type": "text", "value": "Could Japan's demographic shift affect U.S. borrowing costs?"}
  ],
  "constraints": {
    "target_minutes": 12,
    "audience": "general",
    "tone": "documentary",
    "format": "youtube_video_essay",
    "premise": "Demographics can transmit through global bond markets"
  }
}
```

The response is `202 Accepted` with a durable job and case ID. An identical
owner/idempotency-key pair returns the existing job with `created: false`.

## Status and events

```http
GET /v1/jobs/{job_id}
X-Markov-Key: customer-key

GET /v1/jobs/{job_id}/events
X-Markov-Key: customer-key

GET /v1/research-cases/{case_id}
X-Markov-Key: customer-key
```

Case retrieval includes sources and preserved segments, claims and linked
evidence, research gaps, artifacts, and cost records.

## Convert an existing case

```http
POST /v1/research-cases/{case_id}/artifacts
X-Markov-Key: customer-key
Content-Type: application/json

{"mode":"research","review_level":"instant","constraints":{}}
```

Conversion charges the configured product credit cost only when it creates a new
mode/review-level combination. It does not rerun unchanged extraction or claim
research.

## Deepen one claim

```http
POST /v1/claims/{claim_id}/deepen
X-Markov-Key: customer-key
Content-Type: application/json

{"max_sources":5,"time_budget_s":90}
```

Deepening searches for stronger evidence and counterevidence, links exact new
passages, recalculates status, and versions only affected artifact sections plus
global evidence appendices.

## Revise one script section

```http
POST /v1/artifacts/{artifact_id}/revisions
X-Markov-Key: customer-key
Content-Type: application/json

{
  "section_id": "narration",
  "replacement": "A shorter qualified passage using the existing claim [C12] and evidence [E31]."
}
```

A replacement may reuse claim/evidence IDs already assigned to that section. It
cannot introduce provenance IDs from another section or case.

## Export

```http
GET /v1/artifacts/{artifact_id}/export?format=markdown
X-Markov-Key: customer-key
```

Supported formats are `markdown`, `html`, and `json`. HTML escapes all source and
artifact markup before applying the supported heading/list subset.

## Credits and checkout

```http
GET /v1/catalog
X-Markov-Key: customer-key

GET /v1/account
X-Markov-Key: customer-key

POST /v1/billing/checkout
X-Markov-Key: customer-key
Content-Type: application/json

{"pack_name":"starter"}
```

Checkout returns the configured Stripe Checkout URL. It is unavailable when
Stripe keys and credit-pack maps are not configured.

## Internal review

Internal routes require a key from `MARKOV_INTERNAL_API_KEYS`.

```http
GET /internal/reviews?status=queued
X-Markov-Key: reviewer-key

GET /internal/reviews/{review_id}
X-Markov-Key: reviewer-key

POST /internal/reviews/{review_id}/decisions
X-Markov-Key: reviewer-key
Content-Type: application/json

{
  "entity_type": "claim",
  "entity_id": "12",
  "decision_type": "claim_status_changed",
  "new_value": "qualified",
  "reason": "The inspected passage supports only the narrower time period."
}

POST /internal/reviews/{review_id}/finalize
X-Markov-Key: reviewer-key
Content-Type: application/json

{"review_minutes":11.5}
```

Every decision is stored structurally. Finalization records a version, human
review time/cost, reviewer identity, and the completion analytics event.

## Webhook payload

```json
{
  "event": "job.completed",
  "job": {"id": "...", "status": "completed", "stage": "completed"},
  "artifact_ids": [42]
}
```

When configured, verify `X-Markov-Signature` as an HMAC-SHA256 hex digest over
the exact body using `MARKOV_WEBHOOK_SIGNING_SECRET`.
