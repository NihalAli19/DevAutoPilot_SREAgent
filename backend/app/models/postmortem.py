"""Postmortem Pydantic models."""
# TODO(plan: Phase 3) — model timeline, action items, and embedding status.
from __future__ import annotations

from pydantic import BaseModel


class Postmortem(BaseModel):
    """Minimal postmortem stub."""

    org_id: str
    incident_id: str
    title: str
