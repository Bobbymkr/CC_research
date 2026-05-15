# Graphviz DOT Diagram Plan

This document packages the architecture figures into Graphviz-friendly DOT sources for use in online editors and IEEE-style paper preparation.

## Why DOT is used here

DOT is well suited for:

- architecture diagrams,
- trust-boundary diagrams,
- control-loop workflow diagrams.

DOT is not the best tool for:

- quantitative line charts,
- bar charts,
- dumbbell plots,
- occupancy distributions.

For that reason, this package converts the diagrammatic figures into DOT while keeping the quantitative plots as separate chart assets.

## Files added

- `figures/dot/fig1_raasa_architecture_ieee_bw.dot`
- `figures/dot/fig1b_zero_trust_sidecar_ieee_bw.dot`
- `figures/dot/fig1c_control_loop_minimal_ieee_bw.dot`

## Design goals

The DOT sources are tuned for:

- black-and-white IEEE-safe styling,
- no reliance on color,
- orthogonal edge routing where possible,
- label wrapping inside node borders,
- enough spacing to reduce edge crossings and text crowding.

## Rendering guidance

Recommended Graphviz engine:

- `dot`

Recommended export targets:

- `SVG` for drafting,
- `PDF` for final paper submission pipeline,
- `EPS` if your LaTeX / IEEE workflow specifically prefers EPS.

## Practical notes

- If an online Graphviz editor slightly changes edge placement, increase `ranksep` and `nodesep` before changing the structure.
- Keep `splines=ortho` for the architecture and deployment views.
- Keep the minimal control-loop figure as the fallback if the full architecture figure feels too dense at single-column width.
