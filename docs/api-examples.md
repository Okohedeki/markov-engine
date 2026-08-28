# Markov API V2 examples

All customer requests use `X-Markov-Key` or a Bearer token. Mutating job
creation should include a stable `Idempotency-Key` for the logical request.

## Start with one source

```http
POST /v2/jobs
X-Markov-Key: customer-key
Idempotency-Key: japan-demographics-explore-01
Content-Type: application/json

{
  "job": "Explore where it leads",
  "review_level": "instant",
  "source": {
    "type": "url",
    "value": "https://www.youtube.com/watch?v=..."
  },
  "options": {
    "focus": "second-order market effects",
    "max_connections": 8
  },
  "webhook_url": "https://customer.example/hooks/markov"
}
```

Valid job labels are `Catch me up`, `Explore where it leads`, and `Turn it into
a script`; `brief`, `research`, and `script` are accepted aliases. The response
is `202 Accepted` with durable links to the job, event stream, and shared case.
An identical owner/idempotency-key pair returns the original job.

## Observe the work

```http
GET /v2/jobs/{job_id}
GET /v2/jobs/{job_id}/events
X-Markov-Key: customer-key
```

Stages include source extraction, locator preservation, claims, evidence,
connection discovery, connection validation, path construction, insight
synthesis, and artifact rendering.

## Retrieve the complete case graph

```http
GET /v2/cases/{case_id}
GET /v2/cases/{case_id}/connections?status=validated
GET /v2/cases/{case_id}/paths
GET /v2/cases/{case_id}/insights
X-Markov-Key: customer-key
```

The case response contains sources and stable segments, claims and linked
passages, gaps, typed connections and connection evidence, ordered paths,
insight candidates, branch decisions, artifacts, and costs.

Each connection includes both endpoints, its type, mechanism, significance,
supporting and weakening conditions, next step, evidence level, validation
status, six score dimensions, and deterministic total score.

## Revalidate a connection

```http
POST /v2/connections/{connection_id}/validate
X-Markov-Key: customer-key
```

Revalidation uses current stored passages. It can downgrade an evidence level
or reject the candidate; it cannot promote a connection by prose alone.

## Save or dismiss a branch

```http
POST /v2/connections/{connection_id}/decisions
X-Markov-Key: customer-key
Content-Type: application/json

{"action":"save","metadata":{"list":"weekly research"}}
```

Actions are `open`, `save`, `dismiss`, `follow`, `deepen`, and `revisit`.

## Follow a connection into a revised Script

```http
POST /v2/connections/{connection_id}/follow
X-Markov-Key: customer-key
Content-Type: application/json

{
  "artifact_id": 42,
  "options": {"target_minutes": 10, "audience": "general"}
}
```

When `artifact_id` names a Script in the same owner-scoped case, Markov records
the branch decision and adds a `connection_followed` artifact version. If no
Script is supplied, it creates one from the shared graph.

## Convert an insight or artifact

```http
POST /v2/insights/{insight_id}/convert
X-Markov-Key: customer-key
Content-Type: application/json

{"mode":"Turn it into a script","review_level":"instant","constraints":{}}
```

```http
POST /v2/artifacts/{artifact_id}/convert
X-Markov-Key: customer-key
Content-Type: application/json

{"mode":"Catch me up","review_level":"instant","constraints":{}}
```

Conversion reuses extraction, claims, evidence, connections, paths, and insights.
It does not repeat unchanged research.

## Entitlements

```http
GET /v2/entitlements
X-Markov-Key: customer-key
```

Profiles control capacity, retention, API access, export formats, graph size,
and human review. All profiles retain citations, accuracy controls, uncertainty
labels, and source packets. Community mode is unmetered.

## V1 compatibility, exports, billing, and review

Existing `/v1` job, case, claim-deepening, revision, export, credit, Stripe, and
internal review routes remain available. Notable endpoints are:

```http
GET  /v1/artifacts/{artifact_id}/export?format=markdown
POST /v1/claims/{claim_id}/deepen
POST /v1/artifacts/{artifact_id}/revisions
GET  /v1/catalog
GET  /v1/account
POST /v1/billing/checkout
GET  /internal/reviews?status=queued
POST /internal/reviews/{review_id}/finalize
```

Supported export formats are `markdown`, `html`, and `json`, subject to the
owner's configured entitlement. HTML escapes source and artifact markup before
applying the supported heading/list subset.

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
