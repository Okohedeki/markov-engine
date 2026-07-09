"""Extract a summary, entities, and relationships from content via the Anthropic
client, using structured output. PURE — returns a plain dict, no Store."""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.llm import complete_json

logger = logging.getLogger(__name__)
_settings = get_settings()

_PROMPT_TEMPLATE = """You are MARKOV, doing a deep dive on this {source_type} so the reader never has to
open the original. Explain it in detail — do NOT reproduce, quote, or transcribe it.

Title: {title}

Content:
{content}

Produce:
- summary: a 1-2 paragraph overview of what this source is about and why it matters.
- key_points: the 5-9 most important points. For EACH, write:
    - title: a short, specific claim or takeaway (not a topic label).
    - detail: 2-4 sentences that EXPLAIN the point in your own words — the reasoning,
      evidence, context and implication — so the reader fully understands it without the
      original. Explain, don't quote. Don't say "the video says"; state the substance.
  Order key_points from most to least important.
- entities / relationships: normalize names (proper capitalization, full names), merge
  near-duplicates; 3-15 entities by length; only clear, meaningful relationships."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [
                            "person", "topic", "concept", "org",
                            "place", "technology", "event",
                        ],
                    },
                    "description": {"type": "string"},
                },
                "required": ["name", "type"],
            },
        },
        "relationships": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["source", "target", "type"],
            },
        },
    },
    "required": ["summary", "key_points", "entities", "relationships"],
}

_VALID_TYPES = {"person", "topic", "concept", "org", "place", "technology", "event"}


def _coerce_entities(items) -> list[dict]:
    """Small models return entities loosely (bare strings, missing types).
    Coerce to {name, type, description}; drop blanks."""
    out = []
    for e in items if isinstance(items, list) else []:
        if isinstance(e, str) and e.strip():
            out.append({"name": e.strip(), "type": "concept", "description": ""})
        elif isinstance(e, dict):
            name = e.get("name") or e.get("entity") or e.get("title")
            if name:
                etype = str(e.get("type") or "concept").lower()
                out.append({"name": str(name), "type": etype if etype in _VALID_TYPES else "concept",
                            "description": str(e.get("description") or "")})
    return out


def _coerce_key_points(items) -> list[dict]:
    """Normalize key points to {title, detail}; accept bare strings from small
    models (title only) and drop blanks."""
    out = []
    for k in items if isinstance(items, list) else []:
        if isinstance(k, str) and k.strip():
            out.append({"title": k.strip(), "detail": ""})
        elif isinstance(k, dict):
            title = k.get("title") or k.get("point") or k.get("name")
            if title:
                out.append({"title": str(title), "detail": str(k.get("detail") or k.get("explanation") or "")})
    return out


def _coerce_relationships(items) -> list[dict]:
    out = []
    for r in items if isinstance(items, list) else []:
        if isinstance(r, dict) and r.get("source") and r.get("target"):
            out.append({"source": str(r["source"]), "target": str(r["target"]),
                        "type": str(r.get("type") or "related_to")})
    return out


async def extract_entities(
    content_text: str, title: str, source_type: str, model: str | None = None
) -> dict:
    """Returns dict with keys: summary, entities, relationships, cost_usd, success, error."""
    prompt = _PROMPT_TEMPLATE.format(
        source_type=source_type,
        title=title or "Untitled",
        content=content_text[:8000],
    )
    try:
        data, cost = await complete_json(
            prompt,
            schema=_SCHEMA,
            model=model or _settings.model_extraction,
            max_tokens=2048,
        )
        return {
            "summary": str(data.get("summary") or ""),
            "key_points": _coerce_key_points(data.get("key_points") or []),
            "entities": _coerce_entities(data.get("entities") or data.get("items") or []),
            "relationships": _coerce_relationships(data.get("relationships") or []),
            "cost_usd": cost,
            "success": True,
            "error": None,
        }
    except Exception as e:
        logger.exception("Entity extraction failed")
        return {
            "summary": "",
            "key_points": [],
            "entities": [],
            "relationships": [],
            "cost_usd": 0.0,
            "success": False,
            "error": str(e),
        }
