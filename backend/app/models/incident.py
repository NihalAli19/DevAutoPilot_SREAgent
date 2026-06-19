"""Incident Pydantic models."""

# TODO(plan: Phase 2) — flesh out request/response/db schemas with full fields.
from __future__ import annotations

from pydantic import BaseModel


class Incident(BaseModel):
    """Minimal incident stub."""

    org_id: str
    title: str
    service: str
    severity: str = "P4"
    status: str = "open"
