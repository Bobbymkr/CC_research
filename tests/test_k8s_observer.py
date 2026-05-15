"""
Tests for the Kubernetes ObserverK8s telemetry backend.

Strategy: We do not need a real Kubernetes cluster. The K8s API surface is
mocked so we can verify the adapter contract and degraded-mode behavior in
isolation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import time
import unittest
from unittest.mock import MagicMock

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry
import raasa.k8s.observer_k8s as observer_module
from raasa.k8s.observer_k8s import ObserverK8s


def _prime_observer_state(obs: ObserverK8s, probe_dir: str = "/nonexistent") -> ObserverK8s:
    obs.namespace_filter = None
    obs.node_name = "test-node"
    obs.syscall_probe_dir = probe_dir
    obs.syscall_probe_max_age_seconds = 15
    obs.metrics_cache_max_age_seconds = 30
    obs.allow_stale_metrics_fallback = True
    obs.metrics_failure_cooldown_seconds = 15
    obs.namespace_metrics_cache_max_age_seconds = 15
    obs.node_memory_bytes = 8 * 1024**3
    obs._previous_rx = {}
    obs._previous_tx = {}
    obs._prev_cpu_usec = {}
    obs._prev_cpu_time = {}
    obs._prev_k8s_cpu = {}
    obs._metrics_cache = {}
    obs._namespace_metrics_cache = {}
    obs._known_pod_edges = {}
    obs._metrics_api_blocked_until = 0.0
    obs._metrics_api_last_failure_status = "unavailable"
    obs._k8s_client = None
    obs._metrics_client = None
    return obs


class BaseObserverContractTests(unittest.TestCase):
    def test_observer_k8s_is_base_observer_subclass(self) -> None:
        self.assertTrue(issubclass(ObserverK8s, BaseObserver))

    def test_observer_k8s_has_collect_method(self) -> None:
        self.assertTrue(hasattr(ObserverK8s, "collect"))
        self.assertTrue(callable(getattr(ObserverK8s, "collect")))


class ObserverK8sFallbackTests(unittest.TestCase):
    def _make_observer_no_client(self) -> ObserverK8s:
        return _prime_observer_state(ObserverK8s.__new__(ObserverK8s))

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
            self.assertEqual(row.metadata.get("telemetry_status"), "fallback")


class ObserverK8sSyscallProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.probe_root = Path("tests/.tmp_k8s_probe")
        shutil.rmtree(self.probe_root, ignore_errors=True)
        self.probe_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.probe_root, ignore_errors=True)

    def _make_observer(self) -> ObserverK8s:
        return _prime_observer_state(ObserverK8s.__new__(ObserverK8s), probe_dir=str(self.probe_root))

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

    def test_returns_stale_when_syscall_probe_file_is_too_old(self) -> None:
        pod_uid = "stale-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        probe_file = target / "syscall_rate"
        probe_file.write_text("347.5\n", encoding="utf-8")
        old_time = time.time() - 60
        os.utime(probe_file, (old_time, old_time))

        rate, status = self._make_observer()._get_syscall_rate(pod_uid)
        self.assertEqual(rate, 0.0)
        self.assertEqual(status, "probe_stale")

    def test_reads_syscall_counts_from_probe_file(self) -> None:
        pod_uid = "histogram-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "syscall_counts.json").write_text('{"0": 3, "257": "2", "bad": -1}\n', encoding="utf-8")

        counts, status = self._make_observer()._get_syscall_counts(pod_uid)

        self.assertEqual(status, "probe_ok")
        self.assertEqual(counts, {"0": 3, "257": 2})

    def test_returns_empty_for_invalid_syscall_counts_probe_file(self) -> None:
        pod_uid = "bad-histogram-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "syscall_counts.json").write_text("[1, 2, 3]\n", encoding="utf-8")

        counts, status = self._make_observer()._get_syscall_counts(pod_uid)

        self.assertEqual(status, "probe_invalid")
        self.assertEqual(counts, {})


class ObserverK8sLateralMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.probe_root = Path("tests/.tmp_k8s_edges")
        shutil.rmtree(self.probe_root, ignore_errors=True)
        self.probe_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.probe_root, ignore_errors=True)

    def _make_observer(self) -> ObserverK8s:
        return _prime_observer_state(ObserverK8s.__new__(ObserverK8s), probe_dir=str(self.probe_root))

    def test_lateral_signal_fires_on_first_seen_edge_only(self) -> None:
        (self.probe_root / "pod_edges.jsonl").write_text(
            '{"src_ip":"10.42.0.10","dst_ip":"10.42.0.11","count":1}\n',
            encoding="utf-8",
        )
        obs = self._make_observer()

        first = obs._get_lateral_movement_signal("uid-1", "10.42.0.10")
        second = obs._get_lateral_movement_signal("uid-1", "10.42.0.10")

        self.assertEqual(first, (1.0, "new_edge", 1, 1))
        self.assertEqual(second, (0.0, "known_edges", 1, 0))

    def test_lateral_signal_accepts_numeric_bpf_ips(self) -> None:
        # 169090600 == 10.20.30.40 in big-endian IPv4 integer form.
        (self.probe_root / "pod_edges.jsonl").write_text(
            '{"src_ip":169090600,"dst_ip":"10.20.30.41","count":1}\n',
            encoding="utf-8",
        )
        obs = self._make_observer()

        signal, status, total_edges, new_edges = obs._get_lateral_movement_signal(
            "uid-1",
            "10.20.30.40",
        )

        self.assertEqual(signal, 1.0)
        self.assertEqual(status, "new_edge")
        self.assertEqual(total_edges, 1)
        self.assertEqual(new_edges, 1)

    def test_lateral_signal_reports_missing_edge_map(self) -> None:
        signal, status, total_edges, new_edges = self._make_observer()._get_lateral_movement_signal(
            "uid-1",
            "10.42.0.10",
        )

        self.assertEqual(signal, 0.0)
        self.assertEqual(status, "edge_map_missing")
        self.assertEqual(total_edges, 0)
        self.assertEqual(new_edges, 0)


class ObserverK8sEntropyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.probe_root = Path("tests/.tmp_k8s_entropy")
        shutil.rmtree(self.probe_root, ignore_errors=True)
        self.probe_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.probe_root, ignore_errors=True)

    def _make_observer(self) -> ObserverK8s:
        return _prime_observer_state(ObserverK8s.__new__(ObserverK8s), probe_dir=str(self.probe_root))

    def test_reads_file_and_dns_entropy_samples_from_probe_files(self) -> None:
        pod_uid = "entropy-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "file_paths.json").write_text('["/etc/passwd", "/tmp/a", ""]\n', encoding="utf-8")
        (target / "dns_queries.json").write_text('{"dns_queries": ["a.example.test", "b.example.test"]}\n', encoding="utf-8")

        file_samples, file_status = self._make_observer()._read_entropy_sample_list(
            pod_uid,
            "file_paths.json",
            "file_paths",
        )
        dns_samples, dns_status = self._make_observer()._read_entropy_sample_list(
            pod_uid,
            "dns_queries.json",
            "dns_queries",
        )

        self.assertEqual(file_status, "probe_ok")
        self.assertEqual(file_samples, ["/etc/passwd", "/tmp/a"])
        self.assertEqual(dns_status, "probe_ok")
        self.assertEqual(dns_samples, ["a.example.test", "b.example.test"])

    def test_network_destination_entropy_samples_come_from_sock_ops_edges(self) -> None:
        (self.probe_root / "pod_edges.jsonl").write_text(
            "\n".join(
                [
                    '{"src_ip":"10.42.0.10","dst_ip":"10.42.0.11","count":2}',
                    '{"src_ip":"10.42.0.10","dst_ip":"10.42.0.12","count":1}',
                    '{"src_ip":"10.42.0.99","dst_ip":"10.42.0.10","count":9}',
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        samples, status = self._make_observer()._get_network_destination_samples("10.42.0.10")

        self.assertEqual(status, "network_entropy_ok")
        self.assertEqual(samples.count("10.42.0.11"), 2)
        self.assertEqual(samples.count("10.42.0.12"), 1)
        self.assertNotIn("10.42.0.99", samples)

    def test_combined_entropy_sample_metadata_reports_sources(self) -> None:
        pod_uid = "entropy-pod"
        target = self.probe_root / pod_uid
        target.mkdir(parents=True, exist_ok=True)
        (target / "file_paths.json").write_text('["/tmp/a"]\n', encoding="utf-8")
        (target / "dns_queries.json").write_text('["x.example.test"]\n', encoding="utf-8")
        (self.probe_root / "pod_edges.jsonl").write_text(
            '{"src_ip":"10.42.0.10","dst_ip":"10.42.0.11","count":1}\n',
            encoding="utf-8",
        )

        samples, metadata = self._make_observer()._get_entropy_samples(pod_uid, "10.42.0.10")

        self.assertEqual(samples["file_accesses"], ["/tmp/a"])
        self.assertEqual(samples["network_destinations"], ["10.42.0.11"])
        self.assertEqual(samples["dns_queries"], ["x.example.test"])
        self.assertEqual(metadata["file_entropy_status"], "probe_ok")
        self.assertEqual(metadata["network_entropy_status"], "network_entropy_ok")
        self.assertEqual(metadata["dns_entropy_status"], "probe_ok")


class ObserverK8sMetricsTests(unittest.TestCase):
    def _make_observer_with_mock_k8s(self) -> ObserverK8s:
        obs = _prime_observer_state(ObserverK8s.__new__(ObserverK8s))
        obs._k8s_client = MagicMock()
        obs._metrics_client = MagicMock()
        return obs

    def test_parses_nanocores_cpu_correctly(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "500000000n", "memory": "256Mi"}}]
        }
        cpu, mem, metadata = obs._get_pod_metrics_with_status("default", "test-pod")
        self.assertAlmostEqual(cpu, 50.0, places=0)
        self.assertGreater(mem, 3.0)
        self.assertEqual(metadata["cpu_status"], "metrics_ok")
        self.assertEqual(metadata["memory_status"], "metrics_ok")

    def test_parses_millicores_cpu_correctly(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "250m", "memory": "128Mi"}}]
        }
        cpu, _, metadata = obs._get_pod_metrics_with_status("default", "test-pod")
        self.assertAlmostEqual(cpu, 25.0, places=0)
        self.assertEqual(metadata["cpu_status"], "metrics_ok")

    def test_returns_zero_when_metrics_api_unavailable(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        obs._metrics_client.list_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        cpu, mem, metadata = obs._get_pod_metrics_with_status("default", "test-pod")
        self.assertEqual(cpu, 0.0)
        self.assertEqual(mem, 0.0)
        self.assertEqual(metadata["cpu_status"], "unavailable")
        self.assertEqual(metadata["memory_status"], "unavailable")

    def test_uses_cadvisor_memory_when_metrics_api_unavailable(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        obs._metrics_client.list_namespaced_custom_object.side_effect = Exception("metrics unavailable")

        cpu, mem, metadata = obs._get_pod_metrics_with_status(
            "default",
            "test-pod",
            memory_usage_map={("default", "test-pod"): 512 * 1024**2},
        )

        self.assertEqual(cpu, 0.0)
        self.assertGreater(mem, 6.0)
        self.assertEqual(metadata["memory_status"], "cadvisor_fallback")
        self.assertEqual(metadata["memory_source"], "cadvisor")

    def test_reads_k3s_underscored_pod_uid_pids_current(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        original_read_proc_file = observer_module._read_proc_file

        def fake_read_proc_file(path: str) -> str | None:
            if "/host/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod12345678_aaaa_bbbb_cccc_123456789abc.slice/pids.current" in path:
                return "37\n"
            return None

        try:
            observer_module._read_proc_file = fake_read_proc_file
            count = obs._read_process_count("12345678-aaaa-bbbb-cccc-123456789abc", cpu_percent=100.0)
        finally:
            observer_module._read_proc_file = original_read_proc_file

        self.assertEqual(count, 37)

    def test_process_count_falls_back_to_cpu_estimate_when_cgroup_missing(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        original_read_proc_file = observer_module._read_proc_file

        try:
            observer_module._read_proc_file = lambda path: None
            count = obs._read_process_count("missing-pod-uid", cpu_percent=80.0)
        finally:
            observer_module._read_proc_file = original_read_proc_file

        self.assertEqual(count, 8)

    def test_uses_cached_metrics_when_metrics_api_temporarily_fails(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "600000000n", "memory": "256Mi"}}]
        }
        first_cpu, first_mem, first_metadata = obs._get_pod_metrics_with_status("default", "test-pod")
        self.assertEqual(first_metadata["cpu_status"], "metrics_ok")

        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        obs._metrics_client.list_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        cpu, mem, metadata = obs._get_pod_metrics_with_status("default", "test-pod")

        self.assertAlmostEqual(cpu, first_cpu, places=2)
        self.assertAlmostEqual(mem, first_mem, places=2)
        self.assertEqual(metadata["cpu_status"], "metrics_cache_fallback")
        self.assertEqual(metadata["memory_status"], "metrics_cache_fallback")

    def test_cpu_capped_at_100_percent(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.return_value = {
            "containers": [{"usage": {"cpu": "20000000000n", "memory": "1Mi"}}]
        }
        cpu, _, metadata = obs._get_pod_metrics_with_status("default", "cpu-bomb")
        self.assertEqual(cpu, 100.0)
        self.assertEqual(metadata["cpu_status"], "metrics_ok")

    def test_prefers_probe_cpu_when_probe_file_exists(self) -> None:
        probe_root = Path("tests/.tmp_k8s_probe_cpu")
        shutil.rmtree(probe_root, ignore_errors=True)
        try:
            target = probe_root / "uid-1"
            target.mkdir(parents=True, exist_ok=True)
            (target / ".cpu_usec").write_text("500000\n", encoding="utf-8")

            obs = _prime_observer_state(ObserverK8s.__new__(ObserverK8s), probe_dir=str(probe_root))
            obs._k8s_client = MagicMock()
            obs._metrics_client = MagicMock()
            obs._prev_cpu_usec = {"uid-1": 0}
            obs._prev_cpu_time = {"uid-1": time.time() - 1.0}
            obs._metrics_client.get_namespaced_custom_object.return_value = {
                "containers": [{"usage": {"cpu": "10m", "memory": "64Mi"}}]
            }

            cpu, _, metadata = obs._get_pod_metrics_with_status("default", "probe-backed", "uid-1")
        finally:
            shutil.rmtree(probe_root, ignore_errors=True)

        self.assertGreater(cpu, 40.0)
        self.assertEqual(metadata["cpu_status"], "probe_ok")
        self.assertEqual(metadata["cpu_source"], "probe")

    def test_ignores_stale_probe_cpu_and_uses_metrics_api(self) -> None:
        probe_root = Path("tests/.tmp_k8s_probe_cpu_stale")
        shutil.rmtree(probe_root, ignore_errors=True)
        try:
            target = probe_root / "uid-1"
            target.mkdir(parents=True, exist_ok=True)
            cpu_file = target / ".cpu_usec"
            cpu_file.write_text("500000\n", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(cpu_file, (old_time, old_time))

            obs = _prime_observer_state(ObserverK8s.__new__(ObserverK8s), probe_dir=str(probe_root))
            obs._k8s_client = MagicMock()
            obs._metrics_client = MagicMock()
            obs._prev_cpu_usec = {"uid-1": 0}
            obs._prev_cpu_time = {"uid-1": time.time() - 1.0}
            obs._metrics_client.get_namespaced_custom_object.return_value = {
                "containers": [{"usage": {"cpu": "10m", "memory": "64Mi"}}]
            }

            cpu, _, metadata = obs._get_pod_metrics_with_status("default", "probe-backed", "uid-1")
        finally:
            shutil.rmtree(probe_root, ignore_errors=True)

        self.assertLess(cpu, 5.0)
        self.assertEqual(metadata["cpu_status"], "metrics_ok")
        self.assertEqual(metadata["cpu_source"], "metrics_api")

    def test_falls_back_to_namespace_metrics_list_when_direct_lookup_404s(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("404 not found")
        obs._metrics_client.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "test-pod"},
                    "containers": [{"usage": {"cpu": "250m", "memory": "128Mi"}}],
                }
            ]
        }

        cpu, mem, metadata = obs._get_pod_metrics_with_status("default", "test-pod")

        self.assertAlmostEqual(cpu, 25.0, places=0)
        self.assertGreater(mem, 1.0)
        self.assertEqual(metadata["cpu_status"], "metrics_list_fallback")
        self.assertEqual(metadata["memory_status"], "metrics_list_fallback")
        obs._metrics_client.list_namespaced_custom_object.assert_called_once_with(
            group="metrics.k8s.io",
            version="v1beta1",
            namespace="default",
            plural="pods",
        )

    def test_direct_lookup_error_is_raised_when_namespace_list_lacks_target_pod(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("404 not found")
        obs._metrics_client.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "other-pod"},
                    "containers": [{"usage": {"cpu": "50m", "memory": "32Mi"}}],
                }
            ]
        }

        cpu, mem, metadata = obs._get_pod_metrics_with_status("default", "test-pod")

        self.assertEqual(cpu, 0.0)
        self.assertEqual(mem, 0.0)
        self.assertEqual(metadata["cpu_status"], "unavailable")
        self.assertEqual(metadata["memory_status"], "unavailable")
        self.assertEqual(metadata["metrics_api_status"], "metrics_missing")

    def test_metrics_timeout_activates_cooldown_and_reuses_cached_namespace_list(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("subjectaccessreviews timeout")
        obs._metrics_client.list_namespaced_custom_object.return_value = {
            "items": [
                {
                    "metadata": {"name": "pod-a"},
                    "containers": [{"usage": {"cpu": "250m", "memory": "128Mi"}}],
                },
                {
                    "metadata": {"name": "pod-b"},
                    "containers": [{"usage": {"cpu": "100m", "memory": "64Mi"}}],
                },
            ]
        }

        first_cpu, _, first_metadata = obs._get_pod_metrics_with_status("default", "pod-a")
        second_cpu, _, second_metadata = obs._get_pod_metrics_with_status("default", "pod-b")

        self.assertAlmostEqual(first_cpu, 25.0, places=0)
        self.assertAlmostEqual(second_cpu, 10.0, places=0)
        self.assertEqual(first_metadata["memory_status"], "metrics_list_fallback")
        self.assertEqual(first_metadata["metrics_api_status"], "metrics_timeout")
        self.assertEqual(second_metadata["memory_status"], "metrics_list_cooldown_fallback")
        self.assertEqual(second_metadata["metrics_api_status"], "metrics_timeout")
        self.assertEqual(obs._metrics_client.get_namespaced_custom_object.call_count, 1)
        self.assertEqual(obs._metrics_client.list_namespaced_custom_object.call_count, 1)

    def test_memory_percent_uses_configured_node_memory(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        obs.node_memory_bytes = 16 * 1024**3

        self.assertAlmostEqual(obs._memory_percent_from_bytes(4 * 1024**3), 25.0)


class ObserverK8sDiscoveryTests(unittest.TestCase):
    def _make_observer_with_mock_k8s(self) -> ObserverK8s:
        obs = _prime_observer_state(ObserverK8s.__new__(ObserverK8s))
        obs._k8s_client = MagicMock()
        obs._metrics_client = MagicMock()
        return obs

    def test_discover_pods_filters_to_current_node(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        pod = MagicMock()
        pod.metadata.namespace = "default"
        pod.metadata.name = "api"
        obs._k8s_client.list_pod_for_all_namespaces.return_value.items = [pod]

        discovered = obs._discover_pods()

        self.assertEqual(discovered, ["default/api"])
        obs._k8s_client.list_pod_for_all_namespaces.assert_called_once_with(
            field_selector="status.phase=Running,spec.nodeName=test-node",
        )

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

    def test_build_network_counter_map_accepts_prometheus_timestamps(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        metrics_text = "\n".join(
            [
                'container_network_receive_bytes_total{namespace="default",pod="api"} 1000 1778491261809',
                'container_network_transmit_bytes_total{namespace="default",pod="api"} 400 1778491261809',
            ]
        )
        counter_map = obs._build_network_counter_map(metrics_text)
        self.assertEqual(counter_map[("default", "api")], (1000.0, 400.0))

    def test_build_memory_usage_map_prefers_working_set(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        metrics_text = "\n".join(
            [
                'container_memory_usage_bytes{namespace="default",pod="api"} 1000',
                'container_memory_working_set_bytes{namespace="default",pod="api"} 400',
            ]
        )
        memory_map = obs._build_memory_usage_map(metrics_text)
        self.assertEqual(memory_map[("default", "api")], 400.0)

    def test_build_memory_usage_map_accepts_prometheus_timestamps(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        metrics_text = "\n".join(
            [
                'container_memory_usage_bytes{namespace="default",pod="api"} 1000 1778491261809',
                'container_memory_working_set_bytes{namespace="default",pod="api"} 400 1778491261809',
            ]
        )
        memory_map = obs._build_memory_usage_map(metrics_text)
        self.assertEqual(memory_map[("default", "api")], 400.0)

    def test_network_delta_uses_baseline_then_previous_counters(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        first = obs._get_network_delta("default", "api", "uid-1", {("default", "api"): (500.0, 200.0)})
        second = obs._get_network_delta("default", "api", "uid-1", {("default", "api"): (900.0, 350.0)})
        self.assertEqual(first, (0.0, 0.0, "baseline"))
        self.assertEqual(second, (400.0, 150.0, "metrics_ok"))

    def test_network_delta_marks_cadvisor_unavailable_when_missing(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        result = obs._get_network_delta("default", "api", "uid-1", {})
        self.assertEqual(result, (0.0, 0.0, "cadvisor_unavailable"))

    def test_collect_marks_partial_telemetry_when_signals_degrade(self) -> None:
        obs = self._make_observer_with_mock_k8s()
        pod = MagicMock()
        pod.metadata.uid = "uid-1"
        pod.metadata.labels = {}
        pod.status.phase = "Running"
        obs._k8s_client.read_namespaced_pod.return_value = pod
        obs._metrics_client.get_namespaced_custom_object.side_effect = Exception("metrics unavailable")
        obs._metrics_client.list_namespaced_custom_object.side_effect = Exception("metrics unavailable")

        telemetry = obs._collect_pod(
            "default/api",
            datetime.now(timezone.utc),
            {},
            {("default", "api"): 128 * 1024**2},
        )

        self.assertEqual(telemetry.metadata["telemetry_status"], "partial")
        self.assertIn("memory:cadvisor_fallback", telemetry.metadata["degraded_signals"])
        self.assertIn("network:cadvisor_unavailable", telemetry.metadata["degraded_signals"])
        self.assertIn("syscall:probe_missing", telemetry.metadata["degraded_signals"])


if __name__ == "__main__":
    unittest.main()
