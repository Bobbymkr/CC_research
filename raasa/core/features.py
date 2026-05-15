from __future__ import annotations

import math
from typing import Iterable, List, Mapping

from raasa.core.models import ContainerTelemetry, FeatureVector


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalize_distribution(counts: dict[str, int] | dict[int, int]) -> dict[str, float]:
    cleaned = {str(key): max(0.0, float(value)) for key, value in counts.items()}
    total = sum(cleaned.values())
    if total <= 0.0:
        return {}
    return {key: value / total for key, value in cleaned.items() if value > 0.0}


def jensen_shannon_divergence(
    left_counts: dict[str, int] | dict[int, int],
    right_counts: dict[str, int] | dict[int, int],
) -> float:
    """Return base-2 Jensen-Shannon divergence normalized to [0, 1]."""

    left = _normalize_distribution(left_counts)
    right = _normalize_distribution(right_counts)
    if not left or not right:
        return 0.0

    keys = set(left) | set(right)

    def _kl_divergence(source: dict[str, float], mixed: dict[str, float]) -> float:
        total = 0.0
        for key in keys:
            p = source.get(key, 0.0)
            q = mixed.get(key, 0.0)
            if p > 0.0 and q > 0.0:
                total += p * math.log2(p / q)
        return total

    midpoint = {key: 0.5 * (left.get(key, 0.0) + right.get(key, 0.0)) for key in keys}
    return _clamp(0.5 * _kl_divergence(left, midpoint) + 0.5 * _kl_divergence(right, midpoint))


def shannon_entropy_signal(samples: Iterable[object] | Mapping[object, int]) -> float:
    """Return normalized Shannon entropy for a sample stream or count map."""

    if isinstance(samples, Mapping):
        counts = {
            str(key): max(0, int(value))
            for key, value in samples.items()
            if str(key).strip()
        }
    else:
        counts: dict[str, int] = {}
        for sample in samples:
            value = str(sample).strip()
            if not value:
                continue
            counts[value] = counts.get(value, 0) + 1

    counts = {key: value for key, value in counts.items() if value > 0}
    total = sum(counts.values())
    if total <= 0 or len(counts) <= 1:
        return 0.0

    entropy_bits = 0.0
    for count in counts.values():
        probability = count / total
        entropy_bits -= probability * math.log2(probability)
    return _clamp(entropy_bits / math.log2(len(counts)))


class FeatureExtractor:
    """Converts raw telemetry into normalized feature signals."""

    def __init__(
        self,
        process_cap: int = 20,
        network_cap: float = 5_000_000.0,
        syscall_cap: float = 500.0,
        syscall_baseline_alpha: float = 0.05,
    ) -> None:
        self.process_cap = max(process_cap, 1)
        self.network_cap = network_cap
        self.syscall_cap = max(syscall_cap, 1.0)
        self.syscall_baseline_alpha = _clamp(syscall_baseline_alpha)
        self._syscall_baselines: dict[str, dict[str, float]] = {}

    def extract(self, telemetry_batch: Iterable[ContainerTelemetry]) -> List[FeatureVector]:
        features: List[FeatureVector] = []
        for item in telemetry_batch:
            syscall_jsd_signal = self._syscall_jsd_signal(item.container_id, item.syscall_counts)
            features.append(
                FeatureVector(
                    container_id=item.container_id,
                    timestamp=item.timestamp,
                    cpu_signal=_clamp(item.cpu_percent / 100.0),
                    memory_signal=_clamp(item.memory_percent / 100.0),
                    process_signal=_clamp(item.process_count / float(self.process_cap)),
                    network_signal=_clamp((item.network_rx_bytes + item.network_tx_bytes) / max(self.network_cap, 1.0)),
                    syscall_signal=_clamp(item.syscall_rate / self.syscall_cap),
                    lateral_movement_signal=_clamp(item.lateral_movement_signal),
                    syscall_jsd_signal=syscall_jsd_signal,
                    file_entropy_signal=shannon_entropy_signal(item.file_accesses),
                    network_entropy_signal=shannon_entropy_signal(item.network_destinations),
                    dns_entropy_signal=shannon_entropy_signal(item.dns_queries),
                    telemetry_metadata=dict(item.metadata),
                )
            )
        return features

    def _syscall_jsd_signal(self, container_id: str, syscall_counts: dict[str, int]) -> float:
        current = _normalize_distribution(syscall_counts)
        if not current:
            return 0.0

        baseline = self._syscall_baselines.get(container_id)
        if baseline is None:
            self._syscall_baselines[container_id] = dict(current)
            return 0.0

        jsd = jensen_shannon_divergence(
            {key: int(value * 1_000_000) for key, value in current.items()},
            {key: int(value * 1_000_000) for key, value in baseline.items()},
        )
        alpha = self.syscall_baseline_alpha
        merged_keys = set(baseline) | set(current)
        self._syscall_baselines[container_id] = {
            key: ((1.0 - alpha) * baseline.get(key, 0.0)) + (alpha * current.get(key, 0.0))
            for key in merged_keys
        }
        return _clamp(jsd)
