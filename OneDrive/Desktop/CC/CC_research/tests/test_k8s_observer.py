"""
Tests for the Kubernetes ObserverK8s telemetry backend.

Strategy: We do NOT need a real Kubernetes cluster. The entire K8s API surface
is replaced with lightweight mocks that verify the observer's contract:
  1. It returns a ContainerTelemetry per requested pod.
  2. It handles K8s API errors with fail-safe fallback records.
  3. It reads syscall_rate from the eBPF probe file correctly.
  4. It is a valid BaseObserver (interface compliance).
  5. The controller can use it transparently — identical to Docker observer.

This is the standard technique for testing cloud infrastructure adapters:
test the adapter's contracts and error handling in isolation from the cloud.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from typing import Iterable, List
from unittest.mock import MagicMock, patch

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry
from raasa.k8s.observer_k8s import ObserverK8s


class BaseObserverContractTests(unittest.TestCase):
    """Verify that ObserverK8s satisfies the BaseObserver contract."""

    def test_observer_k8s_is_base_observer_subclass(self) -> None:
        self.assertTrue(issubclass(ObserverK8s, BaseObserver))

    def test_observer_k8s_has_collect_method(self) -> None:
        self.assertTrue(hasattr(ObserverK8s, "collect"))
        self.assertTrue(callable(getattr(ObserverK8s, "collect")))


class ObserverK8sFallbackTests(unittest.TestCase):
    """Verify graceful degradation when K8s client is unavailable."""

    def _make_observer_no_client(self) -> ObserverK8s:
        """Observer with no K8s client (simulates missing kubernetes package)."""
        obs = ObserverK8s.__new__(ObserverK8s)
        obs.namespace_filter = None
        obs.node_name = "test-node"
        obs.syscall_probe_dir = "/nonexistent"
        obs._previous_rx = {}
        obs._previous_tx = {}
        obs._k8s_client = None
        obs._metrics_client = None
        return obs

    def test_returns_empty_list_for_empty_input(self) -> None:
        obs = self._make_observer_no_client()
        result = obs.collect([])
        self.assertEqual(result, [])

    def test_returns_fallback_records_when_no_k8s_client(self) -> None:
        obs = self._make_observer_no_client()
        result = obs.collect(["default/nginx-abc", "default/malware-xyz"])
        self.assertEqual(len(result), 2)
        for r in result:
            self.assertIsInstance(r, ContainerTelemetry)
            self.assertEqual(r.cpu_percent, 0.0)
            self.assertEqual(r.memory_percent, 0.0)
            self.assertEqual(r.metadata.get("status"), "fallback")

    def test_fallback_records_have_explanatory_reason(self) -> None:
        obs = self._make_observer_no_client()
        result = obs.collect(["default/pod-1"])
        self.assertIn("reason", result[0].metadata)
        self.assertTrue(len(result[0].metadata["reason"]) > 0)

    def test_collect_returns_one_record_per_pod(self) -> None:
        obs = self._make_observer_no_client()
        ids = ["default/a", "default/b", "default/c"]
        result = obs.collect(ids)
        self.assertEqual(len(result), len(ids))


class ObserverK8sSyscallProbeTests(unittest.TestCase):
    """Verify syscall rate reading from eBPF probe files."""

    def _make_observer(self, probe_dir: str) -> ObserverK8s:
        obs = ObserverK8s.__new__(ObserverK8s)
        obs.syscall_probe_dir = probe_dir
        obs._previous_rx = {}
        obs._previous_tx = {}
        return obs

    def test_reads_syscall_rate_from_probe_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pod_uid = "abc-pod-uid-123"
            probe_path = os.path.join(tmpdir, pod_uid)
            os.makedirs(probe_path)
            with open(os.path.join(probe_path, "syscall_rate"), "w") as f:
                f.write("347.5\n")

            obs = self._make_observer(tmpdir)
            rate = obs._get_syscall_rate(pod_uid)
            self.assertAlmostEqual(rate, 347.5, places=1)

    def test_returns_zero_when_probe_file_absent(self) -> None:
        obs = self._make_observer("/nonexistent/probe/dir")
        rate = obs._get_syscall_rate("some-pod-uid")
        self.assertEqual(rate, 0.0)

    def test_returns_zero_for_invalid_probe_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pod_uid = "broken-uid"
            probe_path = os.path.join(tmpdir, pod_uid)
            os.makedirs(probe_path)
            with open(os.path.join(probe_path, "syscall_rate"), "w") as f:
                f.write("not_a_number\n")
            obs = self._make_observer(tmpdir)
            rate = obs._get_syscall_rate(pod_uid)
            self.assertEqual(rate, 0.0)

    def test_clamps_negative_syscall_rate_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pod_uid = "neg-uid"
            probe_path = os.path.join(tmpdir, pod_uid)
            os.makedirs(probe_path)
            with open(os.path.join(probe_path, "syscall_rate"), "w") as f:
                f.write("-50.0\n")
            obs = self._make_observer(tmpdir)
            rate = obs._get_syscall_rate(pod_uid)
            self.assertEqual(rate, 0.0)


class ObserverK8sMetricsTests(unittest.TestCase):
    """Verify CPU/memory metrics parsing from the Kubernetes Metrics API."""

    def _make_observer_with_mock_k8s(self) -> ObserverK8s:
        obs = ObserverK8s.__new__(ObserverK8s)
        obs.namespace_filter = None
        obs.node_name = "test-node"
        obs.syscall_probe_dir = "/nonexistent"
        obs._previous_rx = {}
        obs._previous_tx = {}
        obs._k8s_client = MagicMock()
        obs._metrics_client = MagicMock()
        return obs

    def test_parses_nanocores_cpu_correctly(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        # 500_000_000 nanocores = 0.5 vCPU = 50%
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "500000000n", "memory": "256Mi"}}]
        }
        cpu, mem = obs._get_pod_metrics("default", "test-pod")
        self.assertAlmostEqual(cpu, 50.0, places=0)

    def test_parses_millicores_cpu_correctly(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        # 250m = 0.25 vCPU = 25%
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "250m", "memory": "128Mi"}}]
        }
        cpu, _ = obs._get_pod_metrics("default", "test-pod")
        self.assertAlmostEqual(cpu, 25.0, places=0)

    def test_returns_zero_when_metrics_api_unavailable(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        cpu, mem = obs._get_pod_metrics("default", "test-pod")
        self.assertEqual(cpu, 0.0)
        self.assertEqual(mem, 0.0)

    def test_cpu_capped_at_100_percent(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        # 2e10 nanocores = 20 vCPU → capped at 100%
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "20000000000n", "memory": "1Mi"}}]
        }
        cpu, _ = obs._get_pod_metrics("default", "cpu-bomb")
        self.assertEqual(cpu, 100.0)


if __name__ == "__main__":
    unittest.main()
