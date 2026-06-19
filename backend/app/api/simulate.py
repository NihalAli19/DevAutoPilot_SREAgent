"""Simulate API — trigger anomalies/incidents on demand for live demos."""

# TODO(plan: Phase 2) — inject synthetic anomalies into the metrics stream.
from fastapi import APIRouter

router = APIRouter(prefix="/simulate", tags=["simulate"])
