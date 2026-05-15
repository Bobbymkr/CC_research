from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from raasa.analysis.metrics import (
    compute_grouped_metrics,
    compute_metrics,
    write_grouped_metrics_summary,
    write_metrics_summary,
)
from raasa.analysis.overhead import summarize_overhead_report
from raasa.analysis.plots import build_plot_manifest, plot_tier_trajectory


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
                "controller_variant": "linear_tuned",
                "metadata": {"workload_class": "benign", "expected_tier": "L1"},
            },
            {
                "container_id": "mal-1",
                "timestamp": (now + timedelta(seconds=5)).isoformat(),
                "cpu": 90.0,
                "memory": 40.0,
                "new_tier": "L3",
                "reason": "escalate",
                "controller_variant": "linear_tuned",
                "metadata": {"workload_class": "malicious", "expected_tier": "L3"},
            },
        ]
        summary = compute_metrics(records)
        self.assertEqual(summary["controller_variant"], "linear_tuned")
        self.assertIn("precision", summary)
        self.assertIn("recall", summary)
        self.assertIn("tier_occupancy", summary)
        self.assertIn("containment_pressure", summary)
        self.assertIn("average_cpu_budget", summary)
        self.assertIn("strict_malicious_containment_rate", summary)
        self.assertIn("expected_tier_hit_rate", summary)
        self.assertGreaterEqual(summary["explanation_coverage"], 1.0)

    def test_strict_metrics_expose_l2_when_l3_was_expected(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {
                "container_id": "mal-1",
                "timestamp": now.isoformat(),
                "cpu": 80.0,
                "memory": 20.0,
                "new_tier": "L2",
                "reason": "contained but not strict",
                "metadata": {"workload_class": "malicious", "expected_tier": "L3"},
            }
        ]

        summary = compute_metrics(records)

        self.assertEqual(summary["recall"], 1.0)
        self.assertEqual(summary["malicious_containment_rate"], 1.0)
        self.assertEqual(summary["strict_malicious_containment_rate"], 0.0)
        self.assertEqual(summary["expected_tier_hit_rate"], 0.0)
        self.assertEqual(summary["security_expected_tier_hit_rate"], 0.0)
        self.assertEqual(summary["under_containment_events"], 1)

    def test_under_containment_ignores_benign_expected_l2_labels(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {
                "container_id": "bursty-1",
                "timestamp": now.isoformat(),
                "cpu": 5.0,
                "memory": 5.0,
                "new_tier": "L1",
                "reason": "quiet benign burst window",
                "metadata": {"workload_class": "benign", "expected_tier": "L2"},
            }
        ]

        summary = compute_metrics(records)

        self.assertEqual(summary["expected_tier_hit_rate"], 0.0)
        self.assertEqual(summary["security_expected_tier_hit_rate"], 0.0)
        self.assertEqual(summary["under_containment_events"], 0)
        self.assertEqual(summary["under_containment_rate"], 0.0)

    def test_compute_metrics_supports_alternate_tier_field(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {
                "container_id": "mal-1",
                "timestamp": now.isoformat(),
                "cpu": 95.0,
                "memory": 40.0,
                "new_tier": "L1",
                "proposed_tier": "L3",
                "reason": "detect only",
                "metadata": {"workload_class": "malicious", "expected_tier": "L3"},
            }
        ]
        applied_summary = compute_metrics(records)
        proposed_summary = compute_metrics(records, tier_field="proposed_tier")
        self.assertEqual(applied_summary["recall"], 0.0)
        self.assertEqual(proposed_summary["recall"], 1.0)
        self.assertEqual(proposed_summary["tier_field"], "proposed_tier")

    def test_compute_grouped_metrics_by_workload_key(self) -> None:
        now = datetime.now(timezone.utc)
        records = [
            {
                "container_id": "steady-1",
                "timestamp": now.isoformat(),
                "cpu": 1.0,
                "memory": 2.0,
                "new_tier": "L1",
                "reason": "hold",
                "metadata": {
                    "workload_class": "benign",
                    "workload_key": "benign_steady",
                    "expected_tier": "L1",
                },
            },
            {
                "container_id": "bursty-1",
                "timestamp": (now + timedelta(seconds=5)).isoformat(),
                "cpu": 50.0,
                "memory": 5.0,
                "new_tier": "L2",
                "reason": "hold",
                "metadata": {
                    "workload_class": "benign",
                    "workload_key": "benign_bursty",
                    "expected_tier": "L2",
                },
            },
        ]
        grouped = compute_grouped_metrics(records)
        self.assertIn("benign_steady", grouped)
        self.assertIn("benign_bursty", grouped)
        self.assertEqual(grouped["benign_bursty"]["benign_restriction_rate"], 1.0)

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

    def test_write_grouped_metrics_summary_outputs_json(self) -> None:
        path = Path("tests/sample_grouped_metrics.jsonl")
        path.write_text(
            json.dumps(
                {
                    "container_id": "c1",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "cpu": 1.0,
                    "memory": 2.0,
                    "new_tier": "L1",
                    "reason": "hold",
                    "metadata": {
                        "workload_class": "benign",
                        "workload_key": "benign_steady",
                        "expected_tier": "L1",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            output = write_grouped_metrics_summary(path)
            self.assertTrue(output.exists())
        finally:
            path.unlink(missing_ok=True)
            Path("tests/sample_grouped_metrics.grouped.summary.json").unlink(missing_ok=True)

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

    def test_plot_tier_trajectory_writes_png(self) -> None:
        now = datetime.now(timezone.utc)
        output = Path("tests/tier_trajectory.png")
        records = [
            {
                "container_id": "c1",
                "timestamp": now.isoformat(),
                "new_tier": "L1",
                "metadata": {"workload_key": "benign_steady"},
            },
            {
                "container_id": "c1",
                "timestamp": (now + timedelta(seconds=5)).isoformat(),
                "new_tier": "L2",
                "metadata": {"workload_key": "benign_steady"},
            },
        ]
        try:
            plot_tier_trajectory(records, output)
            self.assertTrue(output.exists())
        finally:
            output.unlink(missing_ok=True)

    def test_summarize_overhead_report_schema(self) -> None:
        report = summarize_overhead_report(
            baseline_host_cpu=[5.0, 7.0],
            adaptive_host_cpu=[8.0, 10.0],
            adaptive_process_cpu=[1.0, 2.0],
            loop_durations_seconds=[0.4, 0.6],
        )
        self.assertIn("baseline", report)
        self.assertIn("adaptive", report)
        self.assertIn("delta", report)
        self.assertIn("host_cpu_percent_mean", report["adaptive"])
        self.assertIn("loop_duration_seconds_p95", report["adaptive"])


if __name__ == "__main__":
    unittest.main()
