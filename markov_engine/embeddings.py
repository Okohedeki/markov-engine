"""Embeddings with pluggable backends — powers Topic→Chain clustering:

- ``voyage``   — Voyage AI (cloud).
- ``openai``   — any OpenAI-compatible /embeddings endpoint (Ollama, etc.).
- ``llamacpp`` — an in-process GGUF via llama-cpp-python.
- ``hash``     — deterministic hashed bag-of-words; zero setup, lexical-only.

The local SQLite store keeps embeddings as JSON and compares with cosine in
Python, so any dimension works — backends need not agree with ``EMBED_DIM``
(only the ``hash`` backend uses it).
"""

from __future__ import annotations

import hashlib
import logging
import math
import re

import httpx

from markov_engine._local import get_llama
from markov_engine.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

EMBED_DIM = _settings.embed_dim
_voyage_client = None


def _voyage():
    global _voyage_client
    if _voyage_client is None:
        import voyageai
        _voyage_client = voyageai.AsyncClient(api_key=_settings.voyage_api_key)
    return _voyage_client


def _hash_embed(text: str) -> list[float]:
    """Deterministic hashed bag-of-words vector (lexical similarity, no semantics)."""
    v = [0.0] * EMBED_DIM
    for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % EMBED_DIM] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _llamacpp_embed(text: str) -> list[float]:
    path = _settings.llamacpp_embed_model or _settings.llamacpp_model
    llm = get_llama(path, n_ctx=_settings.llamacpp_n_ctx,
                    n_gpu_layers=_settings.llamacpp_n_gpu_layers, embedding=True)
    data = llm.create_embedding(text[:4000])["data"][0]["embedding"]
    # may be a single pooled vector, or per-token vectors → mean-pool
    if data and isinstance(data[0], list):
        cols = list(zip(*data))
        data = [sum(c) / len(c) for c in cols]
    n = math.sqrt(sum(x * x for x in data)) or 1.0
    return [x / n for x in data]


async def _openai_embed(text: str) -> list[float]:
    headers = {}
    if _settings.openai_api_key:
        headers["Authorization"] = f"Bearer {_settings.openai_api_key}"
    url = _settings.openai_base_url.rstrip("/") + "/embeddings"
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json={"model": _settings.openai_embed_model, "input": text[:8000]}, headers=headers)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


async def embed(text: str, *, input_type: str = "document") -> list[float]:
    text = (text or "").strip() or "(empty)"
    b = _settings.embed_backend
    if b == "voyage":
        result = await _voyage().embed([text[:8000]], model=_settings.embed_model, input_type=input_type)
        return result.embeddings[0]
    if b == "openai":
        return await _openai_embed(text)
    if b == "llamacpp":
        import asyncio
        return await asyncio.to_thread(_llamacpp_embed, text)
    if b == "hash":
        return _hash_embed(text)
    raise RuntimeError(f"Unknown EMBED_BACKEND: {b!r}")


async def embed_many(texts: list[str], *, input_type: str = "document") -> list[list[float]]:
    if not texts:
        return []
    if _settings.embed_backend == "voyage":
        cleaned = [(t or "").strip()[:8000] or "(empty)" for t in texts]
        result = await _voyage().embed(cleaned, model=_settings.embed_model, input_type=input_type)
        return result.embeddings
    return [await embed(t, input_type=input_type) for t in texts]
