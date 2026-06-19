# ML — Anomaly Detection Pipeline

The MLOps story for DevAutoPilot: detect anomalies in service telemetry (latency, error rate, throughput, CPU/memory) and hand confirmed anomalies to the agent workflow. **ML gates the LLM** — a cheap deterministic detector runs before expensive generative reasoning.

## Lifecycle

```
data (NAB + synthetic) -> features -> train (IF + LSTM-AE)
  -> evaluate (PR-AUC / F1 gate) -> register (MLflow) -> serve (/score) -> monitor (drift)
```

Each stage is a **separate, runnable script** — that is the clean MLOps story. Keep data prep, training, eval, and serving independent.

## Layout

```
data/         loader (NAB) + synthetic anomaly injector
features/     versioned feature engineering (rolling stats, lags, seasonality)
training/     train_isolation_forest.py, train_lstm_ae.py
evaluation/   evaluate.py — metrics + gate threshold
serving/      predict.py — load model, score telemetry
tests/        pipeline smoke tests
```

## Datasets

- **Primary:** Numenta Anomaly Benchmark (NAB) — labeled real-world streaming time series.
- **Demo:** synthetic generator that injects anomalies on demand.

## Status

**Phase 1** (the differentiator) implements this end to end. Modules here are stubs marked `# TODO(plan: Phase 1)`.

## Run (once implemented)

```bash
cd ml
pip install -r requirements.txt
python -m training.train_isolation_forest
python -m evaluation.evaluate
```
