"""Shared helpers for local/OpenAI-compatible backends: an in-process llama-cpp
loader (cached) and lenient JSON parsing for models without forced tool-use."""

from __future__ import annotations

import json
import re

_LLAMA_CACHE: dict[tuple, object] = {}


def get_llama(model_path: str, *, n_ctx: int, n_gpu_layers: int, embedding: bool = False):
    """Load (and cache) an in-process llama-cpp model. Chat and embeddings need
    separate instances — embedding mode disables causal generation — so the
    cache is keyed by (path, embedding)."""
    if not model_path:
        raise RuntimeError(
            "LLAMACPP_MODEL is not set — point it at a .gguf file to use the llamacpp backend."
        )
    key = (model_path, embedding)
    if key not in _LLAMA_CACHE:
        try:
            from llama_cpp import Llama
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "llama-cpp-python is required for the llamacpp backend: "
                "pip install 'markov-engine[local]'  (or pip install llama-cpp-python)"
            ) from e
        _LLAMA_CACHE[key] = Llama(
            model_path=model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers,
            embedding=embedding, verbose=False,
        )
    return _LLAMA_CACHE[key]


def parse_json_loose(text: str) -> dict:
    """Parse JSON a small model emitted as text. Strips code fences, finds the
    outermost object (or wraps a top-level array), tolerates trailing junk.
    Always returns a dict."""
    if not text:
        return {}
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {"items": v}
    except Exception:
        pass
    # outermost {...}
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            v = json.loads(m.group())
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    # outermost [...]
    m = re.search(r"\[[\s\S]*\]", s)
    if m:
        try:
            v = json.loads(m.group())
            return {"items": v}
        except Exception:
            pass
    return {}
