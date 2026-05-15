# RAASA Paper Figures

This directory stores source-controlled figure definitions for the paper.

Use DOT when the figure is primarily structural:

- architecture
- deployment topology
- evaluation progression

Use Python when the figure is primarily quantitative:

- baseline comparisons
- degraded-mode summaries

For IEEE submission, prefer:

- `PDF` for final manuscript inclusion
- `SVG` for review, web, and draft inspection
- `PNG` only as a fallback when PDF is inconvenient

## Figure source map

- `raasa_control_loop.dot`
  - Fig. 1 candidate
  - Observe-Assess-Decide-Act-Audit architecture with privilege separation
- `raasa_multinode_k3s.dot`
  - Fig. 2 candidate
  - bounded 3-node K3s deployment and node-local enforcement path
- `raasa_validation_progression.dot`
  - appendix or evaluation figure candidate
  - clean-account replay to bounded 3-node K3s evidence ladder
- `plot_local_baseline_tradeoff.py`
  - local adaptive-vs-static comparison chart
- `plot_degraded_mode_summary.py`
  - degraded/failure behavior chart
- `render_python_figures.py`
  - convenience script to render the Python figures into `generated/`

## Rendering

### Python figures

```powershell
python docs/figures/render_python_figures.py
```

This writes PDF, SVG, and PNG outputs into `docs/figures/generated/`.

### DOT figures

If Graphviz is installed locally, render with:

```powershell
pwsh docs/figures/render_dot_figures.ps1
```

If `dot` is not installed, keep the `.dot` files as the canonical source and
render them later on a Graphviz-enabled machine. The PowerShell helper renders
both PDF and SVG outputs, which matches the usual IEEE workflow better than
SVG alone.
