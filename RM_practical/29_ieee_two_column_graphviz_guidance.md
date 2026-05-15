# IEEE Two-Column Graphviz Guidance

This note provides the paper-facing recommendation for using the Graphviz DOT diagrams in an IEEE two-column manuscript.

## Recommended placement

Use the diagrams this way:

- `fig1_raasa_architecture_ieee_2col.dot`
  Place as a `figure*` full-width architecture figure across both IEEE columns.
- `fig1b_zero_trust_sidecar_ieee_2col.dot`
  Place either as a second full-width figure or as a narrower follow-on figure if the manuscript gives the deployment model dedicated discussion space.
- `fig1c_control_loop_ieee_2col.dot`
  Keep as a fallback compact diagram for a regular single-column `figure` if space becomes tight.

## Why this layout is better for IEEE

IEEE two-column papers punish wide horizontal flowcharts.
The safest architecture diagrams are therefore:

- top-to-bottom,
- cluster-bounded,
- label-wrapped,
- structurally sparse.

This pass uses:

- HTML-table labels so text remains inside node borders,
- top-down rank flow for better width control,
- explicit spacing to reduce edge overlap,
- black-and-white styling so grayscale print remains readable.

## Manuscript recommendation

For this paper, the strongest combination is:

1. full-width Figure 1 using `fig1_raasa_architecture_ieee_2col.dot`,
2. optional deployment-focused follow-up figure using `fig1b_zero_trust_sidecar_ieee_2col.dot`.

If only one diagram can survive page pressure, prefer the full-width architecture figure and keep the zero-trust details in text plus caption wording.

## Editing advice for online Graphviz tools

If the online editor still produces crowding:

- increase `ranksep` before increasing font size,
- increase node `CELLPADDING` before increasing node width,
- avoid adding more arrows unless they support a direct claim,
- keep feedback edges dashed and non-dominant.

## Source alignment

These diagrams intentionally stay aligned with the actual implemented system:

- telemetry observation,
- feature extraction,
- bounded risk assessment,
- tiered policy reasoning,
- Docker containment path,
- Kubernetes sidecar enforcement path.

They do not depict:

- seccomp hot-swaps as current implementation,
- CRIU rollback as current implementation,
- unsupported feature signals not present in the repo.
