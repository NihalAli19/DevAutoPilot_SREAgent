"""Tests for incident persistence + GET /api/incidents (requires Postgres)."""

import pytest

from app.config import get_settings
from app.models.incident import Incident
from app.services import db_service

ORG = get_settings().demo_org_id


def _incident(title="Latency spike", severity="P1", type_="latency"):
    return Incident(
        org_id=ORG,
        service="checkout",
        title=title,
        description="p95 elevated",
        severity=severity,
        type=type_,
        confidence=0.9,
        anomaly_score=0.87,
        source="monitor",
    )


@pytest.mark.asyncio
async def test_insert_and_list_incident(db):
    stored = await db_service.insert_incident(_incident())
    assert stored["id"]
    assert stored["detected_at"]

    rows = await db_service.list_incidents(ORG)
    assert len(rows) == 1
    assert rows[0]["title"] == "Latency spike"
    assert rows[0]["severity"] == "P1"
    assert rows[0]["type"] == "latency"  # round-tripped through metadata JSONB


@pytest.mark.asyncio
async def test_list_is_tenant_scoped_and_newest_first(db):
    await db_service.insert_incident(_incident(title="first", severity="P3"))
    await db_service.insert_incident(_incident(title="second", severity="P1"))
    rows = await db_service.list_incidents(ORG)
    assert [r["title"] for r in rows][:2] == ["second", "first"]
    # A different tenant sees nothing.
    other = await db_service.list_incidents("00000000-0000-0000-0000-0000000000ff")
    assert other == []


@pytest.mark.asyncio
async def test_agent_action_audit_row(db):
    stored = await db_service.insert_incident(_incident())
    await db_service.insert_agent_action(
        org_id=ORG, incident_id=stored["id"], agent_name="monitoring", action="classify"
    )  # must not raise; FK to the incident resolves


@pytest.mark.asyncio
async def test_get_incidents_endpoint(client, db):
    await db_service.insert_incident(_incident(title="from endpoint"))
    resp = await client.get("/api/incidents")
    assert resp.status_code == 200
    body = resp.json()
    assert any(i["title"] == "from endpoint" for i in body)
