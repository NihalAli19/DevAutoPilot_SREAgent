"""Tests for POST /api/simulate (agent mocked; requires Postgres for persistence)."""

import pytest

from app.api import simulate as simulate_module
from app.config import get_settings
from app.models.incident import Incident

ORG = get_settings().demo_org_id


class FakeOrchestrator:
    """Stands in for the real Orchestrator: returns a canned incident (or None)."""

    def __init__(self, incident: Incident | None):
        self._incident = incident

    async def handle_telemetry(self, service, metric, points):
        return self._incident


@pytest.mark.asyncio
async def test_simulate_persists_detected_incident(client, db, monkeypatch):
    incident = Incident(
        org_id=ORG,
        service="checkout",
        title="Simulated latency spike",
        severity="P2",
        type="latency",
        confidence=0.8,
        anomaly_score=0.95,
        source="monitor",
    )
    monkeypatch.setattr(simulate_module, "_orchestrator", FakeOrchestrator(incident))

    resp = await client.post("/api/simulate", json={"service": "checkout", "metric": "latency_p95"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["detected"] is True
    assert body["incident"]["title"] == "Simulated latency spike"
    assert body["incident"]["id"]

    # It was actually persisted.
    listed = await client.get("/api/incidents")
    assert any(i["title"] == "Simulated latency spike" for i in listed.json())


@pytest.mark.asyncio
async def test_simulate_no_anomaly_returns_not_detected(client, db, monkeypatch):
    monkeypatch.setattr(simulate_module, "_orchestrator", FakeOrchestrator(None))
    resp = await client.post("/api/simulate", json={})
    assert resp.status_code == 200
    assert resp.json() == {"detected": False, "incident": None}
    assert (await client.get("/api/incidents")).json() == []
