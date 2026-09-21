"""Patch Agent: validate minimal edits and open a human-reviewed draft PR."""

from __future__ import annotations

import ast
import difflib
import json
import re
from pathlib import PurePosixPath
from typing import Any, Protocol
from uuid import uuid4

from agent_framework import Agent
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models.incident import Incident
from app.models.patch import DraftPullRequest, PatchEdit, PatchProposal, RepositoryFile
from app.models.root_cause_analysis import RootCauseAnalysis
from app.services import db_service
from app.services.github_service import GitHubService
from app.services.llm_router import LLMRouter
from app.utils.prompts import PATCH_INSTRUCTIONS, build_patch_prompt
from app.utils.telemetry import agent_step_span, record_llm_usage

_MAX_FILES = 3
_MAX_FILE_BYTES = 100_000
_MAX_CHANGED_LINES = 200
_MAX_DIFF_BYTES = 32_000
_SUPPORTED_SUFFIXES = {".py", ".json"}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|secret|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
)


class PatchRepository(Protocol):
    """GitHub operations the Patch Agent is allowed to invoke."""

    async def get_file(self, path: str) -> RepositoryFile: ...

    async def create_draft_pull_request(
        self,
        *,
        branch: str,
        title: str,
        body: str,
        edits: list[PatchEdit],
        commit_message: str,
    ) -> DraftPullRequest: ...


class PatchStore(Protocol):
    """Persistence surface consumed by the Patch Agent."""

    async def insert_patch(self, patch: PatchProposal) -> PatchProposal: ...

    async def insert_agent_action(
        self,
        *,
        org_id: str,
        agent_name: str,
        action: str,
        incident_id: str | None = None,
        status: str = "succeeded",
        output: dict[str, Any] | None = None,
    ) -> None: ...


class _RequestedEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    content: str


class _PatchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=160)
    edits: list[_RequestedEdit] = Field(min_length=1, max_length=_MAX_FILES)


class PatchAgent:
    """Turn an evidence-grounded RCA into a validated draft pull request."""

    def __init__(
        self,
        *,
        repository: PatchRepository | None = None,
        chat_client: Any | None = None,
        llm_router: LLMRouter | None = None,
        store: PatchStore | None = None,
    ) -> None:
        self.repository = repository or GitHubService()
        self._chat_client = chat_client
        self.router = llm_router or LLMRouter()
        self.store = store or db_service

    def _agent(self) -> Agent:
        client = self._chat_client or self.router.chat_client()
        return Agent(client, instructions=PATCH_INSTRUCTIONS, name="patch")

    def _model_name(self) -> str:
        settings = self.router.settings
        if settings.llm_default_provider == "ollama":
            return settings.ollama_model
        if settings.llm_default_provider == "azure":
            return settings.azure_openai_deployment or settings.llm_cloud_model
        return settings.llm_cloud_model

    async def propose(
        self,
        incident_id: str,
        incident: Incident,
        rca: RootCauseAnalysis,
    ) -> PatchProposal:
        """Fetch allowlisted files, validate generated edits, and open a draft PR."""
        try:
            paths = _validate_rca_scope(incident_id, incident, rca)
            with agent_step_span("patch", "github.fetch_files") as span:
                files = [await self.repository.get_file(path) for path in paths]
                span.set_attribute("github.file_count", len(files))

            with agent_step_span("patch", "llm.generate") as span:
                response = await self._agent().run(
                    build_patch_prompt(incident_id, incident, rca, files)
                )
                record_llm_usage(span, response)
                requested = _parse_patch(response.text)

            edits, diff = _validate_patch(files, requested)
            branch = f"devautopilot/incident-{incident_id[:8]}-{uuid4().hex[:8]}"
            service_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", incident.service).strip("-")
            service_label = service_label[:40] or "service"
            with agent_step_span("patch", "github.create_draft_pr") as span:
                draft = await self.repository.create_draft_pull_request(
                    branch=branch,
                    title=f"fix({service_label}): {requested.summary}",
                    body=_pull_request_body(incident_id, rca, requested.summary),
                    edits=edits,
                    commit_message=f"fix: {requested.summary}",
                )
                span.set_attribute("github.pr_number", draft.number)
                span.set_attribute("github.pr_draft", True)

            proposal = PatchProposal(
                org_id=incident.org_id,
                incident_id=incident_id,
                rca_id=rca.id,
                summary=requested.summary.strip(),
                diff=diff,
                pr_url=draft.url,
                pr_number=draft.number,
                branch=draft.branch,
                status="draft",
                model=self._model_name(),
            )
            with agent_step_span("patch", "postgres.persist"):
                stored = await self.store.insert_patch(proposal)
                await self.store.insert_agent_action(
                    org_id=incident.org_id,
                    incident_id=incident_id,
                    agent_name="patch",
                    action="propose",
                    status="succeeded",
                    output={
                        "patch_id": stored.id,
                        "pr_number": stored.pr_number,
                        "file_count": len(edits),
                        "draft": True,
                    },
                )
            return stored
        except Exception as exc:
            await self._audit_failure(incident, incident_id, exc)
            raise

    async def _audit_failure(self, incident: Incident, incident_id: str, error: Exception) -> None:
        try:
            await self.store.insert_agent_action(
                org_id=incident.org_id,
                incident_id=incident_id,
                agent_name="patch",
                action="propose",
                status="failed",
                output={"error_type": type(error).__name__},
            )
        except Exception:  # noqa: BLE001 - preserve the original patch failure
            return


