"""Tests for the allowlisted GitHub REST client (no live GitHub calls)."""

import base64

import httpx
import pytest

from app.config import Settings
from app.models.patch import PatchEdit
from app.services.github_service import GitHubService


def _settings(**overrides) -> Settings:
    values = {
        "github_token": "test-token",
        "github_repository": "acme/faulty-app",
        "github_base_branch": "main",
        "github_api_url": "https://api.github.test",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_get_file_decodes_utf8_content_from_allowlisted_repository():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/acme/faulty-app/contents/app/main.py"
        assert request.url.params["ref"] == "main"
        assert request.headers["authorization"] == "Bearer test-token"
        content = base64.b64encode(b"print('hello')\n").decode()
        return httpx.Response(
            200,
            json={
                "type": "file",
                "encoding": "base64",
                "size": 15,
                "sha": "blob1",
                "content": content,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    ) as client:
        service = GitHubService(_settings(), client=client)
        file = await service.get_file("app/main.py")

    assert file.path == "app/main.py"
    assert file.content == "print('hello')\n"
    assert file.sha == "blob1"


@pytest.mark.asyncio
async def test_create_pull_request_uses_atomic_commit_and_forces_draft():
    requests: list[tuple[str, str, dict | None]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = None if request.method == "GET" else __import__("json").loads(request.content)
        requests.append((request.method, request.url.path, body))
        responses = {
            ("GET", "/repos/acme/faulty-app/git/ref/heads/main"): {"object": {"sha": "parent1"}},
            ("GET", "/repos/acme/faulty-app/contents/app/main.py"): {
                "type": "file",
                "sha": "blob1",
            },
            ("GET", "/repos/acme/faulty-app/git/commits/parent1"): {"tree": {"sha": "tree1"}},
            ("POST", "/repos/acme/faulty-app/git/trees"): {"sha": "tree2"},
            ("POST", "/repos/acme/faulty-app/git/commits"): {"sha": "commit2"},
            ("POST", "/repos/acme/faulty-app/git/refs"): {"ref": "refs/heads/fix/one"},
            ("POST", "/repos/acme/faulty-app/pulls"): {
                "number": 12,
                "html_url": "https://github.test/acme/faulty-app/pull/12",
                "draft": True,
            },
        }
        return httpx.Response(200, json=responses[(request.method, request.url.path)])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    ) as client:
        service = GitHubService(_settings(), client=client)
        draft = await service.create_draft_pull_request(
            branch="fix/one",
            title="Fix one",
            body="Human approval required",
            edits=[PatchEdit(path="app/main.py", content="print('fixed')\n", source_sha="blob1")],
            commit_message="fix: one",
        )

    assert draft.number == 12
    assert draft.branch == "fix/one"
    assert requests[1][0:2] == (
        "GET",
        "/repos/acme/faulty-app/contents/app/main.py",
    )
    tree_body = requests[3][2]
    assert tree_body == {
        "base_tree": "tree1",
        "tree": [
            {
                "path": "app/main.py",
                "mode": "100644",
                "type": "blob",
                "content": "print('fixed')\n",
            }
        ],
    }
    assert requests[4][2] == {
        "message": "fix: one",
        "tree": "tree2",
        "parents": ["parent1"],
    }
    assert requests[5][2] == {"ref": "refs/heads/fix/one", "sha": "commit2"}
    assert requests[6][2]["draft"] is True
    assert requests[6][2]["base"] == "main"


@pytest.mark.asyncio
async def test_create_pull_request_rejects_a_file_changed_after_analysis():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "parent2"}})
        if request.url.path.endswith("/contents/app/main.py"):
            return httpx.Response(200, json={"type": "file", "sha": "new-blob"})
        raise AssertionError("no GitHub write should occur after the stale-file check")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    ) as client:
        service = GitHubService(_settings(), client=client)
        with pytest.raises(RuntimeError, match="changed after it was analyzed"):
            await service.create_draft_pull_request(
                branch="fix/stale",
                title="Stale",
                body="Draft",
                edits=[
                    PatchEdit(path="app/main.py", content="print('fixed')\n", source_sha="old-blob")
                ],
                commit_message="fix: stale",
            )


def test_service_requires_token_and_explicit_repository_allowlist():
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        GitHubService(_settings(github_token=None))
    with pytest.raises(RuntimeError, match="owner/repository"):
        GitHubService(_settings(github_repository="not-a-repository"))
    with pytest.raises(RuntimeError, match="safe Git branch"):
        GitHubService(_settings(github_base_branch="../main"))


@pytest.mark.asyncio
async def test_get_file_rejects_unsafe_path_before_network_access():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe paths must not reach GitHub")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    ) as client:
        service = GitHubService(_settings(), client=client)
        with pytest.raises(ValueError, match="unsafe repository path"):
            await service.get_file("../secret.py")


@pytest.mark.asyncio
async def test_get_pull_request_returns_authoritative_merge_evidence():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/acme/faulty-app/pulls/17"
        return httpx.Response(
            200,
            json={
                "number": 17,
                "draft": False,
                "merged": True,
                "merged_at": "2026-01-01T12:00:00Z",
                "merged_by": {"login": "reviewer", "type": "User"},
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.test"
    ) as client:
        service = GitHubService(_settings(), client=client)
        pull = await service.get_pull_request(17)

    assert pull.merged is True
    assert pull.draft is False
    assert pull.merged_by == "reviewer"
    assert pull.merged_by_type == "User"
    assert pull.merged_at is not None
