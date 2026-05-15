"""
Kubernetes-native telemetry observer for RAASA DaemonSet deployment.

Replaces the Docker CLI observer in production Kubernetes environments.
Uses the official kubernetes Python client to:
  - Enumerate pods on the current node (via field selectors)
  - Read CPU/memory metrics from the Kubernetes Metrics API
  - Read network I/O from pod annotations or cAdvisor scrapes
  - Estimate syscall rates from pod labels (eBPF integration point)

Architecture
------------
In production, RAASA runs as a DaemonSet — one agent pod per node.
Each agent watches only the pods scheduled on its node (``spec.nodeName``).
This keeps the blast radius small: a compromised agent affects one node, not
the whole cluster. The controller receives the same ContainerTelemetry
records it always has; the K8s backend is entirely transparent.

eBPF Integration
----------------
``syscall_rate`` is populated from a sidecar eBPF probe (Tetragon / Falco).
The probe writes per-pod syscall counts to a shared in-memory file
``/var/run/raasa/<pod-uid>/syscall_rate`` which this observer reads.
If the file is absent (probe not deployed), syscall_rate defaults to 0.0
and the linear fallback path handles scoring without kernel signals.

Graceful Degradation
--------------------
Every error path returns a zero-valued ContainerTelemetry with an
explanatory ``metadata["status"]`` — identical to the Docker observer's
fail-safe contract, ensuring the upper layers always function.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry

logger = logging.getLogger(__name__)
_PROMETHEUS_LINE_RE = re.compile(r'^(?P<metric>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+(?P<value>[-+0-9.eE]+)$')


def _read_proc_file(path: str) -> Optional[str]:
    """Read a /proc or sidecar-written file safely."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
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
        Directory where the eBPF sidecar writes per-pod syscall rates.
        Defaults to ``/var/run/raasa``.
    """

    def __init__(
        self,
        namespace_filter: Optional[str] = None,
        node_name: Optional[str] = None,
        syscall_probe_dir: str = "/var/run/raasa",
    ) -> None:
        self.namespace_filter = namespace_filter
        self.node_name = node_name or os.environ.get("NODE_NAME", "")
        self.syscall_probe_dir = syscall_probe_dir
        self._previous_rx: Dict[str, float] = {}
        self._previous_tx: Dict[str, float] = {}
        self._k8s_client = None
        self._metrics_client = None
        self._init_clients()

    def _init_clients(self) -> None:
        """
        Initialise the Kubernetes Python client.

        Tries in-cluster config first (DaemonSet running inside a pod),
        then falls back to kubeconfig (local development / minikube).
        Logs a warning without raising if neither is available — the observer
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
            ``namespace/pod-name`` strings, e.g. ``default/nginx-7d9c9fbb4f-x2k9p``.
            For bare pod names, ``default`` namespace is assumed.
        """
        timestamp = datetime.now(timezone.utc)
        pod_ids = list(container_ids)

        if self._k8s_client is None:
            if not pod_ids:
                return []
            return self._fallback_batch(pod_ids, timestamp, "k8s client unavailable")

        # Auto-discover pods when no explicit IDs are given (DaemonSet mode)
        if not pod_ids:
            pod_ids = self._discover_pods()
            if not pod_ids:
                return []

        network_counter_map = self._build_network_counter_map(self._fetch_cadvisor_metrics())
        results: List[ContainerTelemetry] = []
        for pod_ref in pod_ids:
            results.append(self._collect_pod(pod_ref, timestamp, network_counter_map))
        return results

    # ── Auto-discovery ────────────────────────────────────────────────────────

    _SYSTEM_NAMESPACES = frozenset({"kube-system", "kube-public", "kube-node-lease", "raasa-system"})

    def _discover_pods(self) -> List[str]:
        """
        List all Running pods across the cluster, excluding system namespaces.

        Returns a list of ``namespace/pod-name`` strings suitable for
        passing to ``_collect_pod()``.  This is the DaemonSet auto-discovery
        path — when no explicit ``--containers`` are provided, the controller
        watches everything outside the Kubernetes control plane.
        """
        try:
            if self.namespace_filter:
                pods = self._k8s_client.list_namespaced_pod(
                    namespace=self.namespace_filter,
                    field_selector="status.phase=Running",
                )
            else:
                pods = self._k8s_client.list_pod_for_all_namespaces(
                    field_selector="status.phase=Running",
                )
            discovered = []
            for pod in pods.items:
                ns = pod.metadata.namespace
                if ns in self._SYSTEM_NAMESPACES:
                    continue
                discovered.append(f"{ns}/{pod.metadata.name}")
            if discovered:
                logger.info(f"[ObserverK8s] Auto-discovered {len(discovered)} pod(s): {discovered}")
            return discovered
        except Exception as exc:
            logger.warning(f"[ObserverK8s] Pod discovery failed: {exc}")
            return []

    def _collect_pod(
        self,
        pod_ref: str,
        timestamp: datetime,
        network_counter_map: dict[tuple[str, str], tuple[float, float]],
    ) -> ContainerTelemetry:
        """Collect telemetry for a single pod."""
        # Parse namespace/pod-name
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

            cpu_percent, memory_percent = self._get_pod_metrics(namespace, pod_name, uid)
            delta_rx, delta_tx, network_status = self._get_network_delta(namespace, pod_name, uid, network_counter_map)
            syscall_rate, syscall_status = self._get_syscall_rate(uid)

            return ContainerTelemetry(
                container_id=pod_ref,
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                process_count=self._read_process_count(uid, cpu_percent),
                network_rx_bytes=delta_rx,
                network_tx_bytes=delta_tx,
                syscall_rate=syscall_rate,
                metadata={
                    "status": pod.status.phase or "unknown",
                    "workload_class": workload_class,
                    "expected_tier": expected_tier,
                    "namespace": namespace,
                    "node": self.node_name,
                    "network_source": "cadvisor",
                    "network_status": network_status,
                    "syscall_source": "probe",
                    "syscall_status": syscall_status,
                },
            )
        except Exception as exc:
            logger.warning(f"K8s observer: failed to collect pod {pod_ref}: {exc}")
            return self._fallback_pod(pod_ref, timestamp, str(exc))

    def _get_pod_metrics(self, namespace: str, pod_name: str, pod_uid: str = "") -> tuple[float, float]:
        """
        Fetch CPU and memory usage.

        Since K3s Metrics API times out under load, this directly reads the 
        `.cpu_usec` written by the RAASA syscall probe sidecar.
        """
        cpu_percent = 0.0
        memory_percent = 0.0
        cpu_from_probe = False
        
        # 1. Try reading direct cgroup CPU stats from the probe sidecar
        if pod_uid:
            try:
                probe_dir = Path("/var/run/raasa") / pod_uid
                cpu_file = probe_dir / ".cpu_usec"
                if cpu_file.exists():
                    current_usec = int(cpu_file.read_text(encoding="utf-8").strip())
                    
                    import time
                    current_time = time.time()
                    
                    # Track previous usec and time to compute delta
                    if not hasattr(self, "_prev_cpu_usec"):
                        self._prev_cpu_usec = {}
                        self._prev_cpu_time = {}
                        
                    prev_usec = self._prev_cpu_usec.get(pod_uid, current_usec)
                    prev_time = self._prev_cpu_time.get(pod_uid, current_time - 1.0)
                    
                    delta_usec = max(0, current_usec - prev_usec)
                    delta_time = max(0.1, current_time - prev_time)
                    
                    self._prev_cpu_usec[pod_uid] = current_usec
                    self._prev_cpu_time[pod_uid] = current_time
                    
                    # delta_usec is in microseconds. delta_time is in seconds.
                    # CPU cores used = (delta_usec / 1_000_000) / delta_time
                    cpu_cores = (delta_usec / 1_000_000.0) / delta_time
                    cpu_percent = min(cpu_cores * 100.0, 100.0)
                    cpu_from_probe = True
                    
            except Exception as e:
                logger.warning(f"[ObserverK8s] Direct CPU read failed for {pod_uid}: {e}")

        # 2. Try K8s Metrics API for memory and as a CPU fallback when direct
        # probe data is absent.
        try:
            metrics = self._metrics_client.get_namespaced_custom_object(
                group="metrics.k8s.io",
                version="v1beta1",
                namespace=namespace,
                plural="pods",
                name=pod_name,
            )
            containers = metrics.get("containers", [])
            total_cpu_nano = 0
            total_memory_bytes = 0
            for c in containers:
                usage = c.get("usage", {})
                cpu_raw = str(usage.get("cpu", "0"))
                mem_raw = str(usage.get("memory", "0"))
                if not cpu_from_probe:
                    if cpu_raw.endswith("n"):
                        total_cpu_nano += int(cpu_raw[:-1])
                    elif cpu_raw.endswith("m"):
                        total_cpu_nano += int(cpu_raw[:-1]) * 1_000_000
                    else:
                        try:
                            total_cpu_nano += int(cpu_raw)
                        except ValueError:
                            pass

                # ── Parse Memory ────────────────────────────────────────────
                if mem_raw.endswith("Ki"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024
                elif mem_raw.endswith("Mi"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024 ** 2
                elif mem_raw.endswith("Gi"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024 ** 3
                else:
                    try:
                        total_memory_bytes += int(mem_raw)
                    except ValueError:
                        pass

            if not cpu_from_probe:
                cpu_percent = min((total_cpu_nano / 1e9) * 100.0, 100.0)

            node_memory_bytes = 8 * 1024 ** 3
            memory_percent = min((total_memory_bytes / node_memory_bytes) * 100.0, 100.0)

        except Exception as exc:
            logger.warning(f"[ObserverK8s] Metrics API failed for {namespace}/{pod_name}: {exc}")

        logger.info(
            f"[ObserverK8s] Metrics {namespace}/{pod_name}: "
            f"cpu={cpu_percent:.2f}%, mem={memory_percent:.2f}%"
        )
        return cpu_percent, memory_percent

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

    def _get_network_delta(
        self,
        namespace: str,
        pod_name: str,
        pod_uid: str,
        network_counter_map: dict[tuple[str, str], tuple[float, float]],
    ) -> tuple[float, float, str]:
        key = (namespace, pod_name)
        raw_rx, raw_tx = network_counter_map.get(key, (0.0, 0.0))
        if key not in network_counter_map:
            return 0.0, 0.0, "metrics_unavailable"

        delta_rx = max(0.0, raw_rx - self._previous_rx.get(pod_uid, raw_rx))
        delta_tx = max(0.0, raw_tx - self._previous_tx.get(pod_uid, raw_tx))
        self._previous_rx[pod_uid] = raw_rx
        self._previous_tx[pod_uid] = raw_tx
        return delta_rx, delta_tx, "metrics_ok"

    def _get_syscall_rate(self, pod_uid: str) -> tuple[float, str]:
        """
        Read syscall rate from the eBPF sidecar probe file.

        The sidecar (Tetragon / Falco / custom bpftrace) writes a float to:
            /var/run/raasa/<pod-uid>/syscall_rate
        at the same frequency as the RAASA poll interval.

        Returns 0.0 if the probe file is absent (graceful degradation).
        """
        probe_path = os.path.join(self.syscall_probe_dir, pod_uid, "syscall_rate")
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

    def _read_process_count(self, pod_uid: str, cpu_percent: float) -> int:
        """
        Read the live PID count for a pod from its cgroup v2 ``pids.current`` file.

        On a real Kubernetes (K3s/EKS/GKE) node the kubelet creates a cgroup slice
        for each pod under::

            /sys/fs/cgroup/kubepods.slice/<uid>/pids.current

        This file is written by the kernel and is always up to date. Reading it
        requires no special privileges beyond read access to the cgroup filesystem,
        which the DaemonSet gets via the ``/sys`` hostPath volume mount.

        Falls back to a CPU-proportional estimate when:
          - Not running on a real node (development / CI)
          - The cgroup path does not exist yet (pod still starting)
          - Any OS error occurs (fail-safe, never raises)
        """
        # Build candidate cgroup paths for this pod UID
        uid_short = pod_uid[:12]
        cgroup_patterns = [
            f"/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod{pod_uid}.slice/pids.current",
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
        # Fallback: CPU-proportional estimate (reproducible in dev/CI)
        return max(1, int(cpu_percent / 10))

    def _fallback_pod(self, pod_ref: str, timestamp: datetime, reason: str) -> ContainerTelemetry:
        return ContainerTelemetry(
            container_id=pod_ref,
            timestamp=timestamp,
            cpu_percent=0.0,
            memory_percent=0.0,
            process_count=0,
            metadata={"status": "fallback", "reason": reason},
        )

    def _fallback_batch(
        self, pod_refs: List[str], timestamp: datetime, reason: str
    ) -> List[ContainerTelemetry]:
        return [self._fallback_pod(ref, timestamp, reason) for ref in pod_refs]
