"""Integration tests for tenant-scoped patch persistence."""

import pytest

from app.config import get_settings
from app.models.incident import Incident
from app.models.patch import PatchProposal
from app.models.root_cause_analysis import RootCauseAnalysis
from app.services import db_service

ORG = get_settings().demo_org_id


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
