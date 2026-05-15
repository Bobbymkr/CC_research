"""
Kubernetes-native telemetry observer for RAASA DaemonSet deployment.

Replaces the Docker CLI observer in production Kubernetes environments.
Uses the official kubernetes Python client to:
  - Enumerate pods on the current node (via field selectors)
  - Read CPU/memory metrics from the Kubernetes Metrics API
  - Read network I/O from cAdvisor scrapes
  - Estimate syscall rates from sidecar probe files

Architecture
------------
In production, RAASA runs as a DaemonSet: one agent pod per node.
Each agent watches only the pods scheduled on its node (``spec.nodeName``).
This keeps the blast radius small: a compromised agent affects one node, not
the whole cluster. The controller receives the same ContainerTelemetry records
it always has; the K8s backend is transparent to upper layers.

Graceful Degradation
--------------------
This observer explicitly reports signal quality in ``metadata`` so upper
layers and experiment reports can distinguish:
  - healthy live signals
  - live fallback paths (namespace metrics list, cAdvisor memory)
  - bounded stale cache fallback
  - total signal loss / full fallback records
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry

logger = logging.getLogger(__name__)
_PROMETHEUS_LINE_RE = re.compile(
    r"^(?P<metric>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+"
    r"(?P<value>[-+0-9.eE]+)(?:\s+[-+0-9.eE]+)?$"
)
_HEALTHY_SIGNAL_STATUSES = frozenset({"metrics_ok", "probe_ok", "baseline"})


def _read_proc_file(path: str) -> Optional[str]:
    """Read a /proc or sidecar-written file safely."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _parse_prometheus_labels(raw_labels: str) -> dict[str, str]:
    if not raw_labels:
        return {}
    matches = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', raw_labels)
    return {key: value for key, value in matches}


