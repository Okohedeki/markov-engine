"""Generate artifacts (article / newsletter) from a Chain's Sources via the
Anthropic client. Chain-scoped."""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.llm import stream_complete
from markov_engine.store.base import Store

logger = logging.getLogger(__name__)
_settings = get_settings()

_TEMPLATES = {
    "article": """You are a skilled writer creating a well-researched article from a
collection of saved sources about a single evolving subject.

SUBJECT: {topic}

SOURCE MATERIAL:
{source_material}

Write a comprehensive, publication-quality article in clean Markdown:
- Open with a compelling hook and thesis.
- Organize into clear sections with headers.
- Synthesize across sources — don't summarize each one in isolation.
- Use specific data points, quotes, and examples; cite naturally ("According to …").
- End with implications or a forward-looking conclusion. Target 1000-1800 words.""",
    "newsletter": """You are writing an edition of a personal briefing about an evolving subject.

SUBJECT: {topic}

AVAILABLE CONTENT:
{source_material}

Create a newsletter edition in Markdown:
- Brief editorial intro (2-3 sentences of context).
- 3-5 themed sections, each with short analysis (not bare summaries).
- A "Quick Links" section for minor items and a "What I'm Watching" close.""",
}


def _title_from(content: str, fallback: str) -> str:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()[:120]
        if line and len(line) > 10:
            return line[:80]
    return fallback


async def generate_artifact(
    store: Store,
    chain_id: int,
    artifact_type: str = "article",
    *,
    model: str | None = None,
) -> dict:
    """Generate one artifact for a Chain from its Sources. Returns a result dict."""
    if artifact_type not in _TEMPLATES:
        return {"success": False, "error": f"Unsupported artifact type: {artifact_type}"}

    chain = await store.get_chain(chain_id)
    if not chain:
        return {"success": False, "error": "Chain not found"}

    rows = await store.list_chain_sources(chain_id, limit=15)
    if not rows:
        return {"success": False, "error": "Chain has no sources yet"}

    material_parts = []
    used_ids = []
    for row in rows:
        s = row.source
        used_ids.append(s.id)
        body = (s.content_text or s.summary or "")[:2000]
        material_parts.append(
            f"### {s.title or s.url or 'Untitled'} ({s.source_type})\n{body}"
        )

    prompt = _TEMPLATES[artifact_type].format(
        topic=chain.title, source_material="\n\n".join(material_parts)
    )
    used_model = model or _settings.model_synthesis
    try:
        content, cost = await stream_complete(prompt, model=used_model, max_tokens=8192)
    except Exception as e:
        logger.exception("Artifact generation failed")
        return {"success": False, "error": str(e)}

    if not content.strip():
        return {"success": False, "error": "Empty generation"}

    title = _title_from(content, f"{artifact_type.title()}: {chain.title}")
    artifact = await store.add_artifact(
        chain_id=chain_id,
        artifact_type=artifact_type,
        title=title,
        content=content,
        parameters={"chain_id": chain_id},
        model_used=used_model,
        cost_usd=cost,
        source_ids=used_ids,
    )
    return {
        "success": True,
        "id": artifact.id,
        "title": title,
        "artifact_type": artifact_type,
        "content": content,
        "cost_usd": cost,
        "source_ids": used_ids,
    }
