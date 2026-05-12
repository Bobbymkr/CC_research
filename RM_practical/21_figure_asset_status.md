# Figure Asset Status

This note records the current paper-usable figure assets stored inside `RM_practical`.

## Newly confirmed / added assets

- `figures/fig1_architecture_zero_trust.svg`
  - New vector architecture figure based on `19_architecture_figure_spec.md`
  - Safe for the current paper position
  - Avoids seccomp / CRIU / feature-semantic mismatch

- `figures/fig6_ablation_linear_vs_ml.svg`
  - New vector ablation figure rendered directly from the documented Table 4 values
  - Matches the paper-safe ablation conclusion:
    tuned linear controller outperforms the current Isolation Forest path on recall at equal FPR

## Existing figure assets already present

- `figures/fig1_detection_comparison.png`
- `figures/fig2_cost_comparison.png`
- `figures/fig3_tier_occupancy.png`
- `figures/fig4_scalability.png`
- `figures/fig5_tier_trajectory.png`
- `figures/fig6_ablation_linear_vs_ml.png`

## Important clarification

The updated audit marked Fig 6 as still missing, but the repo already contained:

- `RM_practical/figures/fig6_ablation_linear_vs_ml.png`

This means the actual missing artifact on the `RM_practical` side was the rendered architecture figure, not the existence of an ablation image.

## Recommended paper usage

- Use `fig1_architecture_zero_trust.svg` as the architecture figure in the manuscript.
- Use either:
  - `fig6_ablation_linear_vs_ml.png`, or
  - `fig6_ablation_linear_vs_ml.svg`
  for the ablation figure, depending on the submission workflow.

For Word or PowerPoint-heavy workflows, the PNG is often simpler.
For LaTeX or vector-first workflows, the SVG is preferable.
