"""Telemetry Pydantic models."""
# TODO(plan: Phase 1) — model raw + feature-engineered metric points.
from __future__ import annotations

from pydantic import BaseModel


class TelemetryPoint(BaseModel):
    """Minimal telemetry stub."""

    org_id: str
    service: str
    metric: str
    value: float
