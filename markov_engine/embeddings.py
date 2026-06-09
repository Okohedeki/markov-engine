"""Embeddings via Voyage AI (voyage-3, 1024-dim by default) — powers
Topic→Chain clustering. Provider-agnostic surface: only this module knows the
vendor/dimension.
"""

from __future__ import annotations

import logging

import voyageai

from markov_engine.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
_client = voyageai.AsyncClient(api_key=_settings.voyage_api_key)

EMBED_DIM = _settings.embed_dim


async def embed(text: str, *, input_type: str = "document") -> list[float]:
    """Embed a single text. ``input_type`` is 'document' (stored) or 'query'."""
    text = (text or "").strip() or "(empty)"
    result = await _client.embed(
        [text[:8000]], model=_settings.embed_model, input_type=input_type
    )
    return result.embeddings[0]


async def embed_many(
    texts: list[str], *, input_type: str = "document"
) -> list[list[float]]:
    if not texts:
        return []
    cleaned = [(t or "").strip()[:8000] or "(empty)" for t in texts]
    result = await _client.embed(
        cleaned, model=_settings.embed_model, input_type=input_type
    )
    return result.embeddings
