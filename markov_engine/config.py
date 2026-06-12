"""Engine configuration via pydantic-settings.

All values have safe defaults so importing the package never fails. Pick a
backend with ``LLM_BACKEND`` / ``EMBED_BACKEND``:

- ``anthropic`` + ``voyage`` — cloud (needs ANTHROPIC_API_KEY / VOYAGE_API_KEY)
- ``openai``  — any OpenAI-compatible endpoint (Ollama, llama.cpp server, vLLM,
  LM Studio, OpenAI itself) via OPENAI_BASE_URL
- ``llamacpp`` — an in-process GGUF via llama-cpp-python (LLAMACPP_MODEL)
- ``hash`` (embeddings only) — deterministic, zero-setup, no semantics

So the engine runs for analysis with no cloud keys: point it at a local model.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── backend selection ───────────────────────────────────────────
    llm_backend: str = Field("anthropic", alias="LLM_BACKEND")   # anthropic|openai|llamacpp
    embed_backend: str = Field("voyage", alias="EMBED_BACKEND")  # voyage|openai|llamacpp|hash

    # ── LLM: Anthropic (cloud) ──────────────────────────────────────
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    model_synthesis: str = Field("claude-opus-4-8", alias="MODEL_SYNTHESIS")
    model_extraction: str = Field("claude-sonnet-4-6", alias="MODEL_EXTRACTION")
    model_classify: str = Field("claude-haiku-4-5", alias="MODEL_CLASSIFY")

    # ── LLM: OpenAI-compatible (local servers / OpenAI) ─────────────
    openai_base_url: str = Field("http://localhost:11434/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    llm_model: str = Field("", alias="LLM_MODEL")  # the model id for openai/llamacpp

    # ── LLM/embeddings: in-process llama-cpp (GGUF) ─────────────────
    llamacpp_model: str = Field("", alias="LLAMACPP_MODEL")              # path to a .gguf
    llamacpp_embed_model: str = Field("", alias="LLAMACPP_EMBED_MODEL")  # defaults to llamacpp_model
    llamacpp_n_ctx: int = Field(8192, alias="LLAMACPP_N_CTX")
    llamacpp_n_gpu_layers: int = Field(-1, alias="LLAMACPP_N_GPU_LAYERS")
    local_max_tokens: int = Field(1024, alias="LOCAL_MAX_TOKENS")

    # ── Embeddings: Voyage (cloud) / OpenAI-compatible ──────────────
    voyage_api_key: str = Field("", alias="VOYAGE_API_KEY")
    embed_model: str = Field("voyage-3", alias="EMBED_MODEL")
    openai_embed_model: str = Field("nomic-embed-text", alias="OPENAI_EMBED_MODEL")
    embed_dim: int = Field(1024, alias="EMBED_DIM")  # only enforced by the hash backend

    # ── Clustering / growth tuning ──────────────────────────────────
    combine_threshold: float = Field(0.82, alias="COMBINE_THRESHOLD")
    relevance_decay: float = Field(0.7, alias="RELEVANCE_DECAY")
    relevance_floor: float = Field(0.45, alias="RELEVANCE_FLOOR")

    # ── Content extraction ──────────────────────────────────────────
    whisper_model: str = Field("base", alias="WHISPER_MODEL")
    tmp_dir: str = Field("data/tmp", alias="TMP_DIR")


@lru_cache
def get_settings() -> Settings:
    return Settings()
