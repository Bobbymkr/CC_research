from __future__ import annotations

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from raasa.core.config import load_config
from raasa.core.enforcement import ActionEnforcer
from raasa.core.features import FeatureExtractor
from raasa.core.logger import AuditLogger
from raasa.core.policy import PolicyReasoner
from raasa.core.risk_model import RiskAssessor
from raasa.core.telemetry import Observer


STATIC_MODE_TO_TIER = {
    "static_L1": "L1",
    "static_L3": "L3",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RAASA v1 controller entrypoint")
    parser.add_argument("--config", default="raasa/configs/config.yaml", help="Path to the config file")
    parser.add_argument("--mode", default=None, help="Override controller mode from config")
    parser.add_argument("--iterations", type=int, default=1, help="Number of controller iterations to run")
    parser.add_argument("--containers", nargs="*", default=[], help="Container IDs to inspect")
    parser.add_argument("--run-label", default=None, help="Optional label used for the audit log filename")
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

    observer = Observer()
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
        use_llm_advisor=config.use_llm_advisor,
    )
    enforcer = ActionEnforcer(cpus_by_tier=config.cpus_by_tier)
    logger = AuditLogger(config.log_directory, run_label=args.run_label)
    iteration_timings: list[dict[str, float | int]] = []

    print(f"[RAASA] Starting controller in {mode!r} mode for {args.iterations} iteration(s).")
    print(f"[RAASA] Tracking {len(args.containers)} container(s).")

    for index in range(args.iterations):
        print(f"[RAASA] Iteration {index + 1}/{args.iterations}")
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
        iteration_timings.append(
            {
                "iteration": index + 1,
                "duration_seconds": time.perf_counter() - loop_started,
            }
        )

        if index + 1 < args.iterations:
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
                    reason=f"{mode} override -> force {forced_tier}",
                    action_required=decision.previous_tier != target_tier,
                    cooldown_active=False,
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
                    reason=f"{decision.reason} (detection_only mode — no action)",
                    action_required=False,
                )
            )
        return updated

    return decisions


if __name__ == "__main__":
    raise SystemExit(run_controller())
