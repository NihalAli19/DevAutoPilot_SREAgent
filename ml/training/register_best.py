"""Register the best trained model in the MLflow Model Registry (the CD step).

Trains the candidates, picks the best *learned* model by PR-AUC (the z-score
baseline is the reference floor, not a registry candidate), and registers it under
a single named model so downstream/Phase-4 deploy can pull a versioned artifact.
"""

from __future__ import annotations

import math

from config import CONFIG
from evaluation.evaluate import Metrics, pick_best, train_all
from training.common import configure_mlflow

REGISTERED_NAME = "devautopilot-anomaly"
# Only trained models are registry candidates; the baseline is the reference floor.
LEARNED_MODELS = {"isolation_forest", "lstm_autoencoder"}


def register_best(
    registered_name: str = REGISTERED_NAME, lstm_epochs: int = 12, use_real: bool = True
) -> tuple[str, Metrics]:
    """Train, pick the best learned model by PR-AUC, and register it in MLflow."""
    import mlflow
    import mlflow.pytorch
    import mlflow.sklearn

    configure_mlflow()
    fitted, _summary, real_nab = train_all(use_real=use_real, lstm_epochs=lstm_epochs)
    learned = {det.name: (det, m) for det, m in fitted if det.name in LEARNED_MODELS}
    results = {name: m for name, (_det, m) in learned.items()}
    best_name = pick_best(results)
    best_det, best_metrics = learned[best_name]

    with mlflow.start_run(run_name=f"register-{best_name}"):
        mlflow.log_params(
            {
                "model": best_name,
                "feature_version": CONFIG.feature_version,
                "real_nab": real_nab,
            }
        )
        mlflow.log_metrics({k: v for k, v in best_metrics.items() if not math.isnan(v)})
        if best_name == "isolation_forest":
            mlflow.sklearn.log_model(
                best_det.model, name="model", registered_model_name=registered_name
            )
        else:
            mlflow.pytorch.log_model(
                best_det.model, name="model", registered_model_name=registered_name
            )
    return best_name, best_metrics


def main() -> None:
    name, metrics = register_best()
    print(
        f"Registered best model '{name}' as '{REGISTERED_NAME}' | PR-AUC {metrics['pr_auc']:.3f}"
    )


if __name__ == "__main__":
    main()
