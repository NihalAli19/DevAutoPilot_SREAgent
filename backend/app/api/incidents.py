"""Incidents API — list incidents for the dashboard."""

# TODO(plan: Phase 3) — incident detail with agent timeline; HITL approval gate.
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.config import get_settings
from app.services import db_service

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("")
async def list_incidents(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """List incidents for the demo tenant, newest first."""
    return await db_service.list_incidents(get_settings().demo_org_id, limit=limit)
