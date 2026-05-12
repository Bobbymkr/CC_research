"""
raasa.core.metrics
~~~~~~~~~~~~~~~~~~
Prometheus metrics endpoint for the RAASA controller.

Exposes an HTTP server on port 9090 (configurable) in a background daemon
thread so the main control loop is never blocked.

Metrics
-------
raasa_risk_score{pod}               Gauge   Current risk score [0.0, 1.0]
raasa_tier{pod}                     Gauge   Current enforcement tier {1, 2, 3}
raasa_confidence{pod}               Gauge   Risk model confidence [0.0, 1.0]
raasa_syscall_rate{pod}             Gauge   eBPF syscall rate /s
raasa_escalations_total{pod}        Counter Total L→L+N tier escalation events
raasa_deescalations_total{pod}      Counter Total L→L-N tier de-escalation events
raasa_detection_latency_seconds     Histogram Time from first anomaly tick to L3 decision
raasa_controller_iterations_total   Counter Total controller loop iterations
raasa_controller_errors_total       Counter Failed telemetry collection or assessment errors
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        start_http_server,
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False

if TYPE_CHECKING:
    from raasa.core.policy import TierDecision

# ── Metric definitions ────────────────────────────────────────────────────────

_RISK_SCORE = None
_TIER = None
_CONFIDENCE = None
_SYSCALL_RATE = None
_ESCALATIONS = None
_DEESCALATIONS = None
_DETECTION_LATENCY = None
_ITERATIONS = None
_ERRORS = None

_INITIALIZED = False
_FIRST_ANOMALY_TS: dict[str, float] = {}  # pod_id → timestamp of first L2+ detection


def _init_metrics() -> None:
    global _RISK_SCORE, _TIER, _CONFIDENCE, _SYSCALL_RATE
    global _ESCALATIONS, _DEESCALATIONS, _DETECTION_LATENCY, _ITERATIONS, _ERRORS
    global _INITIALIZED

    if _INITIALIZED or not _PROMETHEUS_AVAILABLE:
        return

    _RISK_SCORE = Gauge("raasa_risk_score", "Current risk score", ["pod"])
    _TIER = Gauge("raasa_tier", "Current enforcement tier (1/2/3)", ["pod"])
    _CONFIDENCE = Gauge("raasa_confidence", "Risk model confidence", ["pod"])
    _SYSCALL_RATE = Gauge("raasa_syscall_rate", "eBPF syscall rate per second", ["pod"])
    _ESCALATIONS = Counter("raasa_escalations_total", "Total tier escalation events", ["pod"])
    _DEESCALATIONS = Counter("raasa_deescalations_total", "Total tier de-escalation events", ["pod"])
    _DETECTION_LATENCY = Histogram(
        "raasa_detection_latency_seconds",
        "Time from first anomaly to L3 enforcement decision",
        buckets=[1, 2, 5, 10, 15, 20, 30, 60],
    )
    _ITERATIONS = Counter("raasa_controller_iterations_total", "Total controller iterations")
    _ERRORS = Counter("raasa_controller_errors_total", "Total telemetry/assessment errors")
    _INITIALIZED = True


def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus HTTP server on a background daemon thread."""
    if not _PROMETHEUS_AVAILABLE:
        import logging
        logging.getLogger(__name__).warning(
            "prometheus_client not installed. Metrics endpoint disabled. "
            "Install with: pip install prometheus_client"
        )
        return

    _init_metrics()

    def _serve() -> None:
        start_http_server(port)

    thread = threading.Thread(target=_serve, daemon=True, name="raasa-metrics")
    thread.start()
    import logging
    logging.getLogger(__name__).info(f"[RAASA] Prometheus metrics server started on :{port}")


def record_iteration(
    decisions: list,
    telemetry_batch: list,
    error_count: int = 0,
) -> None:
    """
    Update all Prometheus metrics after one controller iteration.

    Parameters
    ----------
    decisions:
        List of ``TierDecision`` objects from the policy reasoner.
    telemetry_batch:
        List of ``ContainerTelemetry`` from this iteration.
    error_count:
        Number of telemetry collection or assessment errors this iteration.
    """
    if not _INITIALIZED or not _PROMETHEUS_AVAILABLE:
        return

    # Index telemetry by container_id for quick lookup
    telemetry_by_id = {t.container_id: t for t in telemetry_batch}

    _ITERATIONS.inc()
    if error_count:
        _ERRORS.inc(error_count)

    for decision in decisions:
        pod = decision.container_id
        tel = telemetry_by_id.get(pod)

        # Risk / tier / confidence gauges (from assessment embedded in decision)
        _RISK_SCORE.labels(pod=pod).set(decision.risk_score if hasattr(decision, "risk_score") else 0.0)
        _CONFIDENCE.labels(pod=pod).set(decision.confidence if hasattr(decision, "confidence") else 0.0)

        prev = getattr(decision, "previous_tier", None)
        new = getattr(decision, "applied_tier", None)
        if prev and new:
            tier_int = {"L1": 1, "L2": 2, "L3": 3}.get(str(new), 0)
            _TIER.labels(pod=pod).set(tier_int)

            # Escalation/de-escalation counters
            tier_order = {"L1": 1, "L2": 2, "L3": 3}
            prev_v = tier_order.get(str(prev), 0)
            new_v = tier_order.get(str(new), 0)
            if new_v > prev_v:
                _ESCALATIONS.labels(pod=pod).inc()
            elif new_v < prev_v:
                _DEESCALATIONS.labels(pod=pod).inc()

            # Detection latency: record when first anomaly (L2+) is seen
            if new_v >= 2 and pod not in _FIRST_ANOMALY_TS:
                _FIRST_ANOMALY_TS[pod] = time.monotonic()
            elif new_v == 3 and pod in _FIRST_ANOMALY_TS:
                latency = time.monotonic() - _FIRST_ANOMALY_TS.pop(pod)
                _DETECTION_LATENCY.observe(latency)
            elif new_v == 1:
                _FIRST_ANOMALY_TS.pop(pod, None)

        # Syscall rate from telemetry
        if tel:
            _SYSCALL_RATE.labels(pod=pod).set(tel.syscall_rate or 0.0)
