"""Async database access (SQLAlchemy + asyncpg).

Tenant-scoped incident persistence plus the replayable ``agent_actions`` audit trail.
Queries run as raw SQL against ``db/schema.sql`` (the schema is the single source of
truth — no ORM model duplication). The incident ``type`` lives in the ``metadata`` JSONB
since the relational table keys on the core columns.
"""

# TODO(plan: Phase 3) — persist postmortem rows; add richer audit fields.
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.models.incident import Incident
from app.models.patch import PatchProposal
from app.models.reliability import MetricAggregate
from app.models.root_cause_analysis import RootCauseAnalysis
from app.models.telemetry import ScoredPoint

_engine: AsyncEngine | None = None
_UTC = ZoneInfo("UTC")


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


_INSERT_INCIDENT = text("""
    INSERT INTO incidents (org_id, title, description, service, severity, status,
                           confidence, anomaly_score, source, metadata)
    VALUES (:org_id, :title, :description, :service, :severity, :status,
            :confidence, :anomaly_score, :source, CAST(:metadata AS jsonb))
    RETURNING id, detected_at
""")

_LIST_INCIDENTS = text("""
    SELECT id, org_id, title, description, service, severity, status, confidence,
           anomaly_score, source, metadata->>'type' AS type, detected_at
    FROM incidents
    WHERE org_id = :org_id
    ORDER BY detected_at DESC
    LIMIT :limit
""")

_INSERT_ACTION = text("""
    INSERT INTO agent_actions (org_id, incident_id, agent_name, action, status, output)
    VALUES (:org_id, :incident_id, :agent_name, :action, :status, CAST(:output AS jsonb))
""")

_INSERT_ROOT_CAUSE_ANALYSIS = text("""
    INSERT INTO root_cause_analyses
        (org_id, incident_id, hypothesis, confidence, affected_files, evidence, model)
    VALUES
        (:org_id, :incident_id, :hypothesis, :confidence,
         CAST(:affected_files AS jsonb), CAST(:evidence AS jsonb), :model)
    RETURNING id, created_at
""")

_LIST_ROOT_CAUSE_ANALYSES = text("""
    SELECT id, org_id, incident_id, hypothesis, confidence, affected_files,
           evidence, model, created_at
    FROM root_cause_analyses
    WHERE org_id = :org_id AND incident_id = :incident_id
    ORDER BY created_at DESC
""")

_INSERT_PATCH = text("""
    INSERT INTO patches
        (org_id, incident_id, rca_id, summary, diff, pr_url, pr_number, branch, status, model)
    VALUES
        (:org_id, :incident_id, :rca_id, :summary, :diff, :pr_url,
         :pr_number, :branch, :status, :model)
    RETURNING id, created_at
""")

_LIST_PATCHES = text("""
    SELECT id, org_id, incident_id, rca_id, summary, diff, pr_url, pr_number,
           branch, status, approved_by, approved_at, model, created_at
    FROM patches
    WHERE org_id = :org_id AND incident_id = :incident_id
    ORDER BY created_at DESC
""")

_MARK_PATCH_MERGED = text("""
    UPDATE patches
    SET status = 'merged', approved_by = :approved_by, approved_at = :approved_at
    WHERE org_id = :org_id AND id = :patch_id
      AND status IN ('draft', 'proposed', 'approved', 'merged')
    RETURNING id, org_id, incident_id, rca_id, summary, diff, pr_url, pr_number,
              branch, status, approved_by, approved_at, model, created_at
""")

_SUMMARIZE_TELEMETRY_WINDOW = text("""
    SELECT metric, AVG(value)::double precision AS average, COUNT(*)::integer AS sample_count
    FROM telemetry
    WHERE org_id = :org_id AND service = :service
      AND ts >= :start AND ts < :end
    GROUP BY metric
    ORDER BY metric
""")