class ObserverK8s(BaseObserver):
    """
    Kubernetes API-backed telemetry collector for RAASA DaemonSet agents.

    Parameters
    ----------
    namespace_filter:
        If set, only collect telemetry for pods in this namespace.
        Defaults to None (all namespaces on this node).
    node_name:
        The hostname of the node this DaemonSet pod is running on.
        Defaults to the ``NODE_NAME`` environment variable injected by
        the DaemonSet's ``env[].fieldRef``.
    syscall_probe_dir:
        Directory where the eBPF sidecar writes per-pod syscall rates and CPU
        deltas. Defaults to ``/var/run/raasa``.
    metrics_cache_max_age_seconds:
        Maximum age of a live Metrics API sample that may be reused when
        ``metrics.k8s.io`` is temporarily unavailable.
    allow_stale_metrics_fallback:
        Whether bounded stale cache fallback is enabled.
    """

    _SYSTEM_NAMESPACES = frozenset({"kube-system", "kube-public", "kube-node-lease", "raasa-system"})

    def __init__(
        self,
        namespace_filter: Optional[str] = None,
        node_name: Optional[str] = None,
        syscall_probe_dir: str = "/var/run/raasa",
        metrics_cache_max_age_seconds: int = 30,
        allow_stale_metrics_fallback: bool = True,
        metrics_failure_cooldown_seconds: int = 15,
        namespace_metrics_cache_max_age_seconds: int = 15,
        node_memory_bytes: Optional[int] = None,
    ) -> None:
        self.namespace_filter = namespace_filter
        self.node_name = node_name or os.environ.get("NODE_NAME", "")
        self.syscall_probe_dir = syscall_probe_dir
        self.metrics_cache_max_age_seconds = max(0, int(metrics_cache_max_age_seconds))
        self.allow_stale_metrics_fallback = allow_stale_metrics_fallback
        self.metrics_failure_cooldown_seconds = max(0, int(metrics_failure_cooldown_seconds))
        self.namespace_metrics_cache_max_age_seconds = max(0, int(namespace_metrics_cache_max_age_seconds))
        self.node_memory_bytes = node_memory_bytes or self._detect_node_memory_bytes()
        self._previous_rx: Dict[str, float] = {}
        self._previous_tx: Dict[str, float] = {}
        self._prev_cpu_usec: Dict[str, int] = {}
        self._prev_cpu_time: Dict[str, float] = {}
        self._prev_k8s_cpu: Dict[str, float] = {}
        self._metrics_cache: Dict[str, Dict[str, float]] = {}
        self._namespace_metrics_cache: Dict[str, Dict[str, object]] = {}
        self._known_pod_edges: Dict[str, set[str]] = {}
        self._metrics_api_blocked_until = 0.0
        self._metrics_api_last_failure_status = "unavailable"
        self._k8s_client = None
        self._metrics_client = None
        self._init_clients()

    def _init_clients(self) -> None:
        """
        Initialise the Kubernetes Python client.

        Tries in-cluster config first (DaemonSet running inside a pod),
        then falls back to kubeconfig (local development / minikube).
        Logs a warning without raising if neither is available; the observer
        will return fallback telemetry on every collect() call.
        """
        try:
            from kubernetes import client, config  # type: ignore[import]

            try:
                config.load_incluster_config()
                logger.info("K8s observer: loaded in-cluster config")
            except Exception:
                config.load_kube_config()
                logger.info("K8s observer: loaded kubeconfig")
            self._k8s_client = client.CoreV1Api()
            self._metrics_client = client.CustomObjectsApi()
        except ImportError:
            logger.warning(
                "kubernetes package not installed. K8s observer will return fallback telemetry. "
                "Install with: pip install kubernetes"
            )
        except Exception as exc:
            logger.warning(f"K8s observer: client init failed ({exc}). Returning fallback telemetry.")

    def collect(self, container_ids: Iterable[str]) -> List[ContainerTelemetry]:
        """
        Collect telemetry for the given pod identifiers.

        Parameters
        ----------
        container_ids:
            ``namespace/pod-name`` strings, e.g. ``default/nginx-abc``.
            For bare pod names, ``default`` namespace is assumed.
        """
        timestamp = datetime.now(timezone.utc)
        pod_ids = list(container_ids)

        if self._k8s_client is None:
            if not pod_ids:
                return []
            return self._fallback_batch(pod_ids, timestamp, "k8s client unavailable")

        if not pod_ids:
            pod_ids = self._discover_pods()
            if not pod_ids:
                return []

        cadvisor_metrics = self._fetch_cadvisor_metrics()
        network_counter_map = self._build_network_counter_map(cadvisor_metrics)
        memory_usage_map = self._build_memory_usage_map(cadvisor_metrics)
        results: List[ContainerTelemetry] = []
        for pod_ref in pod_ids:
            results.append(self._collect_pod(pod_ref, timestamp, network_counter_map, memory_usage_map))
        return results

    def _discover_pods(self) -> List[str]:
        """
        List all running pods across the cluster, excluding system namespaces.

        Returns a list of ``namespace/pod-name`` strings suitable for
        passing to ``_collect_pod()``.
        """
        try:
            field_selector = self._build_pod_field_selector()
            if self.namespace_filter:
                pods = self._k8s_client.list_namespaced_pod(
                    namespace=self.namespace_filter,
                    field_selector=field_selector,
                )
            else:
                pods = self._k8s_client.list_pod_for_all_namespaces(
                    field_selector=field_selector,
                )
            discovered = []
            for pod in pods.items:
                namespace = pod.metadata.namespace
                if namespace in self._SYSTEM_NAMESPACES:
                    continue
                discovered.append(f"{namespace}/{pod.metadata.name}")
            if discovered:
                logger.info(f"[ObserverK8s] Auto-discovered {len(discovered)} pod(s): {discovered}")
            return discovered
        except Exception as exc:
            logger.warning(f"[ObserverK8s] Pod discovery failed: {exc}")
            return []

    def _build_pod_field_selector(self) -> str:
        selectors = ["status.phase=Running"]
        if self.node_name:
            selectors.append(f"spec.nodeName={self.node_name}")
        return ",".join(selectors)

    def _collect_pod(
        self,
        pod_ref: str,
        timestamp: datetime,
        network_counter_map: dict[tuple[str, str], tuple[float, float]],
        memory_usage_map: dict[tuple[str, str], float],
    ) -> ContainerTelemetry:
        """Collect telemetry for a single pod."""
        if "/" in pod_ref:
            namespace, pod_name = pod_ref.split("/", 1)
        else:
            namespace, pod_name = "default", pod_ref

        try:
            pod = self._k8s_client.read_namespaced_pod(name=pod_name, namespace=namespace)
            uid = pod.metadata.uid or pod_ref
            labels = pod.metadata.labels or {}
            workload_class = labels.get("raasa.class", "")
            expected_tier = labels.get("raasa.expected_tier", "")
            image = self._pod_image(pod)
            image_id = self._pod_image_id(pod)

            cpu_percent, memory_percent, metrics_metadata = self._get_pod_metrics_with_status(
                namespace,
                pod_name,
                uid,
                memory_usage_map,
            )
            delta_rx, delta_tx, network_status = self._get_network_delta(
                namespace,
                pod_name,
                uid,
                network_counter_map,
            )
            syscall_rate, syscall_status = self._get_syscall_rate(uid)
            syscall_counts, syscall_counts_status = self._get_syscall_counts(uid)
            pod_ip = getattr(pod.status, "pod_ip", "") or ""
            if not isinstance(pod_ip, str):
                pod_ip = ""
            (
                lateral_movement_signal,
                lateral_movement_status,
                lateral_movement_total_edges,
                lateral_movement_new_edges,
            ) = self._get_lateral_movement_signal(uid, pod_ip)
            entropy_samples, entropy_metadata = self._get_entropy_samples(uid, pod_ip)
            telemetry_status, degraded_signals = self._summarize_telemetry_status(
                {
                    "cpu": metrics_metadata["cpu_status"],
                    "memory": metrics_metadata["memory_status"],
                    "network": network_status,
                    "syscall": syscall_status,
                }
            )

            return ContainerTelemetry(
                container_id=pod_ref,
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                process_count=self._read_process_count(uid, cpu_percent),
                network_rx_bytes=delta_rx,
                network_tx_bytes=delta_tx,
                syscall_rate=syscall_rate,
                lateral_movement_signal=lateral_movement_signal,
                syscall_counts=syscall_counts,
                file_accesses=entropy_samples["file_accesses"],
                network_destinations=entropy_samples["network_destinations"],
                dns_queries=entropy_samples["dns_queries"],
                metadata={
                    "status": pod.status.phase or "unknown",
                    "workload_class": workload_class,
                    "expected_tier": expected_tier,
                    "image": image,
                    "image_id": image_id,
                    "namespace": namespace,
                    "node": self.node_name,
                    "telemetry_status": telemetry_status,
                    "degraded_signals": degraded_signals or "none",
                    **metrics_metadata,
                    "network_source": "cadvisor",
                    "network_status": network_status,
                    "syscall_source": "probe",
                    "syscall_status": syscall_status,
                    "syscall_counts_source": "probe",
                    "syscall_counts_status": syscall_counts_status,
                    "lateral_movement_source": "sock_ops",
                    "lateral_movement_status": lateral_movement_status,
                    "lateral_movement_total_edges": str(lateral_movement_total_edges),
                    "lateral_movement_new_edges": str(lateral_movement_new_edges),
                    **entropy_metadata,
                },
            )
        except Exception as exc:
            logger.warning(f"K8s observer: failed to collect pod {pod_ref}: {exc}")
            return self._fallback_pod(pod_ref, timestamp, str(exc))

    def _get_pod_metrics(
        self,
        namespace: str,
        pod_name: str,
        pod_uid: str = "",
        memory_usage_map: Optional[dict[tuple[str, str], float]] = None,
    ) -> tuple[float, float]:
        """Compatibility wrapper used by existing tests and call sites."""
        cpu_percent, memory_percent, _ = self._get_pod_metrics_with_status(
            namespace,
            pod_name,
            pod_uid,
            memory_usage_map,
        )
        return cpu_percent, memory_percent

    def _get_pod_metrics_with_status(
        self,
        namespace: str,
        pod_name: str,
        pod_uid: str = "",
        memory_usage_map: Optional[dict[tuple[str, str], float]] = None,
    ) -> tuple[float, float, dict[str, str]]:
        """
        Fetch CPU and memory usage with explicit signal provenance.

        Priority order:
          1. probe CPU
          2. Metrics API
          3. cAdvisor memory fallback
          4. bounded stale cache fallback
        """
        pod_ref = f"{namespace}/{pod_name}"
        cpu_percent = 0.0
        memory_percent = 0.0
        cpu_from_probe = False
        cadvisor_memory_bytes = None
        signal_metadata = {
            "cpu_source": "unavailable",
            "cpu_status": "unavailable",
            "memory_source": "unavailable",
            "memory_status": "unavailable",
            "metrics_api_status": "unavailable",
        }

        if memory_usage_map is not None:
            cadvisor_memory_bytes = memory_usage_map.get((namespace, pod_name))

        if pod_uid:
            try:
                probe_dir = Path(self.syscall_probe_dir) / pod_uid
                cpu_file = probe_dir / ".cpu_usec"
                if cpu_file.exists() and self._probe_file_status(cpu_file) == "probe_ok":
                    current_usec = int(cpu_file.read_text(encoding="utf-8").strip())
                    current_time = time.time()
                    prev_usec = self._prev_cpu_usec.get(pod_uid, current_usec)
                    prev_time = self._prev_cpu_time.get(pod_uid, current_time - 1.0)

                    delta_usec = max(0, current_usec - prev_usec)
                    delta_time = max(0.1, current_time - prev_time)

                    self._prev_cpu_usec[pod_uid] = current_usec
                    self._prev_cpu_time[pod_uid] = current_time

                    cpu_cores = (delta_usec / 1_000_000.0) / delta_time
                    cpu_percent = min(cpu_cores * 100.0, 100.0)
                    cpu_from_probe = True
                    signal_metadata["cpu_source"] = "probe"
                    signal_metadata["cpu_status"] = "probe_ok"
            except Exception as exc:
                logger.warning(f"[ObserverK8s] Direct CPU read failed for {pod_uid}: {exc}")

        try:
            metrics, metrics_status, metrics_api_status = self._fetch_metrics_object(namespace, pod_name)
            total_cpu_nano, total_memory_bytes = self._parse_metrics_usage(metrics.get("containers", []))

            raw_cpu_percent = min((total_cpu_nano / 1e9) * 100.0, 100.0)
            memory_percent = self._memory_percent_from_bytes(total_memory_bytes)
            signal_metadata["memory_source"] = "metrics_api"
            signal_metadata["memory_status"] = metrics_status
            signal_metadata["metrics_api_status"] = metrics_api_status

            if not cpu_from_probe:
                prev_val = self._prev_k8s_cpu.get(pod_name, 0.0)
                if raw_cpu_percent == 0.0 and prev_val > 10.0:
                    cpu_percent = prev_val
                    signal_metadata["cpu_source"] = "metrics_api"
                    signal_metadata["cpu_status"] = "metrics_smoothed"
                else:
                    cpu_percent = raw_cpu_percent
                    self._prev_k8s_cpu[pod_name] = raw_cpu_percent
                    signal_metadata["cpu_source"] = "metrics_api"
                    signal_metadata["cpu_status"] = metrics_status

            self._cache_metrics(pod_ref, raw_cpu_percent, memory_percent)
        except Exception as exc:
            signal_metadata["metrics_api_status"] = self._classify_metrics_exception(exc)
            cached_metrics = self._get_cached_metrics(pod_ref)
            if not cpu_from_probe and cached_metrics is not None:
                cpu_percent = cached_metrics["cpu_percent"]
                signal_metadata["cpu_source"] = "metrics_cache"
                signal_metadata["cpu_status"] = "metrics_cache_fallback"
                logger.info(
                    f"[ObserverK8s] Using cached CPU fallback for {namespace}/{pod_name}: "
                    f"{cpu_percent:.2f}%"
                )

            if cadvisor_memory_bytes is not None:
                memory_percent = self._memory_percent_from_bytes(cadvisor_memory_bytes)
                signal_metadata["memory_source"] = "cadvisor"
                signal_metadata["memory_status"] = "cadvisor_fallback"
                logger.info(
                    f"[ObserverK8s] Using cAdvisor memory fallback for {namespace}/{pod_name}: "
                    f"{memory_percent:.2f}%"
                )
            elif cached_metrics is not None:
                memory_percent = cached_metrics["memory_percent"]
                signal_metadata["memory_source"] = "metrics_cache"
                signal_metadata["memory_status"] = "metrics_cache_fallback"
                logger.info(
                    f"[ObserverK8s] Using cached memory fallback for {namespace}/{pod_name}: "
                    f"{memory_percent:.2f}%"
                )

            logger.warning(f"[ObserverK8s] Metrics API failed for {namespace}/{pod_name}: {exc}")

        logger.info(
            f"[ObserverK8s] Metrics {namespace}/{pod_name}: "
            f"cpu={cpu_percent:.2f}% ({signal_metadata['cpu_status']}), "
            f"mem={memory_percent:.2f}% ({signal_metadata['memory_status']})"
        )
        return cpu_percent, memory_percent, signal_metadata

    def _fetch_metrics_object(self, namespace: str, pod_name: str) -> tuple[dict, str, str]:
        """
        Fetch pod metrics from the Metrics API.

        The direct per-pod endpoint occasionally returns ``404 Not Found`` on
        K3s under stress even while the namespace-level PodMetrics list still
        contains the pod. When that happens, fall back to listing pod metrics
        for the namespace and selecting the matching item by metadata.name.
        """
        if self._metrics_client is None:
            raise RuntimeError("metrics client unavailable")

        if self._is_metrics_api_in_cooldown():
            cached_namespace_items = self._get_cached_namespace_metrics(namespace)
            if cached_namespace_items is not None:
                item = self._select_pod_metrics_from_namespace_items(cached_namespace_items, pod_name)
                if item is not None:
                    logger.info(
                        f"[ObserverK8s] Using cached namespace metrics for {namespace}/{pod_name} "
                        f"while Metrics API cooldown is active."
                    )
                    return item, "metrics_list_cooldown_fallback", self._metrics_api_last_failure_status

        try:
            self._metrics_api_last_failure_status = "metrics_ok"
            return (
                self._metrics_client.get_namespaced_custom_object(
                    group="metrics.k8s.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="pods",
                    name=pod_name,
                ),
                "metrics_ok",
                "metrics_ok",
            )
        except Exception as exc:
            failure_status = self._classify_metrics_exception(exc)
            self._activate_metrics_api_cooldown(failure_status)
            logger.warning(
                f"[ObserverK8s] Direct pod metrics lookup failed for {namespace}/{pod_name}: {exc}. "
                "Trying namespace metrics list fallback."
            )
            pod_metrics, list_status = self._fetch_namespace_metrics_list(namespace, allow_cached=True)
            item = self._select_pod_metrics_from_namespace_items(pod_metrics, pod_name)
            if item is not None:
                logger.info(
                    f"[ObserverK8s] Recovered metrics for {namespace}/{pod_name} via namespace list fallback."
                )
                if list_status == "metrics_list_cache_fallback":
                    return item, "metrics_list_cache_fallback", failure_status
                return item, "metrics_list_fallback", failure_status
            raise exc

    def _fetch_namespace_metrics_list(
        self,
        namespace: str,
        *,
        allow_cached: bool,
    ) -> tuple[list[dict], str]:
        if self._metrics_client is None:
            raise RuntimeError("metrics client unavailable")

        try:
            pod_metrics = self._metrics_client.list_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
            )
        except Exception:
            if allow_cached:
                cached_items = self._get_cached_namespace_metrics(namespace)
                if cached_items is not None:
                    return cached_items, "metrics_list_cache_fallback"
            raise

        items = list(pod_metrics.get("items", []))
        self._cache_namespace_metrics(namespace, items)
        return items, "metrics_list_ok"

    def _select_pod_metrics_from_namespace_items(self, items: list[dict], pod_name: str) -> Optional[dict]:
        for item in items:
            metadata = item.get("metadata", {})
            if metadata.get("name") == pod_name:
                return item
        return None

    def _parse_metrics_usage(self, containers: list[dict]) -> tuple[int, int]:
        total_cpu_nano = 0
        total_memory_bytes = 0
        for container in containers:
            usage = container.get("usage", {})
            cpu_raw = str(usage.get("cpu", "0"))
            mem_raw = str(usage.get("memory", "0"))

            if cpu_raw.endswith("n"):
                total_cpu_nano += int(cpu_raw[:-1])
            elif cpu_raw.endswith("m"):
                total_cpu_nano += int(cpu_raw[:-1]) * 1_000_000
            else:
                try:
                    total_cpu_nano += int(cpu_raw)
                except ValueError:
                    pass

            if mem_raw.endswith("Ki"):
                total_memory_bytes += int(mem_raw[:-2]) * 1024
            elif mem_raw.endswith("Mi"):
                total_memory_bytes += int(mem_raw[:-2]) * 1024**2
            elif mem_raw.endswith("Gi"):
                total_memory_bytes += int(mem_raw[:-2]) * 1024**3
            else:
                try:
                    total_memory_bytes += int(mem_raw)
                except ValueError:
                    pass
        return total_cpu_nano, total_memory_bytes

    def _fetch_cadvisor_metrics(self) -> str:
        """
        Read raw cAdvisor metrics text through the Kubernetes node proxy.

        Returns an empty string when the endpoint is unavailable.
        """
        if self._k8s_client is None or not self.node_name:
            logger.warning("[ObserverK8s] cAdvisor: no k8s client or node_name")
            return ""
        try:
            result = str(self._k8s_client.connect_get_node_proxy_with_path(self.node_name, "metrics/cadvisor"))
            if result:
                logger.info(f"[ObserverK8s] cAdvisor: fetched {len(result)} bytes from {self.node_name}")
            return result
        except Exception as exc:
            logger.warning(f"[ObserverK8s] cAdvisor proxy failed for {self.node_name}: {exc}")
            return ""

    def _build_network_counter_map(
        self,
        metrics_text: str,
    ) -> dict[tuple[str, str], tuple[float, float]]:
        counters: dict[tuple[str, str], list[float]] = {}
        if not metrics_text:
            return {}

        for raw_line in metrics_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = _PROMETHEUS_LINE_RE.match(line)
            if match is None:
                continue
            metric_name = match.group("metric")
            if metric_name not in {
                "container_network_receive_bytes_total",
                "container_network_transmit_bytes_total",
            }:
                continue

            labels = _parse_prometheus_labels(match.group("labels") or "")
            namespace = labels.get("namespace", "")
            pod_name = labels.get("pod", "") or labels.get("pod_name", "")
            if not namespace or not pod_name:
                continue
            try:
                value = max(0.0, float(match.group("value")))
            except ValueError:
                continue

            key = (namespace, pod_name)
            if key not in counters:
                counters[key] = [0.0, 0.0]
            if metric_name == "container_network_receive_bytes_total":
                counters[key][0] = value
            else:
                counters[key][1] = value

        return {key: (values[0], values[1]) for key, values in counters.items()}

    def _build_memory_usage_map(self, metrics_text: str) -> dict[tuple[str, str], float]:
        memory_by_pod: dict[tuple[str, str], float] = {}
        if not metrics_text:
            return memory_by_pod

        preferred_metric = "container_memory_working_set_bytes"
        fallback_metric = "container_memory_usage_bytes"

        for raw_line in metrics_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = _PROMETHEUS_LINE_RE.match(line)
            if match is None:
                continue

            metric_name = match.group("metric")
            if metric_name not in {preferred_metric, fallback_metric}:
                continue

            labels = _parse_prometheus_labels(match.group("labels") or "")
            namespace = labels.get("namespace", "")
            pod_name = labels.get("pod", "") or labels.get("pod_name", "")
            if not namespace or not pod_name:
                continue

            try:
                value = max(0.0, float(match.group("value")))
            except ValueError:
                continue

            key = (namespace, pod_name)
            if metric_name == preferred_metric or key not in memory_by_pod:
                memory_by_pod[key] = value

        return memory_by_pod

    def _memory_percent_from_bytes(self, memory_bytes: float) -> float:
        node_memory_bytes = max(float(getattr(self, "node_memory_bytes", 0) or 0), 1.0)
        return min((memory_bytes / node_memory_bytes) * 100.0, 100.0)

    def _detect_node_memory_bytes(self) -> int:
        meminfo = _read_proc_file("/proc/meminfo")
        if meminfo:
            for line in meminfo.splitlines():
                if not line.startswith("MemTotal:"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return max(int(parts[1]) * 1024, 1)
                    except ValueError:
                        break

        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            physical_pages = os.sysconf("SC_PHYS_PAGES")
            return max(int(page_size) * int(physical_pages), 1)
        except (AttributeError, OSError, TypeError, ValueError):
            return 8 * 1024**3

    def _get_network_delta(
        self,
        namespace: str,
        pod_name: str,
        pod_uid: str,
        network_counter_map: dict[tuple[str, str], tuple[float, float]],
    ) -> tuple[float, float, str]:
        key = (namespace, pod_name)
        if key not in network_counter_map:
            return 0.0, 0.0, "cadvisor_unavailable"

        raw_rx, raw_tx = network_counter_map[key]
        previous_rx = self._previous_rx.get(pod_uid)
        previous_tx = self._previous_tx.get(pod_uid)
        self._previous_rx[pod_uid] = raw_rx
        self._previous_tx[pod_uid] = raw_tx

        if previous_rx is None or previous_tx is None:
            return 0.0, 0.0, "baseline"
        if raw_rx < previous_rx or raw_tx < previous_tx:
            return 0.0, 0.0, "counter_reset"

        delta_rx = max(0.0, raw_rx - previous_rx)
        delta_tx = max(0.0, raw_tx - previous_tx)
        return delta_rx, delta_tx, "metrics_ok"

    def _get_syscall_rate(self, pod_uid: str) -> tuple[float, str]:
        """
        Read syscall rate from the eBPF sidecar probe file.

        The sidecar writes a float to:
            /var/run/raasa/<pod-uid>/syscall_rate

        Returns 0.0 if the probe file is absent (graceful degradation).
        """
        probe_path = os.path.join(self.syscall_probe_dir, pod_uid, "syscall_rate")
        probe_status = self._probe_file_status(Path(probe_path))
        if probe_status != "probe_ok":
            return 0.0, probe_status

        raw = _read_proc_file(probe_path)
        if raw is None:
            return 0.0, "probe_missing"
        try:
            value = float(raw)
        except ValueError:
            return 0.0, "probe_invalid"
        if value < 0.0:
            return 0.0, "probe_negative"
        return value, "probe_ok"

    def _get_syscall_counts(self, pod_uid: str) -> tuple[dict[str, int], str]:
        """Read per-syscall sampled counts from the sidecar probe file."""
        probe_path = Path(self.syscall_probe_dir) / pod_uid / "syscall_counts.json"
        probe_status = self._probe_file_status(probe_path)
        if probe_status != "probe_ok":
            return {}, probe_status

        try:
            parsed = json.loads(probe_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}, "probe_invalid"
        if not isinstance(parsed, dict):
            return {}, "probe_invalid"

        counts: dict[str, int] = {}
        for key, value in parsed.items():
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0:
                counts[str(key)] = count
        if not counts:
            return {}, "probe_empty"
        return counts, "probe_ok"

    def _get_lateral_movement_signal(self, pod_uid: str, pod_ip: str) -> tuple[float, str, int, int]:
        """Return 1.0 when the sock_ops edge map shows a first-ever pod edge."""
        pod_ip_norm = self._normalize_ip(pod_ip)
        if not pod_ip_norm:
            return 0.0, "pod_ip_missing", 0, 0

        records, status = self._read_lateral_edge_records()
        if status != "edge_map_ok":
            return 0.0, status, 0, 0

        observed_edges: set[str] = set()
        for edge in records:
            src_ip = self._normalize_ip(edge.get("src_ip"))
            dst_ip = self._normalize_ip(edge.get("dst_ip"))
            if not src_ip or not dst_ip or src_ip == dst_ip:
                continue
            if src_ip == pod_ip_norm:
                observed_edges.add(f"out:{dst_ip}")
            elif dst_ip == pod_ip_norm:
                observed_edges.add(f"in:{src_ip}")

        if not observed_edges:
            return 0.0, "edge_map_no_pod_edges", len(records), 0

        known_edges = self._known_pod_edges.setdefault(pod_uid, set())
        new_edges = observed_edges - known_edges
        known_edges.update(observed_edges)
        if new_edges:
            return 1.0, "new_edge", len(observed_edges), len(new_edges)
        return 0.0, "known_edges", len(observed_edges), 0

    def _get_entropy_samples(self, pod_uid: str, pod_ip: str) -> tuple[dict[str, list[str]], dict[str, str]]:
        file_accesses, file_status = self._read_entropy_sample_list(pod_uid, "file_paths.json", "file_paths")
        dns_queries, dns_status = self._read_entropy_sample_list(pod_uid, "dns_queries.json", "dns_queries")
        network_destinations, network_status = self._get_network_destination_samples(pod_ip)

        return (
            {
                "file_accesses": file_accesses,
                "network_destinations": network_destinations,
                "dns_queries": dns_queries,
            },
            {
                "file_entropy_source": "probe",
                "file_entropy_status": file_status,
                "file_entropy_samples": str(len(file_accesses)),
                "network_entropy_source": "sock_ops",
                "network_entropy_status": network_status,
                "network_entropy_destinations": str(len(set(network_destinations))),
                "dns_entropy_source": "probe",
                "dns_entropy_status": dns_status,
                "dns_entropy_samples": str(len(dns_queries)),
            },
        )

    def _read_lateral_edge_records(self) -> tuple[list[dict], str]:
        edge_path = Path(self.syscall_probe_dir) / "pod_edges.jsonl"
        if not edge_path.exists():
            return [], "edge_map_missing"

        probe_status = self._probe_file_status(edge_path)
        if probe_status != "probe_ok":
            return [], probe_status.replace("probe", "edge_map")

        try:
            raw_text = edge_path.read_text(encoding="utf-8").strip()
        except OSError:
            return [], "edge_map_read_failed"
        if not raw_text:
            return [], "edge_map_empty"

        records: list[dict] = []
        invalid_lines = 0
        if raw_text.startswith("["):
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                return [], "edge_map_invalid"
            if not isinstance(parsed, list):
                return [], "edge_map_invalid"
            records = [item for item in parsed if isinstance(item, dict)]
        else:
            for line in raw_text.splitlines():
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)

        if not records and invalid_lines:
            return [], "edge_map_invalid"
        if not records:
            return [], "edge_map_empty"
        return records, "edge_map_ok"

    def _read_entropy_sample_list(self, pod_uid: str, filename: str, key: str) -> tuple[list[str], str]:
        probe_path = Path(self.syscall_probe_dir) / pod_uid / filename
        probe_status = self._probe_file_status(probe_path)
        if probe_status != "probe_ok":
            return [], probe_status

        try:
            parsed = json.loads(probe_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [], "probe_invalid"

        if isinstance(parsed, dict):
            parsed = parsed.get(key, [])
        if not isinstance(parsed, list):
            return [], "probe_invalid"

        samples = [str(item).strip() for item in parsed if str(item).strip()]
        if not samples:
            return [], "probe_empty"
        return samples[:512], "probe_ok"

    def _get_network_destination_samples(self, pod_ip: str) -> tuple[list[str], str]:
        pod_ip_norm = self._normalize_ip(pod_ip)
        if not pod_ip_norm:
            return [], "pod_ip_missing"

        records, status = self._read_lateral_edge_records()
        if status != "edge_map_ok":
            return [], status.replace("edge_map", "network_entropy")

        destinations: list[str] = []
        for edge in records:
            src_ip = self._normalize_ip(edge.get("src_ip"))
            dst_ip = self._normalize_ip(edge.get("dst_ip"))
            if not src_ip or not dst_ip or src_ip != pod_ip_norm or src_ip == dst_ip:
                continue
            try:
                count = max(1, int(edge.get("count", 1)))
            except (TypeError, ValueError):
                count = 1
            destinations.extend([dst_ip] * min(count, 64))
            if len(destinations) >= 512:
                break

        if not destinations:
            return [], "network_entropy_no_destinations"
        return destinations[:512], "network_entropy_ok"

    def _pod_image(self, pod: object) -> str:
        spec = getattr(pod, "spec", None)
        containers = getattr(spec, "containers", None)
        if not isinstance(containers, list) or not containers:
            return ""
        return str(getattr(containers[0], "image", "") or "")

    def _pod_image_id(self, pod: object) -> str:
        status = getattr(pod, "status", None)
        container_statuses = getattr(status, "container_statuses", None)
        if not isinstance(container_statuses, list) or not container_statuses:
            return ""
        return str(getattr(container_statuses[0], "image_id", "") or "")

    def _normalize_ip(self, raw_value: object) -> str:
        if raw_value is None:
            return ""
        if isinstance(raw_value, (int, float)):
            try:
                return str(ipaddress.IPv4Address(int(raw_value) & 0xFFFFFFFF))
            except ipaddress.AddressValueError:
                return ""

        value = str(raw_value).strip().strip('"')
        if not value:
            return ""
        if value.isdigit():
            try:
                return str(ipaddress.IPv4Address(int(value) & 0xFFFFFFFF))
            except ipaddress.AddressValueError:
                return ""
        try:
            parsed = ipaddress.ip_address(value)
        except ValueError:
            return ""
        if parsed.version != 4:
            return ""
        return str(parsed)

    def _probe_file_status(self, probe_path: Path) -> str:
        if not probe_path.exists():
            return "probe_missing"
        try:
            age_seconds = max(0.0, time.time() - probe_path.stat().st_mtime)
        except OSError:
            return "probe_stat_failed"
        max_age_seconds = max(float(getattr(self, "syscall_probe_max_age_seconds", 15)), 1.0)
        if age_seconds > max_age_seconds:
            return "probe_stale"
        return "probe_ok"

    def _read_process_count(self, pod_uid: str, cpu_percent: float) -> int:
        """
        Read the live PID count for a pod from its cgroup v2 ``pids.current`` file.

        Falls back to a CPU-proportional estimate when the cgroup path does
        not exist or cannot be read in dev/CI.
        """
        uid_cgroup = pod_uid.replace("-", "_")
        uid_short = pod_uid[:12]
        cgroup_patterns = [
            f"/host/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod{uid_cgroup}.slice/pids.current",
            f"/host/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod{pod_uid}.slice/pids.current",
            f"/host/sys/fs/cgroup/kubepods.slice/kubepods-pod{uid_cgroup}.slice/pids.current",
            f"/host/sys/fs/cgroup/kubepods.slice/kubepods-pod{pod_uid}.slice/pids.current",
            f"/host/sys/fs/cgroup/kubepods/{uid_short}/pids.current",
            f"/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod{uid_cgroup}.slice/pids.current",
            f"/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod{pod_uid}.slice/pids.current",
            f"/sys/fs/cgroup/kubepods.slice/kubepods-pod{uid_cgroup}.slice/pids.current",
            f"/sys/fs/cgroup/kubepods.slice/kubepods-pod{pod_uid}.slice/pids.current",
            f"/sys/fs/cgroup/kubepods/{uid_short}/pids.current",
        ]
        for path_str in cgroup_patterns:
            raw = _read_proc_file(path_str)
            if raw is not None:
                try:
                    return max(0, int(raw.strip()))
                except ValueError:
                    pass

        best_count: Optional[int] = None
        uid_tokens = {pod_uid, uid_cgroup, uid_short}
        for root in (
            Path("/host/sys/fs/cgroup/kubepods.slice"),
            Path("/host/sys/fs/cgroup/kubepods"),
            Path("/sys/fs/cgroup/kubepods.slice"),
            Path("/sys/fs/cgroup/kubepods"),
        ):
            try:
                if not root.exists():
                    continue
                for path in root.rglob("pids.current"):
                    path_text = str(path)
                    if not any(token and token in path_text for token in uid_tokens):
                        continue
                    raw = _read_proc_file(path_text)
                    if raw is None:
                        continue
                    try:
                        value = max(0, int(raw.strip()))
                    except ValueError:
                        continue
                    best_count = value if best_count is None else max(best_count, value)
            except OSError:
                continue
        if best_count is not None:
            return best_count
        return max(1, int(cpu_percent / 10))

    def _cache_metrics(self, pod_ref: str, cpu_percent: float, memory_percent: float) -> None:
        self._metrics_cache[pod_ref] = {
            "timestamp": time.time(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
        }

    def _cache_namespace_metrics(self, namespace: str, items: list[dict]) -> None:
        self._namespace_metrics_cache[namespace] = {
            "timestamp": time.time(),
            "items": items,
        }

    def _get_cached_metrics(self, pod_ref: str) -> Optional[Dict[str, float]]:
        if not self.allow_stale_metrics_fallback:
            return None
        cached = self._metrics_cache.get(pod_ref)
        if cached is None:
            return None
        if self.metrics_cache_max_age_seconds <= 0:
            return None
        age_seconds = time.time() - cached["timestamp"]
        if age_seconds > self.metrics_cache_max_age_seconds:
            return None
        return cached

    def _get_cached_namespace_metrics(self, namespace: str) -> Optional[list[dict]]:
        cached = self._namespace_metrics_cache.get(namespace)
        if cached is None:
            return None
        if self.namespace_metrics_cache_max_age_seconds <= 0:
            return None
        age_seconds = time.time() - float(cached["timestamp"])
        if age_seconds > self.namespace_metrics_cache_max_age_seconds:
            return None
        items = cached.get("items")
        if not isinstance(items, list):
            return None
        return items

    def _is_metrics_api_in_cooldown(self) -> bool:
        return time.time() < self._metrics_api_blocked_until

    def _activate_metrics_api_cooldown(self, failure_status: str) -> None:
        self._metrics_api_last_failure_status = failure_status
        if self.metrics_failure_cooldown_seconds <= 0:
            return
        if failure_status in {"metrics_timeout", "metrics_error"}:
            self._metrics_api_blocked_until = time.time() + self.metrics_failure_cooldown_seconds

    def _classify_metrics_exception(self, exc: Exception) -> str:
        message = str(exc).lower()
        if (
            "timeout" in message
            or "timed out" in message
            or "deadline exceeded" in message
            or "subjectaccessreviews" in message
        ):
            return "metrics_timeout"
        if "404" in message or "not found" in message:
            return "metrics_missing"
        return "metrics_error"

    def _summarize_telemetry_status(self, signal_statuses: dict[str, str]) -> tuple[str, str]:
        degraded = [
            f"{signal}:{status}"
            for signal, status in signal_statuses.items()
            if status not in _HEALTHY_SIGNAL_STATUSES
        ]
        if not degraded:
            return "complete", ""
        return "partial", ",".join(degraded)

    def _fallback_pod(self, pod_ref: str, timestamp: datetime, reason: str) -> ContainerTelemetry:
        return ContainerTelemetry(
            container_id=pod_ref,
            timestamp=timestamp,
            cpu_percent=0.0,
            memory_percent=0.0,
            process_count=0,
            metadata={
                "status": "fallback",
                "reason": reason,
                "telemetry_status": "fallback",
                "degraded_signals": "all:unavailable",
                "image": "",
                "image_id": "",
                "cpu_source": "unavailable",
                "cpu_status": "unavailable",
                "metrics_api_status": "unavailable",
                "memory_source": "unavailable",
                "memory_status": "unavailable",
                "network_source": "unavailable",
                "network_status": "unavailable",
                "syscall_source": "unavailable",
                "syscall_status": "unavailable",
                "syscall_counts_source": "unavailable",
                "syscall_counts_status": "unavailable",
                "lateral_movement_source": "unavailable",
                "lateral_movement_status": "unavailable",
                "lateral_movement_total_edges": "0",
                "lateral_movement_new_edges": "0",
                "file_entropy_source": "unavailable",
                "file_entropy_status": "unavailable",
                "file_entropy_samples": "0",
                "network_entropy_source": "unavailable",
                "network_entropy_status": "unavailable",
                "network_entropy_destinations": "0",
                "dns_entropy_source": "unavailable",
                "dns_entropy_status": "unavailable",
                "dns_entropy_samples": "0",
            },
        )

    def _fallback_batch(
        self, pod_refs: List[str], timestamp: datetime, reason: str
    ) -> List[ContainerTelemetry]:
        return [self._fallback_pod(ref, timestamp, reason) for ref in pod_refs]
