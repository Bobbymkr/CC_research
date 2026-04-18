from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from raasa.workloads.catalog import WORKLOAD_CATALOG, WorkloadSpec


@dataclass(frozen=True, slots=True)
class ScenarioItem:
    name: str
    workload: WorkloadSpec


SCENARIO_LAYOUTS = {
    "small": {
        "benign_steady": 1,
        "benign_bursty": 1,
        "malicious_pattern": 1,
    },
    "small_tuned": {
        "benign_steady": 1,
        "benign_bursty": 1,
        "malicious_pattern_heavy": 1,
    },
    "network_test": {
        "benign_steady": 1,
        "malicious_network_heavy": 1,
    },
    "syscall_test": {
        "benign_steady": 1,
        "malicious_syscall_heavy": 1,
    },
    "medium": {
        "benign_steady": 4,
        "benign_bursty": 2,
        "suspicious": 2,
        "malicious_pattern": 2,
    },
    "large": {
        "benign_steady": 8,
        "benign_bursty": 4,
        "suspicious": 4,
        "malicious_pattern": 4,
    },
}


def build_scenario(name: str, run_id: str) -> list[ScenarioItem]:
    layout = SCENARIO_LAYOUTS[name]
    items: list[ScenarioItem] = []
    counters: Counter[str] = Counter()
    for workload_key, count in layout.items():
        workload = WORKLOAD_CATALOG[workload_key]
        for _ in range(count):
            counters[workload_key] += 1
            items.append(
                ScenarioItem(
                    name=f"raasa-{run_id}-{workload_key}-{counters[workload_key]}",
                    workload=workload,
                )
            )
    return items
