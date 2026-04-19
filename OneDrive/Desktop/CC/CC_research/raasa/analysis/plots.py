"""RAASA v1 — Analysis Plots

Generates paper-ready, publication-quality figures from experiment summary JSON files.

Usage (CLI):
    python -m raasa.analysis.plots \\
        --adaptive   raasa/logs/run_*adaptive*.summary.json \\
        --static-l1  raasa/logs/run_*L1*.summary.json \\
        --static-l3  raasa/logs/run_*L3*.summary.json \\
        --outdir     raasa/plots/

Functions (API):
    generate_all_plots(metrics_by_mode, outdir) -> list[Path]
    plot_detection_comparison(metrics_by_mode, outdir) -> Path
    plot_cost_comparison(metrics_by_mode, outdir) -> Path
    plot_stability_comparison(metrics_by_mode, outdir) -> Path

Backward-compatible:
    build_plot_manifest(metrics_by_mode) -> dict (used by test_analysis.py)
    write_plot_manifest(metrics_by_mode, output_path) -> Path
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

from raasa.analysis.metrics import TIER_ORDER, load_records

# ── Style ──────────────────────────────────────────────────────────────────────
matplotlib.use("Agg")  # non-interactive backend — safe for headless/Windows CI

_PALETTE = {
    "RAASA (Adaptive)": "#4C72B0",
    "Static L1": "#DD8452",
    "Static L3": "#C44E52",
    "Detection-Only": "#8172B2",
}
_BAR_WIDTH = 0.22
_FIGURE_DPI = 150
_FONT_FAMILY = "DejaVu Sans"

sns.set_theme(style="whitegrid", font=_FONT_FAMILY, font_scale=1.1)


def _bar_group(
    ax: plt.Axes,
    labels: list[str],
    series: dict[str, list[float]],
    colors: list[str],
    ylabel: str,
    title: str,
    ylim: tuple[float, float] = (0.0, 1.05),
) -> None:
    """Draw a grouped bar chart on *ax* — one group per label, one bar per series."""
    import numpy as np

    n_groups = len(labels)
    n_series = len(series)
    x = np.arange(n_groups)
    offsets = np.linspace(
        -_BAR_WIDTH * (n_series - 1) / 2,
        _BAR_WIDTH * (n_series - 1) / 2,
        n_series,
    )
    for (metric_name, values), offset, color in zip(series.items(), offsets, colors):
        bars = ax.bar(
            x + offset,
            values,
            _BAR_WIDTH,
            label=metric_name.replace("_", " ").title(),
            color=color,
            edgecolor="white",
            linewidth=0.8,
            alpha=0.92,
        )
        # Value annotation above bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.012,
                f"{val:.2f}",
                ha="center",
                va="bottom",
                fontsize=8.5,
                color="#333333",
            )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.set_ylim(*ylim)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10)
    ax.legend(fontsize=9, framealpha=0.85)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    sns.despine(ax=ax, left=False, bottom=False)


# ── Figure 1 — Detection Comparison ───────────────────────────────────────────

def plot_detection_comparison(
    metrics_by_mode: dict[str, dict],
    outdir: str | Path,
) -> Path:
    """Bar chart: precision / recall / FPR per mode."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    modes = list(metrics_by_mode.keys())
    series = {
        "precision":          [metrics_by_mode[m].get("precision", 0.0) for m in modes],
        "recall":             [metrics_by_mode[m].get("recall", 0.0) for m in modes],
        "false_positive_rate":[metrics_by_mode[m].get("false_positive_rate", 0.0) for m in modes],
    }
    colors = ["#4C72B0", "#55A868", "#C44E52"]

    fig, ax = plt.subplots(figsize=(8, 5))
    _bar_group(
        ax, modes, series, colors,
        ylabel="Score",
        title="Figure 1 — Security Detection Comparison\n(Precision / Recall / False Positive Rate)",
    )
    path = outdir / "fig1_detection_comparison.png"
    fig.tight_layout()
    fig.savefig(path, dpi=_FIGURE_DPI)
    plt.close(fig)
    return path


# ── Figure 2 — Cost Comparison ────────────────────────────────────────────────

