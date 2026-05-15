from __future__ import annotations

import shutil
import subprocess
from typing import Callable, Iterable

from raasa.core.models import PolicyDecision, Tier


CommandRunner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


class ActionEnforcer:
    """Applies CPU-based containment for the selected tier."""

    def __init__(
        self,
        cpus_by_tier: dict[Tier | str, float] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.cpus_by_tier = {
            (key if isinstance(key, str) else key.value): float(value)
            for key, value in (cpus_by_tier or {"L1": 1.0, "L2": 0.5, "L3": 0.2}).items()
        }
        self.runner = runner or _default_runner
        self.last_applied_tier: dict[str, str] = {}

    def apply(self, decisions: Iterable[PolicyDecision]) -> None:
        if shutil.which("docker") is None and self.runner is _default_runner:
            return

        for decision in decisions:
            target_tier = decision.applied_tier.value
            if self.last_applied_tier.get(decision.container_id) == target_tier:
                continue
            cpu_value = self.cpus_by_tier[target_tier]
            try:
                self.runner(
                    [
                        "docker",
                        "update",
                        "--cpus",
                        f"{cpu_value}",
                        decision.container_id,
                    ]
                )
                self.last_applied_tier[decision.container_id] = target_tier
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
