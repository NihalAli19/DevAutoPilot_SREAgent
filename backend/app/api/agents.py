"""Agents API — agent status and OpenTelemetry trace view."""
# TODO(plan: Phase 3) — expose agent workload and /agents/{incident_id}/trace.
from fastapi import APIRouter

router = APIRouter(prefix="/agents", tags=["agents"])
