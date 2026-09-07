# Production desk entry refinement

- Problem: a frequent creator needs to start with something they found, not an
  access key or a pitch for paid output types.
- Outcome: open the local production desk, paste a source, choose an interesting
  story, then write from its attached sources.
- Visual thesis: preserve the soft studio, compact worklist, DM Sans, white writing
  surfaces and restrained orange action accent. No new design system or feature tiles.
- Content: Production desk → prominent universal input → TikTok, Instagram,
  YouTube, podcasts and articles → story queue → Write a draft / Plan a series.
- Interaction: input stays visible; selecting stories reveals writing actions and
  their credit cost. Payment is a contextual boundary, not the workspace headline.
- Constraints: local preview entry is explicit, default-off and loopback-only.
  Hosted accounts and API authentication remain protected. Sources requiring login
  or blocked downloads may need pasted text/transcripts; do not promise universal
  extraction success. Preserve free discovery and paid full drafts / series.

Acceptance: no key prompt in the configured localhost preview; no anonymous access
in ordinary or non-loopback deployments; input types visible before typing; mobile
and desktop rendered review; full regression suite and owner isolation preserved.

## Verified

- Local preview at `http://127.0.0.1:8014/app` opens without entering a key;
  `/app/login` redirects to the desk. It uses `MARKOV_LOCAL_PREVIEW_OWNER` with
  loopback client/host checks and a server bound to localhost, without proxy headers.
  The setting is off by default. Never enable it on a shared hosted service.
- Hosted/keyed sessions and the API retain authentication; regression coverage
  rejects non-loopback clients and public Host values, including spoofed headers.
- Intake is visible when the desk opens. TikTok, Instagram, YouTube, podcasts,
  articles and PDFs appear in intake and homepage copy, with blocked-source fallback.
- Selection actions say Write a draft / Plan a series, retain the credit disclosure,
  and leave paid entitlement checks intact. No new social-platform integrations
  or extraction guarantees were introduced; platform names match existing routes.
- 132 tests passed. Chromium checked direct entry, source labels, selected actions,
  homepage, reduced motion and document overflow at desktop/mobile; desk viewports
  include 1440, 760, 390 and 320px. Captures: `.tmp/desk-entry/`.
- Homepage source labels were enlarged after visual inspection. No Lighthouse run:
  this was a scoped copy/entry refinement, not a performance audit or deployment.
- Single-file commits remain local pending the earlier unpushed-history decision.
