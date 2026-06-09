"""Engine configuration via pydantic-settings.

All values have safe defaults (empty strings for credentials) so importing the
package never fails. A real deployment must set ``ANTHROPIC_API_KEY`` and
``VOYAGE_API_KEY`` (via env or a ``.env`` file) to actually reach the providers.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── LLM (Anthropic) ─────────────────────────────────────────────
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    model_synthesis: str = Field("claude-opus-4-8", alias="MODEL_SYNTHESIS")
    model_extraction: str = Field("claude-sonnet-4-6", alias="MODEL_EXTRACTION")
    model_classify: str = Field("claude-haiku-4-5", alias="MODEL_CLASSIFY")

    # ── Embeddings (Voyage) ─────────────────────────────────────────
    voyage_api_key: str = Field("", alias="VOYAGE_API_KEY")
    embed_model: str = Field("voyage-3", alias="EMBED_MODEL")
    embed_dim: int = Field(1024, alias="EMBED_DIM")

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
