"""Monitoring Agent (Microsoft Agent Framework) — ML gates the LLM.

Scores a telemetry window with the trained anomaly model; ONLY if the model flags an
anomaly does it invoke the LLM (an ``agent_framework.Agent``) to classify severity and
type into a structured incident. This is the ML-gates-LLM pattern: a cheap deterministic
filter before expensive generative reasoning.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from agent_framework import Agent

from app.models.incident import Incident
from app.services.anomaly_service import AnomalyService
from app.services.llm_router import LLMRouter
from app.utils.prompts import MONITORING_INSTRUCTIONS, build_monitoring_prompt


class Scorer(Protocol):
    """Anything that can score a telemetry window (the AnomalyService, or a fake)."""

    def score_points(self, points: list[dict[str, Any]]) -> dict[str, Any]: ...


class MonitoringAgent:
    """Detects anomalies (ML), then classifies confirmed ones via an Agent (LLM)."""

    def __init__(
        self,
        *,
        anomaly_service: Scorer | None = None,
        chat_client: Any | None = None,
        llm_router: LLMRouter | None = None,
        org_id: str = "default",
    ) -> None:
        self.anomaly = anomaly_service or AnomalyService()
        self._chat_client = chat_client
        self.router = llm_router or LLMRouter()
        self.org_id = org_id

    def _agent(self) -> Agent:
        client = self._chat_client or self.router.chat_client()
        return Agent(client, instructions=MONITORING_INSTRUCTIONS, name="monitoring")

    async def process(
        self, service: str, metric: str, points: list[dict[str, Any]]
    ) -> Incident | None:
        """Score the window; if anomalous, classify and return an Incident, else None."""
        scored = self.anomaly.score_points(points)["scored"]
        anomalies = [p for p in scored if p["is_anomaly"]]
        if not anomalies:
            return None  # ML gate: nothing anomalous -> no LLM call, no incident

        peak = max(anomalies, key=lambda p: p["anomaly_score"])
        response = await self._agent().run(
            build_monitoring_prompt(service, metric, scored, anomalies, peak)
        )
        data = _parse_classification(response.text)
        return Incident(
            org_id=self.org_id,
            service=service,
            title=data.get("title") or f"Anomaly detected in {service} {metric}",
            description=data.get("summary"),
            severity=data.get("severity", "P4"),
            type=data.get("type"),
            confidence=_as_float(data.get("confidence")),
            anomaly_score=float(peak["anomaly_score"]),
            source="monitor",
        )


def _parse_classification(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
