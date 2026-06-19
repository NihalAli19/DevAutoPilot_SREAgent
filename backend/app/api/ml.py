"""ML API — model versions, eval metrics, drift, and retrain trigger."""

# TODO(plan: Phase 1) — GET /ml/models and POST /ml/retrain.
from fastapi import APIRouter

router = APIRouter(prefix="/ml", tags=["ml"])
