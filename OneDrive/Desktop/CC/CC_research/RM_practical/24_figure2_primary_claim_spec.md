# Figure 2 Redraw Spec - Adaptive vs Static Baselines

This spec defines the strongest final form for the paper's main result figure.
It should replace a generic single-panel comparison chart.

## Figure purpose

Figure 2 is the paper's primary evidence figure.
Its job is to prove the central claim:

- static L1 underreacts,
- static L3 overreacts,
- RAASA provides the best security / benign-cost tradeoff.

## Best chart structure

Use a **two-panel comparison figure**.

### Panel A - Security behavior

Metrics:

- Precision
- Recall
- False Positive Rate

Modes:

- Static L1
- Static L3
- RAASA Linear mean

### Panel B - Benign-cost behavior

Metrics:

- Benign Restriction Rate
- Unnecessary Escalations

Modes:

- Static L1
- Static L3
- RAASA Linear mean

## Best chart type

Preferred:

- lollipop or dot plot

Acceptable fallback:

- grouped bar chart with disciplined styling

## Why this is the best representation

- The result is fundamentally a **tradeoff comparison**.
- A two-panel layout separates security from cost cleanly.
- The reader can see immediately that RAASA is neither the weakest nor the most restrictive option.

## Data values to plot

### Panel A

| Mode | Precision | Recall | FPR |
|---|---:|---:|---:|
| Static L1 | 0.00 | 0.00 | 0.00 |
| Static L3 | 0.33 | 1.00 | 1.00 |
| RAASA Linear mean | 0.87 | 1.00 | 0.11 |

### Panel B

| Mode | BRR | UE |
|---|---:|---:|
| Static L1 | 0.00 | 0.0 |
| Static L3 | 1.00 | 24.0 |
| RAASA Linear mean | 0.11 | 1.3 |

Source:

- `RM_practical/master_results_table.md`
- Table 1, baseline comparison

## Axis guidance

### Panel A

- x-axis: metric
- y-axis: score from 0 to 1

### Panel B

Two options:

Option 1, preferred for clarity:

- left subplot for BRR, y-axis 0 to 1
- right subplot for UE, y-axis 0 to 24

Option 2, if you need compactness:

- normalize UE for plotting and explain that the printed labels are raw values

Do not force BRR and UE onto the same numerical axis without explanation.

## Styling guidance

Mode colors:

- Static L1: muted gray-blue
- Static L3: dark red
- RAASA Linear mean: deep blue

Annotation:

- `RAASA mean (n=3)`
- `Static L1 misses threats`
- `Static L3 restricts every benign workload`

## Visual emphasis

The chart should visually emphasize:

- RAASA's recall equals Static L3,
- RAASA's FPR and BRR are dramatically lower than Static L3,
- RAASA's precision is dramatically higher than Static L3,
- Static L1 is effectively non-protective.

## Caption draft

Figure 2. Primary baseline comparison. Panel A compares security behavior across static L1, static L3, and the RAASA linear controller (3-run mean). Panel B compares benign-cost behavior using benign restriction rate and unnecessary escalations. RAASA preserves recall equivalent to the strong static baseline while sharply reducing benign over-restriction.

## In-text callout draft

Figure 2 shows that RAASA's advantage is not a marginal metric improvement but a tradeoff correction. Static L1 fails to contain malicious workloads, while static L3 achieves full recall only by restricting benign workloads continuously. RAASA retains full recall on the repeated small-scale evaluation while reducing both false positive rate and benign restriction cost.
