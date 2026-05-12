from __future__ import annotations

from typing import Iterable, List

from raasa.core.models import ContainerTelemetry, FeatureVector


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class FeatureExtractor:
    """Converts raw telemetry into normalized feature signals."""

    def __init__(self, process_cap: int = 20, network_cap: float = 5_000_000.0, syscall_cap: float = 500.0) -> None:
        self.process_cap = max(process_cap, 1)
        self.network_cap = network_cap
        self.syscall_cap = max(syscall_cap, 1.0)

    def extract(self, telemetry_batch: Iterable[ContainerTelemetry]) -> List[FeatureVector]:
        return [
            FeatureVector(
                container_id=item.container_id,
                timestamp=item.timestamp,
                cpu_signal=_clamp(item.cpu_percent / 100.0),
                memory_signal=_clamp(item.memory_percent / 100.0),
                process_signal=_clamp(item.process_count / float(self.process_cap)),
                network_signal=_clamp((item.network_rx_bytes + item.network_tx_bytes) / max(self.network_cap, 1.0)),
                syscall_signal=_clamp(item.syscall_rate / self.syscall_cap),
            )
            for item in telemetry_batch
        ]
