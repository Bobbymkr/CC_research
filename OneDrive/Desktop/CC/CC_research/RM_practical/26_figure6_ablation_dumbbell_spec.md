# Figure 6 Redraw Spec - Dumbbell Ablation

This spec defines the best final form for the ablation figure.

## Figure purpose

Figure 6 should prove one narrow but important claim:

- in the current prototype, the tuned linear controller is preferable to the current Isolation Forest path.

## Best chart type

- paired dumbbell plot

## Why this is best

- only two controllers are being compared,
- the important information is the magnitude and direction of the difference,
- dumbbell plots communicate "same metric, two endpoints" more directly than grouped bars.

## Metrics to include

- Precision
- Recall
- False Positive Rate
- Switching Rate

## Values to plot

| Metric | Linear | Isolation Forest |
|---|---:|---:|
| Precision | 0.87 | 0.33 |
| Recall | 1.00 | 0.28 |
| False Positive Rate | 0.11 | 0.11 |
| Switching Rate | 0.019 | 0.056 |

Source:

- `RM_practical/master_results_table.md`
- Table 4
- `RM_practical/results/aws_v2/ablation_small_tuned_linear_vs_ml.json`

## Layout

Y-axis:

- metric name

X-axis:

- score

Range:

- 0.00 to 1.00 for the main axis

Special note:

- Switching rate is much smaller in magnitude than the other metrics.
- Best option: keep it on the same axis but print exact values directly next to endpoints.

Alternative if needed:

- split into two panels:
  - Panel A: Precision / Recall / FPR
  - Panel B: Switching Rate

## Visual styling

Endpoint colors:

- Linear: deep blue
- Isolation Forest: orange

Connector line:

- neutral gray

Direct labels:

- print exact endpoint values next to the dots

## Interpretive annotation

Highlight these three messages:

- `Equal FPR`
- `Higher recall`
- `Lower switching`

This is enough.
Do not overload the figure with long explanatory text.

## Caption draft

Figure 6. Ablation of the tuned linear controller against the current Isolation Forest controller in the small tuned scenario (3-run mean). At equal false positive rate, the linear controller achieves substantially higher recall and lower switching rate, supporting its use as the primary evaluated controller in the present prototype.

## In-text callout draft

Figure 6 shows that the strongest current RAASA result is not driven by model complexity. The linear controller and the Isolation Forest path have equal false positive rate on the repeated small-scale ablation, but the linear controller achieves dramatically higher recall and lower switching, making it the more reliable control component in the present implementation.
