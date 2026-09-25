# Changelog

## Unreleased

Current status: alpha. The package's existing `1.0.0` metadata does not represent
a newly published stable release. This entry describes the work on `main`.

### Bookmark application

- Mobile-first Home, Library, Threads, Search, and You interfaces.
- Durable immediate capture, background source extraction, manual source text,
  explained retrieval, optional model interpretation, and archive rediscovery.
- Distinct user notes, source passages, and generated interpretations; human
  corrections are preserved when the engine processes an item again.
- Read-only Muse connector adapter. Directory submission and live Muse validation
  remain pending.
- Saving a link again adds the new thought to its note and fills source text only
  when the save has none; it previously discarded the new thought.
- YouTube saves extract captions again. Fetch redirects no longer loop on the
  www host, and empty page caption links fall back to yt-dlp caption links.

### Personal computer and phone

- A loopback service owns the SQLite archive and processing queue.
- A phone can pair through a private HTTPS address using an expiring, single-use
  QR invitation. Device sessions persist and can be revoked individually.
- Phone review edits and retries return to the same computer engine. Pages read
  current server state on opening or refreshing; there is no live push sync.
- One Python local service for Linux, Windows, and macOS, with browser/PWA review.
- Removed the Windows executable launcher, native build tooling, and Windows-only
  setup path. Install the service wheel or use the shared source setup instead.
- Read-only diagnostics for the engine, HTTPS pairing route, and proxy access.
- PNG, maskable, and apple-touch icons for home-screen installation.
- Cloudflare Tunnel setup. Tunneled requests never act as the local console, and
  personal service mode no longer publishes its OpenAPI documents.

### Project quality

- Shared dependency constraints, including a compatible runtime for Intel Macs.
- Fixed a queue-claim/capture race that could reject a save while SQLite still
  had an active write statement; added a deterministic concurrent-save regression.
- Declared the HTML cleaner dependency previously hidden by global packages.
- Indexed queue state so the idle worker poll no longer parses every saved payload.
- Regression tests for the pinned fetcher's redirects and private-network refusal.
- CI on Linux, Windows, and Intel/Apple Silicon macOS for clean setup, regression
  tests, wheel installation, service startup, PWA assets, QR generation,
  processing, and restart persistence.
- Contributor guidance, private vulnerability reporting, and security boundaries.

### Release limitations

- A physical phone's QR scan, home-screen install, reconnect, and revoke cycle
  still need verification on a real trusted HTTPS deployment.
- The computer must stay running and reachable. HTTPS networking and automatic
  startup are separate configuration steps. Offline capture is not queued.
- Live push updates and native phone sharing extensions are not part of the
  current setup. No stable release is declared here.
