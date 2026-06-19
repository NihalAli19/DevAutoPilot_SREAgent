-- DevAutoPilot v2 — PostgreSQL schema
-- Every table carries org_id for multi-tenancy; scope all queries by tenant.
-- Vector retrieval lives in Azure AI Search (not pgvector); Postgres holds
-- relational + audit data only.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- incidents — one row per detected anomaly that became an incident.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    service         TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'P4',      -- P1..P4
    status          TEXT NOT NULL DEFAULT 'open',    -- open|investigating|mitigated|resolved|closed
    confidence      DOUBLE PRECISION,                -- model/agent confidence 0..1
    anomaly_score   DOUBLE PRECISION,                -- raw score from the anomaly model
    source          TEXT,                            -- webhook|simulate|monitor
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_incidents_org      ON incidents (org_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status   ON incidents (org_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_detected ON incidents (org_id, detected_at DESC);

-- ---------------------------------------------------------------------------
-- agent_actions — full, replayable audit trail of every agent step.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    incident_id     UUID REFERENCES incidents (id) ON DELETE CASCADE,
    agent_name      TEXT NOT NULL,                   -- monitoring|rca|patch|reliability|postmortem
    action          TEXT NOT NULL,
    tool            TEXT,                            -- tool/function invoked, if any
    status          TEXT NOT NULL DEFAULT 'started', -- started|succeeded|failed|skipped
    input           JSONB,
    output          JSONB,
    model           TEXT,                            -- model used (router decision)
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    latency_ms      INTEGER,
    trace_id        TEXT,                            -- OpenTelemetry trace id
    span_id         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_agent_actions_org      ON agent_actions (org_id);
CREATE INDEX IF NOT EXISTS idx_agent_actions_incident ON agent_actions (incident_id);
CREATE INDEX IF NOT EXISTS idx_agent_actions_trace    ON agent_actions (trace_id);

-- ---------------------------------------------------------------------------
-- root_cause_analyses — RCA agent output, one (or more) per incident.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS root_cause_analyses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    hypothesis      TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    affected_files  JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence        JSONB NOT NULL DEFAULT '[]'::jsonb,   -- RAG hits, commits, metrics
    model           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rca_org      ON root_cause_analyses (org_id);
CREATE INDEX IF NOT EXISTS idx_rca_incident ON root_cause_analyses (incident_id);

-- ---------------------------------------------------------------------------
-- patches — proposed fixes; always a draft PR, never auto-merged.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    rca_id          UUID REFERENCES root_cause_analyses (id) ON DELETE SET NULL,
    summary         TEXT NOT NULL,
    diff            TEXT,
    pr_url          TEXT,
    pr_number       INTEGER,
    branch          TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',   -- draft|proposed|approved|merged|rejected
    approved_by     TEXT,                            -- human-in-the-loop approver
    approved_at     TIMESTAMPTZ,
    model           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_patches_org      ON patches (org_id);
CREATE INDEX IF NOT EXISTS idx_patches_incident ON patches (incident_id);

-- ---------------------------------------------------------------------------
-- postmortems — final write-up; also embedded back into Azure AI Search.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS postmortems (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL,
    incident_id     UUID NOT NULL REFERENCES incidents (id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    summary         TEXT,
    timeline        JSONB NOT NULL DEFAULT '[]'::jsonb,
    root_cause      TEXT,
    resolution      TEXT,
    action_items    JSONB NOT NULL DEFAULT '[]'::jsonb,
    content         TEXT,                            -- full markdown
    embedded        BOOLEAN NOT NULL DEFAULT FALSE,  -- indexed into AI Search?
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_postmortems_org      ON postmortems (org_id);
CREATE INDEX IF NOT EXISTS idx_postmortems_incident ON postmortems (incident_id);

-- ---------------------------------------------------------------------------
-- telemetry — raw / feature-engineered metric points feeding the model.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetry (
    id              BIGSERIAL PRIMARY KEY,
    org_id          UUID NOT NULL,
    service         TEXT NOT NULL,
    metric          TEXT NOT NULL,                   -- latency_p95|error_rate|throughput|cpu|mem
    value           DOUBLE PRECISION NOT NULL,
    features        JSONB,                           -- engineered features for the model
    anomaly_score   DOUBLE PRECISION,
    is_anomaly      BOOLEAN,
    ts              TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_telemetry_org    ON telemetry (org_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_series ON telemetry (org_id, service, metric, ts DESC);

-- ---------------------------------------------------------------------------
-- model_runs — MLOps audit trail: versions, metrics, drift, deployment state.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL,
    model_name          TEXT NOT NULL,               -- isolation_forest|lstm_ae
    version             TEXT NOT NULL,
    dataset_hash        TEXT,
    metrics             JSONB NOT NULL DEFAULT '{}'::jsonb,  -- precision/recall/f1/pr_auc
    drift_scores        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- PSI/KS per feature
    deployment_status   TEXT NOT NULL DEFAULT 'registered',  -- registered|staging|production|archived
    passed_gate         BOOLEAN,
    mlflow_run_id       TEXT,
    trained_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_runs_org  ON model_runs (org_id);
CREATE INDEX IF NOT EXISTS idx_model_runs_name ON model_runs (org_id, model_name, created_at DESC);
