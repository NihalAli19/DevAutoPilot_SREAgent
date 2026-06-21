"""LLMRouter — route each agent task to the cheapest capable model.

Local Ollama by default; an OpenAI-compatible cloud provider (OpenAI, or Gemini via
its OpenAI-compatible endpoint) as automatic fallback on error/quota. Providers
implement a tiny ``chat`` protocol so agents and tests can inject any backend and so
no single provider is hardcoded.
"""

# TODO(plan: Phase 3) — per-tenant token/cost budgets + response caching.
from __future__ import annotations

import json
from typing import Protocol

import httpx

from app.config import Settings, get_settings
from app.models.llm import ChatMessage, LLMResult

# Gemini exposes an OpenAI-compatible API; the OpenAI provider can target it.
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class LLMProvider(Protocol):
    """Minimal chat interface every provider implements."""

    name: str

    def chat(
        self, messages: list[ChatMessage], *, model: str, json_mode: bool = False
    ) -> LLMResult: ...


class OllamaProvider:
    """Local Ollama via its REST API (free, private, the default path)."""

    name = "ollama"

    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(
        self, messages: list[ChatMessage], *, model: str, json_mode: bool = False
    ) -> LLMResult:
        payload: dict = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return LLMResult(content=content, model=model, provider=self.name)


class OpenAIProvider:
    """OpenAI-compatible cloud provider (OpenAI or Gemini's compat endpoint)."""

    def __init__(self, api_key: str, base_url: str | None = None, name: str = "openai") -> None:
        self.name = name
        self._api_key = api_key
        self._base_url = base_url

    def chat(
        self, messages: list[ChatMessage], *, model: str, json_mode: bool = False
    ) -> LLMResult:
        from openai import OpenAI  # lazy: keep import optional for Ollama-only setups

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        kwargs: dict = {"model": model, "messages": [m.model_dump() for m in messages]}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return LLMResult(
            content=resp.choices[0].message.content or "", model=model, provider=self.name
        )


class LLMRouter:
    """Tries providers in order (Ollama first, then cloud), returning the first success."""

    def __init__(
        self, providers: list[LLMProvider] | None = None, settings: Settings | None = None
    ) -> None:
        self.settings = settings or get_settings()
        self.providers = providers if providers is not None else self._default_providers()

    def _default_providers(self) -> list[LLMProvider]:
        s = self.settings
        providers: list[LLMProvider] = [OllamaProvider(s.ollama_base_url)]
        if s.openai_api_key:
            providers.append(OpenAIProvider(s.openai_api_key, name="openai"))
        elif s.gemini_api_key:
            providers.append(
                OpenAIProvider(s.gemini_api_key, base_url=GEMINI_OPENAI_BASE_URL, name="gemini")
            )
        return providers

    def _model_for(self, provider_name: str) -> str:
        return (
            self.settings.ollama_model
            if provider_name == "ollama"
            else self.settings.llm_cloud_model
        )

    def complete(self, messages: list[ChatMessage], *, json_mode: bool = False) -> LLMResult:
        """Return the first provider's reply; fall back on failure."""
        errors: list[str] = []
        for provider in self.providers:
            try:
                return provider.chat(
                    messages, model=self._model_for(provider.name), json_mode=json_mode
                )
            except Exception as exc:  # noqa: BLE001 — fall through to the next provider
                errors.append(f"{provider.name}: {exc}")
        raise RuntimeError("all LLM providers failed: " + "; ".join(errors))

    def classify(self, system: str, user: str) -> dict:
        """Run a structured (JSON) classification and parse the result."""
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user),
        ]
        result = self.complete(messages, json_mode=True)
        return json.loads(result.content)

    def chat_client(self):  # noqa: ANN201 — returns an agent_framework chat client
        """Build the agent-framework chat client for the configured default provider.

        This is the entrypoint agents use; ``complete``/``classify`` above remain the
        direct (non-agent) path. Provider is config-driven (``llm_default_provider``).
        """
        s = self.settings
        provider = s.llm_default_provider
        if provider == "ollama":
            from agent_framework.ollama import OllamaChatClient

            return OllamaChatClient(host=s.ollama_base_url, model=s.ollama_model)
        if provider in ("openai", "azure"):
            from agent_framework.openai import OpenAIChatClient

            return OpenAIChatClient(model=s.llm_cloud_model, api_key=s.openai_api_key)
        if provider == "gemini":
            from agent_framework.openai import OpenAIChatClient

            return OpenAIChatClient(
                model=s.llm_cloud_model,
                api_key=s.gemini_api_key,
                base_url=GEMINI_OPENAI_BASE_URL,
            )
        raise ValueError(f"unknown llm_default_provider: {provider!r}")
