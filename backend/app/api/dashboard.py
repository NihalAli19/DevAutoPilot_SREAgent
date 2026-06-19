"""Dashboard API — aggregate stats for the SRE control center."""
# TODO(plan: Phase 2) — serve incident feed, stats, and model-health widgets.
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
