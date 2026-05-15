from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Tier(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


@dataclass(slots=True)
class ContainerTelemetry:
    container_id: str
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    process_count: int
    network_rx_bytes: float = 0.0
    network_tx_bytes: float = 0.0
    syscall_rate: float = 0.0  # syscalls/sec (simulated or from eBPF)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class FeatureVector:
    container_id: str
    timestamp: datetime
    cpu_signal: float
    memory_signal: float
    process_signal: float
    network_signal: float = 0.0
    syscall_signal: float = 0.0


@dataclass(slots=True)
class Assessment:
    container_id: str
    timestamp: datetime
    risk_score: float
    confidence_score: float
    risk_trend: float = 0.0
    latest_features: Optional[FeatureVector] = None
    reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PolicyDecision:
    container_id: str
    timestamp: datetime
    previous_tier: Tier
    proposed_tier: Tier
    applied_tier: Tier
    reason: str
    action_required: bool
    cooldown_active: bool = False
    approval_required: bool = False
    approval_state: str = "not_needed"


@dataclass(slots=True)
class LoopContext:
    container_ids: List[str]
    mode: str
    scenario: Optional[str] = None
