# Markov: personal memory

This direction supersedes the research-agent and creator-studio positioning.
Markov is a bookmark app that remembers what you forgot.

## Direction contract

- Problem: curious readers save valuable material but forget its existence and context.
- Outcome: save immediately, then rediscover something useful with an explicit reason.
- Thesis: a quiet, precise personal archive with the warmth and hierarchy of an editorial journal.
- Memory hook: an old save returns beside the specific recent activity that makes it useful.
- Composition: a large, readable resurfaced item; supporting thread and activity rail;
  restrained archive rows. Mobile has five bottom destinations and a reachable save action.
- Typography: Georgia display and article titles; locally hosted DM Sans for controls and metadata.
- Color: warm ivory, ink, muted stone, restrained burnt orange for action and relevance.
- Material: source excerpts, timestamps, page references, notes, and source thumbnails.
  Thin rules organize information; radius and shadows are reserved for dialogs.
- Interaction: immediate durable-save acknowledgement; background enrichment with recovery;
  a small explained rediscovery selection, never infinite scroll.
- Forbidden: chat-first entry, invented archive activity, generic gradients, feature-card mosaics,
  mandatory folders, fabricated quotations, inferred reasons presented as source facts.
- Constraints: existing FastAPI/Jinja/SQLite stack; preserve authentication and historical research;
  keyboard operation, reduced motion, 390px mobile and 1440px desktop verification.

## Product story

Functional progress: retrieve material without remembering titles or organizing folders.
Emotional progress: confidence that something worth saving can be found again.
Social progress: arrive with the relevant original source and context.
Dream: an archive that becomes more useful as interests develop.

Best for readers, builders, and researchers with a growing personal archive.
Not a general web research agent. Answers must stay within saved sources.
Primary action: Start saving. Secondary: See how it works.
Brand role: Sage with a small Explorer accent; clear, observant, calm.
Proof: a labeled illustrative save-to-rediscovery sequence and a working archive.
No customer claims or invented personal activity.

Reference principles: Readwise Reader puts source material and revisiting first
(https://readwise.io/read); Are.na lets collections develop from encountered material
(https://www.are.na/); repository editorial layouts provide generous title hierarchy
and source annotations without dashboard decoration.

## Implementation boundaries

Preserve URL and user thought before extraction. Enrichment never overwrites notes.
Retain original source text separately from generated interpretations and locators.
Scope all bookmark and collection persistence to the authenticated owner.
Use configured model and embedding providers; disclose lexical fallback accurately.
Blocked/private sources remain saved and can accept pasted text or transcripts.
Native share extensions, MCP, external project integrations, and automatic monitoring
of source changes remain future extensions; do not imply they already operate.
