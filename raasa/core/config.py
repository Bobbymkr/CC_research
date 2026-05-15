from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

import yaml


@dataclass(slots=True)
class AppConfig:
    raw: Dict[str, Any]

    @property
    def poll_interval_seconds(self) -> int:
        return int(self.raw["controller"]["poll_interval_seconds"])

    @property
    def default_mode(self) -> str:
        return str(self.raw["controller"]["default_mode"])

    @property
    def log_directory(self) -> Path:
        return Path(self.raw["controller"]["log_directory"])

    @property
    def risk_weights(self) -> Dict[str, float]:
        weights = self.raw["risk"]["weights"]
        return {
            "cpu": float(weights.get("cpu", 0.0)),
            "memory": float(weights.get("memory", 0.0)),
            "process": float(weights.get("process", 0.0)),
            "network": float(weights.get("network", 0.0)),
            "syscall": float(weights.get("syscall", 0.0)),
            "syscall_jsd": float(weights.get("syscall_jsd", 0.0)),
            "file_entropy": float(weights.get("file_entropy", 0.0)),
            "network_entropy": float(weights.get("network_entropy", 0.0)),
            "dns_entropy": float(weights.get("dns_entropy", 0.0)),
        }

    @property
    def network_cap(self) -> float:
        return float(self.raw.get("telemetry", {}).get("network_cap", 5000000.0))

    @property
    def syscall_cap(self) -> float:
        return float(self.raw.get("telemetry", {}).get("syscall_cap", 500.0))

    @property
    def syscall_source(self) -> str:
        return str(self.raw.get("telemetry", {}).get("syscall_source", "simulated")).lower()

    @property
    def syscall_probe_directory(self) -> Path:
        value = self.raw.get("telemetry", {}).get("syscall_probe_directory", "raasa/runtime/syscalls")
        return Path(str(value))

    @property
    def syscall_probe_max_age_seconds(self) -> int:
        return int(self.raw.get("telemetry", {}).get("syscall_probe_max_age_seconds", 15))

    @property
    def k8s_metrics_cache_max_age_seconds(self) -> int:
        return int(self.raw.get("telemetry", {}).get("k8s_metrics_cache_max_age_seconds", 30))

    @property
    def k8s_allow_stale_metrics_fallback(self) -> bool:
        return bool(self.raw.get("telemetry", {}).get("k8s_allow_stale_metrics_fallback", True))

    @property
    def k8s_metrics_failure_cooldown_seconds(self) -> int:
        return int(self.raw.get("telemetry", {}).get("k8s_metrics_failure_cooldown_seconds", 15))

    @property
    def k8s_namespace_metrics_cache_max_age_seconds(self) -> int:
        return int(self.raw.get("telemetry", {}).get("k8s_namespace_metrics_cache_max_age_seconds", 15))

    @property
    def k8s_node_memory_bytes(self) -> int | None:
        value = self.raw.get("telemetry", {}).get("k8s_node_memory_bytes")
        if value is None or value == "":
            return None
        return int(value)

    @property
    def use_ml_model(self) -> bool:
        return bool(self.raw.get("ml", {}).get("use_ml_model", False))

    @property
    def ml_model_path(self) -> str | None:
        return self.raw.get("ml", {}).get("model_path")

    @property
    def use_behavioral_dna(self) -> bool:
        return bool(self.raw.get("ml", {}).get("use_behavioral_dna", False))

    @property
    def behavioral_dna_model_path(self) -> str | None:
        return self.raw.get("ml", {}).get("behavioral_dna_model_path")

    @property
    def use_temporal_lstm(self) -> bool:
        return bool(self.raw.get("ml", {}).get("use_temporal_lstm", False))

    @property
    def temporal_lstm_model_path(self) -> str | None:
        return self.raw.get("ml", {}).get("temporal_lstm_model_path")

    @property
    def audit_kms_enabled(self) -> bool:
        return bool(self.raw.get("audit", {}).get("kms_hmac", {}).get("enabled", False))

    @property
    def audit_kms_key_id(self) -> str | None:
        value = self.raw.get("audit", {}).get("kms_hmac", {}).get("key_id")
        if value in {None, ""}:
            return None
        return str(value)

    @property
    def audit_kms_region(self) -> str | None:
        value = self.raw.get("audit", {}).get("kms_hmac", {}).get("region")
        if value in {None, ""}:
            return None
        return str(value)

    @property
    def audit_kms_profile(self) -> str | None:
        value = self.raw.get("audit", {}).get("kms_hmac", {}).get("profile")
        if value in {None, ""}:
            return None
        return str(value)

    @property
    def audit_kms_mac_algorithm(self) -> str:
        return str(self.raw.get("audit", {}).get("kms_hmac", {}).get("mac_algorithm", "HMAC_SHA_256"))

    @property
    def confidence_window(self) -> int:
        return int(self.raw["risk"]["confidence_window"])

    @property
    def use_llm_advisor(self) -> bool:
        return bool(self.raw.get("policy", {}).get("use_llm_advisor", False))

    @property
    def policy_thresholds(self) -> Dict[str, float]:
        thresholds = self.raw["policy"]["thresholds"]
        return {
            "l1_max": float(thresholds["l1_max"]),
            "l2_max": float(thresholds["l2_max"]),
        }

    @property
    def hysteresis_band(self) -> float:
        return float(self.raw["policy"]["hysteresis_band"])

    @property
    def cooldown_seconds(self) -> int:
        return int(self.raw["policy"]["cooldown_seconds"])

    @property
    def l3_min_confidence(self) -> float:
        return float(self.raw["policy"]["l3_min_confidence"])

    @property
    def low_risk_streak_required(self) -> int:
        return int(self.raw.get("policy", {}).get("low_risk_streak_required", 2))

    @property
    def l3_requires_approval(self) -> bool:
        return bool(self.raw.get("policy", {}).get("l3_requires_approval", False))

    @property
    def partial_telemetry_caps_l3(self) -> bool:
        return bool(self.raw.get("policy", {}).get("partial_telemetry_caps_l3", True))

    @property
    def partial_telemetry_blocks_relaxation(self) -> bool:
        return bool(self.raw.get("policy", {}).get("partial_telemetry_blocks_relaxation", True))

    @property
    def cpus_by_tier(self) -> Dict[str, float]:
        return {
            tier: float(value)
            for tier, value in self.raw["enforcement"]["cpus_by_tier"].items()
        }

    @property
    def live_run_guardrails(self) -> Dict[str, Any]:
        return dict(self.raw["enforcement"]["live_run_guardrails"])

    @property
    def controller_variant(self) -> str:
        configured = self.raw.get("evaluation", {}).get("controller_variant")
        if configured:
            return str(configured)
        return "ml_iforest" if self.use_ml_model else "linear_tuned"


def load_config(path: str | Path = "raasa/configs/config.yaml") -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data:
        data = {}
    return AppConfig(raw=data)
