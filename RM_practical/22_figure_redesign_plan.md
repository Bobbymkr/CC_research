# RAASA Figure Redesign Plan

This document replaces the "basic placeholder figure" mindset with a claim-driven figure strategy.
The goal is not merely to visualize data, but to choose the strongest chart type for each paper claim.

Use this as the canonical figure planning document before redrawing or polishing the final paper figures.

## Core principle

Each figure must answer one paper question clearly.

Bad figure design:

- generic chart type chosen because it is easy,
- too many metrics in one panel,
- visual style disconnected from the actual claim,
- a figure that reports numbers but does not help the reader understand the result.

Good figure design:

- one claim per figure,
- chart type matched to the data structure,
- visual emphasis on the most important contrast,
- direct annotation of evidence strength such as `n=3 mean` or `single-run supporting evidence`.

## Final recommended figure lineup

### Figure 1 - Architecture and trust boundary

**Claim proved**

- RAASA is not just a controller loop.
- Its cloud-native novelty includes a zero-trust separation between unprivileged reasoning and privileged enforcement.

**Best chart type**

- layered systems diagram with trust boundaries

**Recommended structure**

- Panel A: logical closed-loop controller
  - Observe
  - Extract
  - Assess
  - Decide
  - Enforce
  - Audit

- Panel B: deployment / security structure
  - unprivileged controller
  - Unix socket IPC
  - privileged enforcer sidecar
  - Docker path
  - Kubernetes path
  - trust boundary clearly shown

**Why this is best**

- A simple flowchart undersells the main systems contribution.
- The strongest architectural story is the "brain vs brawn" separation.

**Caption direction**

- Emphasize adaptive loop plus zero-trust privileged enforcement split.

## Figure 2 - Primary result: adaptive vs static baselines

**Claim proved**

- RAASA outperforms static L1 and static L3 on both security and benign-cost behavior.

**Best chart type**

- two-panel comparison figure

**Panel A**

- security outcome metrics
  - Precision
  - Recall
  - False Positive Rate

**Panel B**

- benign-cost metrics
  - Benign Restriction Rate
  - Unnecessary Escalations

**Recommended visual form**

- lollipop or dot plot preferred
- grouped bars acceptable if styling stays disciplined

**Why this is best**

- The main paper contribution is a tradeoff claim, not just a single score claim.
- Splitting security and benign-cost into separate panels makes the argument much easier to read.

**Data scope**

- Static L1
- Static L3
- RAASA Linear 3-run mean

**Annotation guidance**

- Mark RAASA as `n=3 mean`
- Do not visually imply that AWS or large-scale data are part of the same repeated-evidence pool

## Figure 3 - Scalability behavior

**Claim proved**

- RAASA maintains strong containment behavior as workload count increases.

**Best chart type**

- line chart with markers

**X-axis**

- workload scale
  - 3 containers
  - 10 containers
  - 20 containers

**Y-axis**

- use small multiples or vertically stacked panels for:
  - Precision
  - Recall
  - False Positive Rate

**Why this is best**

- Scale is ordered data.
- Trend across increasing load is better communicated by lines than by bars.

**Important annotation**

- 3 and 10 container points are repeated-run means
- 20 container point is single-run supporting evidence

Use a distinct visual cue:

- solid circle for repeated-run mean
- hollow diamond for single-run evidence

## Figure 4 - Tier occupancy composition

**Claim proved**

- RAASA spends most of its time in low restriction for benign workloads while still escalating risky workloads when needed.

**Best chart type**

- 100% stacked bar chart

**Why this is best**

- This is a composition-over-time question.
- Stacked bars are the right form for tier proportions.

**Design guidance**

- Keep consistent tier colors across the full paper:
  - L1 = green or muted teal
  - L2 = amber
  - L3 = red

- Group scenarios cleanly
- Avoid cluttered legends

**Suggested scenario set**

- small tuned mean
- medium mean
- large single run
- AWS single run if included

**Caution**

- Clearly identify which bars are repeated means and which are supporting single-run evidence.

## Figure 5 - Tier trajectory over time

**Claim proved**

- RAASA behaves like a controller, not just a classifier:
  malicious workloads move upward in restriction while benign workloads remain stable.

