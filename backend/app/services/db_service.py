"""Async database access (SQLAlchemy + asyncpg).

Tenant-scoped incident persistence plus the replayable ``agent_actions`` audit trail.
Queries run as raw SQL against ``db/schema.sql`` (the schema is the single source of
truth — no ORM model duplication). The incident ``type`` lives in the ``metadata`` JSONB
since the relational table keys on the core columns.
"""

# TODO(plan: Phase 3) — persist RCA/patch/postmortem rows; richer audit fields.
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import get_settings
from app.models.incident import Incident

_engine: AsyncEngine | None = None


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
