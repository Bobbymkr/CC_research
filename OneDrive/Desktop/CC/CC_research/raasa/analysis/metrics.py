from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable


TIER_ORDER = {"L1": 1, "L2": 2, "L3": 3}
CPU_BUDGET_BY_TIER = {"L1": 1.0, "L2": 0.5, "L3": 0.2}


def load_records(path: str | Path) -> list[dict]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def compute_metrics(records: Iterable[dict]) -> dict[str, object]:
    rows = list(records)
    if not rows:
        return {}

    tp = fp = tn = fn = 0
    switching_events = 0
    explanation_count = 0
    tier_occupancy: Counter[str] = Counter()
    previous_tier_by_container: dict[str, str] = {}
    first_timestamp: dict[str, datetime] = {}
    first_expected_hit: dict[str, datetime] = {}
    latency_seconds: list[float] = []
    malicious_containment_seconds: list[float] = []
    benign_escalations = 0
    observed_load_total = 0.0
    cpu_budget_total = 0.0
    malicious_rows = 0
    malicious_contained_rows = 0
    benign_rows = 0
    benign_restricted_rows = 0

    for row in rows:
        metadata = row.get("metadata", {})
        workload_class = metadata.get("workload_class", "")
        expected_tier = metadata.get("expected_tier", "L1") or "L1"
        container_id = row["container_id"]
        timestamp = datetime.fromisoformat(row["timestamp"])
        new_tier = row["new_tier"]
        tier_occupancy[new_tier] += 1
        explanation_count += int(bool(row.get("reason")))
        observed_load_total += float(row.get("cpu", 0.0) or 0.0) + float(row.get("memory", 0.0) or 0.0)
        cpu_budget_total += CPU_BUDGET_BY_TIER.get(new_tier, 1.0)

        if container_id not in first_timestamp:
            first_timestamp[container_id] = timestamp
        if (
            container_id not in first_expected_hit
            and TIER_ORDER.get(new_tier, 1) >= TIER_ORDER.get(expected_tier, 1)
        ):
            first_expected_hit[container_id] = timestamp

        previous = previous_tier_by_container.get(container_id)
        if previous is not None and previous != new_tier:
            switching_events += 1
        previous_tier_by_container[container_id] = new_tier

        predicted_positive = TIER_ORDER.get(new_tier, 1) >= TIER_ORDER["L2"]
        actual_positive = workload_class in {"suspicious", "malicious"}
        if workload_class == "malicious":
            malicious_rows += 1
            if predicted_positive:
                malicious_contained_rows += 1
        if workload_class == "benign":
            benign_rows += 1
            if predicted_positive:
                benign_restricted_rows += 1
        if predicted_positive and actual_positive:
            tp += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        elif not predicted_positive and actual_positive:
            fn += 1
        else:
            tn += 1

        if workload_class == "benign" and predicted_positive:
            benign_escalations += 1

    for container_id, start_time in first_timestamp.items():
        hit_time = first_expected_hit.get(container_id)
        if hit_time is not None:
            delta = (hit_time - start_time).total_seconds()
            latency_seconds.append(delta)

    for row in rows:
        metadata = row.get("metadata", {})
        if metadata.get("workload_class") != "malicious":
            continue
        container_id = row["container_id"]
        if container_id in first_expected_hit:
            malicious_containment_seconds.append(
                (first_expected_hit[container_id] - first_timestamp[container_id]).total_seconds()
            )
            first_expected_hit.pop(container_id, None)

    total = tp + fp + tn + fn
    total_rows = len(rows)
    return {
        "precision": _safe_divide(tp, tp + fp),
        "recall": _safe_divide(tp, tp + fn),
        "false_positive_rate": _safe_divide(fp, fp + tn),
        "adaptation_latency_seconds_mean": _mean(latency_seconds),
        "average_observed_load": _safe_divide(observed_load_total, total_rows),
        "average_cpu_budget": _safe_divide(cpu_budget_total, total_rows),
        "containment_pressure": 1.0 - _safe_divide(cpu_budget_total, total_rows),
        "switching_rate": _safe_divide(switching_events, total_rows),
        "unnecessary_escalations": benign_escalations,
        "benign_restriction_rate": _safe_divide(benign_restricted_rows, benign_rows),
        "malicious_containment_rate": _safe_divide(malicious_contained_rows, malicious_rows),
        "tier_occupancy": {
            tier: _safe_divide(count, total_rows) for tier, count in sorted(tier_occupancy.items())
        },
        "explanation_coverage": _safe_divide(explanation_count, total_rows),
        "mean_time_to_safe_containment": _mean(malicious_containment_seconds),
        "total_records": total,
    }


def write_metrics_summary(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    records = load_records(input_path)
    summary = compute_metrics(records)
    target = Path(output_path) if output_path else Path(input_path).with_suffix(".summary.json")
    target.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return target


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
