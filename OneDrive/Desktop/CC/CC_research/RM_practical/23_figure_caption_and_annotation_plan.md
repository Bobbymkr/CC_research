# Figure Caption and Annotation Plan

This document complements the redesign plan by defining what each figure should say, not just how it should look.

## Figure 1 caption draft

Figure 1. RAASA architecture. The system implements a closed-loop adaptive containment controller that transforms runtime telemetry into normalized behavioral signals, computes a bounded risk score, and applies tiered containment decisions. In the Kubernetes-oriented deployment, unprivileged reasoning is separated from privileged enforcement through Unix-domain-socket IPC, reducing the blast radius of autonomous decision logic.

**Recommended in-figure annotation**

- `Unprivileged reasoning`
- `Privileged enforcement`
- `Trust boundary`

## Figure 2 caption draft

Figure 2. Adaptive containment outperforms static baselines on both security and benign-cost behavior. Panel A compares precision, recall, and false positive rate. Panel B compares benign restriction rate and unnecessary escalations. RAASA is shown as the 3-run mean of the small tuned scenario.

**Recommended in-figure annotation**

- `RAASA mean (n=3)`
- `Static L1 misses malicious workloads`
- `Static L3 over-restricts benign workloads`

## Figure 3 caption draft

Figure 3. Scalability behavior of the RAASA linear controller across increasing workload counts. Repeated-run means are shown for the 3-container and 10-container scenarios, while the 20-container point is labeled as single-run supporting evidence.

**Recommended in-figure annotation**

- `mean of 3 runs`
- `single-run supporting evidence`

## Figure 4 caption draft

Figure 4. Tier occupancy across evaluated scenarios. The stacked fractions show how much time the controller spends in each containment tier. Benign-heavy scenarios remain concentrated in L1, while higher-risk scenarios spend more time in L2 or L3.

**Recommended in-figure annotation**

- `L1 = low restriction`
- `L2 = throttled`
- `L3 = strict containment`

## Figure 5 caption draft

Figure 5. Tier trajectory over time. Step plots show the controller's state transitions rather than a static classification result. Malicious workloads escalate upward, while benign workloads remain largely stable at low restriction.

**Recommended in-figure annotation**

- `controller dynamics`
- `benign stability`
- `malicious escalation`

## Figure 6 caption draft

Figure 6. Ablation of the tuned linear controller against the current Isolation Forest controller. At equal false positive rate, the linear controller achieves substantially higher recall and lower switching rate, supporting its use as the primary evaluated controller in the present prototype.

**Recommended in-figure annotation**

- `equal FPR`
- `higher recall`
- `lower switching`

## Annotation rules across all figures

- Never imply that a single-run result has the same evidentiary weight as repeated-run means.
- Keep all claim annotations short and declarative.
- Avoid decorative labels that do not advance interpretation.
- If a chart is already crowded, move part of the claim into the caption instead of forcing extra text into the panel.
