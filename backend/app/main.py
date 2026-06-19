"""FastAPI application entrypoint: app factory, CORS, and a working /health route."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agents,
    dashboard,
    incidents,
    ml,
    score,
    simulate,
    webhooks,
)
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI SRE platform: ML anomaly detection + multi-agent LLM workflow.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok", "service": settings.app_name}

    # Feature routers (mostly Phase 1+ stubs).
    app.include_router(incidents.router, prefix="/api")
    app.include_router(agents.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(webhooks.router, prefix="/api")
    app.include_router(simulate.router, prefix="/api")
    app.include_router(score.router, prefix="/api")
    app.include_router(ml.router, prefix="/api")

    return app


app = create_app()
