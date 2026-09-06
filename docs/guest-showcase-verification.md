# Guest showcase verification

Verified on 2026-09-05, extending the V11 soft-studio design and the
`guest-showcase-brief.md` contract.

## Delivered

- `/demo/` is an account-free workspace with topic exploration, cross-topic
  shortlists, editable post/thread/video outlines, saved drafts and Markdown
  export. Guest data persists on the current device under its own storage key.
- Reset requires confirmation and does not clear the older sample workspace.
- The homepage offers guest entry and three recordings of real guest actions.
  Each recording has a poster, native controls, English captions and a text
  transcript. Videos load on request and do not autoplay.
- The static export includes the same guest experience and walkthrough assets
  under `/markov-engine/`.

The guest discussions and angles are prewritten examples, clearly disclosed in
the interface. Editing, saving and exporting work; live research, AI generation
and social publishing are not enabled for anonymous visitors. `/app` remains
authenticated. No paid engine requests were made during verification.

## Checks completed

- API and guest route tests: 12 passed, including anonymous access without a
  session cookie and continued protection of the authenticated dashboard.
- Guest interaction tests passed against both the live app and static export:
  topic switching, cross-topic selection, draft format and text persistence,
  reload/deep links, exact export contents, empty state, reset cancel/confirm,
  unrelated-storage preservation, mobile drawer focus and blocked-storage fallback.
- Walkthrough tests passed on both versions: no initial MP4 request, click-to-play,
  seeking, caption cues, transcripts, keyboard tab switching and paused hidden
  videos. Responsive checks covered 390, 760, 820 and 1024 px widths.
- Existing public interaction regression suite: 12 checks passed.
- Rendered route matrix: 18 live and 15 static captures at desktop, tablet and
  mobile sizes; no horizontal overflow, console errors, failed resources or
  heading/main landmark failures. Desktop/mobile screens and actual video frames
  were visually reviewed.
- Focused Ruff checks and JavaScript syntax checks passed. The full repository
  suite and Lighthouse were not run for this change.

Videos are silent H.264 MP4 recordings, approximately 21.0, 20.3 and 21.6 seconds,
each below 0.9 MB. Combined video payload is approximately 2.56 MB, requested only
when visitors play the recordings.

## Reproduce

With the local app running at port 8013:

```powershell
py -3.11 -m pytest tests/test_api.py tests/test_guest_ui.py -q
py -3.11 scripts/guest_qa.py --base-url http://127.0.0.1:8013
py -3.11 scripts/walkthrough_qa.py --base-url http://127.0.0.1:8013
py -3.11 scripts/interaction_qa.py --base-url http://127.0.0.1:8013
py -3.11 scripts/build_pages.py
```

To refresh the recordings, run `scripts/record_walkthroughs.py` with the app
running, Chrome available, FFmpeg on PATH and Playwright's recording helper
installed. This verification used the workspace-local helper at
`.tmp/playwright-media` via `PLAYWRIGHT_BROWSERS_PATH`. Recording output goes to
`markov_engine/static/walkthroughs/`; rebuild the static export after updating it.

Local verification evidence remains untracked in `.tmp/guest-showcase-final/`,
`.tmp/guest-static-final/`, `.tmp/walkthrough-playback/` and
`.tmp/static-walkthrough-playback/`.

## Handoff boundary

All implementation checkpoints are local commits. Remote push remains blocked
by the earlier approval rejection; no retry or remote deployment was performed.
The pre-existing deletion of `docs/v5-interaction-contract.md` remains unstaged.
