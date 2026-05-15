from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import unittest

import numpy as np

from raasa.core.models import FeatureVector
from raasa.core.risk_model import RiskAssessor
from raasa.ml.temporal_lstm import TemporalLSTMDetector, build_sequences


class TemporalLSTMTests(unittest.TestCase):
    def test_build_sequences_groups_by_container_and_skips_malicious(self) -> None:
        records = []
        for index in range(6):
            records.append(
                {
                    "container_id": "c1",
                    "timestamp": f"2026-05-15T00:00:0{index}Z",
                    "metadata": {"workload_class": "benign"},
                    "f_cpu": index / 10.0,
                }
            )
        records.append(
            {
                "container_id": "c1",
                "timestamp": "2026-05-15T00:00:09Z",
                "metadata": {"workload_class": "malicious"},
                "f_cpu": 1.0,
            }
        )

        sequences, targets = build_sequences(records, sequence_length=3)

        self.assertEqual(sequences.shape, (3, 3, 9))
        self.assertEqual(targets.shape, (3, 9))
        self.assertAlmostEqual(targets[-1][0], 0.5)

    def test_risk_assessor_uses_temporal_lstm_after_warmup(self) -> None:
        class FakeTemporalDetector:
            sequence_length = 2

            def anomaly_signal(self, sequence, next_vector):
                self.last_sequence = sequence
                self.last_next = next_vector
                return 0.80

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
        assessor = RiskAssessor(weights=zero_weights)
        assessor.temporal_lstm = FakeTemporalDetector()

        now = datetime.now(timezone.utc)
        samples = [
            FeatureVector("c1", now, 0.1, 0.1, 0.1),
            FeatureVector("c1", now, 0.2, 0.2, 0.2),
            FeatureVector("c1", now, 0.9, 0.9, 0.9),
        ]

        first = assessor.assess([samples[0]])[0]
        second = assessor.assess([samples[1]])[0]
        third = assessor.assess([samples[2]])[0]

        self.assertIn("temporal_lstm=0.00:temporal_lstm_warming", first.reasons)
        self.assertIn("temporal_lstm=0.00:temporal_lstm_warming", second.reasons)
        self.assertEqual(third.risk_score, 0.80)
        self.assertIn("temporal_lstm=0.80:temporal_lstm_ok", third.reasons)

    @unittest.skipUnless(importlib.util.find_spec("tensorflow") is not None, "tensorflow unavailable")
    def test_detector_training_smoke(self) -> None:
        rng = np.random.default_rng(42)
        sequences = rng.uniform(0.0, 0.2, size=(8, 2, 9))
        targets = rng.uniform(0.0, 0.2, size=(8, 9))
        detector = TemporalLSTMDetector(sequence_length=2)

        detector.fit(sequences, targets, epochs=1, batch_size=4)
        signal = detector.anomaly_signal(sequences[0], targets[0])

        self.assertGreaterEqual(signal, 0.0)
        self.assertLessEqual(signal, 1.0)


if __name__ == "__main__":
    unittest.main()
