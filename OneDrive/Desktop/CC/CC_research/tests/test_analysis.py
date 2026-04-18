from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from raasa.analysis.metrics import compute_metrics, write_metrics_summary
from raasa.analysis.plots import build_plot_manifest


class AnalysisTests(unittest.TestCase):
    def test_compute_metrics_returns_core_fields(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {
                "container_id": "benign-1",
                "timestamp": now.isoformat(),
                "cpu": 10.0,
                "memory": 20.0,
                "new_tier": "L1",
                "reason": "hold",
                "metadata": {"workload_class": "benign", "expected_tier": "L1"},
            },
            {
                "container_id": "mal-1",
                "timestamp": (now + timedelta(seconds=5)).isoformat(),
                "cpu": 90.0,
                "memory": 40.0,
                "new_tier": "L3",
                "reason": "escalate",
                "metadata": {"workload_class": "malicious", "expected_tier": "L3"},
            },
        ]
        summary = compute_metrics(records)
        self.assertIn("precision", summary)
        self.assertIn("recall", summary)
        self.assertIn("tier_occupancy", summary)
        self.assertIn("containment_pressure", summary)
        self.assertIn("average_cpu_budget", summary)
        self.assertGreaterEqual(summary["explanation_coverage"], 1.0)

    def test_write_metrics_summary_outputs_json(self) -> None:
        path = Path("tests/sample_metrics.jsonl")
        path.write_text(
            json.dumps(
                {
                    "container_id": "c1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "cpu": 1.0,
                    "memory": 2.0,
                    "new_tier": "L1",
                    "reason": "hold",
                    "metadata": {"workload_class": "benign", "expected_tier": "L1"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            output = write_metrics_summary(path)
            self.assertTrue(output.exists())
        finally:
            path.unlink(missing_ok=True)
            Path("tests/sample_metrics.summary.json").unlink(missing_ok=True)

    def test_build_plot_manifest(self) -> None:
        manifest = build_plot_manifest(
            {
                "raasa": {
                    "precision": 0.9,
                    "switching_rate": 0.1,
                    "average_observed_load": 12.0,
                    "containment_pressure": 0.2,
                }
            }
        )
        self.assertIn("detection_comparison", manifest)
        self.assertIn("cost_comparison", manifest)


if __name__ == "__main__":
    unittest.main()
