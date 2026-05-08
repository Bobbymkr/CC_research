# Phase 1 Ablation (ML vs Linear) - April 26, 2026

This note captures the first real Phase 1 controller ablation on the restarted AWS instance.

Use it with:

- `10_phase1_development_direction_2026_04_26.md`
- `results/aws_v2_2026_04_26/phase1_ablation_ml_vs_linear_2026_04_26/`

## Why this matters

Before the ablation, the live K8s controller had a serious experiment-integrity problem:

- the running ConfigMap had `use_ml_model: true`
- the audit label still said `controller_variant: linear_tuned`

So the system was being interpreted as linear while still using an ML path.

That is now fixed in the preserved post-ablation state.

## What the ablation showed

### Clear win

Removing ML from the live path cleaned up at least one unnecessary escalation:

- `raasa-net-client`: `L2 -> L1`

This is important because it improves controller specificity without weakening the malicious case.

### Also good

The malicious CPU/process workload still stays at `L3` in the truthful linear baseline.

So reverting to linear did not make the system blind to the main malicious pod.

### Remaining problem

`raasa-test-benign-compute` still does not settle cleanly.

But the refreshed post-linear audit shows a more nuanced story than "persistent false positive":

- sometimes the pod drops to low risk and proposes `L1`,
- then de-escalation is blocked by `low-risk streak not long enough -> hold`,
- at other points the syscall signal spikes again and pushes the risk back upward.

That means the remaining issue is now better understood as:

- workload semantics,
- syscall-cap calibration,
- and de-escalation policy,

not just "ML misclassification."

## Best paper-safe interpretation

The strongest way to use this in the paper is:

1. the Phase 1 ablation corrected a controller-truthfulness issue,
2. the truthful linear baseline still preserves `L3` for the malicious pod,
3. it removes at least one unnecessary escalation,
4. the remaining benign-compute issue is a calibration/de-escalation problem,
5. telemetry instability on the Metrics API path still persists across the ablation.

## What this means for the next phase

The next high-value work is now:

1. redesign or relabel the benign-compute workload,
2. tune de-escalation (`low_risk_streak_required`) for cloud-native runs,
3. test enforcement blast radius / node-wide shaping,
4. only then decide whether ML deserves to stay in the main paper story.
