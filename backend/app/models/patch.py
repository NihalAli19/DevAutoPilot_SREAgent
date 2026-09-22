"""Structured patch proposal and GitHub draft-PR models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RepositoryFile(BaseModel):
    """A UTF-8 source file fetched from the configured target repository."""

    path: str
    content: str
    sha: str


class PatchEdit(BaseModel):
    """A complete replacement for one existing repository file."""

    path: str
    content: str
    source_sha: str


class DraftPullRequest(BaseModel):
    """The immutable identifiers returned after GitHub opens a draft PR."""

    number: int = Field(gt=0)
    url: str
    branch: str


class PatchProposal(BaseModel):
    """A validated code change proposed by the Patch Agent."""

    id: str | None = None
    org_id: str
    incident_id: str
    rca_id: str | None = None
    summary: str = Field(min_length=1)
    diff: str = Field(min_length=1)
    pr_url: str | None = None
    pr_number: int | None = Field(default=None, gt=0)
    branch: str | None = None
    status: Literal["draft", "proposed", "approved", "merged", "rejected"] = "draft"
    approved_by: str | None = None
    approved_at: datetime | None = None
    model: str | None = None
    created_at: datetime | None = None
