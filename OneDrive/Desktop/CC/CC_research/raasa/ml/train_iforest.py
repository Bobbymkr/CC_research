import glob
import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_training_data(log_dir: str = "raasa/logs") -> np.ndarray:
    patterns = [str(Path(log_dir) / "run_*.jsonl")]
    all_files = []
    for p in patterns:
        all_files.extend(glob.glob(p))

    if not all_files:
        logging.warning("No log files found for training.")
        return np.array([])

    benign_vectors = []
    for path in all_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    # Train normal behavior only on benign samples
                    metadata = record.get("metadata", {})
                    # If there's no metadata, or it's implicitly benign, keep it. But explicitly malicious we skip.
                    if metadata.get("workload_class") != "malicious":
                        vec = [
                            record.get("f_cpu", 0.0) or 0.0,
                            record.get("f_mem", 0.0) or 0.0,
                            record.get("f_proc", 0.0) or 0.0,
                            record.get("f_net", 0.0) or 0.0,
                            record.get("f_sys", 0.0) or 0.0,  # 5th dim: syscall signal
                        ]
                        benign_vectors.append(vec)
        except Exception as e:
            logging.error(f"Failed parsing {path}: {e}")

    X = np.array(benign_vectors)
    logging.info(f"Loaded {len(X)} benign records for training.")
    return X


def train(output_path: str = "raasa/models/iforest_latest.pkl", log_dir: str = "raasa/logs") -> None:
    X = load_training_data(log_dir)
    if len(X) == 0:
        logging.error("No training data. Exiting.")
        return

    # Contamination defines the expected ratio of outliers in our training set.
    # Since we train purely on benign labeled data, contamination should be very small.
    # IForest is sensitive to this boundary.
    logging.info("Training Isolation Forest...")
    model = IsolationForest(
        n_estimators=100,
        max_samples="auto",
        contamination=0.01,
        random_state=42,
    )
    model.fit(X)

    # Save model
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_file)
    logging.info(f"Saved trained Isolation Forest to {out_file}")


if __name__ == "__main__":
    train()
