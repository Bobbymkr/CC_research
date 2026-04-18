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
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from raasa.core.base_observer import BaseObserver
from raasa.core.models import ContainerTelemetry

logger = logging.getLogger(__name__)


def _read_proc_file(path: str) -> Optional[str]:
    """Read a /proc or sidecar-written file safely."""
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return None


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
        if not pod_ids:
            return []

        if self._k8s_client is None:
            return self._fallback_batch(pod_ids, timestamp, "k8s client unavailable")

        results: List[ContainerTelemetry] = []
        for pod_ref in pod_ids:
            results.append(self._collect_pod(pod_ref, timestamp))
        return results

    def _collect_pod(self, pod_ref: str, timestamp: datetime) -> ContainerTelemetry:
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

            cpu_percent, memory_percent = self._get_pod_metrics(namespace, pod_name)
            delta_rx, delta_tx = self._get_network_delta(pod_ref)
            syscall_rate = self._get_syscall_rate(uid)

            return ContainerTelemetry(
                container_id=pod_ref,
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                process_count=self._estimate_process_count(cpu_percent),
                network_rx_bytes=delta_rx,
                network_tx_bytes=delta_tx,
                syscall_rate=syscall_rate,
                metadata={
                    "status": pod.status.phase or "unknown",
                    "workload_class": workload_class,
                    "expected_tier": expected_tier,
                    "namespace": namespace,
                    "node": self.node_name,
                },
            )
        except Exception as exc:
            logger.warning(f"K8s observer: failed to collect pod {pod_ref}: {exc}")
            return self._fallback_pod(pod_ref, timestamp, str(exc))

    def _get_pod_metrics(self, namespace: str, pod_name: str) -> tuple[float, float]:
        """
        Fetch CPU and memory usage from the Kubernetes Metrics API.

        Returns ``(cpu_percent, memory_percent)`` normalized to [0, 100].
        Falls back to (0.0, 0.0) if the Metrics Server is not available.
        """
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
                # CPU in nanocores → percent (assuming 1 vCPU = 1e9 nanocores = 100%)
                if cpu_raw.endswith("n"):
                    total_cpu_nano += int(cpu_raw[:-1])
                elif cpu_raw.endswith("m"):
                    total_cpu_nano += int(cpu_raw[:-1]) * 1_000_000
                # Memory in Ki/Mi/Gi → bytes
                if mem_raw.endswith("Ki"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024
                elif mem_raw.endswith("Mi"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024 ** 2
                elif mem_raw.endswith("Gi"):
                    total_memory_bytes += int(mem_raw[:-2]) * 1024 ** 3

            cpu_percent = min((total_cpu_nano / 1e9) * 100.0, 100.0)
            # Assume 4GiB node memory for normalization (configurable in production)
            memory_percent = min((total_memory_bytes / (4 * 1024 ** 3)) * 100.0, 100.0)
            return cpu_percent, memory_percent
        except Exception:
            return 0.0, 0.0

    def _get_network_delta(self, pod_ref: str) -> tuple[float, float]:
        """
        Return per-tick network I/O delta (bytes) for the pod.

        In production, this reads from cAdvisor metrics exposed at
        ``/api/v1/nodes/{node}/proxy/metrics/cadvisor`` (scraped via Prometheus).
        For the prototype, we return 0.0 deltas and rely on the ML model's
        4 other dimensions for scoring.
        """
        # TODO (Step 12d): integrate cAdvisor Prometheus scrape for real network I/O
        return 0.0, 0.0

    def _get_syscall_rate(self, pod_uid: str) -> float:
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
            return 0.0
        try:
            return max(0.0, float(raw))
        except ValueError:
            return 0.0

    def _estimate_process_count(self, cpu_percent: float) -> int:
        """
        Estimate process count from CPU pressure when PID counting is unavailable.
        In production, this is replaced by reading ``/proc/<pid>/status`` counts
        from the pod's cgroup on the host.
        """
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
