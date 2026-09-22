# Legacy research and model setup

This reference retains configuration for the older research application. For the
bookmark app and paired phone, start with [local service setup](local-service.md).
The examples below require separately installed model runtimes or provider keys;
they are not required for initial bookmark capture and keyword search.

## Local setup

Requirements: Python 3.11+ and FFmpeg for merging separate video/audio streams.
Run the API and CLI from the activated project environment below. Reinstall
dependencies and restart existing servers after upgrading: the speech runtime
requires CTranslate2 4.8.2+ to avoid the obsolete `pkg_resources` dependency.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e .
```

On Windows, the fastest development setup is:

```powershell
.\run-local.cmd
```

This starts the landing page, SaaS workspace, and API together at
`http://127.0.0.1:8000`. When no `.env` exists, the launcher uses safe offline
development defaults: heuristic generation, hash embeddings, 100 test credits,
disabled outbound web search, and a separate `data/local-markov.db` database.
Claims without attached evidence remain visibly unsupported in this mode.
Customer accounts use Clerk: follow [account setup](customer-auth.md) for
email/password and social sign-in. The sign-in page shows a setup state until
connected; it no longer asks customers for access keys. The launcher’s
`local-customer-key` is for developer API use; the reviewer key is `local-review-key`.

Pass `-Port 8010` to choose another port or `-NoReload` to disable automatic
reloads. If `.env` exists, the launcher leaves it in control so you can test real
Anthropic, OpenAI-compatible, or in-process local model backends.

Copy [`.env.example`](../.env.example) to `.env`. Configure Clerk for customer
accounts, a credit balance when needed, and one LLM/search setup. Keep the Clerk
secret key private. `MARKOV_API_KEYS` is a JSON map of developer API keys to
stable owner IDs; it does not authenticate customers when Clerk is configured.
For a single-user, loopback-only preview without Clerk, explicitly set
`MARKOV_LOCAL_PREVIEW_OWNER` to an owner ID in that map. Never enable preview
access on a hosted service. Clerk-enabled installations ignore this bypass.

Hybrid local/cloud example (recommended starting point):

```dotenv
LLM_BACKEND=hybrid
HYBRID_CLOUD_BACKEND=openai
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_API_MODE=chat_completions
LOCAL_LLM_MODEL=llama3.1:8b
LOCAL_MAX_TOKENS=4096
HYBRID_LOCAL_TASKS=claim_extraction,entity_extraction,evidence_classification,query_generation,planning_reduction
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_MODE=responses
OPENAI_API_KEY=replace-me
OPENAI_MODEL_EXTRACTION=gpt-5.6-luna
OPENAI_MODEL_CLASSIFY=gpt-5.6-luna
OPENAI_MODEL_PLANNING=gpt-5.6-luna
OPENAI_MODEL_SYNTHESIS=gpt-5.6-terra
OPENAI_REASONING_EFFORT=low
EMBED_BACKEND=hash
MARKOV_API_KEYS={"local-customer-key":"local-customer"}
MARKOV_INTERNAL_API_KEYS={"local-review-key":"reviewer-1"}
MARKOV_OPENING_CREDITS=20
MARKOV_WEB_SESSION_SECRET=replace-with-a-random-secret
```

Markov remains the orchestrator. Deterministic segmentation and validation stay
in code; Ollama handles chunk-level extraction, query generation, and initial
stance classification. The local planner sees the complete claim ledger, then
sends at most the configured core-claim limit to OpenAI for canonicalization and
topic review. Connection synthesis receives only those core claims and a bounded
support/challenge evidence packet. A low-confidence local stance is the only
classification automatically escalated to cloud. Cloud structured outputs use
the Responses API; local Ollama calls use its OpenAI-compatible chat endpoint.

`EMBED_BACKEND=hash` avoids a second metered provider while the workflow is being
tuned. Switch to a semantic embedding backend before production retrieval
evaluation.

Low-cost Claude alternative:

```dotenv
LLM_BACKEND=anthropic
ANTHROPIC_API_KEY=replace-me
MODEL_SYNTHESIS=claude-haiku-4-5
MODEL_EXTRACTION=claude-haiku-4-5
MODEL_CLASSIFY=claude-haiku-4-5
EMBED_BACKEND=hash
```

Local model example:

```dotenv
LLM_BACKEND=openai
EMBED_BACKEND=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_MODE=chat_completions
LLM_MODEL=qwen2.5:7b-instruct
OPENAI_EMBED_MODEL=nomic-embed-text
MARKOV_API_KEYS={"local-customer-key":"local-customer"}
```

Then run:

```bash
markov-api
# Public site: http://127.0.0.1:8000/
# Pricing: http://127.0.0.1:8000/pricing
# Developer guide: http://127.0.0.1:8000/developers
# Finished-case demo: http://127.0.0.1:8000/sample
# API docs: http://127.0.0.1:8000/docs
# Customer app: http://127.0.0.1:8000/app
# Reviewer app: http://127.0.0.1:8000/app/reviewer/login
```

The V1 runner executes background tasks in the API process. That is suitable for
one-instance demand testing. See [`docs/operations.md`](operations.md) for
restart behavior, backups, reviewer operation, billing, and production limits.
