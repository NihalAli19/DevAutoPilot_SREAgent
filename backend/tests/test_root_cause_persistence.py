"""PostgreSQL integration tests for tenant-scoped RCA persistence."""

import pytest

from app.config import get_settings
from app.models.incident import Incident
from app.models.root_cause_analysis import RCAEvidence, RootCauseAnalysis
from app.services import db_service

ORG = get_settings().demo_org_id


def _incident() -> Incident:
    return Incident(
        org_id=ORG,
        service="checkout",
        title="Latency spike",
        severity="P2",
        type="latency",
        source="monitor",
    )


@pytest.mark.asyncio
async def test_insert_and_list_root_cause_analysis(db):
    incident = await db_service.insert_incident(_incident())
    analysis = RootCauseAnalysis(
        org_id=ORG,
        incident_id=incident["id"],
        hypothesis="The connection pool is saturated.",
        confidence=0.84,
        affected_files=["app/db.py"],
        evidence=[
            RCAEvidence(
                source="latency-spike.md",
                content="Inspect connection pool utilization.",
                score=0.93,
            )
        ],
        model="gemini-test",
    )

    stored = await db_service.insert_root_cause_analysis(analysis)
    rows = await db_service.list_root_cause_analyses(ORG, incident["id"])

    assert stored.id
    assert stored.created_at
    assert rows == [stored]
    assert rows[0].affected_files == ["app/db.py"]
    assert rows[0].evidence[0].source == "latency-spike.md"


@pytest.mark.asyncio
async def test_list_root_cause_analyses_is_tenant_scoped(db):
    incident = await db_service.insert_incident(_incident())
    await db_service.insert_root_cause_analysis(
        RootCauseAnalysis(
            org_id=ORG,
            incident_id=incident["id"],
            hypothesis="A grounded hypothesis.",
            confidence=0.7,
        )
    )

    rows = await db_service.list_root_cause_analyses(
        "00000000-0000-0000-0000-0000000000ff", incident["id"]
    )

    assert rows == []
