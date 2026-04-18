from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict
from typing import Iterable

from raasa.core.models import Assessment, ContainerTelemetry, FeatureVector, PolicyDecision


class AuditLogger:
    """Persists evidence, reasoning, and actions for every loop iteration."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.output_path = self.directory / f"run_{timestamp}.jsonl"

    def log_tick(
        self,
        telemetry_batch: Iterable[ContainerTelemetry],
        features: Iterable[FeatureVector],
        assessments: Iterable[Assessment],
        decisions: Iterable[PolicyDecision],
    ) -> None:
        telemetry_map: Dict[str, ContainerTelemetry] = {item.container_id: item for item in telemetry_batch}
        feature_map: Dict[str, FeatureVector] = {item.container_id: item for item in features}
        assessment_map: Dict[str, Assessment] = {item.container_id: item for item in assessments}
        records = []
        for decision in decisions:
            telemetry = telemetry_map.get(decision.container_id)
            feature = feature_map.get(decision.container_id)
            assessment = assessment_map.get(decision.container_id)
            records.append(
                {
                    "container_id": decision.container_id,
                    "timestamp": decision.timestamp.isoformat(),
                    "cpu": None if telemetry is None else telemetry.cpu_percent,
                    "memory": None if telemetry is None else telemetry.memory_percent,
                    "proc": None if telemetry is None else telemetry.process_count,
                    "net_rx": None if telemetry is None else telemetry.network_rx_bytes,
                    "net_tx": None if telemetry is None else telemetry.network_tx_bytes,
                    "syscall_rate": None if telemetry is None else telemetry.syscall_rate,
                    "f_cpu": None if feature is None else feature.cpu_signal,
                    "f_mem": None if feature is None else feature.memory_signal,
                    "f_proc": None if feature is None else feature.process_signal,
                    "f_net": None if feature is None else feature.network_signal,
                    "f_sys": None if feature is None else feature.syscall_signal,
                    "risk": None if assessment is None else assessment.risk_score,
                    "confidence": None if assessment is None else assessment.confidence_score,
                    "risk_trend": None if assessment is None else getattr(assessment, "risk_trend", 0.0),
                    "assessment_reasons": [] if assessment is None else assessment.reasons,
                    "prev_tier": decision.previous_tier.value,
                    "proposed_tier": decision.proposed_tier.value,
                    "new_tier": decision.applied_tier.value,
                    "reason": decision.reason,
                    "action_required": decision.action_required,
                    "cooldown_active": decision.cooldown_active,
                    "metadata": {} if telemetry is None else telemetry.metadata,
                }
            )

        with self.output_path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")
