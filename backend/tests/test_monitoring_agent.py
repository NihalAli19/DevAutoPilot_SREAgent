"""Tests for the Monitoring Agent (ML-gates-LLM) — no live LLM, no real model."""

import agent_framework as af
import pytest

from app.agents.monitoring_agent import MonitoringAgent


class StubChatClient(af.BaseChatClient):
    """Agent-framework chat client returning canned content; counts invocations."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self.calls = 0

    async def _inner_get_response(self, *, messages, stream=False, options=None, **kwargs):
        self.calls += 1
        return af.ChatResponse(messages=[af.Message(role="assistant", contents=[self._content])])


class FakeScorer:
    """Returns canned scored points (stands in for AnomalyService)."""

    def __init__(self, scored):
        self._scored = scored

    def score_points(self, points):
        return {"model_name": "isolation_forest", "feature_version": "v1", "scored": self._scored}


def _pt(score: float, is_anomaly: bool) -> dict:
    return {
        "timestamp": "2024-01-01T00:00:00",
        "value": 50.0,
        "anomaly_score": score,
        "is_anomaly": is_anomaly,
    }


_INPUT = [{"timestamp": "2024-01-01T00:00:00", "value": 50.0}]


@pytest.mark.asyncio
async def test_anomaly_produces_classified_incident():
    scorer = FakeScorer([_pt(0.2, False), _pt(0.9, True)])
    client = StubChatClient(
        '{"severity": "P1", "type": "latency", "title": "Latency spike", '
        '"summary": "p95 elevated", "confidence": 0.92}'
    )
    agent = MonitoringAgent(anomaly_service=scorer, chat_client=client, org_id="org1")

    incident = await agent.process("checkout", "latency_p95", _INPUT)

    assert incident is not None
    assert incident.org_id == "org1"
    assert incident.severity == "P1"
    assert incident.type == "latency"
    assert incident.confidence == 0.92
    assert incident.anomaly_score == 0.9  # peak of the anomalous points
    assert incident.source == "monitor"
    assert client.calls == 1


@pytest.mark.asyncio
async def test_no_anomaly_skips_llm_and_returns_none():
    scorer = FakeScorer([_pt(-0.5, False), _pt(0.1, False)])
    client = StubChatClient('{"severity": "P1"}')
    agent = MonitoringAgent(anomaly_service=scorer, chat_client=client)

    incident = await agent.process("checkout", "latency_p95", _INPUT)

    assert incident is None
    assert client.calls == 0  # ML gate: no anomaly -> LLM is never invoked


@pytest.mark.asyncio
async def test_unparseable_classification_falls_back_to_defaults():
    scorer = FakeScorer([_pt(0.9, True)])
    client = StubChatClient("not json at all")
    agent = MonitoringAgent(anomaly_service=scorer, chat_client=client)

    incident = await agent.process("svc", "metric", _INPUT)

    assert incident is not None
    assert incident.severity == "P4"  # safe default
    assert incident.title  # synthesized title
