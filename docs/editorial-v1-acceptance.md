# Editorial v1 acceptance

The product unit is a distinct, evidence-backed story angle, not a submitted URL.
Keep the existing soft-studio worklist and its source/writing disclosure. No new
navigation or visual system: titles lead, exact passages support, uncertainty stays
visible, and choosing an angle carries that same packet into paid development.

## Moat hypothesis, not a present claim

Multi-format writing and research alone are not defensible differentiators:
[Jasper](https://www.jasper.ai/) combines research and content workflows;
[Copy.ai](https://www.copy.ai/) covers research and content operations.
Markov must earn an advantage in useful, non-obvious angles per source and less
creator time spent independently checking and developing each one.

An accumulating private editorial history can strengthen that advantage: used
angles, rejected directions, source passages, qualifications and series continuity.
Do not claim that feedback learning, web-wide originality or a proprietary data
advantage already exists. Public sources and prompts alone are reproducible.

## Bounded implementation

- Reuse immutable discovery events for stable angle identity; no new job system,
  vector database, event framework or duplicate persistence layer.
- Expose individual angles in the queue. Preserve older tracked topics and cases.
- Keep selected support and challenge passages attached through preview, export,
  paid drafting and series. Never turn source-count into a verification score.
- Isolate ownership and artifact branches; repeated development reuses only the
  same selection. New discoveries cannot silently change an old selection's meaning.
- Retain free discovery and paid full talking points / Story Mode boundaries.

## Verification

The user has now requested a tested v1. Run focused existing tests, add regression
coverage for the new selection boundary, and exercise real persisted research in
the browser. Include isolation, multiple users, retry/reuse, bulk status and series.
Separate deterministic integration results from live research/editorial quality.
Functional passing tests do not prove publication quality or production capacity.

## Verified implementation — 6 September 2026

- Each discovery angle is a stable `angle:event:index` queue entry with independent
  status and an immutable support/challenge packet. Prior tracked work is preserved.
- Preview and shortlist export use only the selected passages. Paid conversion and
  series episode development preserve the same selection and reuse its saved draft.
- Writing cites retained evidence IDs; application code attaches original passages.
  Unknown references and altered citation quotations are rejected. This validates
  provenance, not whether each narrative inference follows from its citation.
- Drafts remain explicitly unreviewed. Section edits retain their source notes in
  exports. Free accounts cannot bypass paid drafting or Story Mode routes.
- Duplicate requests serialize per case; different creators can draft concurrently.
  This is intentionally a single-process v1 safeguard, not a multi-worker lock.
  Keep one web worker until shared conversion leases are implemented.
- `python -m pytest -q`: 131 passed. Coverage includes ownership, persistent progress,
  series identity, preview filtering, paid conversion/reuse, editing/export, invalid
  provider refunds, two creators concurrently drafting and duplicate requests.
  Older fixtures were updated to declare paid access and use current UI labels;
  production entitlement and evidence requirements were not relaxed.
- Chromium: real saved MLK queue and paid draft inspected at 1440, 390 and 320px,
  including source disclosure and reduced motion. No document overflow or JS errors.
  Screenshots: `.tmp/editorial-v1/`. Initial mid-transition captures were replaced
  with stable viewport captures; retained passages received spacing and source links.

### Live check and limits

The existing hybrid configuration generated a 276-word draft of the labor story
from the saved MLK research in `data/creator-editorial-preview.db`. Its first attempt
altered a citation quotation and was rejected/refunded; ID-based passage assembly
fixed that failure, and the next attempt produced saved artifact 4. It preserves
the caveat that assassination alone does not establish the settlement's cause.
The original research databases were not modified. Preview credits are labeled local
fixtures, not purchases. Discovery was not rerun for this drafting check.

The two retained labor sources are Wikipedia and HISTORY, not two primary accounts.
This is a usable research draft, not a verified historical conclusion. A broader
creator-reviewed source set must establish useful-angle yield and factual quality.
No web-wide novelty guarantee, learned editorial memory, production load benchmark,
automatic series narrative generation, or self-service paid onboarding is claimed.
Series v1 organizes selected stories with creator-supplied premise and episode order.

Preview: `http://127.0.0.1:8014/app`, preview-only key `worklist-local-preview`.
The final preview uses the configured hybrid model and live search; new research
and new paid drafts can incur provider costs. It binds only to localhost.

All checkpoints in this work change one file and remain below 150 changed lines.
They remain local: publishing also includes pre-existing unpushed history, for
which the earlier requested publishing decision remains unanswered.
