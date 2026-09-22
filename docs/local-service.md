# Your service, your archive

## Architecture contract

Markov runs on the user's computer or home server. That service owns the
SQLite archive, extraction queue, model configuration, and device registry.
The phone installs the PWA from that service's stable HTTPS origin. There is
no central Markov account or archive relay in this mode.

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
