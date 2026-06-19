"""Incidents API — list/detail/approve endpoints."""

# TODO(plan: Phase 2) — implement incident CRUD and the HITL approval gate.
from fastapi import APIRouter

router = APIRouter(prefix="/incidents", tags=["incidents"])
