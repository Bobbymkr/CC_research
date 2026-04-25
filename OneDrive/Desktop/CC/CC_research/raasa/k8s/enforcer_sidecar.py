"""
Privileged Enforcer Sidecar Daemon.

Runs as root with NET_ADMIN and SYS_ADMIN in the same pod as the unprivileged
RAASA controller. Listens on a Unix Domain Socket for JSON containment
commands and executes `tc` and `cgroup` modifications.
"""

import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

from raasa.core.ipc import UnixSocketServer, DEFAULT_SOCKET_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("raasa-enforcer")

BANDWIDTH_BY_TIER: Dict[str, str] = {
    "L1": "1000mbit",
    "L2": "100mbit",
    "L3": "1mbit",
}

TC_BURST = "32kbit"
TC_LATENCY = "400ms"

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


def _run_tc(args: list[str]) -> bool:
    """Run a tc command. Returns True on success, False on any failure."""
    try:
        result = subprocess.run(["tc"] + args, capture_output=True, text=True)
        if result.returncode != 0:
            logger.debug(f"[tc] {' '.join(args)} → rc={result.returncode}: {result.stderr.strip()}")
        return result.returncode == 0
    except Exception as exc:
        logger.warning(f"tc command failed: {exc}")
        return False


def _apply_network_throttle(pod_id: str, tier: str, interface: str = DEFAULT_INTERFACE) -> bool:
    bandwidth = BANDWIDTH_BY_TIER.get(tier, "1000mbit")
    _run_tc(["qdisc", "del", "dev", interface, "root"])
    ok = _run_tc([
        "qdisc", "add", "dev", interface,
        "root", "tbf",
        "rate", bandwidth,
        "burst", TC_BURST,
        "latency", TC_LATENCY,
    ])
    if ok:
        logger.info(f"tc: {pod_id} ({interface}) → {tier} at {bandwidth}")
    else:
        logger.warning(f"tc: failed to set {bandwidth} on {interface} for {pod_id}")
    return ok


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
            logger.info(f"cgroup: {pod_id} memory.max → {limit_str} ({mem_max_path})")
            success = True
        except OSError as exc:
            logger.warning(f"cgroup write failed for {mem_max_path}: {exc}")
    return success


def handle_command(payload: Dict[str, Any]) -> bool:
    """Handle incoming IPC command."""
    container_id = payload.get("container_id")
    tier = payload.get("tier")
    
    if not container_id or not tier:
        logger.error(f"Invalid payload missing required fields: {payload}")
        return False

    # Extract clean pod UID or identifier (e.g., 'default/raasa-test-benign')
    # For cgroup searching we just need the pod name or UID part
    pod_id = container_id.split("/")[-1] if "/" in container_id else container_id

    # For the prototype running with hostNetwork: true, throttling eth0 directly
    # throttles ALL node egress. In a real CNI integration we'd resolve the veth
    # associated with the pod_id. 
    # For this cloud deployment, we will apply the limits to eth0 to simulate 
    # the node-level egress throttle for the sandbox.
    net_ok = _apply_network_throttle(pod_id, tier, DEFAULT_INTERFACE)
    mem_ok = _apply_memory_limit(pod_id, tier)

    return net_ok or mem_ok


def main():
    if os.getuid() != 0:
        logger.fatal("Enforcer sidecar MUST run as root!")
        exit(1)

    logger.info("Starting Privileged Enforcer Sidecar")
    server = UnixSocketServer(handler=handle_command)
    server.start()

    # Keep daemon alive
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop()

if __name__ == "__main__":
    main()
