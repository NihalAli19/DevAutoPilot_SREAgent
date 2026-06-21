"""Multi-agent graph workflow orchestrator (Microsoft Agent Framework)."""

# TODO(plan: Phase 3) — full graph: RCA -> Patch -> Reliability -> Postmortem + tracing.
from __future__ import annotations

from typing import Any

from app.agents.monitoring_agent import MonitoringAgent
from app.models.incident import Incident


class Orchestrator:
    """Coordinates the agent workflow. Phase 2: Monitoring Agent only."""

    def __init__(self, monitoring: MonitoringAgent | None = None) -> None:
        self.monitoring = monitoring or MonitoringAgent()

    async def handle_telemetry(
        self, service: str, metric: str, points: list[dict[str, Any]]
    ) -> Incident | None:
        """Run incoming telemetry through the Monitoring Agent."""
        return await self.monitoring.process(service, metric, points)
