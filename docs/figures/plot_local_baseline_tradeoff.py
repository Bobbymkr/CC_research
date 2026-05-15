from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


FIGURE_NAME = "local_baseline_tradeoff"


def render(output_dir: Path) -> None:
    """
    Render the local adaptive-vs-static comparison figure.

    Source values are taken from the current paper draft and evidence story:
    - static_L1 small baseline
    - static_L3 small baseline
    - RAASA small_tuned best run
    - RAASA small_tuned 3-run mean
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = [
        "Precision",
        "Recall",
        "False positive rate",
        "Benign restriction rate",
    ]
    modes = [
        "Static L1",
        "Static L3",
        "RAASA best",
        "RAASA 3-run mean",
    ]
    values = np.array(
        [
            [0.00, 0.00, 0.00, 0.00],
            [0.33, 1.00, 1.00, 1.00],
            [1.00, 1.00, 0.00, 0.00],
            [0.87, 1.00, 0.11, 0.11],
        ]
    )
    colors = ["#94A3B8", "#F97316", "#2563EB", "#059669"]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 7))

    x = np.arange(len(metrics))
    width = 0.18

    for index, (mode, color) in enumerate(zip(modes, colors)):
        offset = (index - 1.5) * width
        bars = ax.bar(
            x + offset,
            values[index],
            width,
            label=mode,
            color=color,
            edgecolor="#1F2937",
            linewidth=0.6,
        )
        for bar, value in zip(bars, values[index]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.025,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=9,
                color="#111827",
            )

    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, rotation=0)
    ax.set_title(
        "Local Adaptive Containment Outperforms Static Extremes\n"
        "Higher is better for precision/recall; lower is better for FPR/BRR"
    )
    ax.legend(frameon=True, loc="upper center", ncol=4)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_dir / f"{FIGURE_NAME}.pdf", bbox_inches="tight")
    fig.savefig(output_dir / f"{FIGURE_NAME}.svg", bbox_inches="tight")
    fig.savefig(output_dir / f"{FIGURE_NAME}.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    render(Path(__file__).resolve().parent / "generated")
