from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from raasa.analysis.metrics import write_metrics_summary
from raasa.core.config import load_config
from raasa.core.app import run_controller
from raasa.core.logger import build_run_path
from raasa.experiments.scenarios import SCENARIO_LAYOUTS, build_scenario


@dataclass(slots=True)
class StartedContainer:
    name: str
    workload_key: str
    category: str
    expected_tier: str


def _docker_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a RAASA experiment scenario")
    parser.add_argument("--mode", choices=["static_L1", "static_L3", "detection_only", "raasa"], required=True)
    parser.add_argument("--scenario", choices=sorted(SCENARIO_LAYOUTS.keys()), required=True)
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--config", default="raasa/configs/config_tuned_small_linear.yaml")
    return parser


def main() -> int:
    parser = build_parser()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
        
    args = parser.parse_args()
    config = load_config(args.config)
    if shutil.which("docker") is None:
        print("[RAASA] Docker is required to run experiments.", file=sys.stderr)
        return 1

    run_id = args.run_id or str(int(time.time()))
    items = build_scenario(args.scenario, run_id)
    log_path = build_run_path(config.log_directory, run_id)
    duration = (
        args.duration
        if args.duration is not None
        else int(config.live_run_guardrails["default_smoke_duration_seconds"])
    )
    started = start_scenario(items, config.live_run_guardrails)
    iterations = max(duration // max(args.poll_interval, 1), 1)

    try:
        print(
            f"[RAASA] Running mode={args.mode}, scenario={args.scenario}, "
            f"containers={len(started)}, iterations={iterations}"
        )
        run_controller(
            [
                "--config",
                args.config,
                "--mode",
                args.mode,
                "--iterations",
                str(iterations),
                "--run-label",
                run_id,
                "--scenario",
                args.scenario,
                "--controller-variant",
                config.controller_variant,
                "--containers",
                *[item.name for item in started],
            ]
        )
    finally:
        cleanup_scenario(started)

    summary_path = write_metrics_summary(log_path)
    manifest_path = Path(config.log_directory) / "experiment_manifest.jsonl"
    _write_manifest_row(
        manifest_path,
        {
            "run_id": run_id,
            "mode": args.mode,
            "scenario": args.scenario,
            "controller_variant": config.controller_variant,
            "config": args.config,
            "duration_seconds": duration,
            "poll_interval_seconds": args.poll_interval,
            "iterations": iterations,
            "log_path": str(log_path),
            "summary_path": str(summary_path),
            "container_count": len(started),
        },
    )
    return 0


def start_scenario(items, guardrails) -> list[StartedContainer]:
    started: list[StartedContainer] = []
    for item in items:
        command = [
            "docker",
            "run",
            "-d",
            "--cpus",
            str(guardrails["initial_cpus"]),
            "--memory",
            str(guardrails["memory_limit"]),
            "--pids-limit",
            str(guardrails["pids_limit"]),
            "--name",
            item.name,
            "--label",
            f"raasa.class={item.workload.category}",
            "--label",
            f"raasa.workload={item.workload.key}",
            "--label",
            f"raasa.expected_tier={item.workload.expected_tier}",
            "--label",
            "raasa.managed=true",
            item.workload.image,
            *item.workload.command,
        ]
        _docker_runner(command)
        started.append(
            StartedContainer(
                name=item.name,
                workload_key=item.workload.key,
                category=item.workload.category,
                expected_tier=item.workload.expected_tier,
            )
        )
    return started


def cleanup_scenario(items: list[StartedContainer]) -> None:
    for item in items:
        try:
            _docker_runner(["docker", "rm", "-f", item.name])
        except subprocess.CalledProcessError:
            continue


def _write_manifest_row(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
