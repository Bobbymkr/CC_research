from __future__ import annotations

from collections import defaultdict, deque
from statistics import mean
import logging
from typing import Iterable, List

from raasa.core.models import Assessment, FeatureVector


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class RiskAssessor:
    """Computes risk and confidence from normalized signals."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        confidence_window: int = 5,
        use_ml_model: bool = False,
        ml_model_path: str | None = None,
    ) -> None:
        self.weights = weights or {"cpu": 0.40, "memory": 0.25, "process": 0.15, "network": 0.10, "syscall": 0.10}
        self.confidence_window = max(confidence_window, 2)
        self.history: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.confidence_window)
        )
        self.ml_model = None
        if use_ml_model and ml_model_path:
            try:
                import joblib
                self.ml_model = joblib.load(ml_model_path)
                logging.info(f"Loaded ML model from {ml_model_path}")
            except Exception as e:
                logging.warning(f"Failed to load ML model from {ml_model_path}: {e}. Falling back to linear weights.")

    def assess(self, feature_batch: Iterable[FeatureVector]) -> List[Assessment]:
        assessments: List[Assessment] = []
        for item in feature_batch:
            if self.ml_model is not None:
                # decision_function returns negative for anomalies
                score = self.ml_model.decision_function([[
                    item.cpu_signal, item.memory_signal, item.process_signal,
                    item.network_signal, item.syscall_signal
                ]])[0]
                risk = _clamp(0.5 - score) 
                reasons = [f"ml_score={score:+.3f}"]
            else:
                risk = _clamp(
                    (item.cpu_signal * self.weights.get("cpu", 0.0))
                    + (item.memory_signal * self.weights.get("memory", 0.0))
                    + (item.process_signal * self.weights.get("process", 0.0))
                    + (item.network_signal * self.weights.get("network", 0.0))
                    + (item.syscall_signal * self.weights.get("syscall", 0.0))
                )
                reasons = [
                    f"cpu={item.cpu_signal:.2f}*{self.weights.get('cpu', 0.0):.2f}",
                    f"mem={item.memory_signal:.2f}*{self.weights.get('memory', 0.0):.2f}",
                    f"proc={item.process_signal:.2f}*{self.weights.get('process', 0.0):.2f}",
                    f"net={item.network_signal:.2f}*{self.weights.get('network', 0.0):.2f}",
                    f"sys={item.syscall_signal:.2f}*{self.weights.get('syscall', 0.0):.2f}",
                ]

            container_history = self.history[item.container_id]
            container_history.append(risk)
            history_list = list(container_history)
            
            confidence = self._compute_confidence(history_list)
            trend = self._compute_trend(history_list)

            reasons.extend([
                f"history={len(container_history)}",
                f"trend={trend:+.2f}",
            ])
            telemetry_metadata = dict(getattr(item, "telemetry_metadata", {}) or {})
            telemetry_status = telemetry_metadata.get("telemetry_status", "")
            degraded_signals = telemetry_metadata.get("degraded_signals", "")
            if telemetry_status and telemetry_status != "complete":
                reasons.append(f"telemetry={telemetry_status}")
            if degraded_signals and degraded_signals != "none":
                reasons.append(f"degraded={degraded_signals}")
            assessments.append(
                Assessment(
                    container_id=item.container_id,
                    timestamp=item.timestamp,
                    risk_score=risk,
                    confidence_score=confidence,
                    risk_trend=trend,
                    latest_features=item,
                    reasons=reasons,
                    telemetry_metadata=telemetry_metadata,
                )
            )
        return assessments

    def _compute_confidence(self, risk_history: list[float]) -> float:
        if not risk_history:
            return 0.0
        avg = mean(risk_history)
        mean_deviation = mean(abs(value - avg) for value in risk_history)
        stability = 1.0 - min(mean_deviation / 0.25, 1.0)
        maturity = min(len(risk_history) / float(self.confidence_window), 1.0)
        return _clamp(stability * maturity)

    def _compute_trend(self, risk_history: list[float]) -> float:
        if len(risk_history) < 2:
            return 0.0
        mid = len(risk_history) // 2
        recent = mean(risk_history[mid:])
        older = mean(risk_history[:mid])
        return recent - older
