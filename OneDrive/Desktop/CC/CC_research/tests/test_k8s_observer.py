"""
Tests for the Kubernetes ObserverK8s telemetry backend.

Strategy: We do NOT need a real Kubernetes cluster. The K8s API surface is
mocked so we can verify the adapter contract and fallback behavior in
isolation.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from unittest.mock import MagicMock

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry
from raasa.k8s.observer_k8s import ObserverK8s


class BaseObserverContractTests(unittest.TestCase):
    def test_observer_k8s_is_base_observer_subclass(self) -> None:
        self.assertTrue(issubclass(ObserverK8s, BaseObserver))

    def test_observer_k8s_has_collect_method(self) -> None:
        self.assertTrue(hasattr(ObserverK8s, "collect"))
        self.assertTrue(callable(getattr(ObserverK8s, "collect")))


class ObserverK8sFallbackTests(unittest.TestCase):
    def _make_observer_no_client(self) -> ObserverK8s:
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
        self.assertEqual(obs.collect([]), [])

    def test_returns_fallback_records_when_no_k8s_client(self) -> None:
        obs = self._make_observer_no_client()
        result = obs.collect(["default/nginx-abc", "default/malware-xyz"])
        self.assertEqual(len(result), 2)
        for row in result:
            self.assertIsInstance(row, ContainerTelemetry)
            self.assertEqual(row.cpu_percent, 0.0)
            self.assertEqual(row.metadata.get("status"), "fallback")


class ObserverK8sSyscallProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.probe_root = Path("tests/.tmp_k8s_probe")
        shutil.rmtree(self.probe_root, ignore_errors=True)
        self.probe_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.probe_root, ignore_errors=True)

    def _make_observer(self) -> ObserverK8s:
        obs = ObserverK8s.__new__(ObserverK8s)
        obs.syscall_probe_dir = str(self.probe_root)
        obs._previous_rx = {}
        obs._previous_tx = {}
        return obs

    def test_reads_syscall_rate_from_probe_file(self) -> None:
        pod_uid = "abc-pod-uid-123"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "syscall_rate").write_text("347.5\n", encoding="utf-8")

        rate, status = self._make_observer()._get_syscall_rate(pod_uid)
        self.assertAlmostEqual(rate, 347.5, places=1)
        self.assertEqual(status, "probe_ok")

    def test_returns_zero_when_probe_file_absent(self) -> None:
        rate, status = self._make_observer()._get_syscall_rate("missing-pod")
        self.assertEqual(rate, 0.0)
        self.assertEqual(status, "probe_missing")

    def test_returns_zero_for_invalid_probe_content(self) -> None:
        pod_uid = "broken-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "syscall_rate").write_text("bad\n", encoding="utf-8")

        rate, status = self._make_observer()._get_syscall_rate(pod_uid)
        self.assertEqual(rate, 0.0)
        self.assertEqual(status, "probe_invalid")

    def test_clamps_negative_syscall_rate_to_zero(self) -> None:
        pod_uid = "negative-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "syscall_rate").write_text("-50\n", encoding="utf-8")

        rate, status = self._make_observer()._get_syscall_rate(pod_uid)
        self.assertEqual(rate, 0.0)
        self.assertEqual(status, "probe_negative")


class ObserverK8sMetricsTests(unittest.TestCase):
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
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "500000000n", "memory": "256Mi"}}]
        }
        cpu, _ = obs._get_pod_metrics("default", "test-pod")
        self.assertAlmostEqual(cpu, 50.0, places=0)

    def test_parses_millicores_cpu_correctly(self) -> None:
        obs = self._make_observer_with_mock_k8s()
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
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "20000000000n", "memory": "1Mi"}}]
        }
        cpu, _ = obs._get_pod_metrics("default", "cpu-bomb")
        self.assertEqual(cpu, 100.0)

    def test_build_network_counter_map_parses_prometheus_metrics(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        metrics_text = "\n".join(
            [
                'container_network_receive_bytes_total{namespace="default",pod="api"} 1000',
                'container_network_transmit_bytes_total{namespace="default",pod="api"} 400',
            ]
        )
        counter_map = obs._build_network_counter_map(metrics_text)
        self.assertEqual(counter_map[("default", "api")], (1000.0, 400.0))

    def test_network_delta_uses_previous_counters(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        first = obs._get_network_delta("default", "api", "uid-1", {("default", "api"): (500.0, 200.0)})
        second = obs._get_network_delta("default", "api", "uid-1", {("default", "api"): (900.0, 350.0)})
        self.assertEqual(first, (0.0, 0.0, "metrics_ok"))
        self.assertEqual(second, (400.0, 150.0, "metrics_ok"))


if __name__ == "__main__":
    unittest.main()
