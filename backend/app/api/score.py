"""Score API — score telemetry with the trained anomaly model."""
# TODO(plan: Phase 1) — POST /score: run telemetry through the anomaly service.
from fastapi import APIRouter

router = APIRouter(prefix="/score", tags=["score"])
