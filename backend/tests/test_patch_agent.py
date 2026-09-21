"""Tests for safe Patch Agent generation (no live GitHub, LLM, or Postgres)."""

import json
from datetime import datetime

import agent_framework as af
import pytest

from app.agents.patch_agent import PatchAgent
from app.config import Settings
from app.models.incident import Incident
from app.models.patch import DraftPullRequest, PatchProposal, RepositoryFile
from app.models.root_cause_analysis import RootCauseAnalysis
from app.services.llm_router import LLMRouter

ORG = "00000000-0000-0000-0000-000000000001"
INCIDENT_ID = "10000000-0000-0000-0000-000000000001"
RCA_ID = "20000000-0000-0000-0000-000000000001"


class StubChatClient(af.BaseChatClient):
    def __init__(self, content: str) -> None:
        super().__init__()
        self._content = content
        self.calls = 0

    async def _inner_get_response(self, *, messages, stream=False, options=None, **kwargs):
        self.calls += 1
        return af.ChatResponse(messages=[af.Message(role="assistant", contents=[self._content])])


class FakeRepository:
    def __init__(self) -> None:
        self.files = {
            "app/main.py": RepositoryFile(path="app/main.py", content="TIMEOUT = 1\n", sha="blob1")
        }
        self.fetched: list[str] = []
        self.drafts: list[dict] = []

    async def get_file(self, path: str) -> RepositoryFile:
        self.fetched.append(path)
        return self.files[path]

    async def create_draft_pull_request(self, **kwargs) -> DraftPullRequest:
        self.drafts.append(kwargs)
        return DraftPullRequest(
            number=17,
            url="https://github.test/acme/faulty-app/pull/17",
            branch=kwargs["branch"],
        )


class FakeStore:
    def __init__(self) -> None:
        self.patches: list[PatchProposal] = []
        self.actions: list[dict] = []

    async def insert_patch(self, patch: PatchProposal) -> PatchProposal:
        stored = patch.model_copy(
            update={"id": "30000000-0000-0000-0000-000000000001", "created_at": datetime.now()}
        )
        self.patches.append(stored)
        return stored

    async def insert_agent_action(self, **kwargs) -> None:
        self.actions.append(kwargs)


def _incident() -> Incident:
    return Incident(
        org_id=ORG,
        service="checkout",
        title="Checkout requests time out",
        description="Timeouts began after a configuration regression",
        severity="P2",
        type="latency",
    )


def _rca(**overrides) -> RootCauseAnalysis:
    values = {
        "id": RCA_ID,
        "org_id": ORG,
        "incident_id": INCIDENT_ID,
        "hypothesis": "The timeout constant is too low",
        "confidence": 0.91,
        "affected_files": ["app/main.py"],
    }
    values.update(overrides)
    return RootCauseAnalysis(**values)


def _router() -> LLMRouter:
    settings = Settings(llm_default_provider="gemini", llm_cloud_model="gemini-test")
    return LLMRouter(providers=[], settings=settings)


def _client(summary: str, path: str, content: str) -> StubChatClient:
    return StubChatClient(
        json.dumps({"summary": summary, "edits": [{"path": path, "content": content}]})
    )


@pytest.mark.asyncio
async def test_propose_validates_persists_and_opens_only_a_draft_pr():
    repository = FakeRepository()
    store = FakeStore()
    agent = PatchAgent(
        repository=repository,
        chat_client=_client("increase the timeout", "app/main.py", "TIMEOUT = 10\n"),
        llm_router=_router(),
        store=store,
    )

    proposal = await agent.propose(INCIDENT_ID, _incident(), _rca())

    assert repository.fetched == ["app/main.py"]
    assert len(repository.drafts) == 1
    assert repository.drafts[0]["edits"][0].content == "TIMEOUT = 10\n"
    assert "Human review and explicit approval are required" in repository.drafts[0]["body"]
    assert proposal.status == "draft"
    assert proposal.pr_number == 17
    assert proposal.model == "gemini-test"
    assert "-TIMEOUT = 1" in proposal.diff
    assert "+TIMEOUT = 10" in proposal.diff
    assert store.actions[0]["output"]["draft"] is True


@pytest.mark.asyncio
async def test_edit_outside_rca_allowlist_fails_before_github_write():
    repository = FakeRepository()
    store = FakeStore()
    agent = PatchAgent(
        repository=repository,
        chat_client=_client("unsafe", "app/other.py", "VALUE = 1\n"),
        llm_router=_router(),
        store=store,
    )

    with pytest.raises(ValueError, match="outside the RCA allowlist"):
        await agent.propose(INCIDENT_ID, _incident(), _rca())

    assert repository.drafts == []
    assert store.patches == []
    assert store.actions[0]["status"] == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "error"),
    [
        ("def broken(:\n", "syntax validation"),
        ('API_KEY = "sk-abcdefghijklmnopqrstuvwxyz"\n', "credential or private key"),
    ],
)
async def test_invalid_or_secret_bearing_code_fails_closed(content: str, error: str):
    repository = FakeRepository()
    store = FakeStore()
    agent = PatchAgent(
        repository=repository,
        chat_client=_client("bad patch", "app/main.py", content),
        llm_router=_router(),
        store=store,
    )

    with pytest.raises(ValueError, match=error):
        await agent.propose(INCIDENT_ID, _incident(), _rca())

    assert repository.drafts == []
    assert store.actions[0]["status"] == "failed"


@pytest.mark.asyncio
async def test_unsafe_rca_path_fails_before_file_fetch_or_llm_call():
    repository = FakeRepository()
    store = FakeStore()
    client = _client("unused", "app/main.py", "TIMEOUT = 10\n")
    agent = PatchAgent(
        repository=repository,
        chat_client=client,
        llm_router=_router(),
        store=store,
    )

    with pytest.raises(ValueError, match="unsafe repository path"):
        await agent.propose(INCIDENT_ID, _incident(), _rca(affected_files=["../main.py"]))

    assert repository.fetched == []
    assert client.calls == 0
    assert store.actions[0]["status"] == "failed"
