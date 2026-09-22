# Security policy

Markov is alpha software. Security fixes target the current `main` branch;
there is no maintained release series or promised response time yet.

## Report a vulnerability privately

Use [GitHub's private vulnerability report form](https://github.com/Okohedeki/markov-engine/security/advisories/new).
Private vulnerability reporting is enabled for this repository. Please include
the commit, operating system, affected route, reproduction steps, and impact.
Use a test archive and redact tokens, invitation codes, cookies, model keys,
and personal saved material. Do not put exploit details or private data in a
public issue. Ordinary defects belong in GitHub Issues.

## Personal-service trust boundaries

- The service computer and its operating-system account are trusted. Direct
  localhost access administers devices without another login. Markov is not a
  security boundary between people sharing that computer account.
- A paired phone can read and change the owner's bookmark archive. Pair only
  devices you control and revoke lost devices from the computer's local console.
- The engine binds to loopback. A phone needs trusted HTTPS through a correctly
  configured private network or reverse proxy. Preserve the external Host and
  forwarding headers; see [the setup contract](docs/local-service.md).
- SQLite archives and configuration are not encrypted by Markov. Protect them
  with operating-system permissions, disk encryption, and private backups.
- Source extraction fetches saved URLs. This is a personal trusted-user service,
  not an anonymous public ingestion endpoint or a hardened multi-tenant sandbox.
- Cloud model providers may receive saved source text when configured. Local
  archive storage does not imply that all processing stays on the computer.

Tests cover pairing expiry/replay, revocation, owner isolation, origin/CSRF
checks, and forwarded-console restrictions. Passing tests are not an independent
security audit. Changes to authentication or proxy handling require regression
coverage and the [physical-phone acceptance checks](docs/local-service.md#verification).
