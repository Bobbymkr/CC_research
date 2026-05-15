from __future__ import annotations

from pathlib import Path

from plot_degraded_mode_summary import render as render_degraded_mode_summary
from plot_local_baseline_tradeoff import render as render_local_baseline_tradeoff


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    output_dir = base_dir / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    render_local_baseline_tradeoff(output_dir)
    render_degraded_mode_summary(output_dir)

    print(f"Rendered Python paper figures into: {output_dir}")


if __name__ == "__main__":
    main()
