"""Typed rollout-health and Reliability Guard decision models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TimeWindow(BaseModel):
    """A half-open UTC telemetry window: start <= timestamp < end."""

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def validate_window(self) -> TimeWindow:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("health windows must use timezone-aware datetimes")
        if self.start >= self.end:
            raise ValueError("health window start must precede end")
        return self


class MetricAggregate(BaseModel):
    """Average value and sample count for one metric window."""

    metric: str = Field(min_length=1)
    average: float
    sample_count: int = Field(ge=1)


class MetricComparison(BaseModel):
    """Baseline/current comparison normalized so positive means regression."""

    metric: str
    baseline: float
    current: float
    baseline_samples: int = Field(ge=1)
    current_samples: int = Field(ge=1)
    direction: Literal["lower_is_better", "higher_is_better"]
    regression_ratio: float


class RolloutHealth(BaseModel):
    """All evidence used to judge one deployment against its baseline."""

    service: str
    baseline_window: TimeWindow
    current_window: TimeWindow
    metrics: list[MetricComparison] = Field(default_factory=list)
    missing_or_unsupported_metrics: list[str] = Field(default_factory=list)
    minimum_samples: int = Field(ge=1)
    sufficient_data: bool

    @property
    def worst_regression_ratio(self) -> float:
        return max((metric.regression_ratio for metric in self.metrics), default=0.0)


class PullRequestStatus(BaseModel):
    """GitHub merge evidence required before rollout assessment."""

    number: int = Field(gt=0)
    draft: bool
    merged: bool
    merged_at: datetime | None = None
    merged_by: str | None = None
    merged_by_type: str | None = None


class ReliabilityAssessment(BaseModel):
    """A recommendation only; it never authorizes or executes a rollback."""

    org_id: str
    incident_id: str
    patch_id: str
    service: str
    decision: Literal["approve", "rollback", "escalate"]
    rationale: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    health: RolloutHealth
    requires_human_approval: bool
    status: Literal["recommendation_only"] = "recommendation_only"
    model: str | None = None
    created_at: datetime | None = None
