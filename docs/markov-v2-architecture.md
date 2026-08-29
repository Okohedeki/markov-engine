# Markov V2 architecture

Status: implementation contract  
Audience: product, engineering, and API consumers  
Thesis: **Start anywhere. Follow the idea. Make something original.**

## The product dream

Markov turns something a person has found into something they can use. A video,
post, article, paper, or question is not treated as an answer to summarize. It is
the first node in a traceable line of inquiry.

The customer should feel three moments:

1. **Orientation** — “I understand this without surrendering my judgment.”
2. **Discovery** — “I can see the non-obvious paths this idea opens.”
3. **Creation** — “I have an original, defensible artifact, not a remix of the
   source.”

The customer-facing jobs are therefore:

- **Catch me up** — a decision-ready brief that states assumptions, omissions,
  uncertainties, and threads worth pulling.
- **Explore where it leads** — a connection map, hidden story, candidate
  hypotheses, research paths, and an inspectable source packet.
- **Turn it into a script** — candidate angles, a chosen defensible angle, full
  narration, fact-check notes, a do-not-repeat list, and section-level revision.

The same promise applies to both product doors: a calm workspace for people and
an asynchronous, structured API for software and agents.

## Audit of the V1 baseline

V1 is a working foundation, not a throwaway prototype.

| Existing capability | V1 implementation | V2 decision |
| --- | --- | --- |
| Source ingestion | `extract.py` classifies and extracts YouTube, articles, PDFs, social URLs, audio, and topics | Keep; improve adapters independently |
| Stable provenance | `source_segments` preserves timestamps, pages, headings, character spans, speakers, and caption origin | Keep as the atomic locator layer |
| Claims and gaps | `claims.py` creates located atomic claims and explicit research gaps | Keep; claims become graph nodes |
| Evidence | inspected passages, source-quality metadata, claim stance/strength, and verification status | Keep; reuse passages for connection validation |
| Shared research | one owner-scoped `research_case` supports Brief, Research Report, and Script conversion | Keep; rename customer-facing Research to Explore |
| Rendering | deterministic renderers preserve claim/evidence IDs and locators | Extend with graph and insight sections |
| Workflow | resumable stage-oriented jobs, idempotency keys, events, webhooks, costs, and review | Extend with connection stages and branch actions |
| Human review | claim/evidence decisions and artifact versions | Extend later to connection and insight review using the same audit shape |
| Commercial surface | credit accounts, product variants, Stripe hooks, workspace, `/v1` API | Preserve `/v1`; add configurable entitlement profiles and `/v2` |
| Deployment | generated static site in `docs/` for GitHub Pages; FastAPI app for the product | Continue splitting static landing and dynamic SaaS deployments |

The current runtime is deliberately compact: FastAPI, SQLite, server-rendered
HTML, and in-process background jobs. That is appropriate for the first complete
V2 slice. The data and service boundaries below let the worker, database, search,
and UI be separated when load requires it, without changing the product model.

## Non-negotiable trust rules

1. **Accuracy and citations are never premium features.** Every plan receives
   the same provenance, uncertainty labels, source visibility, and rejection of
   unsupported assertions.
2. **The seed is context, not corroboration.** A source may originate a claim,
   but it cannot independently verify itself.
3. **Connections explain a mechanism.** Co-occurrence or semantic similarity is
   not enough.
4. **Hypotheses remain hypotheses.** Evidence level travels with a connection
   through the UI, API, renderers, exports, and conversions.
5. **The renderer cannot invent support.** It may only cite persisted claims,
   passages, connections, paths, and insights.
6. **The system can reject the premise.** A useful result may be that the seed's
   framing does not survive evidence or that no defensible connection exists.

## V2 domain model

V2 is an additive graph over the V1 evidence model.

```text
ResearchCase
  ├── Sources ── SourceSegments
  ├── Claims ── ClaimEvidence ── EvidencePassages
  ├── ResearchGaps
  ├── Connections ── ConnectionEvidence
  │      └── endpoints reference claims, sources, gaps, or other connections
  ├── ConnectionPaths ── ordered Connection IDs
  ├── InsightCandidates ── supporting paths and claims
  ├── UserBranchDecisions
  └── Artifacts / versions / review trail
```

### Connection

A connection is an addressable claim about why two nodes belong in the same
line of inquiry. Required fields are:

- two typed endpoints (`claim`, `source`, `gap`, `connection`, or `insight`);
- one connection type;
- statement and mechanism;
- why it matters;
- what supports it and what weakens it;
- where it could lead next;
- evidence level and validation status;
- relevance, evidence strength, novelty, explanatory value, output usefulness,
  risk, and a computed total score.

