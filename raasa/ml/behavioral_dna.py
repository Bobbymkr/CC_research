from __future__ import annotations

import glob
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import joblib
import numpy as np
from sklearn.mixture import GaussianMixture

from raasa.core.models import FeatureVector

logger = logging.getLogger(__name__)

DNA_FEATURE_FIELDS: tuple[str, ...] = (
    "f_cpu",
    "f_mem",
    "f_proc",
    "f_net",
    "f_sys",
    "f_sys_jsd",
    "f_file_entropy",
    "f_network_entropy",
    "f_dns_entropy",
)


@dataclass(slots=True)
class BehavioralDNABaseline:
    image: str
    model: GaussianMixture
    mean_nll: float
    std_nll: float
    sample_count: int


class BehavioralDNARegistry:
    """Per-image Gaussian Mixture baselines for workload behavioral DNA."""

    def __init__(self, min_samples: int = 8, max_components: int = 2, random_state: int = 42) -> None:
        self.min_samples = max(2, int(min_samples))
        self.max_components = max(1, int(max_components))
        self.random_state = random_state
        self.baselines: dict[str, BehavioralDNABaseline] = {}

    def fit_records(self, records: Iterable[Mapping[str, object]]) -> int:
        grouped: dict[str, list[list[float]]] = {}
        for record in records:
            metadata = record.get("metadata", {})
            if isinstance(metadata, Mapping) and metadata.get("workload_class") == "malicious":
                continue
            image = image_fingerprint(metadata if isinstance(metadata, Mapping) else {})
            if not image:
                continue
            grouped.setdefault(image, []).append(record_to_vector(record))

        fitted = 0
        for image, vectors in grouped.items():
            if len(vectors) < self.min_samples:
                continue
            self.fit_image(image, np.asarray(vectors, dtype=float))
            fitted += 1
        return fitted

    def fit_image(self, image: str, vectors: np.ndarray) -> BehavioralDNABaseline:
        if vectors.ndim != 2 or vectors.shape[0] < self.min_samples:
            raise ValueError(f"need at least {self.min_samples} samples for image baseline")
        components = min(self.max_components, vectors.shape[0])
        model = GaussianMixture(
            n_components=components,
            covariance_type="full",
            reg_covar=1e-4,
            random_state=self.random_state,
        )
        model.fit(vectors)
        nll = -model.score_samples(vectors)
        baseline = BehavioralDNABaseline(
            image=image,
            model=model,
            mean_nll=float(np.mean(nll)),
            std_nll=float(max(np.std(nll), 1e-6)),
            sample_count=int(vectors.shape[0]),
        )
        self.baselines[image] = baseline
        return baseline

    def anomaly_signal(self, image: str, vector: Iterable[float]) -> float:
        baseline = self.baselines.get(image)
        if baseline is None:
            return 0.0
        sample = np.asarray([list(vector)], dtype=float)
        nll = float(-baseline.model.score_samples(sample)[0])
        z_score = max(0.0, (nll - baseline.mean_nll) / baseline.std_nll)
        return min(1.0, z_score / 6.0)

    def feature_anomaly_signal(self, feature: FeatureVector) -> tuple[float, str]:
        image = image_fingerprint(feature.telemetry_metadata)
        if not image:
            return 0.0, "behavioral_dna_image_missing"
        if image not in self.baselines:
            return 0.0, "behavioral_dna_baseline_missing"
        return self.anomaly_signal(image, feature_to_vector(feature)), "behavioral_dna_ok"

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, output_path)

    @classmethod
    def load(cls, path: str | Path) -> "BehavioralDNARegistry":
        loaded = joblib.load(path)
        if not isinstance(loaded, cls):
            raise TypeError(f"{path} does not contain a BehavioralDNARegistry")
        return loaded


def image_fingerprint(metadata: Mapping[str, object]) -> str:
    for key in ("image_sha", "image_id", "imageID", "image"):
        value = metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def record_to_vector(record: Mapping[str, object]) -> list[float]:
    return [float(record.get(field, 0.0) or 0.0) for field in DNA_FEATURE_FIELDS]


def feature_to_vector(feature: FeatureVector) -> list[float]:
    return [
        float(feature.cpu_signal),
        float(feature.memory_signal),
        float(feature.process_signal),
        float(feature.network_signal),
        float(feature.syscall_signal),
        float(feature.syscall_jsd_signal),
        float(feature.file_entropy_signal),
        float(feature.network_entropy_signal),
        float(feature.dns_entropy_signal),
    ]


def load_audit_records(log_dir: str | Path = "raasa/logs") -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in glob.glob(str(Path(log_dir) / "run_*.jsonl")):
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid audit record in %s", path)
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
    return records


def train_registry(
    output_path: str | Path = "raasa/models/behavioral_dna_registry.joblib",
    log_dir: str | Path = "raasa/logs",
    min_samples: int = 8,
    max_components: int = 2,
) -> BehavioralDNARegistry:
    registry = BehavioralDNARegistry(min_samples=min_samples, max_components=max_components)
    fitted = registry.fit_records(load_audit_records(log_dir))
    registry.save(output_path)
    logger.info("Saved %s behavioral DNA image baselines to %s", fitted, output_path)
    return registry


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    train_registry()
