"""Tests for the LLMRouter: routing, fallback, and structured output (no network)."""

import pytest

from app.models.llm import ChatMessage, LLMResult
from app.services.llm_router import LLMRouter


class FakeProvider:
    """In-memory provider for tests — records calls, optionally fails."""

    def __init__(self, name="fake", fail=False, content='{"severity": "P2"}'):
        self.name = name
        self.fail = fail
        self.content = content
        self.models: list[str] = []

    def chat(self, messages, *, model, json_mode=False):
        self.models.append(model)
        if self.fail:
            raise RuntimeError("provider down")
        return LLMResult(content=self.content, model=model, provider=self.name)


def _msgs():
    return [ChatMessage(role="user", content="hi")]


def test_uses_first_provider():
    p = FakeProvider(name="ollama")
    res = LLMRouter(providers=[p]).complete(_msgs())
    assert res.provider == "ollama"
    assert p.models  # provider was called


def test_falls_back_when_primary_fails():
    primary = FakeProvider(name="ollama", fail=True)
    fallback = FakeProvider(name="openai", content='{"ok": true}')
    res = LLMRouter(providers=[primary, fallback]).complete(_msgs())
    assert res.provider == "openai"


def test_raises_when_all_providers_fail():
    router = LLMRouter(providers=[FakeProvider(fail=True), FakeProvider(name="openai", fail=True)])
    with pytest.raises(RuntimeError, match="all LLM providers failed"):
        router.complete(_msgs())


def test_classify_parses_json():
    p = FakeProvider(content='{"severity": "P1", "type": "latency"}')
    out = LLMRouter(providers=[p]).classify("system prompt", "user prompt")
    assert out == {"severity": "P1", "type": "latency"}


def test_routes_correct_model_per_provider():
    ollama = FakeProvider(name="ollama")
    router = LLMRouter(providers=[ollama])
    router.complete(_msgs())
    assert ollama.models[0] == router.settings.ollama_model

    cloud = FakeProvider(name="openai")
    router2 = LLMRouter(providers=[cloud])
    router2.complete(_msgs())
    assert cloud.models[0] == router2.settings.llm_cloud_model


def test_default_providers_lead_with_ollama():
    # With no cloud key set (CI default), only Ollama is wired; it's always first.
    router = LLMRouter()
    assert router.providers[0].name == "ollama"
