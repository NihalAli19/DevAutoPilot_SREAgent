"""Webhooks API — GitHub + telemetry ingestion with signature verification."""
# TODO(plan: Phase 3) — verify GitHub webhook signatures and dispatch to agents.
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
