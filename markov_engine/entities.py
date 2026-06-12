"""Extract a summary, entities, and relationships from content via the Anthropic
client, using structured output. PURE — returns a plain dict, no Store."""

from __future__ import annotations

import logging

from markov_engine.config import get_settings
from markov_engine.llm import complete_json

logger = logging.getLogger(__name__)
_settings = get_settings()

_PROMPT_TEMPLATE = """Extract key entities and relationships from this {source_type} content.

Title: {title}

Content:
{content}

Rules:
- Write a thorough summary (1-2 paragraphs) covering all key points so a reader fully
  understands the content without the original.
- Normalize entity names (proper capitalization, full names); merge near-duplicates.
- Include 3-15 entities depending on length; only clear, meaningful relationships."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
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
    "required": ["summary", "entities", "relationships"],
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
            "entities": [],
            "relationships": [],
            "cost_usd": 0.0,
            "success": False,
            "error": str(e),
        }