def _validate_rca_scope(incident_id: str, incident: Incident, rca: RootCauseAnalysis) -> list[str]:
    if rca.org_id != incident.org_id or rca.incident_id != incident_id:
        raise ValueError("RCA does not belong to this incident and tenant")
    if not rca.id:
        raise ValueError("RCA must be persisted before patch generation")
    if not rca.affected_files:
        raise ValueError("RCA did not identify any affected files")
    if len(rca.affected_files) > _MAX_FILES:
        raise ValueError(f"RCA exceeds the {_MAX_FILES}-file patch limit")

    paths = [_validate_path(path) for path in rca.affected_files]
    if len(paths) != len(set(paths)):
        raise ValueError("RCA contains duplicate affected files")
    return paths


def _validate_path(path: str) -> str:
    if not path or "\\" in path or path.startswith("/"):
        raise ValueError(f"unsafe repository path: {path!r}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts) or parts[0] == ".git":
        raise ValueError(f"unsafe repository path: {path!r}")
    normalized = str(PurePosixPath(path))
    if PurePosixPath(normalized).suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported file type for syntax validation: {path}")
    return normalized


def _parse_patch(text: str) -> _PatchOutput:
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("patch response must be a JSON object")
        parsed = _PatchOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ValueError("Patch Agent returned invalid structured output") from exc
    summary = parsed.summary.strip()
    if not summary or "\n" in summary or "\r" in summary:
        raise ValueError("patch summary must be a non-blank single line")
    return parsed.model_copy(update={"summary": summary})


def _validate_patch(
    files: list[RepositoryFile], requested: _PatchOutput
) -> tuple[list[PatchEdit], str]:
    originals = {item.path: item for item in files}
    edits: list[PatchEdit] = []
    diffs: list[str] = []
    seen: set[str] = set()

    for requested_edit in requested.edits:
        path = _validate_path(requested_edit.path)
        if path not in originals:
            raise ValueError(f"Patch Agent edited a file outside the RCA allowlist: {path}")
        if path in seen:
            raise ValueError(f"Patch Agent returned a duplicate edit: {path}")
        seen.add(path)
        original = originals[path]
        if requested_edit.content == original.content:
            raise ValueError(f"Patch Agent returned an unchanged file: {path}")
        if len(requested_edit.content.encode("utf-8")) > _MAX_FILE_BYTES:
            raise ValueError(f"generated file exceeds {_MAX_FILE_BYTES} bytes: {path}")
        _validate_syntax(path, requested_edit.content)

        diff = "\n".join(
            difflib.unified_diff(
                original.content.splitlines(),
                requested_edit.content.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        _reject_secrets(diff)
        diffs.append(diff)
        edits.append(PatchEdit(path=path, content=requested_edit.content, source_sha=original.sha))

    combined = "\n".join(diffs)
    changed_lines = sum(
        1
        for line in combined.splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    if changed_lines > _MAX_CHANGED_LINES:
        raise ValueError(f"patch exceeds the {_MAX_CHANGED_LINES}-line change limit")
    if len(combined.encode("utf-8")) > _MAX_DIFF_BYTES:
        raise ValueError(f"patch diff exceeds {_MAX_DIFF_BYTES} bytes")
    return edits, combined


def _validate_syntax(path: str, content: str) -> None:
    suffix = PurePosixPath(path).suffix.lower()
    try:
        if suffix == ".py":
            ast.parse(content, filename=path)
        elif suffix == ".json":
            json.loads(content)
        else:  # Defensive: _validate_path rejects all unsupported suffixes.
            raise ValueError(f"unsupported file type for syntax validation: {path}")
    except (SyntaxError, json.JSONDecodeError) as exc:
        raise ValueError(f"generated content failed syntax validation: {path}") from exc


def _reject_secrets(diff: str) -> None:
    added = "\n".join(
        line[1:]
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    if any(pattern.search(added) for pattern in _SECRET_PATTERNS):
        raise ValueError("generated patch appears to contain a credential or private key")


def _pull_request_body(
    incident_id: str,
    rca: RootCauseAnalysis,
    summary: str,
) -> str:
    hypothesis = rca.hypothesis[:2_000].replace("@", "@\u200b")
    safe_summary = summary.strip().replace("@", "@\u200b")
    return (
        "## DevAutoPilot proposal\n\n"
        f"- Incident: `{incident_id}`\n"
        f"- RCA: `{rca.id}`\n"
        f"- RCA confidence: `{rca.confidence:.2f}`\n\n"
        f"**Root cause:** {hypothesis}\n\n"
        f"**Proposed fix:** {safe_summary}\n\n"
        "> This pull request is a draft generated by an AI agent. Human review and "
        "explicit approval are required before merge."
    )
