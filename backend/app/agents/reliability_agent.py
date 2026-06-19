"""Reliability Guard Agent — monitors deploy health; Approve / Rollback / Escalate."""
# TODO(plan: Phase 3) — post-merge health checks behind a human-in-the-loop gate.


class ReliabilityAgent:
    """Guards rollouts; all production-affecting actions pass a HITL gate."""
