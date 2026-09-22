"""Compare post-deployment telemetry with a pre-deployment baseline."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from app.models.reliability import (
    MetricAggregate,
    MetricComparison,
    RolloutHealth,
    TimeWindow,
)
from app.services import db_service

MetricDirection = Literal["lower_is_better", "higher_is_better"]

_METRIC_DIRECTIONS: dict[str, MetricDirection] = {
    "latency_p95": "lower_is_better",
    "error_rate": "lower_is_better",
    "cpu": "lower_is_better",
    "mem": "lower_is_better",
    "throughput": "higher_is_better",
    "availability": "higher_is_better",
}


class HealthStore(Protocol):
    async def summarize_telemetry_window(
        self,
        *,
        org_id: str,
        service: str,
        start: datetime,
        end: datetime,
    ) -> list[MetricAggregate]: ...


class HealthService:
    """Load and normalize health metrics without allowing an LLM to calculate them."""

    def __init__(self, store: HealthStore | None = None, minimum_samples: int = 5) -> None:
        if minimum_samples < 1:
            raise ValueError("minimum_samples must be positive")
        self.store = store or db_service
        self.minimum_samples = minimum_samples

    async def compare(
        self,
        *,
        org_id: str,
        service: str,
        baseline_window: TimeWindow,
        current_window: TimeWindow,
    ) -> RolloutHealth:
        if baseline_window.end > current_window.start:
            raise ValueError("baseline window must end before the current window starts")
        baseline = await self.store.summarize_telemetry_window(
            org_id=org_id,
            service=service,
            start=baseline_window.start,
            end=baseline_window.end,
        )
        current = await self.store.summarize_telemetry_window(
            org_id=org_id,
            service=service,
            start=current_window.start,
            end=current_window.end,
        )
        baseline_by_metric = {item.metric: item for item in baseline}
        current_by_metric = {item.metric: item for item in current}
        all_metrics = sorted(baseline_by_metric.keys() | current_by_metric.keys())

        comparisons: list[MetricComparison] = []
        incomplete: list[str] = []
        for metric in all_metrics:
            before = baseline_by_metric.get(metric)
            after = current_by_metric.get(metric)
            direction = _METRIC_DIRECTIONS.get(metric)
            if before is None or after is None or direction is None:
                incomplete.append(metric)
                continue
            comparisons.append(
                MetricComparison(
                    metric=metric,
                    baseline=before.average,
                    current=after.average,
                    baseline_samples=before.sample_count,
                    current_samples=after.sample_count,
                    direction=direction,
                    regression_ratio=_regression_ratio(before.average, after.average, direction),
                )
            )

        sufficient = (
            bool(comparisons)
            and not incomplete
            and all(
                metric.baseline_samples >= self.minimum_samples
                and metric.current_samples >= self.minimum_samples
                for metric in comparisons
            )
        )
        return RolloutHealth(
            service=service,
            baseline_window=baseline_window,
            current_window=current_window,
            metrics=comparisons,
            missing_or_unsupported_metrics=incomplete,
            minimum_samples=self.minimum_samples,
            sufficient_data=sufficient,
        )


def _regression_ratio(baseline: float, current: float, direction: MetricDirection) -> float:
    """Return a signed ratio where positive always means worse health."""
    if baseline == 0.0:
        if current == 0.0:
            return 0.0
        return 1.0 if direction == "lower_is_better" else -1.0
    if direction == "lower_is_better":
        return (current - baseline) / abs(baseline)
    return (baseline - current) / abs(baseline)
