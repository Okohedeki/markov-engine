# Markov connector for Muse

The read-only MCP adapter is implemented at `POST /mcp/muse`. It connects a
single user's saved archive to an MCP client. It is **not yet submitted,
approved, or listed in Muse**. Muse's connector submission details require a
work-email login at <https://muse.ai/platform>; its exact protocol and
authentication requirements still need verification inside that account.

## Self-hosted setup

1. Deploy Markov behind HTTPS with its existing account authentication.
2. Identify the existing archive owner ID. Clerk installations use the identity
   mapping in `MARKOV_CLERK_OWNER_IDS`; do not create a different ID for the same
   person, as that would point to an empty archive.
3. Generate a dedicated random token, for example with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. Set `MARKOV_MUSE_API_KEYS` in the deployment's secret environment to a JSON
   map of that token to the archive owner ID. Leave it `{}` to disable the
   endpoint. Never put real tokens in source control or submission documents.
5. Set `MARKOV_MUSE_ALLOWED_ORIGINS` to the exact trusted browser origins
   confirmed by Muse. The default is `["https://muse.ai"]`. Requests without
   an Origin header still require the dedicated bearer token.
6. Restart Markov. Use a separate test archive for review and connection tests.

The transport is stateless Streamable HTTP with JSON responses. Supply
`Authorization: Bearer <dedicated-token>`, `Content-Type: application/json`,
and `Accept: application/json, text/event-stream`. Initialize with:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"markov-review","version":"1.0"}}}
```

Send `notifications/initialized`, then call `tools/list` and `tools/call`.
The adapter also negotiates MCP 2025-03-26 and 2025-06-18. It does not use
session IDs, open an SSE stream, or provide OAuth discovery. GET and DELETE
return 405. An API-key setup must not be presented as an OAuth integration;
if Muse requires OAuth or another transport, implement and verify that flow
before submission.

## Tools and boundaries

| Tool | Purpose |
| --- | --- |
| `search` | Exact, semantic, or hybrid retrieval; at most 20 results |
| `fetch` | One saved source, paged in 20,000-character chunks |
| `list_threads` | Visible threads built from the connected archive |
| `get_thread` | Thread context and its saved sources |
| `rediscover` | Up to five older saves with explicit reasons to revisit |

Tool inputs are schema-checked. Each request resolves an owner from the
dedicated token; clients cannot supply an owner ID. Results distinguish source
text, user notes, and Markov interpretations, and include original URLs and
available timestamp/page references. Archived saves and other accounts are
excluded. Source content is untrusted data, not instructions for the client.

The adapter cannot save, edit, delete, purchase, send messages, or run code.
It does not grant the existing research API's permissions. Requests are
rate-limited per owner and bounded to 32 KB; responses are not cacheable.
Semantic retrieval uses the configured embedding provider. With hash
embeddings, search reports its keyword fallback rather than claiming semantic
matching. Revocation means removing the token and restarting the deployment.
The connected service receives the returned archive content; account owners
should review that service's data policies before enabling access.

## Submission package

- **Name:** Markov
- **Description:** Retrieve the things you chose to keep. Search saved articles,
  videos, repositories, and papers; bring your notes and connected ideas into
  Muse with references to the original sources.
- **Category:** Personal knowledge and bookmarking
- **Endpoint:** `https://<your-deployed-markov-host>/mcp/muse`
- **Setup page:** `https://<your-deployed-markov-host>/connectors/muse`
- **Source:** <https://github.com/Okohedeki/markov-engine>
- **Permissions:** Read the connected owner's unarchived saves and threads.
- **Example prompts:** “Find what I saved about agent checkpointing”; “Open that
  source and show my note”; “Which older saves relate to my recent interests?”

Before submitting, enter a real HTTPS deployment, privacy policy, support
contact, review account, and logo in Muse's authenticated form. Confirm its
required authentication method and authorized origins. Complete a real Muse
search → fetch → cite journey, verify rejection of revoked credentials and
cross-account IDs, then submit for functional, security, and legal review.
Do not mark the connector available until that review and end-to-end test pass.

Local contract coverage: `pytest -q tests/test_muse_connector.py`.
