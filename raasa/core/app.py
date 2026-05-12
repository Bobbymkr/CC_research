from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from raasa.core.config import load_config
from raasa.core.features import FeatureExtractor
from raasa.core.logger import AuditLogger
from raasa.core.metrics import record_iteration, start_metrics_server
from raasa.core.policy import PolicyReasoner
from raasa.core.risk_model import RiskAssessor
# NOTE: Observer and ActionEnforcer are imported lazily inside _build_backend()
# so that the 'kubernetes' package is NOT required when running --backend docker.


STATIC_MODE_TO_TIER = {
    "static_L1": "L1",
    "static_L3": "L3",
}
K8S_ENFORCER_READY_TIMEOUT_SECONDS = 20.0


def _containment_profile_for_tier(tier) -> str:
    tier_value = getattr(tier, "value", str(tier))
    if tier_value == "L3":
        return "hard_containment"
    if tier_value == "L2":
        return "degraded_operation"
    return "observe_only"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAASA v1 controller entrypoint")
    parser.add_argument("--config", default="raasa/configs/config.yaml", help="Path to the config file")
    parser.add_argument("--mode", default=None, help="Override controller mode from config")
    parser.add_argument(
        "--backend",
        default="docker",
        choices=["docker", "k8s"],
        help=(
            "Telemetry and enforcement backend. "
            "'docker' (v1 default — uses docker stats + docker update, works on Windows/Mac/Linux). "
            "'k8s' (v2 — uses Kubernetes Metrics API + Linux tc/cgroups, requires Linux + root)."
        ),
    )
    parser.add_argument("--iterations", type=int, default=1, help="Number of controller iterations to run")
    parser.add_argument("--containers", nargs="*", default=[], help="Container IDs to inspect")
    parser.add_argument("--run-label", default=None, help="Optional label used for the audit log filename")
    parser.add_argument("--scenario", default=None, help="Optional scenario label for audit metadata")
    parser.add_argument("--controller-variant", default=None, help="Optional controller variant label")
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=9090,
        help="Port for the Prometheus metrics HTTP server (0 = disabled)",
    )
    parser.add_argument(
        "--timing-output",
        default=None,
        help="Optional JSON path to write per-iteration controller timing data",
    )
    return parser


