# DevAutoPilot v2 — Implementation Plan

> **An AI SRE Copilot that detects anomalies in service telemetry with a trained ML model, then runs a multi-agent workflow to diagnose, patch, guard, and document incidents — autonomously, with human-in-the-loop guardrails.**

**Positioning (the one-liner for your pitch):** "Datadog tells you *something broke*. DevAutoPilot tells you *what broke, why, and ships the fix as a reviewed PR* — combining a trained anomaly-detection model with a team of LLM agents."

**Category:** AI SRE / AIOps (comparable products: Cleric, Resolve.ai, Parity, Traversal). Saying you built in this category — and naming the competitors — is itself a credibility signal in interviews.

**Built to satisfy a real-world competency checklist.** Every architectural decision below maps to a specific hiring competency (see the matrix). This is deliberate: the project is designed so that, once built, you can truthfully claim each skill on a resume, in an interview, or on a client form.

---

## 1. Why v2 differs from v1 (read this first)

The original plan was an excellent agentic-DevOps demo, but it had three weaknesses for a *portfolio / pitch* piece:

1. **No real ML.** It used only LLM classification and *simulated* metrics. That leaves two of the most valuable hiring lines — "built ML models end-to-end" and "anomaly detection" — uncovered. v2 adds a genuine trained anomaly-detection model with a full MLOps lifecycle. This is the single biggest upgrade.
2. **Ignored your local-LLM experience.** v2 adds a hybrid local (Ollama) + cloud inference path, which doubles as a cost-control mechanism.
3. **Avoided Azure entirely** (to save cost), which conflicts with an Azure-heavy skill set. v2 puts the project back on Azure using only **free-tier / free-trial** SKUs, so you demonstrate the Azure skills at ~$0.

Everything good from v1 — the 5-agent design, the database schema, the API surface, the dark SRE dashboard — is preserved and extended.

---

## 2. Competency coverage matrix (the strategic core)

| Hiring competency (from the form) | Original answer | How v2 demonstrates it |
|:--|:--|:--|
| Microsoft Azure | 1 yr | Container Apps, Static Web Apps, Azure OpenAI, Key Vault, Monitor, AI Search |
| API Management in Azure | Yes | **Azure APIM (Consumption)** in front of the backend: subscription keys, rate-limit & quota policies, request transformation |
| Azure AI Search for RAG/vector | Yes | Incident knowledge base stored & queried in **Azure AI Search** (vector + hybrid search) |
| MLOps | 1 yr | Train→register→evaluate→deploy→monitor pipeline for the anomaly model; model registry; drift detection |
| CI/CD for ML models | Yes | GitHub Actions: retrain on data change/schedule, eval-metric gates block bad models, auto-deploy scoring endpoint |
| End-to-end AI architecture | Yes | The full system: ingestion → ML scoring → multi-agent reasoning → action → feedback loop |
| **ML models end-to-end (prep→deploy)** | **No → Yes** | Anomaly detector built from raw telemetry to a live endpoint, all stages owned |
| **Fraud / anomaly detection** | **No → Yes** | The detector is a time-series anomaly-detection system trained on a recognized benchmark |
| AI agents (Agentic AI) | Yes | 5-agent graph workflow on Microsoft Agent Framework 1.0 |
| GenAI expertise | 4/5 | LLM agents for RCA, patch synthesis, and postmortem writing; structured outputs; RAG |
| Local LLMs | 2 yr | Ollama inference path (Llama/Phi/Qwen) via Agent Framework's native Ollama connector |
| Python/ML proficiency | 4/5 | FastAPI, scikit-learn/PyTorch, MLflow, Pydantic, async services |

> **Ethics note:** the point is *not* to claim skills you don't have. It's to actually build the artifacts so the claims become true. After this project, "built an end-to-end anomaly-detection system with an MLOps pipeline" is a fact you can defend in a technical interview.

---

## 3. The two gap-closers, explained

### 3a. The anomaly-detection ML model (closes "end-to-end ML" + "anomaly detection")

**Problem framing:** detect anomalous behavior in service telemetry — request latency (p50/p95/p99), error rate, throughput, CPU/memory — and/or log-volume spikes, then hand confirmed anomalies to the agent pipeline.

