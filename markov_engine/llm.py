"""Anthropic LLM client for the engine. One async client; per-call-site model
choice. Cost is computed from ``response.usage`` against a rates table.

Rates default to current public Anthropic pricing (USD per 1M tokens). Override
``RATES`` if your pricing differs.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from markov_engine.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()
_client = AsyncAnthropic(api_key=_settings.anthropic_api_key)

# USD per 1M tokens, (input, output). Keyed by model-id prefix.
RATES: dict[str, tuple[float, float]] = {
    "claude-opus-4": (5.0, 25.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (1.0, 5.0),
}


def _cost(model: str, usage) -> float:
    rate = next((v for k, v in RATES.items() if model.startswith(k)), (0.0, 0.0))
    in_tok = getattr(usage, "input_tokens", 0) or 0
    out_tok = getattr(usage, "output_tokens", 0) or 0
    return (in_tok * rate[0] + out_tok * rate[1]) / 1_000_000


async def complete(
    prompt: str,
    *,
    model: str,
    max_tokens: int = 4096,
    system: str | None = None,
) -> tuple[str, float]:
    """One-shot completion. Returns (text, cost_usd)."""
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    resp = await _client.messages.create(**kwargs)
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return text, _cost(model, resp.usage)


async def complete_json(
    prompt: str,
    *,
    schema: dict,
    model: str,
    max_tokens: int = 4096,
    system: str | None = None,
) -> tuple[dict, float]:
    """Structured output via a forced tool call — no brittle JSON-from-text parsing.
    ``schema`` is a JSON Schema for the tool input. Returns (obj, cost_usd)."""
    tool = {
        "name": "emit_result",
        "description": "Return the structured result.",
        "input_schema": schema,
    }
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "tools": [tool],
        "tool_choice": {"type": "tool", "name": "emit_result"},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    resp = await _client.messages.create(**kwargs)
    cost = _cost(model, resp.usage)
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input, cost
    return {}, cost


async def stream_complete(
    prompt: str,
    *,
    model: str,
    max_tokens: int = 8192,
    system: str | None = None,
) -> tuple[str, float]:
    """Streamed long-form generation (avoids the SDK long-output timeout guard).
    Returns (text, cost_usd)."""
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system
    async with _client.messages.stream(**kwargs) as stream:
        final = await stream.get_final_message()
    text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
    return text, _cost(model, final.usage)
