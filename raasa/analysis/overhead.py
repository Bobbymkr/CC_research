from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

try:
    import psutil
except ModuleNotFoundError:  # pragma: no cover - exercised by runtime environment
    psutil = None

from raasa.core.config import load_config
from raasa.core.logger import build_run_path
from raasa.experiments.run_experiment import cleanup_scenario, start_scenario
from raasa.experiments.scenarios import build_scenario


def summarize_overhead_report(
    baseline_host_cpu: list[float],
    adaptive_host_cpu: list[float],
    adaptive_process_cpu: list[float],
    loop_durations_seconds: list[float],
) -> dict[str, dict[str, float | int]]:
    baseline = {
        "sample_count": len(baseline_host_cpu),
        "host_cpu_percent_mean": _mean(baseline_host_cpu),
        "host_cpu_percent_p95": _percentile(baseline_host_cpu, 95),
    }
    adaptive = {
        "sample_count": len(adaptive_host_cpu),
        "host_cpu_percent_mean": _mean(adaptive_host_cpu),
        "host_cpu_percent_p95": _percentile(adaptive_host_cpu, 95),
        "process_cpu_percent_mean": _mean(adaptive_process_cpu),
        "process_cpu_percent_p95": _percentile(adaptive_process_cpu, 95),
        "loop_duration_seconds_mean": _mean(loop_durations_seconds),
        "loop_duration_seconds_p95": _percentile(loop_durations_seconds, 95),
    }
    return {
        "baseline": baseline,
        "adaptive": adaptive,
        "delta": {
            "host_cpu_percent_mean": adaptive["host_cpu_percent_mean"] - baseline["host_cpu_percent_mean"],
            "host_cpu_percent_p95": adaptive["host_cpu_percent_p95"] - baseline["host_cpu_percent_p95"],
        },
    }


def measure_benign_only_overhead(
    config_path: str | Path,
    duration_seconds: int = 30,
    poll_interval_seconds: int = 5,
    sample_interval_seconds: float = 0.5,
    run_label: str = "benign_only_overhead",
    python_executable: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    _require_psutil()
    config = load_config(config_path)
    output = Path(output_path) if output_path else Path(config.log_directory) / f"{run_label}.overhead.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    iterations = max(duration_seconds // max(poll_interval_seconds, 1), 1)

    baseline_items = build_scenario("benign_only", f"{run_label}_baseline")
    adaptive_items = build_scenario("benign_only", f"{run_label}_adaptive")

    baseline_host_cpu = _measure_baseline_cpu(baseline_items, config, duration_seconds, sample_interval_seconds)
    adaptive_host_cpu, adaptive_process_cpu, timing_path = _measure_controller_cpu(
        adaptive_items,
        config_path,
        config,
        iterations,
        sample_interval_seconds,
        run_label,
        python_executable or sys.executable,
    )
    loop_durations_seconds = _load_loop_durations(timing_path)
    report = summarize_overhead_report(
        baseline_host_cpu=baseline_host_cpu,
        adaptive_host_cpu=adaptive_host_cpu,
        adaptive_process_cpu=adaptive_process_cpu,
        loop_durations_seconds=loop_durations_seconds,
    )
    report["artifacts"] = {
        "controller_log_path": str(build_run_path(config.log_directory, f"{run_label}_adaptive")),
        "timing_path": str(timing_path),
        "config_path": str(config_path),
    }
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return output


def _measure_baseline_cpu(
    items,
    config,
    duration_seconds: int,
    sample_interval_seconds: float,
) -> list[float]:
    host_cpu_samples: list[float] = []
    started = start_scenario(items, config.live_run_guardrails)
    try:
        _prime_cpu_samplers()
        deadline = time.perf_counter() + duration_seconds
        while time.perf_counter() < deadline:
            time.sleep(sample_interval_seconds)
            host_cpu_samples.append(psutil.cpu_percent(interval=None))
    finally:
        cleanup_scenario(started)
    return host_cpu_samples


def _measure_controller_cpu(
    items,
    config_path: str | Path,
    config,
    iterations: int,
    sample_interval_seconds: float,
    run_label: str,
    python_executable: str,
) -> tuple[list[float], list[float], Path]:
    host_cpu_samples: list[float] = []
    process_cpu_samples: list[float] = []
    timing_path = Path(config.log_directory) / f"{run_label}_controller_timings.json"
    started = start_scenario(items, config.live_run_guardrails)
    try:
        command = [
            python_executable,
            "-m",
            "raasa.core.app",
            "--config",
            str(config_path),
            "--mode",
            "adaptive",
            "--iterations",
            str(iterations),
            "--run-label",
            f"{run_label}_adaptive",
            "--timing-output",
            str(timing_path),
            "--containers",
            *[item.name for item in started],
        ]
        process = subprocess.Popen(command)
        process_handle = psutil.Process(process.pid)
        _prime_cpu_samplers(process_handle)

        while process.poll() is None:
            time.sleep(sample_interval_seconds)
            host_cpu_samples.append(psutil.cpu_percent(interval=None))
            try:
                process_cpu_samples.append(process_handle.cpu_percent(interval=None))
            except psutil.Error:
                break

        process.wait(timeout=30)
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
    finally:
        cleanup_scenario(started)
    return host_cpu_samples, process_cpu_samples, timing_path


def _load_loop_durations(path: str | Path) -> list[float]:
    timing_path = Path(path)
    if not timing_path.exists():
        return []
    payload = json.loads(timing_path.read_text(encoding="utf-8"))
    return [float(item.get("duration_seconds", 0.0)) for item in payload]


def _prime_cpu_samplers(process_handle=None) -> None:
    psutil.cpu_percent(interval=None)
    if process_handle is not None:
        process_handle.cpu_percent(interval=None)


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return statistics.mean(values)


def _require_psutil() -> None:
    if psutil is None:
        raise RuntimeError("psutil is required for overhead measurement. Install psutil==6.1.1 first.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure RAASA benign-only monitoring overhead.")
    parser.add_argument("--config", default="raasa/configs/config_tuned_small.yaml")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--sample-interval", type=float, default=0.5)
    parser.add_argument("--run-label", default="benign_only_overhead")
    parser.add_argument("--output", default=None)
    parser.add_argument("--python-executable", default=sys.executable)
    return parser


def _cli() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    output = measure_benign_only_overhead(
        config_path=args.config,
        duration_seconds=args.duration,
        poll_interval_seconds=args.poll_interval,
        sample_interval_seconds=args.sample_interval,
        run_label=args.run_label,
        python_executable=args.python_executable,
        output_path=args.output,
    )
    print(f"[RAASA] Wrote overhead report: {output}")


if __name__ == "__main__":
    _cli()
