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
            "summary": data.get("summary", ""),
            "entities": [
                {
                    "name": e["name"],
                    "type": e.get("type", "concept"),
                    "description": e.get("description", ""),
                }
                for e in data.get("entities", [])
                if e.get("name")
            ],
            "relationships": [
                {
                    "source": r["source"],
                    "target": r["target"],
                    "type": r.get("type", "related_to"),
                }
                for r in data.get("relationships", [])
                if r.get("source") and r.get("target")
            ],
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
