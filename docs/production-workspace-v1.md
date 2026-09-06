# Production workspace V1

Preserve the approved homepage visual direction. The customer is a creator
planning up to 30 videos a day, not a user seeking a one-off summary.

Journey: bring a link → inspect connected stories → collect distinct ideas →
select a production batch → develop paid talking points or a paid series →
record and mark progress. Sources and uncertainty stay available on Free.

Design: a quiet, dense editorial queue with status filters, useful counts,
bulk selection and one clear next action. Mobile uses readable stacked rows,
not a horizontally scrolling desktop table. Story Mode is an ordered series
workspace with a premise, episode sequence and completion progress.

Reference: Buffer's public Publish page separates queue/drafts/workflow states;
Notion's project pages use clear ownership and status. Borrow these organizing
principles, not their branding or claims about direct publishing.

Paid boundary: server-side entitlements on script submission, conversion and
connection following; Plus/Pro include talking points and Story Mode. Default
new deployment profile is Free. Credits alone must not unlock paid capability.
Existing historical outputs are not deleted or confiscated on a downgrade.

Legal identity supplied by the owner: EyeQ enterprises, Phoenix,
okohedeki@gmail.com. Privacy/terms/copyright pages describe verified behavior,
not assumed vendors, retention promises or blanket regulatory compliance.
They require operator/legal review before a production launch.

Verify real persistent queue/series behavior, tenant isolation, paid gates,
mobile/desktop rendering, public journey, source links and static export.
Use the Git checkpoint skill for small verified local commits. The earlier
push rejection remains unresolved; do not publish or retry the push.

## Verification — 6 September 2026

- Full suite: 108 tests passed and the process exited normally, using
  `MARKOV_DEFAULT_ENTITLEMENT_PROFILE=cloud_pro` for legacy paid-workflow tests.
  Free/default capability tests explicitly check the Free profile and block
  script submission, conversion, connection following and batch generation.
- Four older test functions now close their own SQLite connections in a
  `finally` block; these had kept pytest alive after its passing result.
- Focused Ruff checks passed. `py -3.11 scripts/build_pages.py` regenerated
  public pages and assets; a repeat build produced no additional changes.
- Chrome at 1440×900, 1024×768 and 390×844: 27 captures across the homepage,
  pricing, legal pages, queue, series, upgrade and talking-point library;
  no route, asset, JavaScript, landmark or horizontal-overflow failures.
- The restarted localhost preview on port 8013 passed nine additional
  homepage, sign-in and queue captures across the same viewports.
- Isolated, explicitly labelled preview fixtures verified selecting 30 ideas,
  persistent bulk shortlisting, source-linked Markdown export, series creation,
  episode reordering and recording progress after reload. Owner isolation,
  cross-origin rejection and Free paid-action bypass attempts were checked.
- 320px and 760px series reflow, mobile-menu Escape, keyboard FAQ/source
  disclosure, reduced-motion settings and JavaScript-disabled batch forms
  were checked. Rendered desktop/mobile screenshots were visually reviewed.

Not a hosted-launch approval: live model/search quality, production throughput,
  subscription checkout and a Lighthouse/conformance audit were not verified.
  The local preview uses offline research settings; example fixtures are not
  live research. Hosted processors, retention procedures, pricing and legal
  notices still require operator confirmation before launch.

The current changes are local, single-file checkpoints below the 150-line
  ceiling. Remote publication remains paused after the earlier push denial.
  The pre-existing deletion of `docs/v5-interaction-contract.md` and local
  `.tmp/` QA artifacts were deliberately left outside the commits.
