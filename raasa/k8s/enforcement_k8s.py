"""
Kubernetes-native enforcement backend for RAASA v2.

This component now acts as an Unprivileged IPC Client.
It sends JSON enforcement decisions over a Unix Domain Socket to the
Privileged Enforcer Sidecar, which actually executes `tc` and `cgroup` logic.
"""
from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

from raasa.core.models import PolicyDecision
from raasa.core.ipc import UnixSocketClient

logger = logging.getLogger(__name__)


class EnforcerK8s:
    """
    Kubernetes-native enforcement backend (Client).

    Sends containment requests to the privileged sidecar via IPC.
    """

    def __init__(
        self,
        cpus_by_tier: Optional[Dict[str, float]] = None,
        cgroup_base_path: str = "/sys/fs/cgroup",
    ) -> None:
        self.cpus_by_tier = cpus_by_tier or {"L1": 1.0, "L2": 0.5, "L3": 0.2}
        self.last_applied_tier: Dict[str, str] = {}
        self.ipc_client = UnixSocketClient()

    def wait_until_ready(self, timeout_seconds: float = 15.0) -> bool:
        """Wait for the privileged sidecar socket to accept connections."""
        return self.ipc_client.wait_until_available(timeout_seconds=timeout_seconds)

    def apply(self, decisions: Iterable[PolicyDecision]) -> None:
        """Apply all enforcement decisions by sending IPC commands."""
        for decision in decisions:
            tier = decision.applied_tier.value
            cid = decision.container_id

            # Skip if tier has not changed
            if self.last_applied_tier.get(cid) == tier:
                continue

            payload = {
                "container_id": cid,
                "tier": tier
            }

            success = self.ipc_client.send_command(payload)

            if success:
                logger.info(f"[EnforcerK8s] Successfully delegated containment of {cid} → {tier} to sidecar.")
                self.last_applied_tier[cid] = tier
            else:
                logger.warning(f"[EnforcerK8s] Failed to delegate containment of {cid} to sidecar. Will retry next tick.")