def plot_cost_comparison(
    metrics_by_mode: dict[str, dict],
    outdir: str | Path,
) -> Path:
    """Bar chart: containment pressure vs benign restriction rate per mode."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    modes = list(metrics_by_mode.keys())
    series = {
        "containment_pressure":  [metrics_by_mode[m].get("containment_pressure", 0.0) for m in modes],
        "benign_restriction_rate":[metrics_by_mode[m].get("benign_restriction_rate", 0.0) for m in modes],
    }
    colors = ["#DD8452", "#C44E52"]

    fig, ax = plt.subplots(figsize=(8, 5))
    _bar_group(
        ax, modes, series, colors,
        ylabel="Rate (0 = no cost, 1 = maximum cost)",
        title="Figure 2 — Isolation Cost Comparison\n(Containment Pressure / Benign Restriction Rate)",
    )
    path = outdir / "fig2_cost_comparison.png"
    fig.tight_layout()
    fig.savefig(path, dpi=_FIGURE_DPI)
    plt.close(fig)
    return path


# ── Figure 3 — Stability Comparison ──────────────────────────────────────────

def plot_stability_comparison(
    metrics_by_mode: dict[str, dict],
    outdir: str | Path,
) -> Path:
    """Bar chart: switching rate & explanation coverage per mode."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    modes = list(metrics_by_mode.keys())
    series = {
        "switching_rate":      [metrics_by_mode[m].get("switching_rate", 0.0) for m in modes],
        "explanation_coverage":[metrics_by_mode[m].get("explanation_coverage", 0.0) for m in modes],
    }
    colors = ["#8172B2", "#4C72B0"]

    fig, ax = plt.subplots(figsize=(8, 5))
    _bar_group(
        ax, modes, series, colors,
        ylabel="Rate",
        title="Figure 3 — System Stability Comparison\n(Tier Switching Rate / Explanation Coverage)",
    )
    path = outdir / "fig3_stability_comparison.png"
    fig.tight_layout()
    fig.savefig(path, dpi=_FIGURE_DPI)
    plt.close(fig)
    return path


# ── Figure 4 — Tier Occupancy ─────────────────────────────────────────────────

