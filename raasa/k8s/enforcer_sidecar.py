"""
Privileged Enforcer Sidecar Daemon.

Runs as root with NET_ADMIN and SYS_ADMIN in the same pod as the unprivileged
RAASA controller. Listens on a Unix Domain Socket for JSON containment
commands and executes `tc` and `cgroup` modifications.
"""

import logging
import os
import re
import shutil
import subprocess
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from kubernetes import client, config
except ImportError:  # pragma: no cover - exercised in minimal local test envs
    client = None
    config = None

from raasa.core.ipc import (
    CommandVerifier,
    DEFAULT_PUBLIC_KEY_PATH,
    DEFAULT_SOCKET_PATH,
    UnixSocketServer,
    ipc_gid_from_env,
)

try:
    from raasa.k8s.bpf_loader import BpfLoader
except Exception:  # pragma: no cover - loader failures degrade at startup
    BpfLoader = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("raasa-enforcer")
_K8S_NAME_RE = re.compile(r"^[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?$")
_ALLOWED_COMMAND_KEYS = frozenset({"container_id", "tier"})

NETWORK_PROFILE_BY_TIER: Dict[str, Dict[str, str]] = {
    "L1": {"mode": "clear"},
    # L2 is intended to stay degraded but still operational.
    "L2": {
        "mode": "tbf",
        "rate": "20mbit",
        "burst": "1mbit",
        "latency": "250ms",
    },
    # L3 is explicit hard containment.
    "L3": {
        "mode": "netem_loss",
        "loss": "100%",
    },
}

MEMORY_BY_TIER: Dict[str, int] = {
    "L1": -1,
    "L2": 512 * 1024 * 1024,
    "L3": 128 * 1024 * 1024,
}

# The physical host veth interface prefix used by calico/flannel in k3s.
# To find the exact interface we'd need netns resolution.
# For simplicity in this prototype, if `hostNetwork: true`, we attempt
# to throttle `eth0` of the host or known veths.
# A full implementation uses `ip netns` or eBPF TC hooks.
DEFAULT_INTERFACE = "cni0"
CGROUP_BASE_PATH = Path("/sys/fs/cgroup")
DEFAULT_LSM_BLOCK_MAP_PIN = Path("/sys/fs/bpf/raasa/maps/raasa_lsm_blocked_tgids")
POD_NET_INTERFACE_NAME = "eth0"
_K8S_CORE_API: Optional[Any] = None
_K8S_NETWORKING_API: Optional[Any] = None
_LAST_INTERFACE_BY_CONTAINER: Dict[str, str] = {}
_LSM_TRACKED_PIDS_BY_CONTAINER: Dict[str, set[int]] = {}
_BPF_LOADER: Optional[Any] = None
_HOST_INTERFACE_SKIPLIST = {"lo", "eth0", DEFAULT_INTERFACE}
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
NETWORK_POLICY_LABEL_KEY = "raasa.io/contained-pod"
NETWORK_POLICY_TIER_LABEL_KEY = "raasa.io/enforced-tier"
NETWORK_POLICY_NAME_PREFIX = "raasa-l3-contain-"


def _init_k8s_client() -> Optional[Any]:
    global _K8S_CORE_API
    if _K8S_CORE_API is not None:
        return _K8S_CORE_API

    if client is None or config is None:
        logger.warning("Kubernetes client package is not installed in enforcer sidecar environment.")
        return None

    try:
        config.load_incluster_config()
        _K8S_CORE_API = client.CoreV1Api()
        return _K8S_CORE_API
    except Exception as exc:
        logger.warning(f"K8s client init failed in enforcer sidecar: {exc}")
        return None


def _init_k8s_networking_client() -> Optional[Any]:
    global _K8S_NETWORKING_API
    if _K8S_NETWORKING_API is not None:
        return _K8S_NETWORKING_API

    if client is None or config is None:
        logger.warning("Kubernetes client package is not installed in enforcer sidecar environment.")
        return None

    try:
        config.load_incluster_config()
        _K8S_NETWORKING_API = client.NetworkingV1Api()
        return _K8S_NETWORKING_API
    except Exception as exc:
        logger.warning(f"K8s networking client init failed in enforcer sidecar: {exc}")
        return None


