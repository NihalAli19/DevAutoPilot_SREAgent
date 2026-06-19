# Architecture

> Stub — expanded in Phase 4/5. The authoritative spec is `docs/IMPLEMENTATION_PLAN.md`.

## High level

DevAutoPilot v2 combines a **trained anomaly-detection model** with a **5-agent LLM workflow**:

```
Telemetry/Webhooks
   -> Monitoring Agent (calls anomaly model; ML gates the LLM)
   -> RCA Agent (RAG over past incidents via Azure AI Search + GitHub commits)
   -> Patch Agent (minimal diff -> draft PR, never auto-merge)
   -> Reliability Guard (post-merge health; Approve/Rollback/Escalate, HITL gate)
   -> Postmortem Agent (writes report, re-embeds into AI Search — learning loop)
```

## Components

- **FastAPI backend** (Azure Container Apps) — API surface, orchestration.
- **Anomaly ML service** — Isolation Forest baseline + LSTM-AE; MLflow registry; drift monitoring.
- **Microsoft Agent Framework 1.0** — graph workflow with HITL gates and OpenTelemetry tracing.
- **Azure AI Search** — vector + hybrid RAG over incidents/postmortems.
- **PostgreSQL** — relational + audit data (`agent_actions` is the replayable audit trail).
- **LLMRouter** — local Ollama by default, cloud for heavy reasoning, with fallback + budgets.
- **Azure API Management (Consumption)** — keys, rate-limit, quota, request transform.

## TODO(plan: Phase 4/5)

- Component diagram (replace the ASCII sketch).
- Sequence diagrams per agent.
- Deployment topology and network boundaries.
- Data-flow + tenancy isolation notes.
