import json
import joblib
import sys
from pathlib import Path
import numpy as np
from sklearn.ensemble import IsolationForest

def train_model(audit_path: str, output_model: str):
    data = []
    with open(audit_path, "r", encoding="utf-16") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                # Ensure all required features are present
                if all(k in record and record[k] is not None for k in ["f_cpu", "f_mem", "f_proc", "f_net", "f_sys"]):
                    data.append([
                        record["f_cpu"],
                        record["f_mem"],
                        record["f_proc"],
                        record["f_net"],
                        record["f_sys"]
                    ])
            except json.JSONDecodeError:
                pass

    if not data:
        print("No valid telemetry data found.")
        sys.exit(1)

    X = np.array(data)
    print(f"Training on {len(X)} telemetry records.")
    
    # Train Isolation Forest
    # contamination=0.1 means we expect 10% anomalies
    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    model.fit(X)

    joblib.dump(model, output_model)
    print(f"Model saved to {output_model}")

if __name__ == "__main__":
    base_dir = Path(__file__).parent
    audit_file = base_dir / "baseline_audit.jsonl"
    model_out = base_dir / "model.joblib"
    train_model(str(audit_file), str(model_out))
