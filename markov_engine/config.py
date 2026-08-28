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
    # Wall-clock ceiling for one growth cycle's ingest loop. Slow/blocked source
    # extractions can otherwise run a cycle for many minutes, holding a DB
    # connection open until the pooler drops it. Bounds "go deeper" latency.
    grow_time_budget_s: float = Field(90.0, alias="GROW_TIME_BUDGET_S")

    # ── Content extraction ──────────────────────────────────────────
    whisper_model: str = Field("base", alias="WHISPER_MODEL")
    # When False, video/social sources ingest from metadata + captions only
    # (no audio download + Whisper) — much faster, plenty for headlines/clustering.
    transcribe_media: bool = Field(True, alias="TRANSCRIBE_MEDIA")
    tmp_dir: str = Field("data/tmp", alias="TMP_DIR")

    # ── Commercial V1 delivery ─────────────────────────────────────
    database_path: str = Field("data/markov.db", alias="MARKOV_DATABASE_PATH")
    api_keys: dict[str, str] = Field(
        default_factory=dict,
        alias="MARKOV_API_KEYS",
        description="JSON mapping of API key to owner id.",
    )
    internal_api_keys: dict[str, str] = Field(
        default_factory=dict,
        alias="MARKOV_INTERNAL_API_KEYS",
        description="JSON mapping of reviewer API key to reviewer id.",
    )
    web_session_secret: str = Field("change-me", alias="MARKOV_WEB_SESSION_SECRET")
    api_rate_limit_per_minute: int = Field(
        60, alias="MARKOV_API_RATE_LIMIT_PER_MINUTE"
    )
    opening_credits: float = Field(0, alias="MARKOV_OPENING_CREDITS")
    product_credit_costs: dict[str, float] = Field(
        default_factory=lambda: {
            "brief_instant": 1,
            "brief_verified": 3,
            "research_instant": 3,
            "research_verified": 6,
            "script_instant": 4,
            "script_verified": 8,
        },
        alias="MARKOV_PRODUCT_CREDIT_COSTS",
        description="Configurable credits charged for each sellable variant.",
    )
    stripe_secret_key: str = Field("", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field("", alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_ids: dict[str, str] = Field(
        default_factory=dict,
        alias="STRIPE_PRICE_IDS",
        description="JSON mapping of credit-pack names to Stripe Price ids.",
    )
    stripe_credit_packs: dict[str, float] = Field(
        default_factory=dict,
        alias="STRIPE_CREDIT_PACKS",
        description="JSON mapping of Stripe Price ids to granted credits.",
    )
    stripe_success_url: str = Field(
        "http://localhost:8000/app?payment=success", alias="STRIPE_SUCCESS_URL"
    )
    stripe_cancel_url: str = Field(
        "http://localhost:8000/app?payment=cancelled", alias="STRIPE_CANCEL_URL"
    )
    webhook_signing_secret: str = Field("", alias="MARKOV_WEBHOOK_SIGNING_SECRET")
    human_review_hourly_cost: float = Field(
        0, alias="MARKOV_HUMAN_REVIEW_HOURLY_COST"
    )

    # ── V2 connection graph ────────────────────────────────────────
    connection_score_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "relevance": 0.22,
            "evidence_strength": 0.28,
            "novelty": 0.16,
            "explanatory_value": 0.18,
            "output_usefulness": 0.16,
        },
        alias="MARKOV_CONNECTION_SCORE_WEIGHTS",
        description="JSON weights for reproducible V2 connection ranking.",
    )
    connection_risk_penalty: float = Field(
        0.2, alias="MARKOV_CONNECTION_RISK_PENALTY"
    )
    connection_min_score: float = Field(
        0.25, alias="MARKOV_CONNECTION_MIN_SCORE"
    )
    default_entitlement_profile: str = Field(
        "cloud_pro", alias="MARKOV_DEFAULT_ENTITLEMENT_PROFILE"
    )
    owner_entitlement_profiles: dict[str, str] = Field(
        default_factory=dict,
        alias="MARKOV_OWNER_ENTITLEMENT_PROFILES",
        description="JSON mapping of owner id to entitlement profile.",
    )
    entitlement_overrides: dict[str, dict] = Field(
        default_factory=dict,
        alias="MARKOV_ENTITLEMENT_OVERRIDES",
        description="JSON profile overrides for deployment-specific limits.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
