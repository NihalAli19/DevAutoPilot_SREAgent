"""Simulate API — trigger an anomaly on demand for live demos.

Synthesizes an anomalous telemetry window, runs it through the Monitoring Agent
(ML-gates-LLM), and persists any resulting incident + audit row.
"""

# TODO(plan: Phase 3) — drive the full agent graph (RCA/Patch/...) from a simulation.
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
from fastapi import APIRouter, HTTPException

from app.agents.monitoring_agent import MonitoringAgent
from app.agents.orchestrator import Orchestrator
from app.config import get_settings
from app.models.telemetry import SimulateRequest, SimulateResponse
from app.services import db_service

router = APIRouter(prefix="/simulate", tags=["simulate"])

# Module-level so tests can monkeypatch it with a fake orchestrator.
_orchestrator = Orchestrator(MonitoringAgent(org_id=get_settings().demo_org_id))


def _synthetic_window(n: int) -> list[dict]:
    """A seasonal series (5-min cadence) with a clear anomaly injected near the end."""
    rng = np.random.default_rng(0)
    base = datetime(2024, 1, 1)
    t = np.arange(n)
    values = 50.0 + 10.0 * np.sin(2 * np.pi * t / 288) + rng.normal(0.0, 1.0, n)
    values[-10:] += 45.0  # the injected anomaly
    return [
        {"timestamp": (base + timedelta(minutes=5 * i)).isoformat(), "value": float(v)}
        for i, v in enumerate(values)
    ]


@router.post("", response_model=SimulateResponse)
async def simulate(request: SimulateRequest) -> SimulateResponse:
    """Inject a synthetic anomaly, run the agent, and persist the incident."""
    points = _synthetic_window(request.points)
    try:
        incident = await _orchestrator.handle_telemetry(request.service, request.metric, points)
    except FileNotFoundError as exc:  # anomaly model artifact not trained yet
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if incident is None:
        return SimulateResponse(detected=False)

    stored = await db_service.insert_incident(incident)
    await db_service.insert_agent_action(
        org_id=incident.org_id,
        incident_id=stored["id"],
        agent_name="monitoring",
        action="classify",
        output={"severity": incident.severity, "type": incident.type},
    )
    return SimulateResponse(detected=True, incident=stored)
