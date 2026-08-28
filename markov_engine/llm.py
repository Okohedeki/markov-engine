"""LLM client for the engine, with pluggable backends so analysis runs on a
local model or in the cloud:

- ``anthropic`` — Anthropic API, structured output via forced tool-use.
- ``openai``    — official OpenAI Responses API with Structured Outputs, or an
  OpenAI-compatible /chat/completions endpoint (Ollama, llama.cpp, vLLM,
  LM Studio).
- ``llamacpp``  — an in-process GGUF via llama-cpp-python.

Public surface (``complete`` / ``complete_json`` / ``stream_complete``) is the
same across backends. Provider SDKs are imported lazily, so you only need the
one you use. Cost is estimated for known cloud models and 0.0 for local models.
"""

from __future__ import annotations

import json
import logging
import re as _re
from copy import deepcopy
from urllib.parse import urlparse

import httpx

from markov_engine._local import get_llama, parse_json_loose
from markov_engine.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()

ANTHROPIC_RATES: dict[str, tuple[float, float]] = {
    "claude-opus-4": (5.0, 25.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4": (1.0, 5.0),
}

OPENAI_RATES: dict[str, tuple[float, float]] = {
    "gpt-5.6-sol": (4.0, 20.0),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-luna": (0.2, 1.2),
}

_anthropic_client = None


def _anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import AsyncAnthropic
        _anthropic_client = AsyncAnthropic(api_key=_settings.anthropic_api_key)
    return _anthropic_client


def _cost(model: str, usage) -> float:
    rate = next(
        (v for k, v in ANTHROPIC_RATES.items() if model.startswith(k)),
        (0.0, 0.0),
    )
    it = getattr(usage, "input_tokens", 0) or 0
    ot = getattr(usage, "output_tokens", 0) or 0
    return (it * rate[0] + ot * rate[1]) / 1_000_000


def _openai_cost(model: str, usage: dict | None) -> float:
    rate = next(
        (v for k, v in OPENAI_RATES.items() if model.startswith(k)),
        (0.0, 0.0),
    )
    usage = usage or {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    return (input_tokens * rate[0] + output_tokens * rate[1]) / 1_000_000


def _local_model() -> str:
    return _settings.llm_model or "local-model"


def _openai_mode() -> str:
    mode = _settings.openai_api_mode.strip().lower()
    if mode not in {"auto", "responses", "chat_completions"}:
        raise ValueError(
            "OPENAI_API_MODE must be auto, responses, or chat_completions"
        )
    if mode != "auto":
        return mode
    hostname = (urlparse(_settings.openai_base_url).hostname or "").lower()
    return "responses" if hostname == "api.openai.com" else "chat_completions"


def _strict_openai_schema(schema: dict) -> dict:
    """Make the engine's existing JSON Schemas acceptable to strict outputs.

    Anthropic permits optional object properties. OpenAI strict schemas require
    every declared property to be named in ``required``. Markov's callers already
    coerce missing/empty values, so requiring the model to emit those fields is
    both safe and more predictable.
    """
    normalized = deepcopy(schema)

    def visit(node) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["additionalProperties"] = False
                node["required"] = list(node["properties"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    visit(normalized)
    return normalized


# ── heuristic backend (offline, instant, no model) ───────────────


def _heuristic_json(prompt: str, schema: dict) -> dict:
    props = (schema or {}).get("properties", {})
    if "claims" in props:
        located = _re.findall(r"^\[S(\d+)\]\s+(.+)$", prompt, flags=_re.MULTILINE)
        claims = []
        for index, (segment_id, segment_text) in enumerate(located):
            sentences = [
                sentence.strip()
                for sentence in _re.split(r"(?<=[.!?])\s+", segment_text)
                if len(sentence.strip()) >= 8
            ]
            for sentence in sentences[:2]:
                lowered = sentence.lower()
                claim_type = (
                    "predictive"
                    if any(word in lowered for word in (" will ", " may ", " could "))
                    else "quantitative"
                    if _re.search(r"\b\d+(?:\.\d+)?%?\b", sentence)
                    else "opinion"
                    if any(word in lowered for word in ("i think", "i believe", "should"))
                    else "factual"
                )
                claims.append(
                    {
                        "claim_text": sentence,
                        "claim_type": claim_type,
                        "importance": max(0.4, 0.9 - index * 0.05),
                        "speaker_certainty": (
                            "speculative" if claim_type == "predictive" else "asserted_as_fact"
                        ),
                        "source_segment_ids": [int(segment_id)],
                    }
                )
        gaps = []
        if claims:
            gaps.append(
                {
                    "gap_type": "unresolved_evidence",
                    "question": f"What independent evidence verifies: {claims[0]['claim_text']}",
                    "importance": claims[0]["importance"],
                    "related_claim_text": claims[0]["claim_text"],
                }
            )
        return {"claims": claims, "research_gaps": gaps}
    if "stance" in props:
        claim_match = _re.search(r"CLAIM:\s*(.+)", prompt)
        passage_match = _re.search(r"PASSAGE:\s*(.+)", prompt, flags=_re.DOTALL)
        claim_words = set(_re.findall(r"[a-z0-9]+", (claim_match.group(1) if claim_match else "").lower()))
        passage_words = set(_re.findall(r"[a-z0-9]+", (passage_match.group(1) if passage_match else "").lower()))
        overlap = len(claim_words & passage_words) / max(1, len(claim_words))
        return {
            "stance": "supports" if overlap >= 0.35 else "context_only",
            "strength": min(0.9, max(0.2, overlap)),
            "rationale": "Lexical overlap heuristic; requires human review for verified delivery.",
            "confidence": min(0.8, max(0.2, overlap)),
        }
    if "queries" in props:
        m = _re.search(r"SUBJECT:\s*(.+)", prompt)
        subj = (m.group(1).strip() if m else "topic")[:80]
        return {"queries": [{"q": f"{subj} latest", "hop": 0},
                            {"q": f"{subj} explained", "hop": 0},
                            {"q": f"{subj} analysis", "hop": 1}]}
    # entity-extraction schema (trim the prompt's trailing instruction template)
    content = prompt.split("Content:\n", 1)[-1].split("\n\nProduce:")[0].split("\n\nRules:")[0]
    caps = _re.findall(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,2})\b", content)
    names, seen = [], set()
    for c in caps:
        k = c.lower()
        if k not in seen and len(c) > 3:
            seen.add(k)
            names.append(c)
    ents = [{"name": n, "type": "concept", "description": ""} for n in names[:8]] or \
           [{"name": "Subject", "type": "topic", "description": ""}]
    sentences = [s.strip() for s in _re.split(r"(?<=[.!?])\s+", content.strip()) if s.strip()]
    summary = " ".join(sentences[:3])[:400]
    # Fabricate key points from the leading sentences (offline mode has no model
    # to explain, so the sentence stands in as its own detail).
    key_points = [
        {"title": " ".join(s.split()[:8]), "detail": s}
        for s in sentences[:6]
    ] if "key_points" in props else []
    rels = [{"source": ents[0]["name"], "target": e["name"], "type": "related_to"} for e in ents[1:4]]
    out = {"summary": summary, "entities": ents, "relationships": rels}
    if "key_points" in props:
        out["key_points"] = key_points
    return out


def _heuristic_text(prompt: str) -> str:
    m = _re.search(r"SUBJECT:\s*(.+)", prompt)
    subj = (m.group(1).strip() if m else "this subject")[:120]
    titles = _re.findall(r"^###\s+(.+)$", prompt, flags=_re.MULTILINE)
    body = "\n".join(f"- {t.strip()}" for t in titles[:8]) or "- (sources gathered for this chain)"
    return (f"# {subj}\n\n*A synthesis across this chain's sources (offline heuristic mode).*\n\n"
            f"This chain has gathered the following sources:\n\n{body}\n\n"
            f"Enable a real model (LLM_BACKEND=anthropic|openai|llamacpp) for full synthesis.")


# ── OpenAI-compatible chat ────────────────────────────────────────
async def _openai_chat(
    messages: list[dict], *, max_tokens: int, json_mode: bool
) -> tuple[str, float]:
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
        data = r.json()
        text = (data["choices"][0]["message"].get("content") or "").strip()
        return text, _openai_cost(_local_model(), data.get("usage"))


def _responses_output_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()
    texts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "output_text" and isinstance(block.get("text"), str):
                texts.append(block["text"])
    return "".join(texts).strip()


async def _openai_responses(
    messages: list[dict],
    *,
    max_tokens: int,
    schema: dict | None = None,
) -> tuple[str, float]:
    model = _local_model()
    payload: dict = {
        "model": model,
        "input": messages,
        "max_output_tokens": max_tokens,
        "store": False,
    }
    effort = _settings.openai_reasoning_effort.strip().lower()
    if effort:
        payload["reasoning"] = {"effort": effort}
    if schema is not None:
        payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": "markov_result",
                "strict": True,
                "schema": _strict_openai_schema(schema),
            }
        }
    headers = {"Content-Type": "application/json"}
    if _settings.openai_api_key:
        headers["Authorization"] = f"Bearer {_settings.openai_api_key}"
    url = _settings.openai_base_url.rstrip("/") + "/responses"
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    text = _responses_output_text(data)
    if not text:
        raise RuntimeError("OpenAI Responses API returned no output text")
    return text, _openai_cost(model, data.get("usage"))


# ── in-process llama-cpp chat ─────────────────────────────────────
def _llamacpp_chat(messages: list[dict], *, max_tokens: int, json_mode: bool) -> str:
    llm = get_llama(_settings.llamacpp_model, n_ctx=_settings.llamacpp_n_ctx,
                    n_gpu_layers=_settings.llamacpp_n_gpu_layers)
    kw: dict = {"messages": messages, "max_tokens": max_tokens, "temperature": 0.3}
    if json_mode:
        kw["response_format"] = {"type": "json_object"}
    r = llm.create_chat_completion(**kw)
    return (r["choices"][0]["message"].get("content") or "").strip()


async def _chat(
    messages: list[dict], *, max_tokens: int, json_mode: bool = False
) -> tuple[str, float]:
    b = _settings.llm_backend
    if b == "openai":
        if _openai_mode() == "responses":
            return await _openai_responses(messages, max_tokens=max_tokens)
        max_tokens = min(max_tokens, _settings.local_max_tokens)
        return await _openai_chat(messages, max_tokens=max_tokens, json_mode=json_mode)
    if b == "llamacpp":
        import asyncio
        max_tokens = min(max_tokens, _settings.local_max_tokens)
        text = await asyncio.to_thread(
            _llamacpp_chat, messages, max_tokens=max_tokens, json_mode=json_mode
        )
        return text, 0.0
    raise RuntimeError(f"Unknown LLM_BACKEND: {b!r}")


# ── public API ────────────────────────────────────────────────────
async def complete(prompt: str, *, model: str, max_tokens: int = 4096,
                   system: str | None = None) -> tuple[str, float]:
    if _settings.llm_backend == "heuristic":
        return _heuristic_text(prompt), 0.0
    if _settings.llm_backend == "anthropic":
        kw: dict = {"model": model, "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]}
        if system:
            kw["system"] = system
        resp = await _anthropic().messages.create(**kw)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return text, _cost(model, resp.usage)
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    return await _chat(msgs, max_tokens=max_tokens)


async def complete_json(prompt: str, *, schema: dict, model: str,
                        max_tokens: int = 4096, system: str | None = None) -> tuple[dict, float]:
    """Structured output. Anthropic uses forced tool-use (guaranteed schema);
    local backends prompt for JSON and parse leniently. Callers still coerce
    item shapes (small models are loose)."""
    if _settings.llm_backend == "heuristic":
        return _heuristic_json(prompt, schema), 0.0
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
    if _settings.llm_backend == "openai" and _openai_mode() == "responses":
        msgs = (
            [{"role": "system", "content": system}] if system else []
        ) + [{"role": "user", "content": prompt}]
        text, cost = await _openai_responses(
            msgs, max_tokens=max_tokens, schema=schema
        )
        return parse_json_loose(text), cost
    # local: instruct + parse
    instr = ("Respond with ONLY a single JSON object that matches this JSON schema. "
             "No prose, no code fences.\n\nSCHEMA:\n" + json.dumps(schema))
    sys_msg = (system + "\n\n" + instr) if system else instr
    msgs = [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}]
    text, cost = await _chat(msgs, max_tokens=max_tokens, json_mode=True)
    return parse_json_loose(text), cost


async def stream_complete(prompt: str, *, model: str, max_tokens: int = 8192,
                          system: str | None = None) -> tuple[str, float]:
    if _settings.llm_backend == "heuristic":
        return _heuristic_text(prompt), 0.0
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
    return await _chat(msgs, max_tokens=max_tokens)
