from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


FIGURE_NAME = "cloud_degraded_mode_summary"


def render(output_dir: Path) -> None:
    """
    Render the degraded-mode and bounded-stress summary figure.

    Source values come from the fresh-account bounded 3-node K3s evidence:
    - Metrics API outage: complete 1, partial 9, metrics_ok 1, metrics_error 9
    - Syscall probe pause: complete 4, partial 7, clean 4, probe_stale 7
    - Metrics API stress: complete 62, partial 0, clean 62
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    scenarios = ["Metrics outage", "Probe pause", "Metrics stress"]
    complete = np.array([1, 4, 62])
    partial = np.array([9, 7, 0])

    clean = np.array([1, 4, 62])
    metrics_error = np.array([9, 0, 0])
    probe_stale = np.array([0, 7, 0])

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5))

    x = np.arange(len(scenarios))

    axes[0].bar(x, complete, color="#2563EB", label="Complete telemetry")
    axes[0].bar(x, partial, bottom=complete, color="#F97316", label="Partial telemetry")
    axes[0].set_title("Telemetry completeness under bounded failure and stress")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(scenarios)
    axes[0].set_ylabel("Audit rows")
    axes[0].legend(frameon=True)

    stacked_bottom = np.zeros(len(scenarios))
    for values, label, color in [
        (clean, "Clean / no degraded signal", "#059669"),
        (metrics_error, "Metrics API error", "#DC2626"),
        (probe_stale, "Probe stale", "#D97706"),
    ]:
        axes[1].bar(x, values, bottom=stacked_bottom, color=color, label=label)
        stacked_bottom = stacked_bottom + values

    axes[1].set_title("Dominant observed signal status")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(scenarios)
    axes[1].set_ylabel("Observed rows")
    axes[1].legend(frameon=True)

    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle(
        "Bounded 3-Node K3s Degraded-Mode Evidence\n"
        "Explicit partial telemetry is preserved instead of being silently hidden",
        fontsize=14,
    )
    fig.tight_layout()
    fig.subplots_adjust(top=0.82)
    fig.savefig(output_dir / f"{FIGURE_NAME}.pdf", bbox_inches="tight")
    fig.savefig(output_dir / f"{FIGURE_NAME}.svg", bbox_inches="tight")
    fig.savefig(output_dir / f"{FIGURE_NAME}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    render(Path(__file__).resolve().parent / "generated")
