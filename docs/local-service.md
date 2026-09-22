# Your service, your archive

## Architecture contract

Markov runs on the user's computer or home server. That service owns the
SQLite archive, extraction queue, model configuration, and device registry.
The phone installs the PWA from that service's stable HTTPS origin. There is
no central Markov account or archive relay in this mode.

The primary setup is a local web service, started with `run-service.cmd`, and
a phone browser/PWA connected to it. Native executable packaging is optional.
The computer's browser uses localhost; the phone uses a reachable address for
that computer, because localhost always refers to the device opening the page.

The same authenticated service handles both directions:

- Computer to phone: saved sources, processing state, extracted passages,
  interpretations, and connections are available for review.
- Phone to computer: notes, corrected interpretations, favorites, archive
  changes, replacement source text, and processing retries update the local
  database or queue. Human corrections survive subsequent processing.

Pages fetch current state when opened or refreshed. The phone does not keep a
second authoritative database or run extraction. Processing continues on the
computer when the phone closes the page; later review reads the stored results.

```text
Desktop / home server                    Paired phone
Markov + SQLite + extraction  <-------->  Markov PWA
           |                   HTTPS       |
           +-- device pairing QR ----------+
```

The QR is a short-lived invitation, not a permanent API key. It contains the
service address and a random code in the URL fragment. The phone confirms
the named service, redeems the code once, and receives an HttpOnly secure
device cookie. The service stores hashes of secrets. The desktop can revoke
individual phones without changing the archive or other devices.

Only direct loopback access on the service computer can issue invitations
or revoke other devices. A reverse-proxied request is not a local administrator.
Pairing sessions authorize the bookmark application, not developer/reviewer APIs.
The paired phone can disconnect itself. Expired and reused invitations fail closed.

Use a stable, trusted HTTPS origin. Plain `http://192.168.x.x` is not an
installable PWA origin on a phone. Localhost's development exception applies
only on the computer serving it. The QR establishes trust; it does not make
an unreachable computer reachable or wake a sleeping computer.

For private access at home and away, Tailscale Serve can terminate HTTPS and
forward to Markov's loopback port. Both devices must belong to the private
network. A trusted HTTPS reverse proxy on the LAN is also supported. No public
tunnel, firewall rule, or operating-system service is installed automatically.

Model providers remain a separate choice: hosting the archive locally does not
make configured cloud model calls local. Choose a local model and embeddings
when source processing must stay on the service computer.

## Pairing interface direction

- Preserve the existing warm ivory, ink, orange, Georgia, and DM Sans system.
- The desktop shows the service name/address, one scannable QR, expiration,
  and an explicit list of connected devices. Device names are user supplied.
- The phone shows “Connect to your Markov” with the actual service identity,
  a device-name field, and one Connect action; then opens the private archive.
- You shows the connected service and a disconnect control. Connection loss
  says the local service is unreachable; never imply an unsaved link was saved.
- No account signup, decorative network graph, fake connected state, or request
  to paste a permanent secret. Preserve keyboard access and mobile touch targets.
- Verify desktop and 390px mobile, invitation expiry/replay, persistence,
  revocation, CSRF, origin validation, and separation from legacy API access.

References: [PWA installation requirements](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable),
[Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve).

## Run and pair

Install the project into its Python 3.11+ environment (`python -m pip install -e .`).
On Windows, run `.\run-service.cmd --name "My Markov"` from the repository.
On other platforms, use `markov-service --name "My Markov"` in that environment.
Open `http://127.0.0.1:8000/app` on the service computer to start saving.

For private phone access at home and away:

1. Install Tailscale on the service computer and phone, and connect both to your
   private network. Complete Tailscale's HTTPS setup when prompted.
2. In another terminal on the service computer, run
   `tailscale serve --bg http://127.0.0.1:8000`. Note the HTTPS address it reports.
   See the [official Serve command reference](https://tailscale.com/docs/reference/tailscale-cli/serve).
3. Stop Markov with Ctrl+C, then restart with
   `.\run-service.cmd --url https://YOUR-COMPUTER.YOUR-TAILNET.ts.net`, replacing
   the example with the actual address. Use the same data directory each time.
4. On the computer, open `http://127.0.0.1:8000/app/devices` and choose **Create
   pairing code**. Scan it with your phone camera within five minutes.
5. On the phone, confirm the service name/address, name the device, and tap
   **Connect this device**. Install Markov using the browser's home-screen option.

The service remembers its name, address, owner, and database in
`~/.markov/service.json`; the archive and paired-device records live in
`~/.markov/markov.db`. Subsequent starts only need `.\run-service.cmd` (or
`markov-service`). `--data-dir` selects a different persistent directory;
`--port` selects the local port and must match the reverse proxy target.
`--check` validates and saves configuration without starting a server.

Markov must keep running; the launcher does not install an automatic startup
service. A new code replaces previous unused codes. Each device stays connected
for up to 90 days unless revoked on the computer or disconnected on that device.
Browser and installed-app cookie sharing depends on the browser; if the installed
app asks to connect again, pair that app with a fresh invitation link.

For a different HTTPS reverse proxy, preserve the external Host header, set
`X-Forwarded-Proto: https`, and forward only to the loopback listener. Configure
`--url` as that exact HTTPS origin, without a path. Never expose the local console
through a proxy that removes forwarding headers and rewrites Host to localhost.

## Keep an existing archive

The launcher creates a separate personal archive by default. To adopt an existing
database, stop the previous Markov process, then start with `--database` pointing
to that file and `--owner` set to its existing archive owner ID. Both choices are
remembered. Ownership is not migrated or merged automatically. Back up the
database before adopting it; stop Markov before copying SQLite files, or use
SQLite's backup API for a live backup. Keep `service.json` with the backup.

The launcher disables inherited developer/reviewer login keys and Clerk login.
Your configured model providers remain in effect. If the default Anthropic or
Voyage backend has no key, the launcher falls back to heuristic processing or
keyword indexing respectively. Configure local models for richer processing
without cloud model calls; the launcher does not install model runtimes.

The existing [Muse connector](muse-connector.md) remains an optional read-only
adapter with its own credentials. A hosted Muse client cannot reach a private
tailnet address unless its deployment has an appropriate private network path.
QR pairing does not publish that adapter or register it in Muse's directory.

## Verification

The normal `python -m pytest -q` suite passes 166 tests, including concurrent
single-use redemption, invitation and session expiry, restart persistence,
owner isolation, phone capture, revocation, self-disconnect, CSRF rejection,
forwarded-request restrictions, and launcher configuration persistence.

Browser review covered the real desktop invitation form and generated SVG QR
at 1440px, and the phone confirmation at 390px. The review caught and corrected
a referrer policy that suppressed form Origin headers, and spacing that pushed
the mobile Connect action below the initial viewport. Keyboard focus reaches
the Connect button visibly; no browser console warnings or errors were reported.
The local browser preview used a test HTTPS identity. A physical phone scan,
trusted HTTPS deployment, home-screen installation, and away-from-home access
still require verification on the user's configured network and devices.
