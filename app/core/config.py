"""
Application configuration via Pydantic Settings.

All configuration comes from environment variables / .env file.
No secrets are hardcoded.
"""

import os
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_sqlite_url() -> str:
    """Return a local SQLite database path for demo and offline development."""
    backend_dir = Path(__file__).resolve().parents[1]
    return f"sqlite:///{(backend_dir / 'sih_local.db').as_posix()}"


def _resolve_database_url(candidate: str) -> str:
    """Prefer PostgreSQL when available; otherwise fall back to SQLite for local demo runs."""
    if not candidate:
        return _default_sqlite_url()
    if candidate.startswith("sqlite"):
        return candidate

    if not candidate.lower().startswith(("postgresql://", "postgresql+psycopg://", "postgresql+psycopg2://")):
        return candidate

    if os.getenv("SIH_FORCE_SQLITE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return _default_sqlite_url()

    try:
        import psycopg
        with psycopg.connect(candidate, connect_timeout=1, autocommit=True):
            return candidate
    except Exception:
        return _default_sqlite_url()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Application ---
    app_env: str = "development"
    app_debug: bool = False

    # --- Database ---
    database_url: str = Field(default_factory=_default_sqlite_url)

    @model_validator(mode="after")
    def _normalize_database_url(self) -> "Settings":
        self.database_url = _resolve_database_url(self.database_url)
        return self

    # --- API ---
    api_v1_prefix: str = "/api/v1"

    # --- Security ---
    reviewer_tokens_raw: str | None = Field(
        default=None,
        validation_alias=AliasChoices("REVIEWER_TOKENS", "reviewer_tokens"),
    )
    reviewer_token: str | None = Field(
        default="mvp-secret-token",
        validation_alias=AliasChoices("REVIEWER_TOKEN", "reviewer_token"),
    )

    @staticmethod
    def _parse_reviewer_tokens(*token_sources: str | None) -> list[str]:
        tokens: list[str] = []
        for token_source in token_sources:
            if not token_source:
                continue
            for token in token_source.split(","):
                cleaned = token.strip()
                if cleaned:
                    tokens.append(cleaned)

        unique_tokens: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token not in seen:
                seen.add(token)
                unique_tokens.append(token)
        return unique_tokens

    @property
    def reviewer_tokens(self) -> list[str]:
        return self._parse_reviewer_tokens(self.reviewer_tokens_raw, self.reviewer_token)

    # --- CORS ---
    # Comma-separated string in env; parsed into a list.
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # --- AI & Material Intelligence ---
    ai_enabled: bool = True
    ai_hybrid_retrieval_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AI_HYBRID_RETRIEVAL_ENABLED", "ai_hybrid_retrieval_enabled"),
    )
    ai_semantic_reranking_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("AI_SEMANTIC_RERANKING_ENABLED", "ai_semantic_reranking_enabled"),
    )
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_dimension: int = 384
    candidate_retrieval_top_k: int = 15
    candidate_similarity_threshold: float = 0.50

    @property
    def AI_HYBRID_RETRIEVAL_ENABLED(self) -> bool:
        return self.ai_hybrid_retrieval_enabled

    @property
    def AI_SEMANTIC_RERANKING_ENABLED(self) -> bool:
        return self.ai_semantic_reranking_enabled


settings = Settings()
