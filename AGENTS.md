# AGENTS.md — DevAutoPilot v2 (project rules for AI coding agents)

> Save this file as **`AGENTS.md`** in the repo root for Antigravity, and copy it to **`CLAUDE.md`** if you also use Claude Code. Same content works for both.

## What this project is
DevAutoPilot v2 — an AI SRE platform that detects anomalies in service telemetry with a **trained ML model**, then runs a **multi-agent LLM workflow** (Microsoft Agent Framework) to diagnose root cause (RAG over past incidents), propose a fix as a PR, guard the rollout, and write the postmortem.

## Source of truth
- The full spec lives at **`docs/IMPLEMENTATION_PLAN.md`**. Read it before writing code. If anything here conflicts with the plan, ask me — do not guess.
- Build **phase by phase** (the plan has Phases 0-5). Do not attempt to build the whole system in one pass.
- **Plan before coding:** for each new phase, first output (a) a short summary of your understanding, (b) the files you'll create/modify, (c) a task list. Wait for my approval before writing code.

## Tech stack (do not substitute without asking)
- Backend: Python 3.11+, FastAPI, async, full type hints, Pydantic v2.
- Agents: `agent-framework` (Microsoft Agent Framework 1.0).
- ML: scikit-learn (Isolation Forest baseline) + PyTorch (LSTM-autoencoder); MLflow for tracking/registry.
- Data: PostgreSQL (SQLAlchemy/asyncpg). Vector store: Azure AI Search (free tier).
- LLM access: an `LLMRouter` abstraction — local Ollama by default in dev, cloud (Azure OpenAI / Gemini) for heavy reasoning. Never hardcode a single provider.
- Frontend: Next.js (App Router), TypeScript, Tailwind, Recharts.
- Infra targets: Azure Container Apps, Azure API Management (Consumption), Azure Static Web Apps — all free-tier SKUs only.

## Hard rules
- **Never hardcode secrets or API keys.** Use `.env` locally and `.env.example` for placeholders. Read config through `app/config.py`.
- **Free tier only.** Do not generate code or scripts that provision paid Azure SKUs. If a paid resource seems required, stop and ask.
- **Human-in-the-loop:** agents must NOT auto-merge PRs or auto-rollback against a real repo. Generate draft PRs and require an explicit approval step.
- **Small, reviewable commits.** One logical change per commit with a clear message. Don't dump 30 files in one commit.
- **Tests alongside code.** Add pytest tests for services and API routes as you build them. The ML pipeline needs an eval step with metric gates.
- Keep the anomaly model's data prep, training, eval, and serving as separate, runnable scripts (this is the MLOps story — keep it clean).

## Conventions
- Folder structure follows the "Project Structure" section of the plan.
- Async everywhere in the API and DB layers.
- Structured logging (JSON) via `app/utils/logger.py`.
- Type-checked (mypy-friendly) and formatted (ruff/black).
- Every agent step emits an OpenTelemetry span (agent name, tool, tokens, latency).

## How to work with me
- At the end of each phase: summarize what was built, what's tested, and what's next. Then stop.
- If you're blocked or a decision isn't covered by the plan, ask a specific question rather than assuming.
- Prefer clarity over cleverness. This is a portfolio/interview project — the code should be readable and defensible.

## Git & GitHub workflow (do this autonomously — never ask me to run git manually)

Manage this repo yourself using `git` and the `gh` CLI, like a disciplined engineer.
For every unit of work, run this full loop:

1. Sync:        git checkout main && git pull --ff-only
2. Branch:      git checkout -b <descriptive>   (phase-1-ml-pipeline, feat/..., fix/...)
3. Build:       small commits, conventional-commit messages.
                Before EVERY commit, run local checks and fix failures first:
                  (cd backend && ruff check . && ruff format --check . && mypy app && pytest -q)
                  (cd ml && pytest -q)
4. Push:        git push -u origin <branch>
5. PR:          gh pr create --base main --fill   (body: what changed, why, how tested,
                which phase of docs/IMPLEMENTATION_PLAN.md it implements)
6. Auto-merge:  gh pr merge --auto --squash --delete-branch
                (GitHub merges only after required CI checks pass — let the gate work)
7. Re-sync main before starting the next task.

GUARDRAILS — never violate:
- Never force-push to main; never use --admin or bypass branch protection.
- Never merge a red build. If CI fails, fix on the same branch and push again.
- Never commit secrets or .env; respect .gitignore.
- One PR per logical slice; keep diffs reviewable.
- If a check fails 3 times, or a decision isn't covered by AGENTS.md or the plan, STOP and ask me.
