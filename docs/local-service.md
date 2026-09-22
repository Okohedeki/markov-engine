# Your service, your archive

## Architecture contract

Markov runs on the user's computer or home server. That service owns the
SQLite archive, extraction queue, model configuration, and device registry.
The phone installs the PWA from that service's stable HTTPS origin. There is
no central Markov account or archive relay in this mode.

The setup is a Python local web service on Linux, Windows, or macOS, started
with `markov-service`, and a phone browser/PWA connected to it.
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

Install Python 3.11 or newer and follow the
[Linux, Windows, or macOS setup commands](../README.md#local-service-setup) to
create and activate a virtual environment. From the repository, run:

```sh
python -m pip install -c requirements/constraints.txt -e .
python -m pip check
markov-service --open-browser --name "My Markov"
```

The same service and commands work on all three operating systems. Installation
needs network access; initial capture and keyword indexing need no model keys.
On a headless computer, omit `--open-browser` and open the address manually.
Open `http://127.0.0.1:8000/app` on the service computer to start saving.

For private phone access at home and away:

1. Install Tailscale on the service computer and phone, and connect both to your
   private network. Complete Tailscale's HTTPS setup when prompted.
2. In another terminal on the service computer, run
   `tailscale serve --bg http://127.0.0.1:8000`. Note the HTTPS address it reports.
   See the [official Serve command reference](https://tailscale.com/docs/reference/tailscale-cli/serve).
3. Stop Markov with Ctrl+C, then restart with
   `markov-service --url https://YOUR-COMPUTER.YOUR-TAILNET.ts.net`, replacing
   the example with the actual address. Use the same data directory each time.
4. On the computer, open `http://127.0.0.1:8000/app/devices` and choose **Create
   pairing code**. Scan it with your phone camera within five minutes.
5. On the phone, confirm the service name/address, name the device, and tap
   **Connect this device**. Install Markov using the browser's home-screen option.

The service remembers its name, address, owner, and database in
`~/.markov/service.json`; the archive and paired-device records live in
`~/.markov/markov.db`. Subsequent starts only need `markov-service`. `--data-dir` selects a different persistent directory;
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

## Diagnose a connection

With Markov running, open another terminal in the repository and run:

```sh
python -m markov_engine.doctor --phone
```

Pass the same `--data-dir` and `--port` as the service if you changed them.
Omit `--phone` when evaluating localhost only. The command reads configuration
and makes unauthenticated GET requests; it does not change the archive, create
pairing invitations, or revoke devices. A failed check returns exit code 1.

| Result | Next step |
| --- | --- |
| Cannot read service.json | Start Markov once; check the data directory. |
| Cannot reach the local engine | Start `markov-service`; check the port and terminal errors. |
| No phone address configured | Configure a trusted private HTTPS origin with `--url`. |
| HTTPS connection failed | Check private-network connection, DNS, certificate trust, and proxy target. |
| Pairing page unavailable | Verify the proxy points to Markov's loopback port and preserves Host. |
| Unexpected device-console access | Stop exposing that proxy; correct forwarding headers before pairing. |

A passing check proves reachability from the computer, not from the phone.
Connect the phone to the same private network and open the configured address.
If the computer is asleep or offline, the phone cannot review or save material.
Restarting the engine with the same archive retains device sessions. If a code
expired or was already used, create a fresh one from the local console.

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

The `python -m pytest -q` suite covers concurrent
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

### Physical-phone acceptance gate

Status: **not yet performed**. Before calling a release ready, record the commit,
computer OS/version, phone OS/browser, private-network method, and results below.
Do not publish pairing codes, cookies, or private archive contents with the report.

1. Start from a clean installation on Linux, Windows, or macOS using the documented setup. Save a
   URL with supplied source text and a note; confirm processing finishes.
2. Configure a trusted HTTPS address. Run the diagnostic command with `--phone`.
   Scan a fresh QR on the physical phone, confirm the service identity, and pair.
3. Install the PWA, close the browser, and open the installed app. If the browser
   keeps a separate cookie store, pair the installed app with a fresh invitation.
4. Review the computer's saved item on the phone. Edit its note and interpretation,
   favorite it, and replace source text. Refresh the computer view and confirm
   every change arrived and reprocessing preserved the human interpretation.
5. Save a new item from the phone. Confirm it appears and finishes processing on
   the computer, then refresh the phone to review the result.
6. Stop and restart the engine with the same data directory. Confirm the archive
   and phone session survive. Test computer sleep/wake and private-network
   disconnect/reconnect; failed saves must not appear successfully saved.
7. If away-from-home access is intended, repeat review and saving on mobile data
   with the private network connected. Record Wi-Fi-only testing as such.
8. Revoke the phone on the computer. Confirm new archive requests fail from that
   phone; reusing the consumed QR must fail. Pair again with a fresh invitation.

CI verifies software behavior and installed assets. It does not scan a camera QR,
validate mobile cookie-store behavior, or establish the user's HTTPS network.
