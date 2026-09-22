"""Integration tests for tenant-scoped patch and rollout persistence."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config import get_settings
from app.models.incident import Incident
from app.models.patch import PatchProposal
from app.models.root_cause_analysis import RootCauseAnalysis
from app.models.telemetry import ScoredPoint
from app.services import db_service

ORG = get_settings().demo_org_id
UTC = ZoneInfo("UTC")


def _incident() -> Incident:
    return Incident(org_id=ORG, service="checkout", title="Timeout regression")


@pytest.mark.asyncio
async def test_insert_and_list_patch(db):
    incident = await db_service.insert_incident(_incident())
    rca = await db_service.insert_root_cause_analysis(
        RootCauseAnalysis(
            org_id=ORG,
            incident_id=incident["id"],
            hypothesis="Timeout constant is too low",
            confidence=0.9,
            affected_files=["app/main.py"],
        )
    )
    patch = PatchProposal(
        org_id=ORG,
        incident_id=incident["id"],
        rca_id=rca.id,
        summary="Increase timeout",
        diff="--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1 @@\n-TIMEOUT=1\n+TIMEOUT=10",
        pr_url="https://github.test/acme/faulty-app/pull/17",
        pr_number=17,
        branch="devautopilot/incident-1",
        model="gemini-test",
    )

    stored = await db_service.insert_patch(patch)
    rows = await db_service.list_patches(ORG, incident["id"])

    assert stored.id
    assert stored.created_at
    assert len(rows) == 1
    assert rows[0].id == stored.id
    assert rows[0].status == "draft"
    assert rows[0].pr_number == 17
    assert rows[0].rca_id == rca.id


@pytest.mark.asyncio
async def test_list_patches_is_tenant_scoped(db):
    incident = await db_service.insert_incident(_incident())
    await db_service.insert_patch(
        PatchProposal(
            org_id=ORG,
            incident_id=incident["id"],
            summary="Safe patch",
            diff="--- a/app/main.py\n+++ b/app/main.py",
        )
    )

    rows = await db_service.list_patches("00000000-0000-0000-0000-0000000000ff", incident["id"])

    assert rows == []


@pytest.mark.asyncio
async def test_record_human_merge_and_summarize_tenant_telemetry(db):
    incident = await db_service.insert_incident(_incident())
    patch = await db_service.insert_patch(
        PatchProposal(
            org_id=ORG,
            incident_id=incident["id"],
            summary="Increase worker limit",
            diff="--- a/app.py\n+++ b/app.py",
            pr_number=17,
        )
    )
    merged_at = datetime(2026, 1, 1, 12, tzinfo=UTC)

    merged = await db_service.mark_patch_merged(
        org_id=ORG,
        patch_id=patch.id or "",
        approved_by="human-reviewer",
        approved_at=merged_at,
    )

    assert merged.status == "merged"
    assert merged.approved_by == "human-reviewer"
    assert merged.approved_at == merged_at

    start = merged_at - timedelta(minutes=10)
    await db_service.insert_scored_telemetry(
        org_id=ORG,
        service="checkout",
        metric="latency_p95",
        points=[
            ScoredPoint(
                timestamp=(start + timedelta(minutes=index)).replace(tzinfo=None),
                value=value,
                anomaly_score=0.1,
                is_anomaly=False,
            )
            for index, value in enumerate([100.0, 120.0, 140.0])
        ],
    )

    summary = await db_service.summarize_telemetry_window(
        org_id=ORG,
        service="checkout",
        start=start,
        end=start + timedelta(minutes=5),
    )

    assert len(summary) == 1
    assert summary[0].metric == "latency_p95"
    assert summary[0].average == pytest.approx(120.0)
    assert summary[0].sample_count == 3
