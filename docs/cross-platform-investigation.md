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
- Findings distinguish transcript, description-only, post text and page text.
  A post proves what its author wrote, not that every claim in it is true.
- Queries follow evidence-led entity/relationship bridges and seek challenges.
  Eight source slots, twelve read attempts and the existing two-round deadline
  remain bounded. Initial three-question plans reserve slots for follow-up.
- Saved cases retain coverage and findings without rerunning discovery. Existing
  completed cases, drafts, entitlements and customer records are not rewritten.

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
