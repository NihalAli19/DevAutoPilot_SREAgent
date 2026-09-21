"""Test: the best learned model gets registered in the MLflow Model Registry."""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import torch


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


def test_register_lstm_supplies_valid_pt2_input_example(monkeypatch):
    import mlflow
    import mlflow.pytorch
    import training.register_best as register_module
    from training.lstm_ae import _LSTMAutoencoder

    n_features = 3
    seq_len = 5
    model = _LSTMAutoencoder(n_features=n_features, hidden=4, latent=2)
    lstm = SimpleNamespace(
        name="lstm_autoencoder",
        model=model,
        seq_len=seq_len,
        cols=["value", "rolling_mean", "lag_1"],
    )
    isolation_forest = SimpleNamespace(name="isolation_forest", model=object())
    fitted = [
        (isolation_forest, {"pr_auc": 0.4}),
        (lstm, {"pr_auc": 0.8}),
    ]
    captured: dict = {}

    monkeypatch.setattr(
        register_module,
        "train_all",
        lambda **_kwargs: (fitted, {}, False),
    )
    monkeypatch.setattr(register_module, "configure_mlflow", lambda: None)
    monkeypatch.setattr(mlflow, "start_run", lambda **_kwargs: nullcontext())
    monkeypatch.setattr(mlflow, "log_params", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mlflow, "log_metrics", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        mlflow.pytorch,
        "log_model",
        lambda pytorch_model, **kwargs: captured.update(model=pytorch_model, **kwargs),
    )

    name, _metrics = register_module.register_best(use_real=False, lstm_epochs=1)

    example = captured["input_example"]
    assert name == "lstm_autoencoder"
    assert captured["model"] is model
    assert captured["serialization_format"] == "pt2"
    assert example.dtype == np.float32
    assert example.shape == (1, seq_len, n_features)
    assert captured["signature"].inputs.inputs[0].shape == (1, seq_len, n_features)
    assert model(torch.from_numpy(example)).shape == torch.Size(
        (1, seq_len, n_features)
    )


def test_lstm_pt2_artifact_exports(tmp_path):
    import mlflow.pytorch

    from training.lstm_ae import _LSTMAutoencoder
    from training.register_best import _lstm_export_contract

    seq_len = 5
    n_features = 3
    model = _LSTMAutoencoder(n_features=n_features, hidden=4, latent=2)
    example, signature = _lstm_export_contract(seq_len, n_features)

    mlflow.pytorch.save_model(
        model,
        tmp_path / "model",
        input_example=example,
        signature=signature,
        serialization_format="pt2",
        pip_requirements=[],
    )
