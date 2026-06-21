"""Deep detector: an LSTM autoencoder whose reconstruction error is the score.

Sequences of standardized features are encoded to a latent vector and decoded back;
windows the model reconstructs poorly are anomalous. Kept separate from the classical
detectors so the torch dependency stays isolated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn

from config import CONFIG, MLConfig
from features.engineering import feature_columns


class _LSTMAutoencoder(nn.Module):
    def __init__(self, n_features: int, hidden: int, latent: int) -> None:
        super().__init__()
        self.encoder = nn.LSTM(n_features, hidden, batch_first=True)
        self.to_latent = nn.Linear(hidden, latent)
        self.from_latent = nn.Linear(latent, hidden)
        self.decoder = nn.LSTM(hidden, hidden, batch_first=True)
        self.output = nn.Linear(hidden, n_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        seq_len = x.shape[1]
        _, (h, _) = self.encoder(x)
        latent = self.to_latent(h[-1])
        repeated = self.from_latent(latent).unsqueeze(1).repeat(1, seq_len, 1)
        decoded, _ = self.decoder(repeated)
        return self.output(decoded)


class LSTMAutoencoderDetector:
    """LSTM-autoencoder detector (reconstruction error -> anomaly score)."""

    name = "lstm_autoencoder"

    def __init__(
        self,
        config: MLConfig = CONFIG,
        seq_len: int = 32,
        hidden: int = 32,
        latent: int = 16,
        epochs: int = 12,
        lr: float = 1e-3,
        batch_size: int = 128,
    ) -> None:
        self.config = config
        self.cols = feature_columns(config)
        self.seq_len = seq_len
        self.hidden = hidden
        self.latent = latent
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.scaler = StandardScaler()
        self.model: _LSTMAutoencoder | None = None

    def _windows(self, x: np.ndarray, seq_len: int) -> np.ndarray:
        n = len(x)
        idx = np.arange(seq_len)[None, :] + np.arange(n - seq_len + 1)[:, None]
        return x[idx]  # (num_windows, seq_len, n_features)

    def _effective_seq_len(self, n: int) -> int:
        return max(2, min(self.seq_len, n - 1))

    def fit(self, train: pd.DataFrame) -> LSTMAutoencoderDetector:
        torch.manual_seed(self.config.seed)
        x = self.scaler.fit_transform(train[self.cols]).astype(np.float32)
        seq_len = self._effective_seq_len(len(x))
        windows = torch.from_numpy(self._windows(x, seq_len))

        self.model = _LSTMAutoencoder(x.shape[1], self.hidden, self.latent)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        self.model.train()
        for _ in range(self.epochs):
            perm = torch.randperm(len(windows))
            for start in range(0, len(windows), self.batch_size):
                batch = windows[perm[start : start + self.batch_size]]
                opt.zero_grad()
                loss = loss_fn(self.model(batch), batch)
                loss.backward()
                opt.step()
        return self

    def score(self, df: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("LSTMAutoencoderDetector must be fit before scoring")
        x = self.scaler.transform(df[self.cols]).astype(np.float32)
        n = len(x)
        seq_len = self._effective_seq_len(n)
        windows = torch.from_numpy(self._windows(x, seq_len))

        self.model.eval()
        with torch.no_grad():
            recon = self.model(windows)
            err = ((recon - windows) ** 2).mean(dim=(1, 2)).numpy()  # per window

        # Assign each window's error to its last row; back-fill the warm-up rows.
        scores = np.empty(n, dtype=float)
        scores[seq_len - 1 :] = err
        scores[: seq_len - 1] = err[0]
        return scores
