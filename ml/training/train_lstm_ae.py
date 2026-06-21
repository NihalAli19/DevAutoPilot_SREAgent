"""Train the LSTM-autoencoder detector and log the run to MLflow."""

from __future__ import annotations

from training.common import train_and_log
from training.lstm_ae import LSTMAutoencoderDetector


def main() -> None:
    det = LSTMAutoencoderDetector()
    metrics, _ = train_and_log(
        det, {"seq_len": det.seq_len, "hidden": det.hidden, "epochs": det.epochs}
    )
    print("lstm_autoencoder:", metrics)


if __name__ == "__main__":
    main()