def _run_tc(args: list[str]) -> bool:
    """Run a tc command. Returns True on success, False on any failure."""
    try:
        result = subprocess.run(["tc"] + args, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug(f"[tc] {' '.join(args)} â†’ rc={result.returncode}: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as exc:
        logger.warning(f"tc command failed: {exc}")
        return False


def _run_command(command: list[str]) -> Optional[str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug("command failed rc=%s: %s", result.returncode, " ".join(command))
            if result.stderr.strip():
                logger.debug(result.stderr.strip())
            return None
        return result.stdout.strip()
    except Exception as exc:
        logger.warning(f"command failed ({' '.join(command)}): {exc}")
        return None


def _lsm_block_map_path() -> Path:
    raw = os.environ.get("RAASA_LSM_BLOCK_MAP_PIN", "").strip()
    return Path(raw) if raw else DEFAULT_LSM_BLOCK_MAP_PIN


def _bpftool_available() -> bool:
    return shutil.which("bpftool") is not None


def _lsm_block_map_ready(map_path: Optional[Path] = None) -> bool:
    return (map_path or _lsm_block_map_path()).exists()


def _hex_u32(value: int) -> list[str]:
    if value < 0 or value > 0xFFFFFFFF:
        raise ValueError("value does not fit in an unsigned 32-bit integer")
    return [f"{byte:02x}" for byte in value.to_bytes(4, "little", signed=False)]


def _update_lsm_block_map(pid: int, blocked: bool, map_path: Optional[Path] = None) -> bool:
    target = map_path or _lsm_block_map_path()
    if not _bpftool_available() or not _lsm_block_map_ready(target):
        return False

    value = 1 if blocked else 0
    command = [
        "bpftool",
        "map",
        "update",
        "pinned",
        str(target),
        "key",
        "hex",
        *_hex_u32(pid),
        "value",
        "hex",
        *_hex_u32(value),
    ]
    return _run_command(command) is not None


def _parse_container_ref(container_id: str) -> tuple[str, str]:
    if "/" in container_id:
        namespace, pod_name = container_id.split("/", 1)
        return namespace, pod_name
    return "default", container_id


def _is_valid_k8s_name(value: str) -> bool:
    return bool(value) and len(value) <= 253 and _K8S_NAME_RE.fullmatch(value) is not None


def _validate_command_payload(payload: Dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"

    extra_keys = sorted(set(payload) - _ALLOWED_COMMAND_KEYS)
    if extra_keys:
        return False, f"unexpected fields: {', '.join(extra_keys)}"

    container_id = payload.get("container_id")
    tier = payload.get("tier")
    if not isinstance(container_id, str) or not container_id.strip():
        return False, "container_id must be a non-empty string"
    if not isinstance(tier, str) or tier not in NETWORK_PROFILE_BY_TIER:
        return False, "tier must be one of L1, L2, or L3"

    namespace, pod_name = _parse_container_ref(container_id.strip())
    if not _is_valid_k8s_name(namespace):
        return False, "namespace is not a valid Kubernetes resource name"
    if not _is_valid_k8s_name(pod_name):
        return False, "pod name is not a valid Kubernetes resource name"
    return True, ""


def _contained_pod_token(namespace: str, pod_name: str) -> str:
    raw = re.sub(r"[^a-z0-9.-]+", "-", f"{namespace}-{pod_name}".lower()).strip(".-")
    digest = hashlib.sha256(f"{namespace}/{pod_name}".encode("utf-8")).hexdigest()[:10]
    prefix = raw[:52].strip(".-") or "pod"
    return f"{prefix}-{digest}"


def _network_policy_name(namespace: str, pod_name: str) -> str:
    token = _contained_pod_token(namespace, pod_name)
    return f"{NETWORK_POLICY_NAME_PREFIX}{token}"[:253].rstrip(".-")


def _l3_network_policy_body(namespace: str, pod_name: str) -> Dict[str, Any]:
    token = _contained_pod_token(namespace, pod_name)
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": _network_policy_name(namespace, pod_name),
            "namespace": namespace,
            "labels": {
                "app.kubernetes.io/managed-by": "raasa",
                NETWORK_POLICY_LABEL_KEY: token,
                NETWORK_POLICY_TIER_LABEL_KEY: "L3",
            },
        },
        "spec": {
            "podSelector": {
                "matchLabels": {
                    NETWORK_POLICY_LABEL_KEY: token,
                    NETWORK_POLICY_TIER_LABEL_KEY: "L3",
                }
            },
            "policyTypes": ["Ingress", "Egress"],
            "ingress": [],
            "egress": [],
        },
    }


def _patch_pod_containment_labels(namespace: str, pod_name: str, tier: str) -> bool:
    core_api = _init_k8s_client()
    if core_api is None:
        return False

    if tier == "L3":
        labels = {
            NETWORK_POLICY_LABEL_KEY: _contained_pod_token(namespace, pod_name),
            NETWORK_POLICY_TIER_LABEL_KEY: "L3",
        }
    else:
        labels = {
            NETWORK_POLICY_LABEL_KEY: None,
            NETWORK_POLICY_TIER_LABEL_KEY: None,
        }

    try:
        core_api.patch_namespaced_pod(name=pod_name, namespace=namespace, body={"metadata": {"labels": labels}})
        return True
    except Exception as exc:
        logger.warning(f"Failed to patch containment labels on pod {namespace}/{pod_name}: {exc}")
        return False


def _api_status(exc: Exception) -> Optional[int]:
    status = getattr(exc, "status", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def _ensure_l3_network_policy(namespace: str, pod_name: str) -> bool:
    networking_api = _init_k8s_networking_client()
    if networking_api is None:
        return False
    if not _patch_pod_containment_labels(namespace, pod_name, "L3"):
        return False

    name = _network_policy_name(namespace, pod_name)
    body = _l3_network_policy_body(namespace, pod_name)
    try:
        networking_api.patch_namespaced_network_policy(name=name, namespace=namespace, body=body)
        logger.info(f"NetworkPolicy: patched deny-all L3 policy {namespace}/{name}")
        return True
    except Exception as exc:
        if _api_status(exc) != 404:
            logger.warning(f"Failed to patch NetworkPolicy {namespace}/{name}: {exc}")
            return False

    try:
        networking_api.create_namespaced_network_policy(namespace=namespace, body=body)
        logger.info(f"NetworkPolicy: created deny-all L3 policy {namespace}/{name}")
        return True
    except Exception as exc:
        if _api_status(exc) == 409:
            return True
        logger.warning(f"Failed to create NetworkPolicy {namespace}/{name}: {exc}")
        return False


def _clear_l3_network_policy(namespace: str, pod_name: str) -> bool:
    networking_api = _init_k8s_networking_client()
    label_ok = _patch_pod_containment_labels(namespace, pod_name, "L1")
    if networking_api is None:
        return label_ok

    name = _network_policy_name(namespace, pod_name)
    try:
        networking_api.delete_namespaced_network_policy(name=name, namespace=namespace)
        logger.info(f"NetworkPolicy: deleted L3 policy {namespace}/{name}")
        return label_ok
    except Exception as exc:
        if _api_status(exc) == 404:
            return label_ok
        logger.warning(f"Failed to delete NetworkPolicy {namespace}/{name}: {exc}")
        return False


def _apply_network_policy(container_id: str, tier: str) -> bool:
    namespace, pod_name = _parse_container_ref(container_id)
    if tier == "L3":
        return _ensure_l3_network_policy(namespace, pod_name)
    return _clear_l3_network_policy(namespace, pod_name)


def _allow_default_interface_fallback() -> bool:
    return os.environ.get("RAASA_ALLOW_DEFAULT_INTERFACE_FALLBACK", "").strip().lower() in _TRUTHY_ENV_VALUES


def _enforcer_bpf_loader_enabled() -> bool:
    raw = os.environ.get("RAASA_ENFORCER_LOAD_BPF", "true")
    return raw.strip().lower() in _TRUTHY_ENV_VALUES


def _bpf_export_interval_seconds() -> float:
    try:
        return max(1.0, float(os.environ.get("RAASA_BPF_EXPORT_INTERVAL_SECONDS", "5")))
    except ValueError:
        return 5.0


def _init_bpf_loader_from_env() -> Optional[Any]:
    global _BPF_LOADER
    if not _enforcer_bpf_loader_enabled():
        logger.info("RAASA eBPF loader disabled by RAASA_ENFORCER_LOAD_BPF")
        _BPF_LOADER = None
        return None
    if BpfLoader is None:
        logger.warning("RAASA eBPF loader module could not be imported; eBPF programs will not be loaded.")
        _BPF_LOADER = None
        return None

    try:
        loader = BpfLoader.from_env()
        results = loader.load_all()
        for result in results.values():
            log = logger.info if result.ok else logger.warning
            log("RAASA eBPF %s: %s", result.component, result.status_line)
        _BPF_LOADER = loader
        return loader
    except Exception as exc:
        logger.warning("RAASA eBPF loader startup failed: %s", exc)
        _BPF_LOADER = None
        return None


def _export_bpf_edges_once(loader: Any) -> None:
    try:
        result = loader.export_pod_edges()
    except Exception as exc:
        logger.debug("RAASA eBPF pod edge export failed: %s", exc)
        return
    if not result.ok and result.status not in {"edge_map_missing", "edge_map_empty"}:
        logger.debug("RAASA eBPF pod edge export status: %s", result.status_line)


def _find_host_pids_for_pod_uid(pod_uid: str) -> list[int]:
    uid_variants = {pod_uid, pod_uid.replace("-", "_")}
    matches: list[int] = []
    for proc_entry in Path("/proc").iterdir():
        if not proc_entry.name.isdigit():
            continue
        cgroup_path = proc_entry / "cgroup"
        try:
            raw = cgroup_path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(uid in raw for uid in uid_variants):
            matches.append(int(proc_entry.name))
    return matches


def _resolve_pod_uid(container_id: str) -> Optional[str]:
    namespace, pod_name = _parse_container_ref(container_id)
    core_api = _init_k8s_client()
    if core_api is None:
        return None

    try:
        pod = core_api.read_namespaced_pod(name=pod_name, namespace=namespace)
    except Exception as exc:
        logger.warning(f"Failed to resolve pod {container_id} via K8s API: {exc}")
        return None

    pod_uid = (pod.metadata.uid or "").strip()
    if not pod_uid:
        logger.warning(f"Pod {container_id} has no UID; cannot resolve host process state.")
        return None
    return pod_uid


def _read_target_iflink(pid: int, interface_name: str) -> Optional[int]:
    iflink_raw = _run_command([
        "nsenter",
        "-t",
        str(pid),
        "-n",
        "cat",
        f"/sys/class/net/{interface_name}/iflink",
    ])
    if not iflink_raw:
        return None

    try:
        return int(iflink_raw.strip().splitlines()[-1])
    except ValueError:
        logger.warning(f"Could not parse iflink value for PID {pid}: {iflink_raw!r}")
        return None


def _list_target_interfaces(pid: int) -> list[tuple[str, Optional[int]]]:
    raw = _run_command([
        "nsenter",
        "-t",
        str(pid),
        "-n",
        "ip",
        "-o",
        "link",
        "show",
    ])
    if not raw:
        return []

    interfaces: list[tuple[str, Optional[int]]] = []
    for line in raw.splitlines():
        match = re.match(r"^\d+:\s+([^:@]+)(?:@if(\d+))?:", line.strip())
        if not match:
            continue
        iface = match.group(1).strip()
        peer_ifindex = int(match.group(2)) if match.group(2) else None
        if iface and all(existing_iface != iface for existing_iface, _ in interfaces):
            interfaces.append((iface, peer_ifindex))
    return interfaces


def _resolve_host_interface_for_pid(pid: int) -> Optional[str]:
    interface_details = _list_target_interfaces(pid)
    candidate_interfaces: list[tuple[str, Optional[int]]] = []
    for candidate_iface, peer_ifindex in interface_details:
        if candidate_iface == POD_NET_INTERFACE_NAME:
            candidate_interfaces.insert(0, (candidate_iface, peer_ifindex))
        else:
            candidate_interfaces.append((candidate_iface, peer_ifindex))

    if not candidate_interfaces:
        candidate_interfaces.append((POD_NET_INTERFACE_NAME, None))

    iflink = None
    attempted: list[str] = []
    for candidate_iface, peer_ifindex in candidate_interfaces:
        attempted.append(f"{candidate_iface}:{peer_ifindex or 'none'}")
        if peer_ifindex is not None:
            iflink = peer_ifindex
            break
        iflink = _read_target_iflink(pid, candidate_iface)
        if iflink is not None:
            break

    if iflink is None:
        logger.debug("Could not determine peer ifindex for PID %s. Candidates=%s", pid, attempted)
        return None

    for iface_entry in Path("/sys/class/net").iterdir():
        ifindex_path = iface_entry / "ifindex"
        try:
            ifindex = int(ifindex_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        if ifindex == iflink:
            return iface_entry.name
    return None


def _resolve_pod_interface(container_id: str) -> Optional[str]:
    pod_uid = _resolve_pod_uid(container_id)
    if not pod_uid:
        return None

    pids = _find_host_pids_for_pod_uid(pod_uid)
    if not pids:
        logger.warning(f"Could not find host PID for pod {container_id} (uid={pod_uid}).")
        return None

    interface = None
    attempted: list[str] = []
    for pid in pids:
        candidate = _resolve_host_interface_for_pid(pid)
        attempted.append(f"{pid}:{candidate or 'none'}")
        if candidate and candidate not in _HOST_INTERFACE_SKIPLIST:
            interface = candidate
            logger.info(f"Resolved pod {container_id} to host interface {interface} via PID {pid}.")
            break

    if interface is None:
        logger.warning(
            "Could not map pod %s (uid=%s) to a pod-specific host interface. Attempts=%s",
            container_id,
            pod_uid,
            ", ".join(attempted),
        )
    return interface


def _apply_lsm_exec_block(container_id: str, tier: str) -> bool:
    map_path = _lsm_block_map_path()
    if not _bpftool_available() or not _lsm_block_map_ready(map_path):
        logger.debug("eBPF LSM exec blocking map is not available at %s", map_path)
        return False

    pod_uid = _resolve_pod_uid(container_id)
    if not pod_uid:
        return False

    current_pids = set(_find_host_pids_for_pod_uid(pod_uid))
    tracked_pids = _LSM_TRACKED_PIDS_BY_CONTAINER.get(container_id, set())
    if tier == "L3":
        target_pids = current_pids
        blocked = True
        _LSM_TRACKED_PIDS_BY_CONTAINER[container_id] = set(current_pids)
    else:
        target_pids = current_pids | tracked_pids
        blocked = False
        _LSM_TRACKED_PIDS_BY_CONTAINER.pop(container_id, None)

    if not target_pids:
        logger.debug("No host PIDs found for eBPF LSM exec control on %s", container_id)
        return False

    success = False
    for pid in sorted(target_pids):
        if _update_lsm_block_map(pid, blocked, map_path):
            success = True

    if success:
        action = "blocked" if blocked else "cleared"
        logger.info("eBPF LSM exec blocking %s for %s host PID(s) on %s", action, len(target_pids), container_id)
    else:
        logger.warning("Failed to update eBPF LSM exec block map for %s", container_id)
    return success


def _clear_network_throttle(interface: str) -> bool:
    return _run_tc(["qdisc", "del", "dev", interface, "root"])


def _apply_network_throttle(pod_id: str, tier: str, interface: str = DEFAULT_INTERFACE) -> bool:
    profile = NETWORK_PROFILE_BY_TIER.get(tier, NETWORK_PROFILE_BY_TIER["L1"])
    _clear_network_throttle(interface)

    mode = profile.get("mode", "clear")
    if mode == "clear":
        logger.info(f"tc: {pod_id} ({interface}) -> L1 reset (no root qdisc)")
        return True

    if mode == "tbf":
        ok = _run_tc([
            "qdisc", "add", "dev", interface,
            "root", "tbf",
            "rate", profile["rate"],
            "burst", profile["burst"],
            "latency", profile["latency"],
        ])
        if ok:
            logger.info(f"tc: {pod_id} ({interface}) -> {tier} at {profile['rate']}")
        else:
            logger.warning(f"tc: failed to set {profile['rate']} on {interface} for {pod_id}")
        return ok

    if mode == "netem_loss":
        ok = _run_tc([
            "qdisc", "add", "dev", interface,
            "root", "netem",
            "loss", profile["loss"],
        ])
        if ok:
            logger.info(f"tc: {pod_id} ({interface}) -> {tier} netem loss {profile['loss']}")
        else:
            logger.warning(f"tc: failed to set netem loss {profile['loss']} on {interface} for {pod_id}")
        return ok

    logger.warning(f"Unknown network profile mode {mode!r} for tier {tier}; no throttle applied.")
    return False


def _apply_memory_limit(pod_id: str, tier: str) -> bool:
    limit_bytes = MEMORY_BY_TIER.get(tier, -1)
    limit_str = "max" if limit_bytes == -1 else str(limit_bytes)

    cgroup_candidates = list(CGROUP_BASE_PATH.glob(
        f"kubepods.slice/**/{pod_id[:12]}*/memory.max"
    ))

    if not cgroup_candidates:
        return False

    success = False
    for mem_max_path in cgroup_candidates:
        try:
            mem_max_path.write_text(limit_str, encoding="utf-8")
            logger.info(f"cgroup: {pod_id} memory.max â†’ {limit_str} ({mem_max_path})")
            success = True
        except OSError as exc:
            logger.warning(f"cgroup write failed for {mem_max_path}: {exc}")
    return success


def handle_command(payload: Dict[str, Any]) -> bool:
    """Handle incoming IPC command."""
    valid, error = _validate_command_payload(payload)
    if not valid:
        logger.error(f"Rejected IPC payload: {error}. Payload={payload!r}")
        return False
    container_id = str(payload["container_id"]).strip()
    tier = str(payload["tier"])

    # Extract clean pod UID or identifier (e.g., 'default/raasa-test-benign')
    # For cgroup searching we just need the pod name or UID part
    pod_id = container_id.split("/")[-1] if "/" in container_id else container_id

    policy_ok = _apply_network_policy(container_id, tier)
    lsm_ok = _apply_lsm_exec_block(container_id, tier)

    interface = _resolve_pod_interface(container_id)
    if interface is None:
        interface = _LAST_INTERFACE_BY_CONTAINER.get(container_id)
        if interface is None and _allow_default_interface_fallback():
            interface = DEFAULT_INTERFACE
        if interface is None:
            logger.error(
                "No pod-specific host interface resolved for %s; refusing broad fallback. "
                "Set RAASA_ALLOW_DEFAULT_INTERFACE_FALLBACK=true only for explicit diagnostics.",
                container_id,
            )
            return policy_ok or lsm_ok
        logger.warning(f"Falling back to cached/default interface {interface} for {container_id}.")
    else:
        _LAST_INTERFACE_BY_CONTAINER[container_id] = interface

    net_ok = _apply_network_throttle(pod_id, tier, interface)
    mem_ok = _apply_memory_limit(pod_id, tier)

    return net_ok or mem_ok or policy_ok or lsm_ok


def _wait_for_public_key(public_key_path: str, timeout_seconds: float) -> bool:
    deadline = time.time() + max(0.0, timeout_seconds)
    while time.time() < deadline:
        if os.path.exists(public_key_path):
            return True
        time.sleep(0.25)
    return os.path.exists(public_key_path)


def main():
    if os.getuid() != 0:
        logger.fatal("Enforcer sidecar MUST run as root!")
        exit(1)

    logger.info("Starting Privileged Enforcer Sidecar")
    bpf_loader = _init_bpf_loader_from_env()
    ipc_gid = ipc_gid_from_env(default=1000)
    public_key_path = os.environ.get("RAASA_IPC_SIGNING_PUBLIC_KEY", DEFAULT_PUBLIC_KEY_PATH)
    socket_path = os.environ.get("RAASA_IPC_SOCKET_PATH", DEFAULT_SOCKET_PATH)
    try:
        public_key_wait_seconds = float(os.environ.get("RAASA_IPC_PUBLIC_KEY_WAIT_SECONDS", "60"))
    except ValueError:
        public_key_wait_seconds = 60.0
    if not _wait_for_public_key(public_key_path, public_key_wait_seconds):
        logger.fatal("Signed IPC public key did not appear at %s", public_key_path)
        exit(1)
    verifier = CommandVerifier.from_public_key_file(public_key_path)
    server = UnixSocketServer(
        handler=handle_command,
        socket_path=socket_path,
        verifier=verifier,
        socket_gid=ipc_gid,
        ipc_dir_gid=ipc_gid,
    )
    server.start()

    # Keep daemon alive
    try:
        while True:
            if bpf_loader is not None:
                _export_bpf_edges_once(bpf_loader)
                time.sleep(_bpf_export_interval_seconds())
            else:
                time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop()

if __name__ == "__main__":
    main()