def run_controller(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    mode = args.mode or config.default_mode
    controller_variant = args.controller_variant or config.controller_variant

    observer, enforcer = _build_backend(args.backend, config)
    _wait_for_backend_readiness(args.backend, enforcer)
    print(f"[RAASA] Backend: {args.backend!r}")
    extractor = FeatureExtractor(network_cap=config.network_cap, syscall_cap=config.syscall_cap)
    assessor = RiskAssessor(
        weights=config.risk_weights,
        confidence_window=config.confidence_window,
        use_ml_model=config.use_ml_model,
        ml_model_path=config.ml_model_path,
    )
    reasoner = PolicyReasoner(
        l1_max=config.policy_thresholds["l1_max"],
        l2_max=config.policy_thresholds["l2_max"],
        hysteresis_band=config.hysteresis_band,
        cooldown_seconds=config.cooldown_seconds,
        l3_min_confidence=config.l3_min_confidence,
        low_risk_streak_required=config.low_risk_streak_required,
        l3_requires_approval=config.l3_requires_approval,
        use_llm_advisor=config.use_llm_advisor,
        partial_telemetry_caps_l3=config.partial_telemetry_caps_l3,
        partial_telemetry_blocks_relaxation=config.partial_telemetry_blocks_relaxation,
    )
    logger = AuditLogger(
        config.log_directory,
        run_label=args.run_label,
        run_metadata={
            "mode": mode,
            "scenario": args.scenario or "",
            "controller_variant": controller_variant,
            "config_path": str(args.config),
        },
    )
    iteration_timings: list[dict[str, float | int]] = []
    run_forever = args.iterations == 0

    if run_forever:
        print(f"[RAASA] Starting controller in {mode!r} mode (daemon — runs indefinitely).")
    else:
        print(f"[RAASA] Starting controller in {mode!r} mode for {args.iterations} iteration(s).")
    print(f"[RAASA] Tracking {len(args.containers)} container(s).")

    # Start Prometheus metrics server (daemon thread, non-blocking)
    if args.metrics_port > 0:
        start_metrics_server(port=args.metrics_port)

    index = 0
    while run_forever or index < args.iterations:
        index += 1
        label = f"{index}" if run_forever else f"{index}/{args.iterations}"
        print(f"[RAASA] Iteration {label}")
        loop_started = time.perf_counter()
        telemetry_batch = observer.collect(args.containers)
        features = extractor.extract(telemetry_batch)
        assessments = assessor.assess(features)
        decisions = reasoner.decide(assessments)
        decisions = _apply_mode_override(decisions, mode)
        for decision in decisions:
            reasoner.current_tiers[decision.container_id] = decision.applied_tier
        enforcer.apply(decisions)
        logger.log_tick(telemetry_batch, features, assessments, decisions)
        record_iteration(decisions, telemetry_batch)
        iteration_timings.append(
            {
                "iteration": index,
                "duration_seconds": time.perf_counter() - loop_started,
            }
        )

        time.sleep(config.poll_interval_seconds)

    if args.timing_output:
        timing_path = Path(args.timing_output)
        timing_path.parent.mkdir(parents=True, exist_ok=True)
        timing_path.write_text(json.dumps(iteration_timings, indent=2), encoding="utf-8")

    print("[RAASA] Controller loop completed.")
    return 0


def _apply_mode_override(decisions, mode):
    forced_tier = STATIC_MODE_TO_TIER.get(mode)
    if forced_tier:
        updated = []
        for decision in decisions:
            target_tier = decision.previous_tier.__class__(forced_tier)
            updated.append(
                replace(
                    decision,
                    proposed_tier=target_tier,
                    applied_tier=target_tier,
                    containment_profile=_containment_profile_for_tier(target_tier),
                    reason=f"{mode} override -> force {forced_tier}",
                    action_required=decision.previous_tier != target_tier,
                    cooldown_active=False,
                    approval_required=False,
                    approval_state="forced",
                )
            )
        return updated

    if mode == "detection_only":
        updated = []
        for decision in decisions:
            updated.append(
                replace(
                    decision,
                    applied_tier=decision.previous_tier,
                    containment_profile=_containment_profile_for_tier(decision.previous_tier),
                    reason=f"{decision.reason} (detection_only mode — no action)",
                    action_required=False,
                    approval_required=False,
                    approval_state="not_needed",
                )
            )
        return updated

    return decisions


def _wait_for_backend_readiness(backend: str, enforcer, timeout_seconds: float = K8S_ENFORCER_READY_TIMEOUT_SECONDS):
    wait_until_ready = getattr(enforcer, "wait_until_ready", None)
    if backend != "k8s" or not callable(wait_until_ready):
        return None

    print("[RAASA] Waiting for privileged enforcer sidecar readiness...")
    ready = bool(wait_until_ready(timeout_seconds=timeout_seconds))
    if ready:
        print("[RAASA] Privileged enforcer sidecar is ready.")
    else:
        print("[RAASA] Privileged enforcer sidecar not ready before timeout; proceeding with retry-based startup.")
    return ready


def _build_backend(backend: str, config):
    """
    Factory function: selects and initialises the Observer + Enforcer pair
    that matches the requested backend.

    docker (v1 — default)
        Uses ``Observer`` (docker stats) and ``ActionEnforcer`` (docker update).
        Works on Windows, macOS, and Linux without root.
        Use this for local development, CI, and Docker Desktop testing.

    k8s (v2 — cloud native)
        Uses ``ObserverK8s`` (Kubernetes Metrics API + cAdvisor + eBPF sidecar)
        and ``EnforcerK8s`` (Linux tc + cgroups v2).
        Requires: Linux kernel 5.8+, K3s/Kubernetes running, root privileges.
        Use this on AWS EC2 after running bootstrap_k8s_ebpf.sh.
    """
    if backend == "k8s":
        from raasa.k8s.observer_k8s import ObserverK8s          # type: ignore[import]
        from raasa.k8s.enforcement_k8s import EnforcerK8s       # type: ignore[import]
        observer = ObserverK8s(
            namespace_filter=getattr(config, "k8s_namespace", None),
            syscall_probe_dir=getattr(config, "syscall_probe_directory", "/var/run/raasa"),
            metrics_cache_max_age_seconds=getattr(config, "k8s_metrics_cache_max_age_seconds", 30),
            allow_stale_metrics_fallback=getattr(config, "k8s_allow_stale_metrics_fallback", True),
            metrics_failure_cooldown_seconds=getattr(config, "k8s_metrics_failure_cooldown_seconds", 15),
            namespace_metrics_cache_max_age_seconds=getattr(
                config,
                "k8s_namespace_metrics_cache_max_age_seconds",
                15,
            ),
            node_memory_bytes=getattr(config, "k8s_node_memory_bytes", None),
        )
        enforcer = EnforcerK8s(cpus_by_tier=getattr(config, "cpus_by_tier", None))
    else:
        # Default: Docker backend (v1) — always safe to use
        from raasa.core.telemetry import Observer                # type: ignore[import]
        from raasa.core.enforcement import ActionEnforcer        # type: ignore[import]
        observer = Observer(
            syscall_source=config.syscall_source,
            syscall_probe_dir=config.syscall_probe_directory,
            syscall_probe_max_age_seconds=config.syscall_probe_max_age_seconds,
        )
        enforcer = ActionEnforcer(cpus_by_tier=config.cpus_by_tier)
    return observer, enforcer


if __name__ == "__main__":
    raise SystemExit(run_controller())
