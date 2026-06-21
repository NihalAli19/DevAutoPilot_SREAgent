"""Incident Pydantic models."""

# TODO(plan: Phase 2c) — DB persistence fields (id, timestamps) land with the store.
from __future__ import annotations

from pydantic import BaseModel


class Incident(BaseModel):
    """An incident dispatched by the Monitoring Agent (ML-gated, LLM-classified)."""

    org_id: str
    service: str
    title: str
    description: str | None = None
    severity: str = "P4"  # P1 (critical) .. P4 (minor)
    type: str | None = None  # latency | error_rate | throughput | resource | ...
    status: str = "open"
    confidence: float | None = None  # LLM classification confidence 0..1
    anomaly_score: float | None = None  # peak score from the anomaly model
    source: str | None = None  # monitor | webhook | simulate
