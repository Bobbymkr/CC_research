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
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Run for an exact number of controller polling iterations; overrides --duration.",
    )
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--config", default="raasa/configs/config_tuned_small_linear.yaml")
    parser.add_argument(
        "--backend",
        default="docker",
        choices=["docker", "k8s"],
        help=(
            "'docker' (v1 default): spins up Docker containers and monitors via docker stats. "
            "'k8s' (v2 eBPF): monitors existing Kubernetes pods via Metrics API + eBPF sidecar. "
            "The Docker container lifecycle is skipped when using k8s backend."
        ),
    )
    return parser


def main() -> int:
    parser = build_parser()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
        
    args = parser.parse_args()
    config = load_config(args.config)

    # Docker availability is only required for the Docker backend.
    # The K8s backend watches existing cluster pods via the Kubernetes API.
    if args.backend == "docker" and shutil.which("docker") is None:
        print("[RAASA] Docker is required to run experiments with --backend docker.", file=sys.stderr)
        return 1

    run_id = args.run_id or str(int(time.time()))
    items = build_scenario(args.scenario, run_id)
    log_path = build_run_path(config.log_directory, run_id)
    poll_interval = max(args.poll_interval, 1)
    if args.iterations is not None:
        iterations = max(args.iterations, 1)
        duration = iterations * poll_interval
    else:
        duration = (
            args.duration
            if args.duration is not None
            else int(config.live_run_guardrails["default_smoke_duration_seconds"])
        )
        iterations = max(duration // poll_interval, 1)

    # For the K8s backend, containers are Kubernetes Pods already running
    # in the cluster. We skip the Docker run/rm lifecycle entirely and
    # pass an empty container list — ObserverK8s discovers pods via the K8s API.
    if args.backend == "k8s":
        started = []
        container_args: list[str] = []
        print(
            f"[RAASA] Running mode={args.mode}, scenario={args.scenario}, "
            f"backend=k8s, iterations={iterations}"
        )
    else:
        started = start_scenario(items, config.live_run_guardrails)
        container_args = ["--containers", *[item.name for item in started]]
        print(
            f"[RAASA] Running mode={args.mode}, scenario={args.scenario}, "
            f"containers={len(started)}, iterations={iterations}"
        )

    try:
        run_controller(
            [
                "--config",
                args.config,
                "--mode",
                args.mode,
                "--backend",
                args.backend,
                "--iterations",
                str(iterations),
                "--run-label",
                run_id,
                "--scenario",
                args.scenario,
                "--controller-variant",
                config.controller_variant,
                *container_args,
            ]
        )
    finally:
        if args.backend == "docker":
            cleanup_scenario(started)

    summary_path = write_metrics_summary(log_path)
    manifest_path = Path(config.log_directory) / "experiment_manifest.jsonl"
    _write_manifest_row(
        manifest_path,
        {
            "run_id": run_id,
            "mode": args.mode,
            "scenario": args.scenario,
            "backend": args.backend,
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
