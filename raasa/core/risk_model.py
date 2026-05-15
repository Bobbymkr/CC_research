from __future__ import annotations

from collections import defaultdict, deque
from statistics import mean
import logging
from typing import Iterable, List

from raasa.core.attribution import linear_shap_attributions
from raasa.core.models import Assessment, FeatureVector
from raasa.ml.behavioral_dna import BehavioralDNARegistry, feature_to_vector
from raasa.ml.temporal_lstm import TemporalLSTMDetector


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
        use_behavioral_dna: bool = False,
        behavioral_dna_path: str | None = None,
        use_temporal_lstm: bool = False,
        temporal_lstm_path: str | None = None,
    ) -> None:
        self.weights = weights if weights is not None else {
            "cpu": 0.40,
            "memory": 0.25,
            "process": 0.15,
            "network": 0.10,
            "syscall": 0.10,
            "syscall_jsd": 0.10,
            "file_entropy": 0.05,
            "network_entropy": 0.05,
            "dns_entropy": 0.05,
        }
        self.confidence_window = max(confidence_window, 2)
        self.history: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.confidence_window)
        )
        self.ml_model = None
        self.behavioral_dna: BehavioralDNARegistry | None = None
        self.temporal_lstm: TemporalLSTMDetector | None = None
        self.temporal_history: dict[str, deque[list[float]]] = defaultdict(lambda: deque(maxlen=16))
        if use_ml_model and ml_model_path:
            try:
                import joblib
                self.ml_model = joblib.load(ml_model_path)
                logging.info(f"Loaded ML model from {ml_model_path}")
            except Exception as e:
                logging.warning(f"Failed to load ML model from {ml_model_path}: {e}. Falling back to linear weights.")
        if use_behavioral_dna and behavioral_dna_path:
            try:
                self.behavioral_dna = BehavioralDNARegistry.load(behavioral_dna_path)
                logging.info(f"Loaded behavioral DNA registry from {behavioral_dna_path}")
            except Exception as e:
                logging.warning(f"Failed to load behavioral DNA registry from {behavioral_dna_path}: {e}.")
        if use_temporal_lstm and temporal_lstm_path:
            try:
                self.temporal_lstm = TemporalLSTMDetector.load(temporal_lstm_path)
                logging.info(f"Loaded temporal LSTM detector from {temporal_lstm_path}")
            except Exception as e:
                logging.warning(f"Failed to load temporal LSTM detector from {temporal_lstm_path}: {e}.")

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
                attributions = []
            else:
                attributions = linear_shap_attributions(item, self.weights)
                risk = _clamp(sum(float(row["shap_value"]) for row in attributions))
                reasons = [
                    f"cpu={item.cpu_signal:.2f}*{self.weights.get('cpu', 0.0):.2f}",
                    f"mem={item.memory_signal:.2f}*{self.weights.get('memory', 0.0):.2f}",
                    f"proc={item.process_signal:.2f}*{self.weights.get('process', 0.0):.2f}",
                    f"net={item.network_signal:.2f}*{self.weights.get('network', 0.0):.2f}",
                    f"sys={item.syscall_signal:.2f}*{self.weights.get('syscall', 0.0):.2f}",
                    f"sys_jsd={item.syscall_jsd_signal:.2f}*{self.weights.get('syscall_jsd', 0.0):.2f}",
                    f"file_ent={item.file_entropy_signal:.2f}*{self.weights.get('file_entropy', 0.0):.2f}",
                    f"net_ent={item.network_entropy_signal:.2f}*{self.weights.get('network_entropy', 0.0):.2f}",
                    f"dns_ent={item.dns_entropy_signal:.2f}*{self.weights.get('dns_entropy', 0.0):.2f}",
                ]
            if self.behavioral_dna is not None:
                dna_signal, dna_status = self.behavioral_dna.feature_anomaly_signal(item)
                risk = max(risk, dna_signal)
                reasons.append(f"behavioral_dna={dna_signal:.2f}:{dna_status}")
            if self.temporal_lstm is not None:
                current_vector = feature_to_vector(item)
                history = self.temporal_history[item.container_id]
                if len(history) >= self.temporal_lstm.sequence_length:
                    sequence = list(history)[-self.temporal_lstm.sequence_length :]
                    temporal_signal = self.temporal_lstm.anomaly_signal(sequence, current_vector)
                    risk = max(risk, temporal_signal)
                    reasons.append(f"temporal_lstm={temporal_signal:.2f}:temporal_lstm_ok")
                else:
                    reasons.append("temporal_lstm=0.00:temporal_lstm_warming")
                history.append(current_vector)

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
                    attributions=attributions,
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
