"""Score API — score telemetry with the trained anomaly model (in-process)."""

# TODO(plan: Phase 3) — dispatch anomalous windows into the full agent graph.
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.telemetry import ScoreRequest, ScoreResponse
from app.services import db_service
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
    response = ScoreResponse(**result)
    if request.service and request.metric:
        await db_service.insert_scored_telemetry(
            org_id=get_settings().demo_org_id,
            service=request.service,
            metric=request.metric,
            points=response.scored,
        )
    return response
