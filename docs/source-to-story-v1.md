# Source-to-story V1

2026-09-05. The user's correction supersedes V10/V11's generic posting-angle
positioning. On 6 September the user explicitly set aside the previous UI/UX
skills and requested independent, high-quality reference-led design judgment.

## Scope and acceptance

Default scope, pending the user's optional clarification: a complete public
how-it-works section. Do not develop the guest demo or change the engine,
authentication, billing, private data or signed-in workspace.

The customer posts often and needs genuinely different stories. They bring a
link; Markov follows related articles and non-obvious connections, then develops
fresh script ideas. Summarization is an internal aid, not the product promise.

V1 is ready when a visitor can follow one complete example, inspect each
original source, understand why the connection matters, choose a script angle,
and read/copy its source-linked outline. The page and recorded walkthrough must
not pretend that this curated example is a live engine run.

## Direction contract

1. Problem: creators need stories beyond the obvious retelling of a source.
2. Outcome: see a link become connected stories and a specific script idea.
3. Thesis: an inviting, softly dimensional source trail; curiosity made legible.
4. Content: original source, two unexpected related stories, a chosen script
   treatment, inspectable source notes. Keep the transformation on one canvas.
5. Interaction: purposeful step controls, branching story selection, a readable
   script treatment with copy/download and a captioned click-to-play recording.
6. Constraints: existing FastAPI/Jinja/static export; no new account-free app,
   paid generation or simulated research. Keyboard, no-JS and narrow mobile work.

Memory hook: a space-station water story leads to a brewery and a chip factory.
The newer design instruction replaces the prior prescribed archetype and visual
rules. Keep working interactions and real content; design the page independently.

Live references visually inspected in the browser on 6 September:

- Recall, https://www.recall.it/: asymmetrical opening, medium-weight headline,
  compact capsule navigation and tangible source material as the visual anchor.
- Linear, https://linear.app/: readable type, deliberate spacing, restrained
  interface detail and one clear product story per section.
- Cosmos, https://www.cosmos.so/: visual discovery and layered objects that feel
  connected to the product's purpose rather than a feature list.

Translation: a focused left-hand promise, a photographic source-to-story
composition, then a spacious interactive source trail. Do not copy competitors'
assets, proprietary fonts, logos, testimonials or claims. Use the existing
self-hosted DM Sans as a pragmatic licensed typeface, with a lighter hierarchy.

## Source ledger

Public sources inspected on 2026-09-05. This is an editorial example, not a
claim that Markov automatically discovered these exact connections.

- NASA, 20 June 2023: [water recovery milestone](https://www.nasa.gov/missions/station/iss-research/nasa-achieves-water-recovery-milestone-on-international-space-station/).
  Supports the ISS system demonstrating 98% total water recovery. This is an
  archival starting article, not a current breaking-news claim.
- Epic Cleantec: [recycled-water beer project](https://epiccleantec.com/blog/epic-onewater-brew-recycled-beer).
  The company's account describes treated shower/laundry greywater from a San
  Francisco building used for a beer project with Devil's Canyon. Treat claims
  as a participant's account, not independent proof of public acceptance.
- TSMC: [Arizona sustainability and water plans](https://www.tsmc.com/static/abouttsmcaz/index.htm).
  The company describes a water reclamation plant expected in 2028 and a target
  of at least 90% recycling. These are plans, not achieved results.

The thematic connection is water reuse under different constraints. Do not
claim shared hardware, NASA technology transfer, equal water standards or
comparable percentage denominators. Script angles are editorial interpretations.
The supporting links and these boundaries must travel with copied outlines.

## Verification plan

Check desktop, tablet and mobile renders; all step/branch controls; keyboard
and focus; copy success and manual fallback; exact export; deep links; reduced
motion; no-JS readable content; no eager video load; playback/captions; source
links; no guest-demo promotion; live/static parity; and preserved private auth.

Use small verified local commits. Earlier remote push approval was rejected;
do not retry without explicit user approval. Preserve unrelated worktree changes.

## Verified delivery · 6 September 2026

- Replaced the homepage's generic posting-angle promotion with a visual
  source-to-story opening and an inspectable, branching editorial example.
- Both branches include a hook, a three-beat outline, reporting boundaries,
  original sources, exact clipboard output and a Markdown download.
- Added an actual 46.2-second recording of the section, English captions, a
  native click-to-play player and a direct download. The MP4 is 1.12 MB and is
  not requested on initial page load. Closing the player pauses playback.
- Updated the GitHub Pages export, including project-relative assets and
  accurately labeled local-setup links instead of guest-demo promotion.

Checks completed in Chrome against the local FastAPI site and static export:

- `pytest tests/test_api.py tests/test_guest_ui.py -q`: 12 passed.
- `source_trail_qa.py`: seven check groups passed on both builds, including
  both branches, exact exports, clipboard fallback, keyboard tabs, deep links,
  reduced motion, readable no-JS content and widths 320/390/760/1024/1440.
  Layered titles and source credits are checked for visual occlusion.
- `source_film_qa.py`: five check groups passed on both builds, including real
  H.264 playback/seek, default captions, lazy loading, pause-on-close and no-JS.
- `interaction_qa.py`: all 12 existing public/sample regression checks passed.
- `visual_qa.py`: nine local captures (homepage, pricing, login) and nine
  static captures (homepage, pricing, API) reported zero failures. Inspected
  desktop/mobile homepage renders and sampled actual video frames.
- Focused Ruff checks and `node --check static/source-trail.js` passed.

The guest workspace and engine were not developed in this change. No live
research job, paid generation, posting, billing or deployment was performed.
The example is deliberately identified as curated; these checks do not certify
the research engine or a production-ready signed-in workflow. Remote publishing
still needs resolution of the earlier push-approval rejection.
