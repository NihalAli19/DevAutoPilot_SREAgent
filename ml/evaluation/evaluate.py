"""Evaluate models on holdout; report precision/recall/F1/PR-AUC and enforce the gate."""
# TODO(plan: Phase 1) — compute metrics, compare models, FAIL if below gate threshold.

GATE_PR_AUC = 0.7  # placeholder gate; tune in Phase 1


def main():
    """Evaluate the candidate model and exit non-zero on metric regression."""
    raise NotImplementedError("TODO(plan: Phase 1)")


if __name__ == "__main__":
    main()
