"""Application configuration via pydantic-settings (reads .env, no hardcoded secrets)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings loaded from environment / .env. All secrets are optional here
    so the app boots in dev without a fully-populated environment."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- App ----
    app_name: str = "DevAutoPilot v2"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    # ---- LLM providers ----
    openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    gemini_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # ---- Data layer ----
    database_url: str = "postgresql+asyncpg://devautopilot:devautopilot@localhost:5432/devautopilot"

    # ---- Azure AI Search (RAG vector store) ----
    azure_search_endpoint: str | None = None
    azure_search_key: str | None = None

    # ---- GitHub ----
    github_token: str | None = None

    # ---- Anomaly model serving ----
    # Path to the joblib serving artifact; defaults to ml/models/isolation_forest.joblib.
    anomaly_model_path: str | None = None

    # ---- LLM routing ----
    # Local Ollama is the default; cloud (OpenAI/Gemini) is the fallback.
    ollama_model: str = "llama3.1"
    llm_cloud_model: str = "gpt-5-mini"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used across the app."""
    return Settings()
