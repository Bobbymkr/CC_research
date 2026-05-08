# Figure 3 Redraw Spec - Scalability

This spec defines the best final form for the scalability figure.

## Figure purpose

Figure 3 should show how RAASA behaves as workload count increases.
It is meant to support the claim that the controller remains effective beyond the smallest scenario.

## Best chart type

- line chart with markers

## Why this is best

- workload count is ordered data,
- the reader needs to see trend, not category-only comparison,
- line plots communicate progression more naturally than grouped bars.

## Data structure

X-axis:

- 3 containers
- 10 containers
- 20 containers

Y-axis:

Use three vertically stacked small-multiple panels:

- Precision
- Recall
- False Positive Rate

## Data values

| Scale | Evidence type | Precision | Recall | FPR |
|---|---|---:|---:|---:|
| 3 containers | mean of 3 runs | 0.87 | 1.00 | 0.11 |
| 10 containers | mean of 3 runs | 0.95 | 1.00 | 0.04 |
| 20 containers | single run | 0.87 | 1.00 | 0.10 |

Source:

- `RM_practical/master_results_table.md`
- Table 2, scalability study

## Marker rules

Use evidence strength in the marker style.

- repeated-run means: solid circle
- single-run supporting evidence: hollow diamond

This is important because the 20-container result should not be read as having the same evidentiary weight as the repeated means.

## Styling

Single series color:

- RAASA Linear: deep blue

Optional confidence emphasis:

- use a subtle darker outline around the repeated-run mean markers
- label the 20-container point directly with `n=1`

## Axes

### Precision panel

- y-axis from 0.75 to 1.00 or 0.70 to 1.00

### Recall panel

- y-axis from 0.90 to 1.00 or 0.85 to 1.00

### FPR panel

- y-axis from 0.00 to 0.15 or 0.20

Do not force all three panels to use the exact same y-range if it hurts readability.
But do keep each panel honest and clearly labeled.

## Visual message

The figure should make these points visible:

- recall remains at 1.00 throughout,
- precision improves from small to medium,
- large-scale result is supportive but not yet repeated.

## Caption draft

Figure 3. Scalability behavior of the RAASA linear controller across increasing workload counts. Points at 3 and 10 containers are repeated-run means, while the 20-container point is single-run supporting evidence. Recall remains stable across scales, while precision and false positive rate remain favorable through the repeated 10-container evaluation.

## In-text callout draft

As shown in Figure 3, RAASA's strongest repeated evidence extends beyond the 3-container scenario. The controller maintains recall of 1.00 while improving precision and reducing false positive rate at 10 containers. The 20-container result remains encouraging, but is explicitly treated as single-run supporting evidence rather than the primary basis for generalization.