**Best chart type**

- step plot

**Best layout**

- small multiples by workload class
  - benign
  - suspicious
  - malicious

**Why this is best**

- A single combined trajectory plot becomes visually noisy.
- Small multiples preserve timing while making each class legible.

**Design guidance**

- Add light background bands for L1 / L2 / L3
- Keep identical y-axis scaling across panels
- Use thin but readable step lines

## Figure 6 - Ablation: linear vs Isolation Forest

**Claim proved**

- In the current implementation, the tuned linear controller is preferable to the Isolation Forest controller.

**Best chart type**

- paired dumbbell plot

**Metrics**

- Precision
- Recall
- False Positive Rate
- Switching Rate

**Why this is best**

- Only two controllers are being compared.
- The most important visual fact is the difference between them.
- Dumbbells show magnitude and direction of the gap more clearly than grouped bars.

**Visual interpretation goal**

- Equal FPR
- much better recall for linear
- lower switching rate for linear

This directly supports the paper-safe conclusion:

- adaptive design value is stronger than ML novelty in the current prototype

## Figure 7 option - Cloud-native supporting evidence panel

This is optional.

If the paper needs a cloud-native visual beyond tables, do not force the AWS result into a large generic chart.

**Best chart type**

- compact evidence panel or annotated summary card

**Could include**

- AWS environment summary
- single-run metrics
- note that `tc` enforcement was confirmed
- note that this is supporting evidence, not the primary repeated-run dataset

**Why**

- A single-run result should not visually dominate repeated-run results.

## Best chart type by result class

| Result class | Best figure type | Avoid |
|---|---|---|
| Architecture and trust boundary | layered systems diagram | plain sequential flowchart only |
| Security vs benign-cost baseline comparison | two-panel lollipop / dot comparison | one overloaded multi-metric bar chart |
| Ordered scale progression | line chart with markers | grouped bars |
| Tier composition | 100% stacked bar | pie chart |
| State transitions over time | step plot | smoothed line plot |
| Two-model ablation | dumbbell plot | radar chart |
| Single-run cloud-native evidence | compact annotated panel | oversized main-result chart |

## Recommended visual language

### Color system

Use one stable semantic palette across the entire paper.

- `L1`: #4E9F6D or similar green/teal
- `L2`: #D9A441 or similar amber
- `L3`: #C85A54 or similar muted red

Controller family colors:

- `RAASA Linear`: deep blue
- `Isolation Forest`: orange
- `Static L1`: gray-blue
- `Static L3`: dark red or charcoal-red

### Typography

- prefer a restrained sans serif
- do not mix many font sizes
- keep figure labels slightly bolder than axis text

### Annotation rules

- annotate `n=3 mean` wherever used
- annotate `single-run supporting evidence` wherever needed
- annotate the main conclusion directly when possible

Examples:

- `Best repeated-run security/cost tradeoff`
- `Equal FPR, higher recall`
- `Single AWS run; supportive, not primary basis`

## Figure-specific rewrite recommendations for the current packet

### Current architecture figure

Status:

- usable as placeholder
- not strong enough for final paper

Recommended action:

- redraw as two-layer trust-boundary systems diagram

### Current detection comparison figure

Status:

- acceptable if needed quickly
- not ideal for final paper

Recommended action:

- convert into two-panel claim-first comparison

### Current scalability figure

Status:

- should be replaced if it is bar-based

Recommended action:

- redraw as line chart with explicit evidence-strength markers

### Current occupancy figure

Status:

- fundamentally correct chart type

Recommended action:

- polish rather than redesign

### Current trajectory figure

Status:

- fundamentally correct chart type

Recommended action:

- split into small multiples if readability is weak

### Current ablation figure

Status:

- grouped bar acceptable but not optimal

Recommended action:

- redraw as dumbbell plot

## Best final recommendation

For a publication-quality packet, use this final set:

1. trust-boundary architecture diagram
2. adaptive vs static two-panel baseline comparison
3. scalability line chart
4. tier occupancy stacked composition
5. tier trajectory step plot
6. linear vs Isolation Forest dumbbell ablation

That set is the best match to the actual claims, evidence structure, and research position of the project.
