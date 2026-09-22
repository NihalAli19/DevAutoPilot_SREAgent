"""Tests for the post-merge Reliability Guard (no live GitHub, LLM, or Postgres)."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import agent_framework as af
import pytest

from app.agents.reliability_agent import ReliabilityAgent
from app.config import Settings
from app.models.incident import Incident
from app.models.patch import PatchProposal
from app.models.reliability import (
    MetricComparison,
    PullRequestStatus,
    RolloutHealth,
    TimeWindow,
)
from app.services.llm_router import LLMRouter

ORG = "00000000-0000-0000-0000-000000000001"
INCIDENT_ID = "10000000-0000-0000-0000-000000000001"
PATCH_ID = "30000000-0000-0000-0000-000000000001"
UTC = ZoneInfo("UTC")
START = datetime(2026, 1, 1, tzinfo=UTC)
BASELINE = TimeWindow(start=START, end=START + timedelta(minutes=5))
CURRENT = TimeWindow(start=START + timedelta(minutes=5), end=START + timedelta(minutes=10))


class StubChatClient(af.BaseChatClient):
    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self.calls = 0

    async def _inner_get_response(self, *, messages, stream=False, options=None, **kwargs):
        self.calls += 1
        return af.ChatResponse(messages=[af.Message(role="assistant", contents=[self._content])])


class FakeRepository:
    def __init__(self, pull: PullRequestStatus | None = None) -> None:
        self.pull = pull or PullRequestStatus(
            number=17,
            draft=False,
            merged=True,
            merged_at=BASELINE.end,
            merged_by="human-reviewer",
            merged_by_type="User",
        )
        self.calls: list[int] = []

    async def get_pull_request(self, number: int) -> PullRequestStatus:
        self.calls.append(number)
        return self.pull


class FakeHealthService:
    def __init__(self, health: RolloutHealth) -> None:
        self.health = health
        self.calls: list[dict] = []

    async def compare(self, **kwargs) -> RolloutHealth:
        self.calls.append(kwargs)
        return self.health


class FakeStore:
    def __init__(self) -> None:
        self.merges: list[dict] = []
        self.actions: list[dict] = []

    async def mark_patch_merged(self, **kwargs) -> PatchProposal:
        self.merges.append(kwargs)
        return _patch().model_copy(
            update={
                "status": "merged",
                "approved_by": kwargs["approved_by"],
                "approved_at": kwargs["approved_at"],
            }
        )

    async def insert_agent_action(self, **kwargs) -> None:
        self.actions.append(kwargs)


def _settings() -> Settings:
    return Settings(
        llm_default_provider="gemini",
        llm_cloud_model="gemini-test",
        guard_llm_provider="gemini",
        guard_min_samples=5,
        guard_escalate_regression_ratio=0.2,
        guard_rollback_regression_ratio=0.5,
        guard_min_confidence=0.7,
    )


def _incident() -> Incident:
    return Incident(org_id=ORG, service="checkout", title="Latency regression")


def _patch(**overrides) -> PatchProposal:
    values = {
        "id": PATCH_ID,
        "org_id": ORG,
        "incident_id": INCIDENT_ID,
        "summary": "Increase worker limit",
        "diff": "--- a/app.py\n+++ b/app.py",
        "pr_url": "https://github.test/acme/faulty-app/pull/17",
        "pr_number": 17,
        "branch": "devautopilot/fix",
        "status": "draft",
    }
    values.update(overrides)
    return PatchProposal(**values)


def _health(regression: float, *, sufficient: bool = True) -> RolloutHealth:
    return RolloutHealth(
        service="checkout",
        baseline_window=BASELINE,
        current_window=CURRENT,
        metrics=[
            MetricComparison(
                metric="latency_p95",
                baseline=100.0,
                current=100.0 * (1 + regression),
                baseline_samples=10,
                current_samples=10,
                direction="lower_is_better",
                regression_ratio=regression,
            )
        ],
        minimum_samples=5,
        sufficient_data=sufficient,
    )


def _agent(
    *,
    health: RolloutHealth,
    client: StubChatClient,
    repository: FakeRepository | None = None,
    store: FakeStore | None = None,
) -> tuple[ReliabilityAgent, FakeStore, FakeHealthService]:
    settings = _settings()
    fake_store = store or FakeStore()
    health_service = FakeHealthService(health)
    return (
        ReliabilityAgent(
            repository=repository or FakeRepository(),
            health_service=health_service,
            chat_client=client,
            llm_router=LLMRouter(providers=[], settings=settings),
            store=fake_store,
            settings=settings,
        ),
        fake_store,
        health_service,
    )


@pytest.mark.asyncio
async def test_severe_regression_recommends_human_approved_rollback_without_llm():
    client = StubChatClient("unused")
    agent, store, _ = _agent(health=_health(0.7), client=client)

    result = await agent.assess(
        incident_id=INCIDENT_ID,
        incident=_incident(),
        patch=_patch(),
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    assert result.decision == "rollback"
    assert result.requires_human_approval is True
    assert result.status == "recommendation_only"
    assert result.model is None
    assert client.calls == 0
    assert store.merges[0]["approved_by"] == "human-reviewer"
    assert store.actions[0]["output"]["decision"] == "rollback"


@pytest.mark.asyncio
async def test_insufficient_health_data_escalates_without_llm():
    client = StubChatClient("unused")
    agent, _, _ = _agent(health=_health(0.0, sufficient=False), client=client)

    result = await agent.assess(
        incident_id=INCIDENT_ID,
        incident=_incident(),
        patch=_patch(),
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    assert result.decision == "escalate"
    assert result.requires_human_approval is True
    assert "Insufficient" in result.rationale
    assert client.calls == 0


@pytest.mark.asyncio
async def test_healthy_rollout_uses_llm_and_can_be_approved():
    client = StubChatClient(
        json.dumps(
            {
                "decision": "approve",
                "rationale": "Latency remained within baseline.",
                "confidence": 0.92,
            }
        )
    )
    agent, store, health_service = _agent(health=_health(-0.1), client=client)

    result = await agent.assess(
        incident_id=INCIDENT_ID,
        incident=_incident(),
        patch=_patch(),
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    assert result.decision == "approve"
    assert result.requires_human_approval is False
    assert result.model == "gemini-test"
    assert client.calls == 1
    assert len(health_service.calls) == 1
    assert store.actions[0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_deterministic_regression_overrides_unsafe_llm_approval():
    client = StubChatClient('{"decision":"approve","rationale":"Looks fine","confidence":0.95}')
    agent, _, _ = _agent(health=_health(0.3), client=client)

    result = await agent.assess(
        incident_id=INCIDENT_ID,
        incident=_incident(),
        patch=_patch(),
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    assert result.decision == "escalate"
    assert result.requires_human_approval is True
    assert "despite" in result.rationale


@pytest.mark.asyncio
async def test_unmerged_pull_request_fails_before_health_analysis():
    repository = FakeRepository(PullRequestStatus(number=17, draft=True, merged=False))
    store = FakeStore()
    agent, _, health_service = _agent(
        health=_health(0.0),
        client=StubChatClient("unused"),
        repository=repository,
        store=store,
    )

    with pytest.raises(ValueError, match="human-approved and merged"):
        await agent.assess(
            incident_id=INCIDENT_ID,
            incident=_incident(),
            patch=_patch(),
            baseline_window=BASELINE,
            current_window=CURRENT,
        )

    assert health_service.calls == []
    assert store.merges == []
    assert store.actions[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_bot_merge_is_rejected():
    repository = FakeRepository(
        PullRequestStatus(
            number=17,
            draft=False,
            merged=True,
            merged_at=BASELINE.end,
            merged_by="merge-bot[bot]",
            merged_by_type="Bot",
        )
    )
    agent, store, _ = _agent(
        health=_health(0.0),
        client=StubChatClient("unused"),
        repository=repository,
    )

    with pytest.raises(ValueError, match="not performed by a human"):
        await agent.assess(
            incident_id=INCIDENT_ID,
            incident=_incident(),
            patch=_patch(),
            baseline_window=BASELINE,
            current_window=CURRENT,
        )

    assert store.actions[0]["status"] == "failed"
