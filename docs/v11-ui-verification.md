# Soft studio verification

Verified locally on 2026-09-05. Direction: `v11-soft-studio.md`.

## Delivered

- Replaced the warm, flat pastel treatment with a cool opening, compact floating
  white navigation, self-hosted rounded typography, tactile segmented controls,
  and softly elevated white writing surfaces.
- Replaced the homepage's embedded dashboard with a conversation → angles →
  outline demonstration. Selecting an angle opens its actual matching example.
- Reorganized the example studio around a horizontal topic selector, readable
  idea summaries and a contextual editor. Shortlists, local edits, copy and
  Markdown export retain their existing behavior.
- Carried the shared material and control system through authentication, the
  working studio, topic views, draft surfaces and supporting public pages.
- Exported the same public implementation to the existing static site.

The frontend/design and branded-landing-page skills informed the reference
contract, focused demonstration and rendered iteration. Recall's actual browser
rendering was the visual reference; its logo, font and proprietary assets were
not copied. DM Sans is an 89,000-byte self-hosted WOFF2 converted from Google's
official font repository; the SIL Open Font License is included beside it.

## Verification

- Live route matrix: 39 captures across 13 routes, zero reported failures.
- Static route matrix: 12 captures across four routes, zero reported failures.
- Final public spacing/contrast refinements: six additional live and six static
  captures, zero reported failures.
- Viewports: 1440 × 900, 1024 × 768 and 390 × 844.
- Working/public interaction suite: 18 checks passed after final refinements.
- Static interaction suite: 12 checks passed.
- Additional state captures: conversation, draft, outline editor, empty shortlist,
  invalid-key error and authenticated composer at all three viewports.
- Self-hosted font loads at all tested widths. Sampled opening text/background
  contrast passes at every width; the lowest final ratio is 5.92:1. This is a
  targeted gradient-text check, not a claim of a complete accessibility audit.
- Focused API/static-export tests: 11 passed after the final content changes.
- Full Python suite reported 92 passed. The process stayed alive after reporting
  completion and was interrupted during shutdown; no clean full-suite process
  exit is claimed. The focused suite exited normally.
- JavaScript syntax, focused Ruff and final diff whitespace checks passed.

Manually reviewed desktop and mobile composition, tablet hierarchy, native
editors, the invalid-key error, focus outlines and the authenticated topic view.
Keyboard tests cover demo tabs (arrows/Home/End), mobile navigation, focus
restoration, app drawer containment, collection persistence, export contents,
clipboard success/fallback, corrupt/blocked storage and reduced motion.

Reports and screenshots are in `.tmp/soft-studio-final/`,
`.tmp/soft-studio-polished/`, `.tmp/soft-studio-static/`,
`.tmp/soft-studio-static-polished/`, and `.tmp/soft-studio-states/`.
Lighthouse is not installed in the available runtime; Lighthouse and field
Core Web Vitals scores were not collected.

## Preserved boundaries

No backend feature was replaced or removed. Examples remain explicitly
prewritten, not a live discussion feed. Live discovery, bulk AI generation,
scheduling and social publishing remain separate engine integrations.

The pre-existing deletion of `docs/v5-interaction-contract.md` remains unstaged.
No real customer data or credits were changed by verification; authenticated
checks used the existing isolated QA database. All checkpoints remain local.
The earlier shared-main push rejection was respected; no push was retried.
