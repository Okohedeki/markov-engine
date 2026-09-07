# Cross-platform investigations

Markov is an investigative partner for creators and independent writers. Its
unit of value is an overlooked, source-backed connection that a creator can
explore in their own voice. Accepting links is the entrance, not the whole offer.
Discovery must cross platforms without asking the customer to pick one silo.
Full writing remains an optional paid continuation; this work changes discovery.

## Implemented retrieval contract

- Editorial discovery no longer restricts searches to web and news.
- Each query fans out through bounded, rate-limited routes: general web/news and
  video indexes, native YouTube search, a public Bluesky API adapter, and indexed
  pages on TikTok, Instagram, Reddit, X/Twitter, Bluesky, Threads, Facebook,
  LinkedIn, Substack, Spotify, Apple Podcasts, SoundCloud, Vimeo, Rumble and Twitch.
- The general web route remains open to other domains and primary sources.
- Every route identifies its method: `native_search`, `native_api`, or `web_index`.
  Results, empty responses, denial, throttling, timeout and failure are distinct.
  A site-restricted index query is never represented as complete platform access.
- URL deduplication retains discovery provenance and case-sensitive paths.
- Relevance filtering precedes platform-diverse selection. Known profile/search
  directories on major social platforms are excluded from passage-reading slots.
- Investigations retain selected candidates and read outcomes. Search previews
  are leads; evidence must come from separately extracted, located passages.
- Findings distinguish downloaded-media transcripts, post text and page text.
  A post proves what its author wrote, not that every claim in it is true.
- Queries follow evidence-led entity/relationship bridges and seek challenges.
  Eight source slots, twelve read attempts and the existing two-round deadline
  remain bounded. Initial three-question plans reserve slots for follow-up.
- Saved cases retain coverage and findings without rerunning discovery. Existing
  completed cases, drafts, entitlements and customer records are not rewritten.

## Required media-first ingestion

Video ingestion must download a real video file before using its timed captions
or transcribing its speech. Podcast ingestion downloads audio. Descriptions and
titles are never substitutes for media content, and failed media reads must not
fall back to article extraction. No usable transcript means an explicit failure,
not a description-based investigation. Disabling transcription does not disable
the required download; captionless media then fails.

Downloads use isolated temporary directories and a 100 MB file limit. The
transcript retains timestamps, caption/transcription provenance, downloaded byte
count and a SHA-256 fingerprint. Files are temporary, not a permanent video
archive. Visual frame analysis and on-screen text recognition are not implemented.

Legacy media records without download provenance are not reusable as new seeds
or inspected evidence. Existing cases remain unchanged; automatic historical
reprocessing is not implemented. Genuine text-only posts remain valid sources.

## Access and quality boundaries

Platform independence is a product requirement, not a claim of exhaustive access.
Private, deleted, login-only or unindexed material may be unavailable. Supported
extraction does not imply guaranteed transcripts or the right to access a source.
Do not bypass authentication, access controls or platform approvals.

The [Bluesky search contract](https://github.com/bluesky-social/atproto/blob/main/lexicons/app/bsky/feed/searchPosts.json)
allows implementations to require authentication. The unauthenticated adapter
must expose that denial rather than silently reporting no relevant posts.
[TikTok's Research Tools FAQ](https://developers.tiktok.com/docs/en/research-api-faq)
excludes commercial users; it is not an assumed native integration for Markov.
Native or appropriately licensed access for restricted platforms remains work
requiring actual provider access. Indexed coverage alone does not finish this.

More retrieved platforms do not prove novel connections, independent
corroboration, publication readiness or a time-to-insight promise. Measure those
on real investigations. General claim verification still has its separate
authority-focused web/news pass; the editorial investigation runs across media.

## Live development observations — September 7, 2026

These are diagnostic observations, not a quality benchmark or a launch claim.

- A public discovery probe for `bioscience organoids` returned in 12.3 seconds.
  It attempted 22 routes and returned candidate links across media. The native
  Bluesky route was denied; indexed coverage remained explicitly partial.
- The probe also returned profiles, directories and irrelevant hits, motivating
  relevance and content-path filtering before platform-diverse source selection.
- A real investigation started from Crown Bioscience's organoid product page,
  with no preferred story supplied. The local model was unavailable; configured
  cloud fallback extracted 68 claims. That preliminary stage took about 97 seconds.
- The initial investigation stalled without saving external evidence and was
  stopped. Its cause was not established; a successful retry does not resolve it.
- A traced retry reused the isolated source/claims with a 90-second research
  budget. It inspected six sources: LinkedIn, a preprint, Substack, TikTok, X and
  SoundCloud. Some media supplied description text, not transcripts. Spotify
  reads failed; no access control or DRM was bypassed.
- That retry exhausted its research budget. One proposed angle failed existing
  validation, leaving **zero accepted leads**. More coverage has not yet proved
  the product's promised discovery quality, latency or reliability.
- Records remain in the local temporary database
  `.tmp/cross-platform-live-cb77b4e6.db`; no customer case was overwritten.

Deterministic checks covered coverage failures versus empty searches, native
post normalization/reading, safe host matching, cancellation capacity, retained
provenance, media-diverse selection, case-scoped persistence and cached reuse.
The existing 132-test suite passed. No new permanent test suite or service was
introduced. Native restricted-platform access, the original runtime stall and
consistent valuable connection discovery remain unfinished.

### Download-first TikTok retest

The supplied TikTok short link `https://www.tiktok.com/t/ZTUhAPacY` downloaded a
26,622,649-byte video with an inspected video stream. An isolated extraction
produced 21 timed Whisper segments in 14.7 seconds, about Arendt, Eichmann and
radicalization, not the generic themes of its description. Speech recognition
still makes wording and proper-name errors; this is not a reviewed transcript.

The subsequent full engine run retained 14 located claims and four external
sources, including another downloaded TikTok transcript. It returned zero
accepted angles (one rejected), with two source-read timeouts and partial
coverage. The model cost ledger recorded $0.0249626; this excludes unmetered
download/CPU work. Source processing now works on this example, but investigative
quality is not established. Records: `.tmp/tiktok-download-first-20260907.db`.

Verification used the project `.venv` with CTranslate2 4.8.2, fixing the prior
`pkg_resources` import crash without modifying shared Python. The existing
preview process was not restarted into this environment. Old description-based
records were preserved, not upgraded or presented as transcript-based results.
