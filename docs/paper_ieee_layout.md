# RAASA IEEE Layout Guide

This guide turns the current RAASA paper assets into an IEEE-friendly package.
It assumes the manuscript will be authored in LaTeX and that the draft should
use source-controlled tables and figures rather than manually copied content.

## 1. Preamble

Use these packages at minimum:

```latex
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
```

If the venue template already loads one of these, do not duplicate it.

## 2. Preferred Figure Formats

For IEEE submission:

- use `PDF` for final manuscript inclusion
- keep `SVG` for draft review and web inspection
- use `PNG` only as a fallback

Current Python-rendered figures already support PDF:

- [docs/figures/generated/local_baseline_tradeoff.pdf](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/local_baseline_tradeoff.pdf)
- [docs/figures/generated/cloud_degraded_mode_summary.pdf](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/cloud_degraded_mode_summary.pdf)

DOT architecture figures should be rendered to PDF with:

```powershell
pwsh docs/figures/render_dot_figures.ps1
```

That script requires Graphviz `dot` to be installed locally.

## 3. Preferred Table Includes

Use the rendered `.tex` files directly with `\input{...}`.

### Table I

```latex
\input{docs/tables/generated/local_baseline_comparison.tex}
```

### Table II

```latex
\input{docs/tables/generated/cloud_evidence_ladder.tex}
```

### Table III

```latex
\input{docs/tables/generated/failure_degraded_mode_summary.tex}
```

### Appendix / Rebuttal Scope Table

```latex
\input{docs/tables/generated/scope_nonclaims.tex}
```

## 4. Figure Include Pattern

For single-column figures:

```latex
\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{docs/figures/generated/local_baseline_tradeoff.pdf}
\caption{Local adaptive containment outperforms both static permissive and static strict baselines.}
\label{fig:local-baseline-tradeoff}
\end{figure}
```

For wide figures:

```latex
\begin{figure*}[t]
\centering
\includegraphics[width=\textwidth]{docs/figures/generated/raasa_multinode_k3s.pdf}
\caption{Bounded 3-node K3s deployment view of RAASA with node-local enforcement.}
\label{fig:multinode-k3s}
\end{figure*}
```

## 5. Suggested Mapping Into The Draft

- **Fig. 1**: `raasa_control_loop.pdf`
- **Fig. 2**: `raasa_multinode_k3s.pdf`
- **Fig. 3** or evaluation figure: `local_baseline_tradeoff.pdf`
- **Fig. 4** or appendix progression figure: `raasa_validation_progression.pdf`
- **Fig. 5** or limitations figure: `cloud_degraded_mode_summary.pdf`

- **Table I**: local baseline comparison
- **Table II**: cloud evidence ladder
- **Table III**: failure and degraded-mode summary
- **Appendix table**: scope and non-claims

## 6. Why This Layout Fits IEEE Better

- The table snippets use `booktabs` rather than heavy gridlines.
- Wide cloud tables use `table*` plus `tabularx` so long text wraps without
  destroying column alignment.
- Narrower tables stay in `table` form to preserve reading flow.
- PDF-first figures avoid last-minute vector/raster surprises in the final
  manuscript build.
