"""Least-privilege GitHub client for source reads and draft pull requests."""

from __future__ import annotations

import base64
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings
from app.models.patch import DraftPullRequest, PatchEdit, RepositoryFile
from app.models.reliability import PullRequestStatus

_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
_MAX_SOURCE_BYTES = 100_000


class GitHubService:
    """Use GitHub's Git Data API against one explicitly configured repository."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        repository = self.settings.github_repository
        if not self.settings.github_token:
            raise RuntimeError("GITHUB_TOKEN is required for GitHub operations")
        if not repository or not _REPOSITORY_PATTERN.fullmatch(repository):
            raise RuntimeError("GITHUB_REPOSITORY must use owner/repository format")
        _validate_branch(self.settings.github_base_branch, setting="GITHUB_BASE_BRANCH")

        self.repository = repository
        self.base_branch = self.settings.github_base_branch
        self._client = client
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.settings.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_file(self, path: str) -> RepositoryFile:
        """Fetch one UTF-8 file from the configured base branch."""
        _validate_repo_path(path)
        encoded_path = quote(path, safe="/")
        data = await self._request(
            "GET",
            f"/repos/{self.repository}/contents/{encoded_path}",
            params={"ref": self.base_branch},
        )
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise ValueError(f"GitHub path is not a base64-encoded file: {path}")
        if int(data.get("size", 0)) > _MAX_SOURCE_BYTES:
            raise ValueError(f"GitHub file exceeds {_MAX_SOURCE_BYTES} bytes: {path}")

        try:
            encoded = "".join(str(data["content"]).split())
            decoded = base64.b64decode(encoded, validate=True)
            if len(decoded) > _MAX_SOURCE_BYTES:
                raise ValueError("decoded file exceeds the source size limit")
            content = decoded.decode("utf-8")
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f"GitHub file is not valid UTF-8 text: {path}") from exc
        return RepositoryFile(path=path, content=content, sha=str(data["sha"]))

    async def create_draft_pull_request(
        self,
        *,
        branch: str,
        title: str,
        body: str,
        edits: list[PatchEdit],
        commit_message: str,
    ) -> DraftPullRequest:
        """Atomically commit validated edits, create a branch, and open a draft PR."""
        if not edits:
            raise ValueError("at least one edit is required")
        _validate_branch(branch, setting="branch")
        for edit in edits:
            _validate_repo_path(edit.path)

        encoded_base = quote(self.base_branch, safe="/")
        ref = await self._request("GET", f"/repos/{self.repository}/git/ref/heads/{encoded_base}")
        parent_sha = str(ref["object"]["sha"])
        for edit in edits:
            current = await self._request(
                "GET",
                f"/repos/{self.repository}/contents/{quote(edit.path, safe='/')}",
                params={"ref": parent_sha},
            )
            if current.get("type") != "file" or current.get("sha") != edit.source_sha:
                raise RuntimeError(f"target file changed after it was analyzed: {edit.path}")
        parent = await self._request("GET", f"/repos/{self.repository}/git/commits/{parent_sha}")
        base_tree_sha = str(parent["tree"]["sha"])

        tree = await self._request(
            "POST",
            f"/repos/{self.repository}/git/trees",
            json={
                "base_tree": base_tree_sha,
                "tree": [
                    {
                        "path": edit.path,
                        "mode": "100644",
                        "type": "blob",
                        "content": edit.content,
                    }
                    for edit in edits
                ],
            },
        )
        commit = await self._request(
            "POST",
            f"/repos/{self.repository}/git/commits",
            json={
                "message": commit_message,
                "tree": str(tree["sha"]),
                "parents": [parent_sha],
            },
        )
        commit_sha = str(commit["sha"])
        await self._request(
            "POST",
            f"/repos/{self.repository}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": commit_sha},
        )
        pull = await self._request(
            "POST",
            f"/repos/{self.repository}/pulls",
            json={
                "title": title,
                "body": body,
                "head": branch,
                "base": self.base_branch,
                "draft": True,
            },
        )
        if pull.get("draft") is not True:
            raise RuntimeError("GitHub did not confirm that the pull request is a draft")
        return DraftPullRequest(
            number=int(pull["number"]),
            url=str(pull["html_url"]),
            branch=branch,
        )

    async def get_pull_request(self, number: int) -> PullRequestStatus:
        """Read GitHub's authoritative merge state for one target-repository PR."""
        if number < 1:
            raise ValueError("pull request number must be positive")
        pull = await self._request("GET", f"/repos/{self.repository}/pulls/{number}")
        merged_by = pull.get("merged_by")
        if merged_by is not None and not isinstance(merged_by, dict):
            raise ValueError("GitHub returned invalid merged-by metadata")
        return PullRequestStatus(
            number=int(pull["number"]),
            draft=bool(pull["draft"]),
            merged=bool(pull["merged"]),
            merged_at=pull.get("merged_at"),
            merged_by=str(merged_by["login"]) if merged_by else None,
            merged_by_type=str(merged_by["type"]) if merged_by else None,
        )

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._client is not None:
            response = await self._client.request(method, path, headers=self._headers, **kwargs)
        else:
            async with httpx.AsyncClient(
                base_url=self.settings.github_api_url.rstrip("/"), timeout=30.0
            ) as client:
                response = await client.request(method, path, headers=self._headers, **kwargs)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("GitHub API returned an unexpected response")
        return data


def _validate_repo_path(path: str) -> None:
    parts = path.split("/")
    if (
        not path
        or path.startswith("/")
        or "\\" in path
        or any(part in {"", ".", ".."} for part in parts)
        or parts[0] == ".git"
    ):
        raise ValueError(f"unsafe repository path: {path!r}")


def _validate_branch(branch: str, *, setting: str) -> None:
    if (
        not _BRANCH_PATTERN.fullmatch(branch)
        or ".." in branch
        or "//" in branch
        or branch.endswith(("/", ".", ".lock"))
    ):
        raise RuntimeError(f"{setting} is not a safe Git branch name")