**Data (use a recognized benchmark for credibility, not pure simulation):**
- **Numenta Anomaly Benchmark (NAB)** — labeled real-world time series, the standard reference for streaming anomaly detection. *(Recommended primary dataset.)*
- Alternatives: Server Machine Dataset (SMD), Yahoo Webscope S5, or KPI/AIOps challenge datasets.
- For the live demo, layer a synthetic generator that injects anomalies into a metrics stream so you can trigger incidents on demand.

**Modeling progression (show ML maturity by comparing approaches):**
1. **Baseline:** seasonal decomposition (STL) + dynamic thresholding, or a simple z-score/robust-MAD detector. Establishes a defensible floor.
2. **Classical ML:** Isolation Forest / One-Class SVM on engineered features (rolling stats, lags, seasonality features).
3. **Deep model:** LSTM autoencoder *or* a small Transformer time-series detector — reconstruction error as the anomaly score.
4. Report precision / recall / F1 / PR-AUC on labeled anomalies, and pick the model that wins on your eval — *the comparison itself signals senior judgment.*

**Serving:** expose the chosen model as a scoring endpoint. Two options:
- **Simple/free:** load the model in the FastAPI backend and serve `/score` directly.
- **Azure-native (stronger MLOps story):** deploy to an **Azure ML managed online endpoint** (uses trial credit) or containerize and run on Container Apps.

**Integration:** the **Monitoring Agent** calls the anomaly endpoint on incoming telemetry. The model flags *that* something is anomalous and how severe; the LLM then enriches and classifies *what kind*. This ML-gates-the-LLM pattern is current best practice (cheap deterministic filter before expensive generative reasoning) and reads as production-grade.

### 3b. The MLOps lifecycle (closes "MLOps" + "CI/CD for ML")

```
data (NAB + synthetic) 
   → feature engineering (versioned)
   → train (multiple models)
   → evaluate (PR-AUC / F1 on holdout, gate threshold)
   → register (MLflow Model Registry or Azure ML Registry)
   → deploy (online endpoint, blue/green)
   → monitor (data drift + prediction drift + latency)
   → drift/schedule triggers retrain  ──┐
        ▲                                │
        └────────────────────────────────┘
```

- **Experiment tracking & registry:** MLflow (free, self-host) or Azure ML.
- **CI/CD (GitHub Actions):** on data/code change or schedule → run training + eval → **fail the pipeline if metrics regress below the gate** → register & deploy the new version → smoke-test the endpoint. This "eval gate blocks deploy" pattern is exactly what "CI/CD for ML models" means to a hiring manager.
- **Monitoring:** log feature distributions + scores; compute drift (PSI / KS test) on a schedule; alert + optionally auto-trigger retrain. Surface drift on the dashboard.

---

## 4. Revised architecture (Azure free-tier centric)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DevAutoPilot v2 Architecture                       │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────┐        ┌──────────────────────────────────────┐  │
│  │ Next.js Dashboard   │        │  GitHub (Webhooks + API)             │  │
│  │ Azure Static Web    │◄──────►│  Source of truth for code            │  │
│  │ Apps / Vercel       │        └───────────────────┬──────────────────┘  │
│  └─────────┬───────────┘                            │                     │
│            │                                         │                     │
│            ▼                                         ▼                     │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │           Azure API Management (Consumption tier)                  │    │
│  │   keys · rate-limit · quota · request transform · 1M calls free    │    │
│  └────────────────────────────────┬─────────────────────────────────┘    │
│                                    ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │            FastAPI Backend (Azure Container Apps)                   │    │
│  │   /incidents /agents /dashboard /webhooks /simulate /score /ml      │    │
│  └───────────────┬───────────────────────────────────┬───────────────┘    │
│                  │                                     │                    │
│                  ▼                                     ▼                    │
│  ┌────────────────────────────────────┐   ┌────────────────────────────┐  │
│  │  Microsoft Agent Framework 1.0      │   │  Anomaly ML Service         │  │
│  │  (graph workflow + HITL gates)      │◄──│  Isolation Forest / LSTM-AE │  │
│  │  Monitor→RCA→Patch→Guard→Postmortem │   │  MLflow registry + drift    │  │
│  └───────────────┬─────────────────────┘   └────────────────────────────┘  │
│                  │                                                          │
│      ┌───────────┼───────────────┬───────────────────┐                     │
│      ▼           ▼               ▼                   ▼                      │
│ ┌─────────┐ ┌──────────┐ ┌───────────────┐ ┌──────────────────┐           │
│ │  LLM    │ │  Azure   │ │  Azure        │ │  GitHub API       │           │
│ │ routing │ │  Postgres│ │  AI Search    │ │  (PRs, commits,   │           │
│ │ local + │ │  Flexible│ │  (RAG vector  │ │   file contents)  │           │
│ │ cloud   │ │  Server  │ │   store)      │ │                   │           │
│ └────┬────┘ └──────────┘ └───────────────┘ └──────────────────┘           │
│      │                                                                     │
│  ┌───┴───────────────────────────┐                                        │
│  │ Ollama (local) · Azure OpenAI  │   Observability: OpenTelemetry →       │
│  │ · Gemini Flash · GitHub Models │   Azure Monitor / App Insights         │
│  └────────────────────────────────┘   Secrets: Azure Key Vault            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Free-tier cost table (verified June 2026 — confirm SKUs before provisioning)

