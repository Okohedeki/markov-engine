# Creator worklist direction

## Working brief

- Problem: frequent creators lose their place moving between ideas, sources and drafts.
- Outcome: scan a batch, inspect a lead, write from its evidence and track progress.
- Visual thesis: an uncluttered editorial worklist inside the existing soft studio.
- Content: real story titles, source provenance, research state and saved outputs.
- Interaction: details appear on demand; filters and writing context stay intact.
- Constraints: mobile and desktop, existing server templates, no new dependencies.

## Art-direction contract

- Memory hook: a story opens its source material directly beneath its queue row.
- Composition: compact heading and intake, status filters, one continuous worklist.
- Type: retain DM Sans; titles lead, metadata supports, controls remain readable.
- Color: existing cool paper, dark ink and restrained orange for active choices.
- Material: quiet rules and a white reading surface, not a grid of feature cards.
- Motion: native disclosure; no automatic movement or ornamental loading effects.
- Forbidden: dashboard hero copy, fake metrics, channel-specific workflow labels,
  omnipresent upsells, scheduling, publishing, analytics or a new project hierarchy.

## Reference principles

- [Recall](https://www.recall.it/): source identity beside the material it informs;
  retain the existing brand direction without borrowing its knowledge-base scope.
- [Vitsœ](https://www.vitsoe.com/us/about/good-design): understandable, unobtrusive
  tools; remove repeated explanation once the user is in the working surface.
- [W3C disclosure](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/): explicit,
  keyboard-operable reveal controls, visible focus and understandable open state.

## Scope and verification

Keep discovery, selection, source inspection, existing writing and story progress.
Generated scripts and Story Mode retain their server-side paid gates. Manual
progress is not proof of verification or publication. Case-wide sources must not
be presented as evidence supporting every lead. No new generation or storage system.

Review actual desktop and mobile renders with populated, empty and filtered views.
Exercise selection, status persistence, source loading/retry, editor links and
keyboard access through direct browser checks; do not add or run test suites.

## Implemented and reviewed — 2026-09-06

- Compact queue, four core navigation destinations and contextual batch actions.
- Owner-checked, read-only source/document previews loaded on demand; no model call
  or generation charge when opening one. Failed loads have a retry and full-page fallback.
- Format-neutral manual progress; filters survive bulk moves and writing revisions.
- Source links beside the desktop editor; direct source access and saved/unsaved
  feedback on mobile. Revision history is collapsed until needed.
- Existing script-generation and Story Mode paid gates remain unchanged.

Browser review used isolated copies of local data, including the saved MLK research;
the original databases were not modified. Research notes in that preview were
rendered from stored findings, not newly generated scripts. A separate preview
owner had 31 explicitly labeled layout fixtures for pagination and batch checks.

Verified through direct Chromium interactions:

- Queue and writing at 1440, 1024 and 390px; additional 320px editor check exposed
  a tab overflow that was fixed and rechecked.
- Keyboard disclosure, on-demand fetch/reopen without refetch, source links,
  writing entry and filtered return, source-tab editing continuity and saving.
- Failed source request and successful retry; mobile navigation focus restoration.
- Empty workspace, empty search, 30-row selection, next-page navigation and persisted
  bulk progress with the original search retained.
- Cross-owner preview denial, cross-origin mutation denial, free-account script
  and series upgrade redirects. No paid generation was triggered.
- Series library/detail desktop, tablet and mobile renders; no reported page errors
  or document overflow. Modified Python modules pass syntax and Ruff checks.

At the end of this initial UI pass, no test suites were added or run and angles
were still stored only inside topic documents. Those limitations are superseded
by [the tested editorial v1 follow-up](editorial-v1-acceptance.md): individual angle
tracking, selected evidence packets and paid drafts now work together. That record
distinguishes the live drafting check from functional coverage and remaining limits.