Allowed connection types:

- shared mechanism
- hidden intermediary
- historical analogue
- second-order consequence
- contradiction
- cross-domain transfer
- incentive link
- emerging pattern
- constraint link
- dependency link

Evidence levels are ordered but not presented as false precision:

1. `established`
2. `evidence_backed_interpretation`
3. `plausible_hypothesis`
4. `speculative_lead`

`ConnectionEvidence` links inspected V1 evidence passages to a connection with
a stance (`supports`, `weakens`, or `context`), strength, and rationale.

### ConnectionPath

A path is an ordered, coherent sequence of validated connections. It stores a
title, summary, ordered connection IDs, aggregate score dimensions, and status.
Ordering is meaningful and validated: each adjacent connection must share an
endpoint or explicitly bridge through the prior connection.

### InsightCandidate

An insight is a possible conclusion or creative angle supported by one or more
paths. It records the thesis, novelty basis, supporting path and claim IDs,
evidence strength, counterevidence, uncertainty, next research step, and status.
An insight cannot silently outrank its weakest essential connection.

### UserBranchDecision

Every `follow`, `save`, `dismiss`, `deepen`, `convert`, or `revisit` action is
persisted with owner, target connection, action, metadata, and timestamp. This
makes exploration resumable and supplies product analytics without hiding state
inside a generated document.

## Discovery and validation pipeline

The first complete V2 workflow is:

```text
submit source
  → extract and segment
  → identify claims and gaps
  → inspect independent evidence
  → propose typed connections
  → validate mechanism and evidence
  → rank connections and build paths
  → derive insight candidates
  → render Brief / Explore / Script
  → user follows a connection
  → new evidence and insight state are persisted
  → Script is regenerated as a version, without redoing prior research
```

Discovery may use an LLM to propose candidates, but validation is a separate
boundary. The validator checks:

- endpoints exist and are not identical;
- connection type and evidence level are from closed vocabularies;
- the mechanism, significance, support, weakness, and next step are explicit;
- cited evidence passages belong to sources attached to the case;
- supporting and weakening evidence is represented honestly;
- the evidence level does not exceed the inspected support;
- a deterministic score can be reproduced from stored dimensions;
- unsupported candidates are rejected rather than polished into prose.

The default score is configurable and intentionally transparent:

```text
score = weighted_mean(
  relevance,
  evidence_strength,
  novelty,
  explanatory_value,
  output_usefulness
) - risk_penalty
```

Weights and thresholds live in configuration. They rank candidates; they do not
convert a hypothesis into a fact. Speculative leads may remain visible when
useful, but must carry the label and a concrete validation step.

## Hybrid model orchestration

Markov owns the workflow and trust boundaries; a provider agent does not decide
what evidence becomes true. The default hybrid route minimizes cloud context:

```text
deterministic extraction + stable locators
  -> local model: chunk claims, entities, queries, initial stance
  -> local model: reduce the complete claim ledger
  -> cloud model: review only the bounded candidate ledger
  -> deterministic search + passage selection
  -> local model: classify each inspected passage
       -> cloud only when local confidence is below the configured threshold
  -> cloud model: synthesize connections from core claims + bounded evidence
  -> deterministic validation, scoring, paths, insight levels, and rendering
```

This is intentionally narrower than delegating the case to a general-purpose
agent. The Responses API and agent tooling remain useful provider capabilities,
but Markov's persisted stages, retries, evidence IDs, budgets, and stopping
conditions are the product contract. A model may propose; it cannot bypass the
validator or silently promote its own outside knowledge to evidence.

## Rendering contracts

All three renderers use the same case graph and emit both readable Markdown and
structured JSON.

### Catch me up / Brief

Required sections:

- bottom line and source orientation;
- strongest supported claims and exact locators;
- assumptions;
- what the source leaves out;
- what may be wrong or unresolved;
- threads worth pulling, backed by ranked connections;
- evidence and source packet.

### Explore where it leads / Research report

Required sections:

- executive synthesis;
- connection map;
- hidden story;
- novel hypotheses with evidence levels;
- ranked research paths;
- counterevidence, limitations, and rejected candidates;
- source packet with inspectable passages.

### Turn it into a script / Script

Required sections:

- candidate angles and the selected original, defensible angle;
- premise check, including permission to reject the seed framing;
- full narration with claim/connection markers;
- visual and production notes;
- fact-check notes and uncertainty;
- do-not-repeat list;
- section IDs that support bounded revision;
- source packet.