| Component | Choice | Cost | Notes |
|:--|:--|:--|:--|
| Agent framework | Microsoft Agent Framework 1.0 (open source) | $0 | GA April 2026; `pip install agent-framework` |
| LLM — fast/private tasks | **Ollama** (Llama 3.x / Phi-4 / Qwen) | $0 | Local, unlimited; uses your local-LLM skill |
| LLM — heavy reasoning | Azure OpenAI (trial credit) **or** Gemini Flash (free API) | $0* | Gemini Flash is the most generous permanent free API |
| LLM — convenience fallback | GitHub Models | $0 | ~10 RPM / 50–150 RPD per model; demo-only |
| Embeddings | OpenAI `text-embedding-3-small` or local (e.g. `bge-small`) | ~$0 | Local embeddings keep it fully free |
| RAG vector store | **Azure AI Search (Free tier)** | $0 | 3 indexes, 50 MB, vector+hybrid; 1 free service/subscription |
| API gateway | **Azure API Management (Consumption)** | $0 | First 1M calls/month free, then ~$3.50/M |
| Backend hosting | Azure Container Apps (free grant) | $0 | Or Render free tier as fallback |
| Frontend hosting | Azure Static Web Apps (free) or Vercel Hobby | $0 | |
| Database | Azure PostgreSQL Flexible (12-mo free) or Cosmos DB free tier | $0 | Supabase free is a non-Azure fallback |
| Experiment tracking / registry | MLflow (self-host) or Azure ML | $0 | |
| Secrets | Azure Key Vault | ~$0 | Pennies at low op volume |
| Observability | Azure Monitor / App Insights (free cap) or OTel + Grafana | $0 | |
| CI/CD | GitHub Actions (free for public repos) | $0 | |
| **Total** | | **~$0** | Azure OpenAI is the only paid risk; Ollama/Gemini remove it |

