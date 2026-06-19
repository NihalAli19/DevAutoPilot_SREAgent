# DevAutoPilot v2

> An AI SRE platform that detects anomalies in service telemetry with a **trained ML model**, then runs a **multi-agent LLM workflow** (Microsoft Agent Framework) to diagnose root cause, propose a fix as a PR, guard the rollout, and write the postmortem.

**One-liner:** "Datadog tells you *something broke*. DevAutoPilot tells you *what broke, why, and ships the fix as a reviewed PR* — combining a trained anomaly-detection model with a team of LLM agents."

This repository is built **phase by phase**. See `docs/IMPLEMENTATION_PLAN.md` for the full spec and `AGENTS.md` for the rules AI coding agents must follow.

## Status

**Phase 0 — Foundations.** This is the project scaffold: repo structure, FastAPI skeleton with a working `/health` endpoint, config loading, database schema, CI workflows, and placeholders for the ML pipeline, agents, frontend, and demo app. Most modules are stubs marked with `# TODO(plan: Phase N)`.

## Repository layout

```
backend/    FastAPI app, multi-agent orchestration, services
ml/         Anomaly-detection MLOps pipeline (data -> train -> eval -> serve)
frontend/   Next.js dark SRE dashboard (placeholders)
db/         PostgreSQL schema
infra/      Azure APIM policies and infra notes
demo/       Intentionally-faulty sample app + incident simulator
docs/        Architecture & setup docs
.github/    CI and ML pipeline workflows
```

## Quickstart (local backend)

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env          # fill in placeholders as needed
uvicorn app.main:app --reload
```

Then open http://localhost:8000/health and http://localhost:8000/docs.

### Run the tests

```bash
cd backend
pytest
```

### Docker (Postgres + backend)

```bash
docker compose up --build
```

## Tech stack

- **Backend:** Python 3.11+, FastAPI (async), Pydantic v2
- **Agents:** Microsoft Agent Framework 1.0 (`agent-framework`)
- **ML:** scikit-learn (Isolation Forest) + PyTorch (LSTM-autoencoder), MLflow
- **Data:** PostgreSQL (SQLAlchemy/asyncpg); vector store: Azure AI Search
- **LLM access:** `LLMRouter` — local Ollama by default, cloud for heavy reasoning
- **Frontend:** Next.js (App Router), TypeScript, Tailwind, Recharts
- **Infra:** Azure Container Apps, API Management (Consumption), Static Web Apps — free-tier only

## License

For portfolio / educational use.
