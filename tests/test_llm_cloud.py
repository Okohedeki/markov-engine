from __future__ import annotations

import json

import pytest

from markov_engine import llm


class _FakeResponse:
    def __init__(self, data: dict):
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._data


class _FakeClient:
    response_data: dict = {}
    request: dict = {}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, *, json: dict, headers: dict):
        type(self).request = {"url": url, "json": json, "headers": headers}
        return _FakeResponse(type(self).response_data)


@pytest.mark.asyncio
async def test_official_openai_uses_responses_structured_outputs_and_tracks_cost(
    monkeypatch,
):
    monkeypatch.setattr(llm.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(llm._settings, "llm_backend", "openai")
    monkeypatch.setattr(llm._settings, "openai_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(llm._settings, "openai_api_mode", "auto")
    monkeypatch.setattr(llm._settings, "openai_api_key", "test-key")
    monkeypatch.setattr(llm._settings, "llm_model", "gpt-5.6-luna")
    monkeypatch.setattr(llm._settings, "openai_reasoning_effort", "low")
    _FakeClient.response_data = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": '{"canonical_name":"Jason Arday"}'}
                ],
            }
        ],
        "usage": {"input_tokens": 1_000, "output_tokens": 100},
    }

    result, cost = await llm.complete_json(
        "Correct the transcript entity Jason Arde.",
        schema={
            "type": "object",
            "properties": {"canonical_name": {"type": "string"}},
            "required": ["canonical_name"],
        },
        model="ignored-for-openai",
    )

    assert result == {"canonical_name": "Jason Arday"}
    assert cost == pytest.approx(0.00032)
    assert _FakeClient.request["url"] == "https://api.openai.com/v1/responses"
    assert _FakeClient.request["headers"]["Authorization"] == "Bearer test-key"
    payload = _FakeClient.request["json"]
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert payload["store"] is False


@pytest.mark.asyncio
async def test_local_openai_compatible_server_keeps_chat_contract_and_token_cap(
    monkeypatch,
):
    monkeypatch.setattr(llm.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(llm._settings, "llm_backend", "openai")
    monkeypatch.setattr(llm._settings, "openai_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(llm._settings, "openai_api_mode", "auto")
    monkeypatch.setattr(llm._settings, "openai_api_key", "")
    monkeypatch.setattr(llm._settings, "llm_model", "qwen-local")
    monkeypatch.setattr(llm._settings, "local_max_tokens", 256)
    _FakeClient.response_data = {
        "choices": [{"message": {"content": json.dumps({"ok": True})}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 25},
    }

    result, cost = await llm.complete_json(
        "Return ok.",
        schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        model="ignored-for-openai",
        max_tokens=4_096,
    )

    assert result == {"ok": True}
    assert cost == 0.0
    assert _FakeClient.request["url"] == "http://localhost:11434/v1/chat/completions"
    assert _FakeClient.request["json"]["max_tokens"] == 256
    assert _FakeClient.request["json"]["response_format"] == {"type": "json_object"}


def test_strict_openai_schema_requires_declared_nested_properties():
    schema = {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["name"],
                },
            }
        },
        "required": ["entities"],
    }

    normalized = llm._strict_openai_schema(schema)

    assert normalized["additionalProperties"] is False
    item = normalized["properties"]["entities"]["items"]
    assert item["required"] == ["name", "description"]
    assert item["additionalProperties"] is False
    assert schema["properties"]["entities"]["items"]["required"] == ["name"]


@pytest.mark.asyncio
async def test_hybrid_routes_extraction_to_local_ollama(monkeypatch):
    monkeypatch.setattr(llm.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(llm._settings, "llm_backend", "hybrid")
    monkeypatch.setattr(llm._settings, "hybrid_cloud_backend", "openai")
    monkeypatch.setattr(llm._settings, "hybrid_local_tasks", "claim_extraction")
    monkeypatch.setattr(llm._settings, "local_llm_base_url", "http://localhost:11434/v1")
    monkeypatch.setattr(llm._settings, "local_llm_api_mode", "chat_completions")
    monkeypatch.setattr(llm._settings, "local_llm_model", "llama3.1:8b")
    monkeypatch.setattr(llm._settings, "local_llm_api_key", "")
    monkeypatch.setattr(llm._settings, "local_max_tokens", 512)
    _FakeClient.response_data = {
        "choices": [{"message": {"content": '{"claims":[]}'}}],
        "usage": {"prompt_tokens": 500, "completion_tokens": 25},
    }

    result, cost = await llm.complete_json(
        "Extract bounded claims.",
        schema={
            "type": "object",
            "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
            "required": ["claims"],
        },
        model="ignored-for-local",
        task="claim_extraction",
    )

    assert result == {"claims": []}
    assert cost == 0
    assert _FakeClient.request["url"] == "http://localhost:11434/v1/chat/completions"
    assert _FakeClient.request["json"]["model"] == "llama3.1:8b"
    assert "Authorization" not in _FakeClient.request["headers"]


@pytest.mark.asyncio
async def test_hybrid_routes_synthesis_to_task_specific_cloud_model(monkeypatch):
    monkeypatch.setattr(llm.httpx, "AsyncClient", _FakeClient)
    monkeypatch.setattr(llm._settings, "llm_backend", "hybrid")
    monkeypatch.setattr(llm._settings, "hybrid_cloud_backend", "openai")
    monkeypatch.setattr(llm._settings, "hybrid_local_tasks", "claim_extraction")
    monkeypatch.setattr(llm._settings, "openai_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(llm._settings, "openai_api_key", "test-key")
    monkeypatch.setattr(llm._settings, "llm_model", "")
    monkeypatch.setattr(llm._settings, "openai_model_synthesis", "gpt-5.6-terra")
    monkeypatch.setattr(llm._settings, "openai_reasoning_effort", "low")
    _FakeClient.response_data = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"connections":[]}'}],
            }
        ],
        "usage": {"input_tokens": 1_000, "output_tokens": 100},
    }

    result, cost = await llm.complete_json(
        "Synthesize bounded connections.",
        schema={
            "type": "object",
            "properties": {
                "connections": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["connections"],
        },
        model="ignored-for-openai",
        task="connection_synthesis",
    )

    assert result == {"connections": []}
    assert cost == pytest.approx(0.0032)
    assert _FakeClient.request["url"] == "https://api.openai.com/v1/responses"
    assert _FakeClient.request["json"]["model"] == "gpt-5.6-terra"
    assert _FakeClient.request["headers"]["Authorization"] == "Bearer test-key"
