"""Classical anomaly detectors with a shared fit/score interface.

Each detector consumes an engineered feature frame (from ``features.engineering``)
and returns a per-row anomaly score where **higher = more anomalous**. The deep
LSTM-autoencoder lives in ``training.lstm_ae`` to keep the torch import isolated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from config import CONFIG, MLConfig
from features.engineering import feature_columns


class RobustZScoreDetector:
    """Baseline: rolling robust z-score (median/MAD) on the raw ``value`` series.

    Unsupervised and training-free — establishes a defensible floor the learned
    models must beat.
    """

    name = "robust_zscore"

    def __init__(self, window: int = CONFIG.rolling_windows[-1]) -> None:
        self.window = window

    def fit(self, train: pd.DataFrame) -> RobustZScoreDetector:  # noqa: ARG002
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        v = df["value"].astype(float)
        med = v.rolling(self.window, min_periods=1).median()
        mad = (v - med).abs().rolling(self.window, min_periods=1).median()
        scale = (1.4826 * mad).replace(0.0, np.nan)
        z = ((v - med) / scale).abs().fillna(0.0)
        return z.to_numpy()


class IsolationForestDetector:
    """Classical ML: Isolation Forest on standardized engineered features."""

    name = "isolation_forest"

    def __init__(self, config: MLConfig = CONFIG, n_estimators: int = 200) -> None:
        self.cols = feature_columns(config)
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=n_estimators,
            contamination="auto",
            random_state=config.seed,
            n_jobs=-1,
        )

    def fit(self, train: pd.DataFrame) -> IsolationForestDetector:
        self.model.fit(self.scaler.fit_transform(train[self.cols]))
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        # score_samples: higher = more normal -> negate so higher = more anomalous.
        return -self.model.score_samples(self.scaler.transform(df[self.cols]))