def plot_tier_occupancy(
    metrics_by_mode: dict[str, dict],
    outdir: str | Path,
) -> Path:
    """Stacked bar chart: L1 / L2 / L3 occupancy fraction per mode."""
    import numpy as np

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    modes = list(metrics_by_mode.keys())
    l1 = [metrics_by_mode[m].get("tier_occupancy", {}).get("L1", 0.0) for m in modes]
    l2 = [metrics_by_mode[m].get("tier_occupancy", {}).get("L2", 0.0) for m in modes]
    l3 = [metrics_by_mode[m].get("tier_occupancy", {}).get("L3", 0.0) for m in modes]

    x = np.arange(len(modes))
    fig, ax = plt.subplots(figsize=(8, 5))

    b1 = ax.bar(x, l1, label="L1 (Minimal)", color="#55A868", edgecolor="white", linewidth=0.8)
    b2 = ax.bar(x, l2, bottom=l1, label="L2 (Moderate)", color="#DD8452", edgecolor="white", linewidth=0.8)
    b3 = ax.bar(x, l3,
                bottom=[a + b for a, b in zip(l1, l2)],
                label="L3 (Strict)", color="#C44E52", edgecolor="white", linewidth=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(modes, fontsize=10)
    ax.set_ylabel("Fraction of time in tier", fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.set_title(
        "Figure 4 — Isolation Tier Occupancy\n(Fraction of ticks per tier)",
        fontsize=12, fontweight="bold", pad=10,
    )
    ax.legend(fontsize=9, framealpha=0.85)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    sns.despine(ax=ax, left=False, bottom=False)

    path = outdir / "fig4_tier_occupancy.png"
    fig.tight_layout()
    fig.savefig(path, dpi=_FIGURE_DPI)
    plt.close(fig)
    return path


def plot_tier_trajectory(
    records_or_path: str | Path | list[dict],
    output_path: str | Path,
    tier_field: str = "new_tier",
    title: str | None = None,
) -> Path:
    records = (
        load_records(records_or_path)
        if isinstance(records_or_path, (str, Path))
        else list(records_or_path)
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        raise ValueError("Tier trajectory plot requires at least one record.")

    grouped: defaultdict[str, list[dict]] = defaultdict(list)
    for row in records:
        grouped[row["container_id"]].append(row)

    first_timestamp = min(datetime.fromisoformat(row["timestamp"]) for row in records)
    fig, ax = plt.subplots(figsize=(9, 5))

    for container_id, container_rows in sorted(grouped.items()):
        sorted_rows = sorted(container_rows, key=lambda row: row["timestamp"])
        xs = [
            (datetime.fromisoformat(row["timestamp"]) - first_timestamp).total_seconds()
            for row in sorted_rows
        ]
        ys = [TIER_ORDER.get(str(row.get(tier_field) or "L1"), 1) for row in sorted_rows]
        metadata = sorted_rows[-1].get("metadata", {})
        workload_key = metadata.get("workload_key", "workload")
        label = f"{workload_key}:{container_id[-4:]}"
        ax.step(xs, ys, where="post", label=label, linewidth=2.0)

    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(["L1", "L2", "L3"])
    ax.set_xlabel("Time (seconds)", fontsize=11)
    ax.set_ylabel(f"Tier ({tier_field})", fontsize=11)
    ax.set_title(
        title or f"Tier Trajectory Over Time ({tier_field})",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax.grid(axis="both", linestyle="--", alpha=0.45)
    ax.legend(fontsize=8, framealpha=0.85, loc="best")
    sns.despine(ax=ax, left=False, bottom=False)

    fig.tight_layout()
    fig.savefig(output, dpi=_FIGURE_DPI)
    plt.close(fig)
    return output


# ── Master entrypoint ──────────────────────────────────────────────────────────

def generate_all_plots(
    metrics_by_mode: dict[str, dict],
    outdir: str | Path,
) -> list[Path]:
    """Generate all 4 paper figures. Returns list of saved file paths."""
    outdir = Path(outdir)
    paths = [
        plot_detection_comparison(metrics_by_mode, outdir),
        plot_cost_comparison(metrics_by_mode, outdir),
        plot_stability_comparison(metrics_by_mode, outdir),
        plot_tier_occupancy(metrics_by_mode, outdir),
    ]
    return paths


# ── Backward-compatible manifest (used by test_analysis.py) ───────────────────

def build_plot_manifest(metrics_by_mode: dict[str, dict]) -> dict:
    return {
        "detection_comparison": {
            "type": "bar",
            "x": list(metrics_by_mode.keys()),
            "series": {
                "precision": [metrics_by_mode[k].get("precision", 0.0) for k in metrics_by_mode],
                "recall": [metrics_by_mode[k].get("recall", 0.0) for k in metrics_by_mode],
                "false_positive_rate": [
                    metrics_by_mode[k].get("false_positive_rate", 0.0) for k in metrics_by_mode
                ],
            },
        },
        "cost_comparison": {
            "type": "bar",
            "x": list(metrics_by_mode.keys()),
            "series": {
                "average_observed_load": [
                    metrics_by_mode[k].get("average_observed_load", 0.0) for k in metrics_by_mode
                ],
                "containment_pressure": [
                    metrics_by_mode[k].get("containment_pressure", 0.0) for k in metrics_by_mode
                ],
            },
        },
        "stability_comparison": {
            "type": "bar",
            "x": list(metrics_by_mode.keys()),
            "series": {
                "switching_rate": [
                    metrics_by_mode[k].get("switching_rate", 0.0) for k in metrics_by_mode
                ],
                "explanation_coverage": [
                    metrics_by_mode[k].get("explanation_coverage", 0.0) for k in metrics_by_mode
                ],
            },
        },
    }


def write_plot_manifest(metrics_by_mode: dict[str, dict], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.write_text(
        json.dumps(build_plot_manifest(metrics_by_mode), indent=2), encoding="utf-8"
    )
    return target


# ── CLI ───────────────────────────────────────────────────────────────────────

def _mean_summary(paths: list[str]) -> dict:
    """Load multiple summary JSONs and average their numeric fields."""
    summaries = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    if not summaries:
        return {}
    result: dict = {}
    for key in summaries[0]:
        vals = [s[key] for s in summaries if key in s and isinstance(s[key], (int, float))]
        if vals and len(vals) == len(summaries):
            result[key] = statistics.mean(vals)
        elif key == "tier_occupancy":
            # Merge tier occupancies by averaging
            all_tiers: dict[str, list[float]] = {}
            for s in summaries:
                for tier, fraction in s.get("tier_occupancy", {}).items():
                    all_tiers.setdefault(tier, []).append(fraction)
            result[key] = {t: statistics.mean(fracs) for t, fracs in all_tiers.items()}
        else:
            result[key] = summaries[0].get(key)
    return result


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Generate paper-ready plots from RAASA experiment summaries."
    )
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
        
    parser.add_argument(
        "--adaptive", nargs="+", metavar="SUMMARY_JSON",
        help="Summary JSON files for adaptive (RAASA) runs",
    )
    parser.add_argument(
        "--static-l1", nargs="+", metavar="SUMMARY_JSON",
        help="Summary JSON files for static L1 runs",
    )
    parser.add_argument(
        "--static-l3", nargs="+", metavar="SUMMARY_JSON",
        help="Summary JSON files for static L3 runs",
    )
    parser.add_argument(
        "--outdir", default="raasa/plots",
        help="Output directory for plot PNG files (default: raasa/plots)",
    )
    args = parser.parse_args()

    metrics_by_mode: dict[str, dict] = {}
    if args.adaptive:
        metrics_by_mode["RAASA (Adaptive)"] = _mean_summary(args.adaptive)
    if args.static_l1:
        metrics_by_mode["Static L1"] = _mean_summary(args.static_l1)
    if args.static_l3:
        metrics_by_mode["Static L3"] = _mean_summary(args.static_l3)

    if not metrics_by_mode:
        parser.error("Provide at least one of --adaptive, --static-l1, --static-l3")

    saved = generate_all_plots(metrics_by_mode, args.outdir)
    print(f"[RAASA] Generated {len(saved)} plot(s):")
    for p in saved:
        print(f"  {p}")


if __name__ == "__main__":
    _cli()
