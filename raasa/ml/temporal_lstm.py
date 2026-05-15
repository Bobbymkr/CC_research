from __future__ import annotations

import json
import logging
import argparse
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Any

import numpy as np

from raasa.ml.behavioral_dna import load_audit_records, record_to_vector

logger = logging.getLogger(__name__)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class TemporalLSTMDetector:
    """LSTM next-step detector for temporal feature sequence anomalies."""

    def __init__(
        self,
        sequence_length: int = 5,
        threshold: float = 0.05,
        model: Any | None = None,
    ) -> None:
        self.sequence_length = max(2, int(sequence_length))
        self.threshold = max(float(threshold), 1e-9)
        self.model = model

    def build_model(self, feature_count: int) -> Any:
        from tensorflow import keras

        model = keras.Sequential(
            [
                keras.layers.Input(shape=(self.sequence_length, feature_count)),
                keras.layers.LSTM(24),
                keras.layers.Dense(feature_count),
            ]
        )
        model.compile(optimizer="adam", loss="mse")
        return model

    def fit(
        self,
        sequences: np.ndarray,
        targets: np.ndarray,
        epochs: int = 8,
        batch_size: int = 16,
        verbose: int = 0,
    ) -> "TemporalLSTMDetector":
        if sequences.ndim != 3 or targets.ndim != 2:
            raise ValueError("sequences must be 3D and targets must be 2D")
        if len(sequences) == 0:
            raise ValueError("no sequences available for LSTM training")
        if self.model is None:
            self.model = self.build_model(sequences.shape[-1])
        self.model.fit(sequences, targets, epochs=epochs, batch_size=batch_size, verbose=verbose)
        errors = self.prediction_errors(sequences, targets)
        self.threshold = float(max(np.quantile(errors, 0.95), 1e-9))
        return self

    def prediction_errors(self, sequences: np.ndarray, targets: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("temporal LSTM model is not trained")
        predictions = self.model.predict(sequences, verbose=0)
        return np.mean(np.square(predictions - targets), axis=1)

    def anomaly_signal(self, sequence: Iterable[Iterable[float]], next_vector: Iterable[float]) -> float:
        if self.model is None:
            return 0.0
        sequence_array = np.asarray([list(list(row) for row in sequence)], dtype=float)
        target_array = np.asarray([list(next_vector)], dtype=float)
        if sequence_array.shape[1] != self.sequence_length:
            return 0.0
        error = float(self.prediction_errors(sequence_array, target_array)[0])
        if error <= self.threshold:
            return 0.0
        return _clamp((error - self.threshold) / max(self.threshold * 4.0, 1e-9))

    def save(self, model_path: str | Path) -> None:
        if self.model is None:
            raise ValueError("cannot save an untrained temporal LSTM model")
        path = Path(model_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save(path)
        metadata_path(path).write_text(
            json.dumps(
                {
                    "sequence_length": self.sequence_length,
                    "threshold": self.threshold,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, model_path: str | Path) -> "TemporalLSTMDetector":
        from tensorflow import keras

        path = Path(model_path)
        metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
        model = keras.models.load_model(path)
        return cls(
            sequence_length=int(metadata["sequence_length"]),
            threshold=float(metadata["threshold"]),
            model=model,
        )


def metadata_path(model_path: Path) -> Path:
    return model_path.with_suffix(model_path.suffix + ".metadata.json")


def build_sequences(
    records: Iterable[Mapping[str, object]],
    sequence_length: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        metadata = record.get("metadata", {})
        if isinstance(metadata, Mapping) and metadata.get("workload_class") == "malicious":
            continue
        container_id = str(record.get("container_id", "") or "unknown")
        grouped[container_id].append(record)

    sequences: list[list[list[float]]] = []
    targets: list[list[float]] = []
    for rows in grouped.values():
        rows.sort(key=lambda item: str(item.get("timestamp", "")))
        vectors = [record_to_vector(row) for row in rows]
        if len(vectors) <= sequence_length:
            continue
        for index in range(len(vectors) - sequence_length):
            sequences.append(vectors[index : index + sequence_length])
            targets.append(vectors[index + sequence_length])

    return np.asarray(sequences, dtype=float), np.asarray(targets, dtype=float)


def train_temporal_lstm(
    output_path: str | Path = "raasa/models/temporal_lstm.keras",
    log_dir: str | Path = "raasa/logs",
    sequence_length: int = 5,
    epochs: int = 8,
) -> TemporalLSTMDetector:
    records = load_audit_records(log_dir)
    sequences, targets = build_sequences(records, sequence_length=sequence_length)
    detector = TemporalLSTMDetector(sequence_length=sequence_length)
    detector.fit(sequences, targets, epochs=epochs)
    detector.save(output_path)
    logger.info("Saved temporal LSTM detector to %s", output_path)
    return detector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train RAASA temporal LSTM detector from audit logs.")
    parser.add_argument("--output-path", default="raasa/models/temporal_lstm.keras")
    parser.add_argument("--log-dir", default="raasa/logs")
    parser.add_argument("--sequence-length", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=8)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    train_temporal_lstm(
        output_path=args.output_path,
        log_dir=args.log_dir,
        sequence_length=args.sequence_length,
        epochs=args.epochs,
    )


if __name__ == "__main__":
    main()
