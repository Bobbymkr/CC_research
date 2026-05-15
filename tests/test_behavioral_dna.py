from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
import unittest

import numpy as np

from raasa.core.models import FeatureVector
from raasa.core.risk_model import RiskAssessor
from raasa.ml.behavioral_dna import BehavioralDNARegistry, feature_to_vector


class BehavioralDNARegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests/.tmp_behavioral_dna")
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _records(self, image: str = "nginx@sha256:abc") -> list[dict[str, object]]:
        rng = np.random.default_rng(7)
        records: list[dict[str, object]] = []
        for row in rng.normal(0.10, 0.01, size=(12, 9)):
            records.append(
                {
                    "metadata": {"image": image, "workload_class": "benign"},
                    "f_cpu": float(row[0]),
                    "f_mem": float(row[1]),
                    "f_proc": float(row[2]),
                    "f_net": float(row[3]),
                    "f_sys": float(row[4]),
                    "f_sys_jsd": float(row[5]),
                    "f_file_entropy": float(row[6]),
                    "f_network_entropy": float(row[7]),
                    "f_dns_entropy": float(row[8]),
                }
            )
        records.append(
            {
                "metadata": {"image": image, "workload_class": "malicious"},
                "f_cpu": 0.99,
                "f_mem": 0.99,
                "f_proc": 0.99,
                "f_net": 0.99,
                "f_sys": 0.99,
            }
        )
        return records

    def test_fits_per_image_gmm_and_scores_far_sample_higher(self) -> None:
        registry = BehavioralDNARegistry(min_samples=6, max_components=1)
        fitted = registry.fit_records(self._records())

        near = [0.10] * 9
        far = [0.90] * 9

        self.assertEqual(fitted, 1)
        self.assertLess(registry.anomaly_signal("nginx@sha256:abc", near), 0.5)
        self.assertGreater(registry.anomaly_signal("nginx@sha256:abc", far), 0.9)

    def test_registry_round_trips_through_joblib(self) -> None:
        registry = BehavioralDNARegistry(min_samples=6, max_components=1)
        registry.fit_records(self._records())
        model_path = self.tmp_dir / "behavioral_dna.joblib"

        registry.save(model_path)
        loaded = BehavioralDNARegistry.load(model_path)

        self.assertIn("nginx@sha256:abc", loaded.baselines)

    def test_risk_assessor_uses_behavioral_dna_when_configured(self) -> None:
        registry = BehavioralDNARegistry(min_samples=6, max_components=1)
        registry.fit_records(self._records())
        model_path = self.tmp_dir / "behavioral_dna.joblib"
        registry.save(model_path)
        zero_weights = {
            "cpu": 0.0,
            "memory": 0.0,
            "process": 0.0,
            "network": 0.0,
            "syscall": 0.0,
            "syscall_jsd": 0.0,
            "file_entropy": 0.0,
            "network_entropy": 0.0,
            "dns_entropy": 0.0,
        }
        assessor = RiskAssessor(
            weights=zero_weights,
            use_behavioral_dna=True,
            behavioral_dna_path=str(model_path),
        )
        feature = FeatureVector(
            container_id="c1",
            timestamp=datetime.now(timezone.utc),
            cpu_signal=0.90,
            memory_signal=0.90,
            process_signal=0.90,
            network_signal=0.90,
            syscall_signal=0.90,
            syscall_jsd_signal=0.90,
            file_entropy_signal=0.90,
            network_entropy_signal=0.90,
            dns_entropy_signal=0.90,
            telemetry_metadata={"image": "nginx@sha256:abc"},
        )

        result = assessor.assess([feature])[0]

        self.assertGreater(result.risk_score, 0.9)
        self.assertTrue(any(reason.startswith("behavioral_dna=") for reason in result.reasons))
        self.assertEqual(len(feature_to_vector(feature)), 9)

    def test_feature_signal_falls_back_to_image_when_digest_baseline_missing(self) -> None:
        registry = BehavioralDNARegistry(min_samples=6, max_components=1)
        registry.fit_records(self._records(image="ubuntu:24.04"))

        signal, status = registry.feature_anomaly_signal(
            FeatureVector(
                container_id="c1",
                timestamp=datetime.now(timezone.utc),
                cpu_signal=0.90,
                memory_signal=0.90,
                process_signal=0.90,
                network_signal=0.90,
                syscall_signal=0.90,
                syscall_jsd_signal=0.90,
                file_entropy_signal=0.90,
                network_entropy_signal=0.90,
                dns_entropy_signal=0.90,
                telemetry_metadata={
                    "image_id": "docker-pullable://ubuntu@sha256:missing-from-registry",
                    "image": "ubuntu:24.04",
                },
            )
        )

        self.assertEqual(status, "behavioral_dna_ok")
        self.assertGreater(signal, 0.9)


if __name__ == "__main__":
    unittest.main()
