"""Tests for deterministic pre/post-deployment health comparison."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.reliability import MetricAggregate, TimeWindow
from app.services.health_service import HealthService

UTC = ZoneInfo("UTC")
START = datetime(2026, 1, 1, tzinfo=UTC)
BASELINE = TimeWindow(start=START, end=START + timedelta(minutes=5))
CURRENT = TimeWindow(start=START + timedelta(minutes=5), end=START + timedelta(minutes=10))


class FakeStore:
    def __init__(
        self,
        baseline: list[MetricAggregate],
        current: list[MetricAggregate],
    ) -> None:
        self.baseline = baseline
        self.current = current
        self.calls = 0

    async def summarize_telemetry_window(self, **kwargs) -> list[MetricAggregate]:
        self.calls += 1
        return self.baseline if kwargs["start"] == BASELINE.start else self.current


@pytest.mark.asyncio
async def test_compare_normalizes_lower_and_higher_is_better_metrics():
    store = FakeStore(
        baseline=[
            MetricAggregate(metric="latency_p95", average=100.0, sample_count=10),
            MetricAggregate(metric="throughput", average=100.0, sample_count=10),
        ],
        current=[
            MetricAggregate(metric="latency_p95", average=160.0, sample_count=10),
            MetricAggregate(metric="throughput", average=80.0, sample_count=10),
        ],
    )
    service = HealthService(store=store, minimum_samples=5)

    result = await service.compare(
        org_id="org",
        service="checkout",
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    metrics = {item.metric: item for item in result.metrics}
    assert metrics["latency_p95"].regression_ratio == pytest.approx(0.6)
    assert metrics["throughput"].regression_ratio == pytest.approx(0.2)
    assert result.worst_regression_ratio == pytest.approx(0.6)
    assert result.sufficient_data is True
    assert store.calls == 2


@pytest.mark.asyncio
async def test_missing_current_metric_fails_closed_as_insufficient_data():
    service = HealthService(
        store=FakeStore(
            baseline=[MetricAggregate(metric="latency_p95", average=100.0, sample_count=10)],
            current=[],
        ),
        minimum_samples=5,
    )

    result = await service.compare(
        org_id="org",
        service="checkout",
        baseline_window=BASELINE,
        current_window=CURRENT,
    )

    assert result.metrics == []
    assert result.missing_or_unsupported_metrics == ["latency_p95"]
    assert result.sufficient_data is False


def test_time_window_requires_ordered_timezone_aware_datetimes():
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeWindow(start=datetime(2026, 1, 1), end=datetime(2026, 1, 2))
    with pytest.raises(ValueError, match="start must precede"):
        TimeWindow(start=CURRENT.end, end=CURRENT.start)


@pytest.mark.asyncio
async def test_overlapping_baseline_and_current_windows_are_rejected():
    service = HealthService(store=FakeStore([], []))
    overlapping = TimeWindow(
        start=BASELINE.end - timedelta(minutes=1),
        end=BASELINE.end + timedelta(minutes=1),
    )

    with pytest.raises(ValueError, match="baseline window must end"):
        await service.compare(
            org_id="org",
            service="checkout",
            baseline_window=BASELINE,
            current_window=overlapping,
        )
