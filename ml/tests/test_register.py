"""Test: the best learned model gets registered in the MLflow Model Registry."""

from __future__ import annotations


def test_register_best_creates_a_registry_version():
    import mlflow

    from training.common import configure_mlflow
    from training.register_best import REGISTERED_NAME, register_best

    name, metrics = register_best(use_real=False, lstm_epochs=2)
    assert name in {"isolation_forest", "lstm_autoencoder"}
    assert "pr_auc" in metrics

    configure_mlflow()
    versions = mlflow.MlflowClient().search_model_versions(f"name='{REGISTERED_NAME}'")
    assert len(versions) >= 1
