"""Structured root-cause analysis models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RCAEvidence(BaseModel):
    """A retrieved passage used to ground a root-cause hypothesis."""

    source: str
    content: str
    score: float | None = None


class RootCauseAnalysis(BaseModel):
    """Evidence-grounded output produced by the RCA Agent."""

    id: str | None = None
    org_id: str
    incident_id: str
    hypothesis: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    affected_files: list[str] = Field(default_factory=list)
    evidence: list[RCAEvidence] = Field(default_factory=list)
    model: str | None = None
    created_at: datetime | None = None
