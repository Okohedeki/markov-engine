# Customer accounts: Clerk

Clerk is the selected identity provider. Use email/password, Google and Apple;
enable only the methods actually configured in the Clerk application. Its
prebuilt account flow handles registration, verification, recovery and social
authorization. Markov keeps FastAPI, Jinja and its current research database.
No separate user database, password storage or bespoke OAuth service is added.

## Connect this installation

1. Create a Markov application in the [Clerk Dashboard](https://dashboard.clerk.com/).
   Enable email/password with email verification. Enable Google and Apple under
   social connections when their provider setup is ready. Disable unneeded
   username, phone, organization and billing features.
2. Copy the matching development publishable and secret keys into the local,
   ignored `.env` as `CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`. Do not paste
   the secret into chat, source code, a browser script or Git. No keys are
   included in this repository.
3. Set `CLERK_AUTHORIZED_PARTIES` to a JSON list of the exact app origins, for
   example `["http://127.0.0.1:8014","http://localhost:8014"]`. Include the real
   port. Paths, trailing slashes and wildcards are rejected. Hosted origins
   must use HTTPS. Partial/mismatched configuration prevents app startup.
4. Configure the application home URL as `/app/links` and sign-in URL as
   `/app/login` for the chosen origin. Keep any dashboard redirect settings
   restricted to your application. The component uses hash routing for its
   sign-in, registration and verification steps.
5. Restart the FastAPI process with the project virtual environment. Open
   `/app/login` in a regular browser. The actual enabled methods come from
   Clerk; Markov never fabricates disabled provider buttons.

The production Clerk instance needs its own keys, domain/DNS setup and provider
credentials. Follow Clerk's [Google setup](https://clerk.com/docs/guides/configure/auth-strategies/social-connections/google)
and [Apple setup](https://clerk.com/docs/guides/configure/auth-strategies/social-connections/apple).
Google's development credentials are not production credentials. Test Google
in a normal system browser, not an embedded WebView. Do not request permission
to read a user's social feed: signing in is separate from source investigation.

## Identity and existing work

- The server verifies Clerk's short-lived signed session on each customer
  request, including issuer, allowed origin, expiry and active session state.
  Machine tokens and unverified browser identity fields cannot open a workspace.
- New accounts own records under `clerk:user_ID`. Existing owner-scoped access,
  paid capabilities and research queues remain unchanged. New users do not
  inherit an old customer's credits or research.
- To reconnect an existing workspace, an administrator must independently
  confirm its owner and configure `MARKOV_CLERK_OWNER_IDS`, for example
  `{"user_CONFIRMED_ID":"existing-owner-id"}`. Do not map by email alone,
  automatically assign the first signup, or share one owner ID between people.
  Back up the database before any separate data migration; none happens here.
- Clerk-enabled customer pages reject old access-key login and old Markov
  session cookies. They never fall back to the single-user localhost preview.
- Developer API keys and the internal reviewer login remain separate. For
  compatibility, installations with both Clerk keys empty retain the old
  programmatic key-login endpoint; the customer page no longer offers it.
  Do not use that unconfigured mode as the hosted customer sign-in service.
- Native mobile SDK integration and Clerk bearer authentication for `/v1` and
  `/v2` are not implemented by this change. Those APIs still use developer keys.

## Runtime behavior

No provider credentials: show an explicit setup state and a working sample link.
Provider JavaScript failure: show a readable error, never a pretend sign-in.
Valid login: go to Add a link. The sidebar account control manages the session
and signs out through Clerk. Expired tokens cannot open protected routes;
the sign-in page refreshes the provider session and checks server acceptance
before navigation. A failed form submission is not silently replayed.

Customer pages are not cacheable. Managed browser mutations require the same
application origin, preventing cross-site form submissions. SDK verification
has an eight-second deadline and uses the SDK's instance-scoped signing-key
cache; there is no new session service or shared mutable current-user client.
Session revocation is subject to the short-lived token's remaining validity,
not claimed to be instantaneous. No token contents are deliberately logged.

Clerk account deletion does not erase Markov's retained research database.
Export work first and contact the operator for research-data deletion. A hosted
launch must confirm its retention and deletion procedures.

## Verification boundary — 7 September 2026

- Existing suite: 132 checks passed. Updated the existing login-copy assertion;
  no new permanent test suite was added.
- Isolated RSA-signed sessions exercised expiry, tampering, issuer/origin
  mismatch, pending accounts, explicit legacy mapping and missing credentials.
- In-memory app checks verified cross-account denial, 30 concurrent ownership
  requests, old-cookie/key rejection, CSRF rejection and reviewer separation.
- Rendered setup and blocked-provider screens at desktop, 390 and 320px;
  checked keyboard entry, sample navigation and reduced-motion layout.
  Provider mounting options were checked with a clearly mocked SDK.
- Live email delivery, recovery, Google/Apple authorization, logout/revocation,
  idle-session renewal and the actual Clerk widget require a real application
  and remain unverified. This integration is not a completed hosted launch.

Integration references: [JavaScript quickstart](https://clerk.com/docs/quickstarts/javascript),
[Python SDK](https://github.com/clerk/clerk-sdk-python),
[sign-in component](https://clerk.com/docs/js-frontend/reference/components/authentication/sign-in).