Conversion reads existing graph state. Following or deepening a connection adds
new records and produces a new artifact version; it does not mutate old evidence
or erase the prior script.

## API V2

`/v1` remains stable. `/v2` exposes the graph as first-class resources:

- `POST /v2/jobs` — submit source, customer job, review level, and options;
- `GET /v2/jobs/{job_id}` and `/events` — observe meaningful stages;
- `GET /v2/cases/{case_id}` — retrieve case state and resource links;
- `GET /v2/cases/{case_id}/connections` — filter and rank connections;
- `GET /v2/cases/{case_id}/paths` — retrieve ordered paths;
- `GET /v2/cases/{case_id}/insights` — retrieve insight candidates;
- `POST /v2/connections/{id}/validate` — revalidate or attach inspected support;
- `POST /v2/connections/{id}/follow` — branch the research;
- `POST /v2/connections/{id}/decisions` — save, dismiss, or revisit;
- `POST /v2/insights/{id}/convert` — render Brief, Explore, or Script from the
  selected insight;
- `POST /v2/artifacts/{id}/convert` — cross-mode conversion using the same graph.

Responses expose stable IDs, enums, evidence levels, scores, and links. Owner
checks apply to every resource. Mutation endpoints accept idempotency keys where
retries could create cost or duplicate state.

## Entitlements

Entitlements are capability profiles, not scattered plan-name checks:

- `community`
- `cloud_free`
- `cloud_plus`
- `cloud_pro`
- `verified_add_on`

Configuration controls throughput, storage duration, concurrent jobs, export
formats, API access, connection depth, and human-review availability. Community
mode is self-hosted and not artificially metered. Every profile includes claim
provenance, citations, connection validation, uncertainty labels, and access to
its own source packet.

## Analytics

Analytics use the existing owner-scoped usage event ledger. V2 records at least:

- `source_submitted`
- `mode_selected`
- `job_started`, `job_completed`, `job_failed`
- `connection_discovered`, `connection_validated`, `connection_rejected`
- `connection_opened`, `connection_saved`, `connection_dismissed`
- `connection_followed`, `connection_deepened`
- `path_opened`
- `insight_selected`, `insight_converted`
- `artifact_generated`, `artifact_revised`
- `converted_to_brief`, `converted_to_research`, `converted_to_script`

Events contain IDs and categorical metadata, not source text or private artifact
content. Operational cost remains in the separate cost ledger.

## Workspace and landing experience

The workspace begins with one clear input and the three customer jobs. During a
run, the timeline names the work: extract, claims, evidence, connections,
validation, paths, insights, artifact. The case view keeps the document primary
and adds a connection rail with evidence level, mechanism, strengths,
weaknesses, and the next action. Follow, save, dismiss, deepen, and convert are
explicit controls with reversible state where possible.

The landing page is a concise product demonstration, not a simulated live SaaS.
It uses the promise **“Turn anything you find into something you can use.”**,
puts the source input concept above the fold, labels supported source types, and
offers an interactive precomputed sample built from real, inspectable sources.
The visual system is a plain modern sans serif, neutral palette, one accent,
generous whitespace, restrained motion, and no invented case numbers, passages,
or performance claims.

GitHub Pages hosts the static marketing and sample experience. The FastAPI SaaS
requires a service host with a writable database and background execution; its
deployment remains separate from Pages.

## Delivery sequence

1. Add migration 2 and typed store records/methods.
2. Add deterministic scoring, candidate validation, paths, and insights.
3. Insert V2 stages between evidence comparison and artifact rendering.
4. Extend all renderers and implement branch-to-revised-Script behavior.
5. Add `/v2` resources, entitlement enforcement, and analytics.
6. Replace the workspace labels and add the connection rail.
7. Replace the landing and sample with the real source-to-insight demonstration.
8. Verify migrations, unit tests, API tests, renderer contracts, cross-mode
   conversion, rejected candidates, entitlements, and the complete vertical
   slice before publishing the Pages checkpoint.

## Acceptance slice

The first release is complete only when an automated end-to-end test proves:

1. one YouTube or TikTok source becomes located segments;
2. claims and gaps are persisted;
3. at least three different typed connections are validated with evidence
   levels and reproducible scores;
4. one connection path supports an insight candidate;
5. complete Brief, Explore, and Script artifacts render from that shared state;
6. one connection is followed and the user decision is recorded;
7. a revised Script version incorporates the followed branch;
8. one unsupported connection is rejected and never presented as established;
9. citations, uncertainty, and source access are identical across entitlement
   profiles.
