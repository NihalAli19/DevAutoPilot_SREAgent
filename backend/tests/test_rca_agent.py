"""Tests for the RAG-grounded RCA Agent (no live Azure, LLM, or Postgres)."""

from datetime import datetime

import agent_framework as af
import pytest

from app.agents.rca_agent import RCAAgent
from app.config import Settings
from app.models.incident import Incident
from app.models.knowledge import KnowledgeChunk
from app.models.root_cause_analysis import RootCauseAnalysis
from app.services.llm_router import LLMRouter

ORG = "00000000-0000-0000-0000-000000000001"
INCIDENT_ID = "10000000-0000-0000-0000-000000000001"


class StubChatClient(af.BaseChatClient):
    """Agent Framework client returning canned RCA output."""

    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self.calls = 0

    async def _inner_get_response(self, *, messages, stream=False, options=None, **kwargs):
        self.calls += 1
        return af.ChatResponse(messages=[af.Message(role="assistant", contents=[self._content])])


class FakeRetriever:
    def __init__(self, chunks: list[KnowledgeChunk] | None = None) -> None:
        self.chunks = chunks or []
        self.queries: list[tuple[str, int]] = []

    async def retrieve(self, query: str, k: int = 3) -> list[KnowledgeChunk]:
        self.queries.append((query, k))
        return self.chunks[:k]


class FakeStore:
    def __init__(self) -> None:
        self.analyses: list[RootCauseAnalysis] = []
        self.actions: list[dict] = []

    async def insert_root_cause_analysis(self, analysis: RootCauseAnalysis) -> RootCauseAnalysis:
        stored = analysis.model_copy(
            update={"id": "20000000-0000-0000-0000-000000000001", "created_at": datetime.now()}
        )
        self.analyses.append(stored)
        return stored

    async def insert_agent_action(self, **kwargs) -> None:
        self.actions.append(kwargs)


def _incident() -> Incident:
    return Incident(
        org_id=ORG,
        service="checkout",
        title="Checkout latency spike",
        description="p95 latency increased after deployment",
        severity="P2",
        type="latency",
        confidence=0.91,
        anomaly_score=0.88,
        source="monitor",
    )


def _router() -> LLMRouter:
    settings = Settings(llm_default_provider="gemini", llm_cloud_model="gemini-test")
    return LLMRouter(providers=[], settings=settings)


@pytest.mark.asyncio
async def test_analyze_retrieves_reasons_persists_and_audits():
    chunks = [
        KnowledgeChunk(
            source="latency-spike.md",
            content="Check connection-pool saturation after deployments.",
            score=0.94,
        )
    ]
    retriever = FakeRetriever(chunks)
    store = FakeStore()
    client = StubChatClient(
        '{"hypothesis": "The deployment exhausted the DB connection pool", '
        '"confidence": 0.82, "affected_files": ["app/db.py"]}'
    )
    agent = RCAAgent(
        rag_service=retriever,
        chat_client=client,
        llm_router=_router(),
        store=store,
        top_k=2,
    )

    analysis = await agent.analyze(INCIDENT_ID, _incident())

    assert retriever.queries == [
        ("checkout | Checkout latency spike | p95 latency increased after deployment | latency", 2)
    ]
    assert client.calls == 1
    assert analysis.id
    assert analysis.hypothesis == "The deployment exhausted the DB connection pool"
    assert analysis.confidence == 0.82
    assert analysis.affected_files == ["app/db.py"]
    assert analysis.evidence[0].source == "latency-spike.md"
    assert analysis.model == "gemini-test"
    assert store.actions[0]["status"] == "succeeded"
    assert store.actions[0]["output"]["rca_id"] == analysis.id


@pytest.mark.asyncio
async def test_invalid_llm_output_fails_closed_and_is_audited():
    store = FakeStore()
    agent = RCAAgent(
        rag_service=FakeRetriever(),
        chat_client=StubChatClient("not-json"),
        llm_router=_router(),
        store=store,
    )

    with pytest.raises(ValueError, match="invalid structured output"):
        await agent.analyze(INCIDENT_ID, _incident())

    assert store.analyses == []
    assert store.actions == [
        {
            "org_id": ORG,
            "incident_id": INCIDENT_ID,
            "agent_name": "rca",
            "action": "analyze",
            "status": "failed",
            "output": {"error_type": "ValueError"},
        }
    ]


@pytest.mark.asyncio
async def test_out_of_range_confidence_is_rejected():
    store = FakeStore()
    client = StubChatClient('{"hypothesis": "Guess", "confidence": 1.5, "affected_files": []}')
    agent = RCAAgent(
        rag_service=FakeRetriever(),
        chat_client=client,
        llm_router=_router(),
        store=store,
    )

    with pytest.raises(ValueError, match="invalid structured output"):
        await agent.analyze(INCIDENT_ID, _incident())

    assert store.analyses == []
    assert store.actions[0]["status"] == "failed"