> *Trial caveats:* the **$200 / 30-day Azure free-trial credit** and **12-month free services** require a *new* Azure account, and Microsoft adjusts terms periodically — check the Azure free-account page and set a **$0 spending cap** before provisioning. The *always-free* items (AI Search free tier, APIM's 1M free calls, Container Apps grant, GitHub Actions) keep the project alive at ~$0 after the trial ends. **Azure for Students** (~$100, no credit card) is worth checking if you qualify.

---

## 6. LLM routing strategy (hybrid local + cloud)

Route each agent task to the cheapest model that's good enough. This demonstrates cost-awareness *and* your local-LLM experience.

| Agent task | Default model | Rationale |
|:--|:--|:--|
| Monitoring (classify severity) | Local Ollama (Phi-4 / Llama 3.1 8B) | High volume, simple classification → keep it free & fast |
| RCA (root-cause reasoning) | Cloud frontier (Azure OpenAI / Gemini) | Deep reasoning over RAG context |
| Patch (code generation) | Cloud frontier | Strong codegen for accurate diffs |
| Reliability Guard (decision) | Local Ollama | Simple approve/rollback/escalate |
| Postmortem (report writing) | Local Ollama or cheap cloud | Templated generation |
| Embeddings | Local `bge-small` or `text-embedding-3-small` | RAG indexing |

Implement this as a single `LLMRouter` service with a config-driven map and automatic fallback (cloud → local on rate-limit/quota errors). Agent Framework's unified connector interface makes swapping providers a one-line change.

---

## 7. Agent design (refined, with guardrails)

Five agents on a **graph workflow** (Agent Framework's explicit multi-agent execution paths). Key additions vs v1 are in **bold**.

1. **Monitoring Agent** — receives telemetry/webhooks → **calls the anomaly ML endpoint** → if anomalous, LLM classifies type & severity (P1–P4) with a confidence score → dispatches structured incident. *(ML gates the LLM.)*
2. **RCA Agent (RAG)** — embeds the incident → vector search in **Azure AI Search** over past incidents/postmortems → pulls recent commits from GitHub → frontier LLM generates a ranked root-cause hypothesis with confidence and affected files.
3. **Patch Agent** — fetches current file content → generates a minimal diff → validates syntax → **opens a draft PR** (never auto-merges) linking incident + RCA + explanation.
4. **Reliability Guard Agent** — after a (human-approved) merge, monitors deploy health vs baseline → decides **Approve / Rollback / Escalate**. **All production-affecting actions pass a human-in-the-loop gate.**
5. **Postmortem Agent** — compiles the timeline → writes a structured postmortem → stores it → **embeds it back into Azure AI Search**, closing the learning loop so future RCAs get smarter.

**Maturity signals to build in (these separate a toy from a product):**
- **Human-in-the-loop gates** before any merge/rollback to a real repo. Autonomy with a kill-switch reads as senior; full auto-merge reads as naive.
- **Agent tracing** via OpenTelemetry — every agent step, tool call, token count, and latency captured and viewable in the dashboard.
- **Per-tenant token/cost budgets** enforced in the router.

---

## 8. Data layer & schema

Keep v1's schema (incidents, agent_actions, root_cause_analyses, patches, postmortems) and extend for production:

- **Multi-tenancy:** add `org_id` to every table; scope all queries by tenant.
- **New `telemetry` table:** raw/feature-engineered metric points feeding the anomaly model.
- **New `model_runs` table:** model version, dataset hash, eval metrics, deployment status, drift scores — your MLOps audit trail.
- **Vector store moves to Azure AI Search** (the `knowledge_base` pgvector table from v1 is replaced by an AI Search index with vector + hybrid retrieval). Keep Postgres for relational/audit data.

(Full DDL for the relational tables carries over from v1 with the `org_id` and new-table additions.)

---

## 9. API surface + APIM

Backend (FastAPI) keeps v1's endpoints and adds:

| Method | Endpoint | Purpose |
|:--|:--|:--|
| `POST` | `/api/score` | Score telemetry with the anomaly model |
| `GET` | `/api/ml/models` | List model versions + eval metrics + drift |
| `POST` | `/api/ml/retrain` | Trigger a retrain run |
| `GET` | `/api/agents/{incident_id}/trace` | OpenTelemetry agent trace |
| `POST` | `/api/incidents/{id}/approve` | Human-in-the-loop approval gate |

All of it sits behind **Azure APIM (Consumption)**: subscription keys per tenant, rate-limit and quota policies, and request/response transformation. This is your concrete "API Management in Azure" artifact.

---

## 10. SaaS-maturity layer (what makes it sellable, not just a demo)

- **Auth & tenancy:** Azure AD B2C (free tier) or Clerk/Supabase Auth (free); org-scoped data isolation.
- **Security:** GitHub webhook signature verification, secrets in **Azure Key Vault**, least-privilege GitHub tokens, RBAC on approval actions.
- **Evaluation harness:** a golden set of labeled incidents + LLM-as-judge scoring of RCA/patch quality, run in CI so agent changes can't silently regress. *(Evals-in-CI is a strong, current signal.)*
- **Observability:** OpenTelemetry traces + metrics → Azure Monitor; dashboards for agent latency, token spend, model drift.
- **Cost guardrails:** per-tenant token budgets, model-routing fallbacks, caching of embeddings/RCA results.
- **Audit log:** the `agent_actions` table already gives you a full, replayable audit trail — lean on it in the pitch (compliance teams love this).

---

## 11. Frontend (keep v1's design, add the new surfaces)

Premium dark SRE control center (Next.js, Tailwind, Framer Motion, Recharts). Pages:
1. **Dashboard** — live incident feed, stats, agent activity, **model-health & drift widget**.
2. **Incidents** — list + detail with the full agent timeline and **trace view**.
3. **Agents** — status of all five agents, workload, token/cost per run.
4. **ML / Models** — model versions, eval metrics, drift charts, retrain button. *(This page is your visible MLOps proof.)*
5. **Postmortems** — searchable archive.
6. **Simulate** — trigger anomalies/incidents on demand for live demos.

---

## 12. Phased roadmap (realistic, MVP-first)

Scope is large — build in slices so you always have something demo-able.

**Phase 0 — Foundations (set up cheap, fail fast)**
Repo, Azure account + $0 spend cap, FastAPI skeleton, Postgres, GitHub Actions hello-world, Ollama running locally.

**Phase 1 — The ML core (your differentiator; do this early)**
NAB data → feature pipeline → train Isolation Forest + LSTM-AE → eval → MLflow registry → `/score` endpoint → CI training+eval gate. **At the end of Phase 1 you can already claim end-to-end ML + anomaly detection + MLOps + CI/CD-for-ML.** Prioritize this.

**Phase 2 — Single-agent vertical slice**
Monitoring Agent → anomaly score → LLM classify → store incident → show on dashboard. Proves the ML-gates-LLM pattern end to end.

**Phase 3 — Full agent graph + RAG**
Add RCA (Azure AI Search RAG), Patch (draft PR), Guard (with HITL gate), Postmortem (feedback loop). Agent Framework graph workflow + tracing.

**Phase 4 — Azure productionization**
Container Apps deploy, APIM in front, Key Vault, Static Web Apps frontend, Azure Monitor.

**Phase 5 — SaaS polish & pitch**
Auth + multi-tenancy, eval harness in CI, drift monitoring UI, demo script, README, architecture docs, short Loom walkthrough.

**Sequencing tip:** if your deadline is tight, ship **Phase 1 + 2 + a minimal Phase 3** first — that already covers *every* "No" gap and most of the matrix. Phases 4–5 raise it from "strong portfolio project" to "looks like a real product."

---

## 13. How to pitch it (turn the build into career capital)

**Resume/LinkedIn bullet template:**
> Built DevAutoPilot, an AI SRE platform combining a trained time-series **anomaly-detection model** (LSTM-autoencoder, deployed via an **MLOps pipeline** with CI/CD eval gates and drift monitoring) with a **5-agent LLM workflow** (Microsoft Agent Framework) that performs RAG-based root-cause analysis (**Azure AI Search**), generates fix PRs, and auto-writes postmortems. Deployed on **Azure** (Container Apps, **API Management**, Azure OpenAI) with hybrid local-LLM (Ollama) inference for cost control.

**Interview talking points (each maps to a competency):**
- *"Walk me through an ML model you shipped end to end."* → the anomaly detector: data choice (NAB), why you compared three approaches, the eval gate, drift monitoring.
- *"Have you done MLOps / CI-CD for ML?"* → the GitHub Actions pipeline that blocks deploys on metric regression.
- *"Tell me about an agentic system."* → the graph workflow, HITL guardrails, and the ML-gates-LLM cost pattern.
- *"How do you control LLM cost in production?"* → the router: local-first, cloud for reasoning, budgets, caching, fallback.
- *"Azure experience?"* → APIM policies, AI Search vector index, Container Apps, Key Vault.

**Publish it:** public GitHub repo with a great README + architecture diagram, a 3-minute demo video, and a short write-up/blog on the ML-gates-LLM pattern. The write-up is often what gets you noticed.

---

## 14. Decision points (defaults chosen so you're not blocked)

| Question | Recommended default | Change if… |
|:--|:--|:--|
| Demo target repo | Create a small intentionally-buggy sample app repo | You already have a repo to break safely |
| Cloud LLM provider | Gemini Flash (free) for dev; Azure OpenAI (trial) for the "Azure" demo | You have OpenAI credits you'd rather use |
| Database | Azure PostgreSQL Flexible (12-mo free) | You want zero-Azure storage → Supabase free |
| Vector store | Azure AI Search free tier (covers the skill) | — keep this, it's a listed competency |
| Anomaly dataset | NAB + synthetic injector | You have your own telemetry to use |
| Deadline | Phase 1+2+minimal 3 first | Plenty of time → do all 5 phases |
| Embeddings | Local `bge-small` (fully free) | You want to showcase OpenAI embeddings |

---

*Built to be true, not just impressive: finish it and every line on that competency form becomes something you can defend in a room.*
