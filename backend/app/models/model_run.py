"""Model-run (MLOps audit) Pydantic models."""
# TODO(plan: Phase 1) — model version, metrics, drift, deployment status.
from __future__ import annotations

from pydantic import BaseModel


class ModelRun(BaseModel):
    """Minimal model-run stub."""

    org_id: str
    model_name: str
    version: str
    deployment_status: str = "registered"
