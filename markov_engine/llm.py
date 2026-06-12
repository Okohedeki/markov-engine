"""LLM client for the engine, with pluggable backends so analysis runs on a
local model or in the cloud:

- ``anthropic`` — Anthropic API, structured output via forced tool-use.
- ``openai``    — any OpenAI-compatible /chat/completions endpoint (Ollama,
  llama.cpp server, vLLM, LM Studio, OpenAI). JSON via prompt + lenient parse.
- ``llamacpp``  — an in-process GGUF via llama-cpp-python.

Public surface (``complete`` / ``complete_json`` / ``stream_complete``) is the
same across backends. Provider SDKs are imported lazily, so you only need the
one you use. Cost is real for Anthropic and 0.0 for local backends.
"""

from __future__ import annotations

import json
import logging

import httpx

from markov_engine._local import get_llama, parse_json_loose
from markov_engine.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

RATES: dict[str, tuple[float, float]] = {
    "claude-opus-4": (5.0, 25.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (1.0, 5.0),
}

_anthropic_client = None


def _anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic
        _anthropic_client = AsyncAnthropic(api_key=_settings.anthropic_api_key)
    return _anthropic_client


def _cost(model: str, usage) -> float:
    rate = next((v for k, v in RATES.items() if model.startswith(k)), (0.0, 0.0))
    it = getattr(usage, "input_tokens", 0) or 0
    ot = getattr(usage, "output_tokens", 0) or 0
    return (it * rate[0] + ot * rate[1]) / 1_000_000


def _local_model() -> str:
    return _settings.llm_model or "local-model"


# ── OpenAI-compatible chat ────────────────────────────────────────
async def _openai_chat(messages: list[dict], *, max_tokens: int, json_mode: bool) -> str:
    payload = {"model": _local_model(), "messages": messages,
               "max_tokens": max_tokens, "temperature": 0.3}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    headers = {}
    if _settings.openai_api_key:
        headers["Authorization"] = f"Bearer {_settings.openai_api_key}"
    url = _settings.openai_base_url.rstrip("/") + "/chat/completions"
    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        return (r.json()["choices"][0]["message"].get("content") or "").strip()


# ── in-process llama-cpp chat ─────────────────────────────────────
def _llamacpp_chat(messages: list[dict], *, max_tokens: int, json_mode: bool) -> str:
    llm = get_llama(_settings.llamacpp_model, n_ctx=_settings.llamacpp_n_ctx,
                    n_gpu_layers=_settings.llamacpp_n_gpu_layers)
    kw: dict = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    r = llm.create_chat_completion(**kw)
    return (r["choices"][0]["message"].get("content") or "").strip()


async def _chat(messages: list[dict], *, max_tokens: int, json_mode: bool = False) -> str:
    b = _settings.llm_backend
    max_tokens = min(max_tokens, _settings.local_max_tokens)  # local models are slow; keep it bounded
    if b == "openai":
        return await _openai_chat(messages, max_tokens=max_tokens, json_mode=json_mode)
    if b == "llamacpp":
        import asyncio
        return await asyncio.to_thread(_llamacpp_chat, messages, max_tokens=max_tokens, json_mode=json_mode)
    raise RuntimeError(f"Unknown LLM_BACKEND: {b!r}")


# ── public API ────────────────────────────────────────────────────
async def complete(prompt: str, *, model: str, max_tokens: int = 4096,
                   system: str | None = None) -> tuple[str, float]:
    if _settings.llm_backend == "anthropic":
        kw: dict = {"model": model, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
        if system:
            kw["system"] = system
        resp = await _anthropic().messages.create(**kw)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return text, _cost(model, resp.usage)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    return await _chat(msgs, max_tokens=max_tokens), 0.0


async def complete_json(prompt: str, *, schema: dict, model: str,
                        max_tokens: int = 4096, system: str | None = None) -> tuple[dict, float]:
    """Structured output. Anthropic uses forced tool-use (guaranteed schema);
    local backends prompt for JSON and parse leniently. Callers still coerce
    item shapes (small models are loose)."""
    if _settings.llm_backend == "anthropic":
        tool = {"name": "emit_result", "description": "Return the structured result.",
                "input_schema": schema}
        kw: dict = {"model": model, "max_tokens": max_tokens, "tools": [tool],
                    "tool_choice": {"type": "tool", "name": "emit_result"},
                    "messages": [{"role": "user", "content": prompt}]}
        if system:
            kw["system"] = system
        resp = await _anthropic().messages.create(**kw)
        cost = _cost(model, resp.usage)
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input, cost
        return {}, cost
    # local: instruct + parse
    instr = ("Respond with ONLY a single JSON object that matches this JSON schema. "
             "No prose, no code fences.\n\nSCHEMA:\n" + json.dumps(schema))
    sys_msg = (system + "\n\n" + instr) if system else instr
    msgs = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
    text = await _chat(msgs, max_tokens=max_tokens, json_mode=True)
    return parse_json_loose(text), 0.0


async def stream_complete(prompt: str, *, model: str, max_tokens: int = 8192,
                          system: str | None = None) -> tuple[str, float]:
    if _settings.llm_backend == "anthropic":
        kw: dict = {"model": model, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
        if system:
            kw["system"] = system
        async with _anthropic().messages.stream(**kw) as stream:
            final = await stream.get_final_message()
        text = "".join(b.text for b in final.content if getattr(b, "type", None) == "text")
        return text, _cost(model, final.usage)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    return await _chat(msgs, max_tokens=max_tokens), 0.0