_INSERT_SCORED_TELEMETRY = text("""
    INSERT INTO telemetry
        (org_id, service, metric, value, anomaly_score, is_anomaly, ts)
    VALUES
        (:org_id, :service, :metric, :value, :anomaly_score, :is_anomaly, :ts)
""")


def _serialize(incident: Incident, incident_id: str, detected_at: str) -> dict[str, Any]:
    return {"id": incident_id, "detected_at": detected_at, **incident.model_dump()}


async def insert_incident(incident: Incident) -> dict[str, Any]:
    """Persist an incident; return it with its generated id + detected_at."""
    params = {
        "org_id": uuid.UUID(incident.org_id),
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "severity": incident.severity,
        "status": incident.status,
        "confidence": incident.confidence,
        "anomaly_score": incident.anomaly_score,
        "source": incident.source,
        "metadata": json.dumps({"type": incident.type} if incident.type else {}),
    }
    async with get_engine().begin() as conn:
        row = (await conn.execute(_INSERT_INCIDENT, params)).mappings().one()
    return _serialize(incident, str(row["id"]), row["detected_at"].isoformat())


async def list_incidents(org_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List incidents for a tenant, newest first."""
    async with get_engine().connect() as conn:
        rows = (
            (await conn.execute(_LIST_INCIDENTS, {"org_id": uuid.UUID(org_id), "limit": limit}))
            .mappings()
            .all()
        )
    incidents: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        record["id"] = str(row["id"])
        record["org_id"] = str(row["org_id"])
        record["detected_at"] = row["detected_at"].isoformat()
        incidents.append(record)
    return incidents


async def insert_agent_action(
    *,
    org_id: str,
    agent_name: str,
    action: str,
    incident_id: str | None = None,
    status: str = "succeeded",
    output: dict[str, Any] | None = None,
) -> None:
    """Append a row to the replayable agent_actions audit trail."""
    params = {
        "org_id": uuid.UUID(org_id),
        "incident_id": uuid.UUID(incident_id) if incident_id else None,
        "agent_name": agent_name,
        "action": action,
        "status": status,
        "output": json.dumps(output or {}),
    }
    async with get_engine().begin() as conn:
        await conn.execute(_INSERT_ACTION, params)


async def insert_root_cause_analysis(
    analysis: RootCauseAnalysis,
) -> RootCauseAnalysis:
    """Persist an RCA result and return it with its generated id and timestamp."""
    params = {
        "org_id": uuid.UUID(analysis.org_id),
        "incident_id": uuid.UUID(analysis.incident_id),
        "hypothesis": analysis.hypothesis,
        "confidence": analysis.confidence,
        "affected_files": json.dumps(analysis.affected_files),
        "evidence": json.dumps([item.model_dump() for item in analysis.evidence]),
        "model": analysis.model,
    }
    async with get_engine().begin() as conn:
        row = (await conn.execute(_INSERT_ROOT_CAUSE_ANALYSIS, params)).mappings().one()
    return analysis.model_copy(update={"id": str(row["id"]), "created_at": row["created_at"]})


async def list_root_cause_analyses(org_id: str, incident_id: str) -> list[RootCauseAnalysis]:
    """List RCA results for one incident, strictly scoped to its tenant."""
    params = {"org_id": uuid.UUID(org_id), "incident_id": uuid.UUID(incident_id)}
    async with get_engine().connect() as conn:
        rows = (await conn.execute(_LIST_ROOT_CAUSE_ANALYSES, params)).mappings().all()

    return [
        RootCauseAnalysis(
            id=str(row["id"]),
            org_id=str(row["org_id"]),
            incident_id=str(row["incident_id"]),
            hypothesis=row["hypothesis"],
            confidence=row["confidence"],
            affected_files=_json_value(row["affected_files"]),
            evidence=_json_value(row["evidence"]),
            model=row["model"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def insert_patch(patch: PatchProposal) -> PatchProposal:
    """Persist a validated draft-PR proposal."""
    params = {
        "org_id": uuid.UUID(patch.org_id),
        "incident_id": uuid.UUID(patch.incident_id),
        "rca_id": uuid.UUID(patch.rca_id) if patch.rca_id else None,
        "summary": patch.summary,
        "diff": patch.diff,
        "pr_url": patch.pr_url,
        "pr_number": patch.pr_number,
        "branch": patch.branch,
        "status": patch.status,
        "model": patch.model,
    }
    async with get_engine().begin() as conn:
        row = (await conn.execute(_INSERT_PATCH, params)).mappings().one()
    return patch.model_copy(update={"id": str(row["id"]), "created_at": row["created_at"]})


async def list_patches(org_id: str, incident_id: str) -> list[PatchProposal]:
    """List patch proposals for one incident, strictly scoped to its tenant."""
    params = {"org_id": uuid.UUID(org_id), "incident_id": uuid.UUID(incident_id)}
    async with get_engine().connect() as conn:
        rows = (await conn.execute(_LIST_PATCHES, params)).mappings().all()

    return [_patch_from_row(row) for row in rows]


async def mark_patch_merged(
    *,
    org_id: str,
    patch_id: str,
    approved_by: str,
    approved_at: datetime,
) -> PatchProposal:
    """Record a human GitHub merge after the Guard verifies it remotely."""
    params = {
        "org_id": uuid.UUID(org_id),
        "patch_id": uuid.UUID(patch_id),
        "approved_by": approved_by,
        "approved_at": approved_at,
    }
    async with get_engine().begin() as conn:
        row = (await conn.execute(_MARK_PATCH_MERGED, params)).mappings().one_or_none()
    if row is None:
        raise LookupError("patch not found or is not eligible for merge recording")
    return _patch_from_row(row)


async def summarize_telemetry_window(
    *,
    org_id: str,
    service: str,
    start: datetime,
    end: datetime,
) -> list[MetricAggregate]:
    """Aggregate one tenant/service telemetry window by metric."""
    params = {
        "org_id": uuid.UUID(org_id),
        "service": service,
        "start": start,
        "end": end,
    }
    async with get_engine().connect() as conn:
        rows = (await conn.execute(_SUMMARIZE_TELEMETRY_WINDOW, params)).mappings().all()
    return [
        MetricAggregate(
            metric=row["metric"],
            average=float(row["average"]),
            sample_count=int(row["sample_count"]),
        )
        for row in rows
    ]


async def insert_scored_telemetry(
    *,
    org_id: str,
    service: str,
    metric: str,
    points: list[ScoredPoint],
) -> None:
    """Persist scored observations used by later rollout-health comparisons."""
    if not points:
        return
    params = [
        {
            "org_id": uuid.UUID(org_id),
            "service": service,
            "metric": metric,
            "value": point.value,
            "anomaly_score": point.anomaly_score,
            "is_anomaly": point.is_anomaly,
            "ts": (
                point.timestamp
                if point.timestamp.tzinfo is not None
                else point.timestamp.replace(tzinfo=_UTC)
            ),
        }
        for point in points
    ]
    async with get_engine().begin() as conn:
        await conn.execute(_INSERT_SCORED_TELEMETRY, params)


def _patch_from_row(row: Any) -> PatchProposal:
    return PatchProposal(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        incident_id=str(row["incident_id"]),
        rca_id=str(row["rca_id"]) if row["rca_id"] else None,
        summary=row["summary"],
        diff=row["diff"],
        pr_url=row["pr_url"],
        pr_number=row["pr_number"],
        branch=row["branch"],
        status=row["status"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        model=row["model"],
        created_at=row["created_at"],
    )


def _json_value(value: Any) -> Any:
    """Normalize JSONB values across asyncpg/SQLAlchemy driver configurations."""
    return json.loads(value) if isinstance(value, str) else value
