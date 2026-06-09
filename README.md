# markov-engine

A storage-agnostic **knowledge engine** that turns saved links — articles, PDFs,
YouTube / TikTok / Reddit / Twitter posts, audio — into living **Chains** of
knowledge that grow on their own.

Give it a URL and it will: extract the content (transcribing media when needed),
pull out a summary plus entities and relationships with an LLM, embed the
summary, and **cluster** the result into the most similar existing Chain (or seed
a new one). On demand it will **grow** a Chain by searching the web for new
related sources, and **generate** publication-quality artifacts (articles,
newsletters) synthesized across a Chain's sources.

It is **storage-agnostic**: all persistence goes through a small `Store`
interface. A local single-file **SQLite** backend ships as the default; plug in
your own backend (Postgres, a vector DB, anything) by implementing `Store`.

This is the open-source engine extracted from a closed-source full-stack product.
There is **no multi-tenancy, no tiers/billing, and no web framework** here — just
the engine and a CLI.

## What's in the box

| Module | What it does |
| --- | --- |
| `markov_engine.extract` / `transcribe` | Pure content extraction (trafilatura, yt-dlp, PyMuPDF, faster-whisper) |
| `markov_engine.llm` | Anthropic client (`complete` / `complete_json` / `stream_complete`) |
| `markov_engine.embeddings` | Voyage embeddings |
| `markov_engine.entities` | Summary + entity/relationship extraction (returns a dict) |
| `markov_engine.vectors` | Pure cosine similarity + incremental-mean helpers |
| `markov_engine.search` | DuckDuckGo web/news/video search |
| `markov_engine.clustering` | `assign_topic` — embed a source and cluster it into a Chain |
| `markov_engine.growth` | `grow_chain` — discover + ingest new sources for a Chain |
| `markov_engine.generate` | `generate_artifact` — synthesize an article/newsletter |
| `markov_engine.ingest` | `ingest_url` — the full extract → entities → store → cluster pipeline |
| `markov_engine.store` | The `Store` ABC, record dataclasses, and `SqliteStore` |

## Install

```bash
pip install markov-engine
```

Set your provider keys (or put them in a `.env` file):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export VOYAGE_API_KEY=...
```

## CLI

The CLI is backed by the local SQLite store (default `~/.markov/markov.db`,
override with `--db`).

```bash
# Ingest a URL and cluster it into a Chain
markov ingest https://example.com/some-article
# -> {"source_id": 1, "title": "...", "chain_id": 1, "entities": 7, "cost_usd": 0.0123}

# Grow a Chain — discover and ingest related sources
markov grow 1 --hops 2 --budget 10

# Generate an artifact from a Chain (prints markdown)
markov generate 1 --type article

# Inspect state
markov chains        # id, title, status, topic_count
markov sources       # recent sources
markov search "transformers"   # best-effort entity/source search
```

## Use it from your own agent / code

Everything is async. Open a store, then call the engine functions directly:

```python
import asyncio
from markov_engine import SqliteStore, ingest_url, grow_chain, generate_artifact

async def main():
    store = await SqliteStore.open("~/.markov/markov.db")
    try:
        # 1. Ingest + cluster
        res = await ingest_url(store, "https://example.com/article")
        chain_id = res["chain_id"]

        # 2. Grow the chain (caller controls reach + spend — no tiers)
        await grow_chain(
            store,
            await store.get_chain(chain_id),
            hop_depth=2,
            source_budget=10,
            cycle_cost_cap=0.50,
        )

        # 3. Generate an artifact
        artifact = await generate_artifact(store, chain_id, artifact_type="article")
        print(artifact["content"])
    finally:
        await store.close()

asyncio.run(main())
```

The pure pieces are usable on their own too — e.g. `markov_engine.extract.extract_content`,
`markov_engine.entities.extract_entities`, `markov_engine.embeddings.embed`,
`markov_engine.vectors.cosine_similarity`.

## The `Store` interface — bring your own backend

The engine never touches a database directly; it talks only to a `Store`. To
back it with Postgres, a vector store, or an in-memory dict, implement the
abstract base class in `markov_engine.store.base.Store`. Records returned must
expose attributes (e.g. `chain.id`, `chain.centroid_embedding`,
`source.content_text`) — the dataclasses in `markov_engine.store.records` are the
canonical shape.

All methods are async:

```text
# sources
add_source(*, url, title, source_type, content_text, summary, is_note=False) -> SourceRec
get_source(source_id) -> SourceRec | None
get_source_by_url(url) -> SourceRec | None
list_sources(limit=20) -> list[SourceRec]
set_source_topic(source_id, topic_id)

# topics
add_topic(*, canonical_title, summary, embedding) -> TopicRec
attach_topic_to_chain(topic_id, chain_id)

# chains
create_chain(*, title, centroid, hop_depth, source_budget, cadence_hours) -> ChainRec
get_chain(chain_id) -> ChainRec | None
list_chains(limit=50) -> list[ChainRec]
nearest_chain(embedding) -> tuple[ChainRec, float] | None    # (chain, cosine_similarity)
update_chain_centroid(chain_id, centroid, topic_count)
touch_chain_grown(chain_id)
update_chain(chain_id, **fields)

# chain_sources
add_chain_source(*, chain_id, source_id, hop_distance, relevance) -> bool   # False if already linked
list_chain_sources(chain_id, limit=50) -> list[ChainSourceRec]              # .source, .hop_distance, .relevance, .added_at

# entities / relationships
add_entity(*, name, entity_type, description) -> int
get_entity_by_name(name) -> EntityRec | None
add_relationship(*, src_id, tgt_id, rel_type)
link_entity_to_source(entity_id, source_id)
gather_entity_neighbors(entity_id, limit=8) -> list[str]
top_entities_for_chain(chain_id, limit=8) -> list[dict]      # {"id": .., "name": ..}

# artifacts
add_artifact(*, chain_id, artifact_type, title, content, parameters, model_used, cost_usd, source_ids) -> ArtifactRec
list_artifacts(chain_id=None, limit=20) -> list[ArtifactRec]

# events
log_event(kind, *, chain_id=None, detail=None)
```

Then pass your store to any engine function — `ingest_url(my_store, url)`, etc.

## Configuration

All settings come from the environment (pydantic-settings) with safe defaults so
import never fails. Set credentials before making real calls.

| Env var | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API key |
| `VOYAGE_API_KEY` | `""` | Voyage AI API key |
| `MODEL_SYNTHESIS` | `claude-opus-4-8` | Model for artifact generation |
| `MODEL_EXTRACTION` | `claude-sonnet-4-6` | Model for entity/summary + growth queries |
| `MODEL_CLASSIFY` | `claude-haiku-4-5` | Model for lightweight classification |
| `EMBED_MODEL` | `voyage-3` | Embedding model |
| `EMBED_DIM` | `1024` | Embedding dimension |
| `COMBINE_THRESHOLD` | `0.82` | Min cosine similarity to merge into an existing Chain |
| `RELEVANCE_DECAY` | `0.7` | Per-hop relevance decay during growth |
| `RELEVANCE_FLOOR` | `0.45` | Min decayed relevance to keep a growth candidate |
| `WHISPER_MODEL` | `base` | faster-whisper model size |
| `TMP_DIR` | `data/tmp` | Scratch dir for downloaded media/PDFs |

## License

MIT — see [LICENSE](./LICENSE).
