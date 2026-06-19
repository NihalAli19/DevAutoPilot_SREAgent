# Demo

A small, **intentionally-buggy** sample app to break safely, plus a script to trigger incidents on demand for live demos.

## Files

- `faulty_app/app.py` — a tiny FastAPI service with deliberate fault toggles (latency spikes, error bursts). The Patch Agent's target in later phases.
- `faulty_app/requirements.txt` — its dependencies.
- `simulate_incident.py` — drives anomalous telemetry / triggers an incident against the backend.

## Usage

```bash
# 1. Run the faulty app
cd demo/faulty_app
pip install -r requirements.txt
uvicorn app:app --port 9000 --reload

# 2. From another shell, trigger an incident
cd demo
python simulate_incident.py
```

## Status

**Phase 2** wires the simulator to the Monitoring Agent. These are Phase 0 placeholders.
