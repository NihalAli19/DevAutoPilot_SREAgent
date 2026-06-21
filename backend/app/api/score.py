"""Score API — score telemetry with the trained anomaly model (in-process)."""

# TODO(plan: Phase 2) — persist scored telemetry; dispatch anomalies to the Monitoring Agent.
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.telemetry import ScoreRequest, ScoreResponse
from app.services.anomaly_service import AnomalyService

router = APIRouter(prefix="/score", tags=["score"])

_service = AnomalyService()


@router.post("", response_model=ScoreResponse)
async def score(request: ScoreRequest) -> ScoreResponse:
    """Score a window of telemetry; returns per-point anomaly scores + flags."""
    points = [{"timestamp": p.timestamp.isoformat(), "value": p.value} for p in request.points]
    try:
        result = _service.score_points(points)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ScoreResponse(**result)
