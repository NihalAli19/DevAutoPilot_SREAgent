"""Telemetry + scoring request/response models for POST /api/score."""

# TODO(plan: Phase 2) — persist scored telemetry to the telemetry table.
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryPoint(BaseModel):
    """A single raw metric observation."""

    timestamp: datetime
    value: float


class ScoreRequest(BaseModel):
    """A window of telemetry to score (enough points for feature warm-up)."""

    service: str | None = None
    metric: str | None = None
    points: list[TelemetryPoint] = Field(min_length=1)


class ScoredPoint(BaseModel):
    """A scored telemetry point."""

    timestamp: datetime
    value: float
    anomaly_score: float
    is_anomaly: bool


class ScoreResponse(BaseModel):
    """Scoring result: tail points that survived feature warm-up, plus metadata."""

    # 'model_name' would collide with Pydantic's protected 'model_' namespace.
    model_config = ConfigDict(protected_namespaces=())

    model_name: str
    feature_version: str
    warmup_skipped: int
    scored: list[ScoredPoint]
