"""Intentionally-faulty sample service — the demo target for the agent workflow."""
# TODO(plan: Phase 2) — add fault toggles (latency spikes, error bursts) the
# Monitoring Agent can detect and the Patch Agent can fix.
from fastapi import FastAPI

app = FastAPI(title="Faulty Demo App")


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/work")
async def work() -> dict[str, str]:
    """A normally-healthy endpoint that later phases can degrade on demand."""
    return {"result": "done"}
