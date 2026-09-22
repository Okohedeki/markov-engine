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

### Personal computer and phone

- A loopback service owns the SQLite archive and processing queue.
- A phone can pair through a private HTTPS address using an expiring, single-use
  QR invitation. Device sessions persist and can be revoked individually.
- Phone review edits and retries return to the same computer engine. Pages read
  current server state on opening or refreshing; there is no live push sync.
- Browser-first Windows launcher; standalone executable packaging is optional.
- Read-only diagnostics for the engine, HTTPS pairing route, and proxy access.

### Project quality

- Checked Windows x64 / Python 3.11 installation using tested dependency versions.
- Declared the HTML cleaner dependency previously hidden by global packages.
- Windows CI for clean setup, the regression suite, wheel installation, real
  service startup, PWA assets, QR generation, processing, and restart persistence.
- Contributor guidance, private vulnerability reporting, and security boundaries.

### Release limitations

- A physical phone's QR scan, home-screen install, reconnect, and revoke cycle
  still need verification on a real trusted HTTPS deployment.
- The computer must stay running and reachable. HTTPS networking and automatic
  startup are separate configuration steps. Offline capture is not queued.
- Mac and Linux ports, live push updates, and native sharing extensions are not
  part of the current supported setup. No stable release is declared here.
