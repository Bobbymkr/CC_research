# AWS Phase 1 Ablation Report - April 26, 2026

This note records a live controller ablation performed on the restarted AWS instance `54.227.40.170`.

The goal was simple: stop mixing controller labels and controller behavior, then measure what actually changed.

## Primary artifacts

- `phase1_ablation_ml_vs_linear_2026_04_26/before_configmap_ml_on.yaml`
- `phase1_ablation_ml_vs_linear_2026_04_26/before_audit_ml_on.jsonl`
- `phase1_ablation_ml_vs_linear_2026_04_26/after_configmap_linear.yaml`
- `phase1_ablation_ml_vs_linear_2026_04_26/after_audit_linear.jsonl`
- `phase1_ablation_ml_vs_linear_2026_04_26/after_audit_linear_refreshed.jsonl`
- `phase1_ablation_ml_vs_linear_2026_04_26/post_linear_live_validation/`
- `AWS_Phase1_Development_Direction_2026_04_26.md`

## 1. What changed on the live node

### Before the ablation

The running ConfigMap had:

- `ml.use_ml_model: true`
- `evaluation.controller_variant: linear_tuned`

The live audit records still said `controller_variant: "linear_tuned"`, but the assessment reasons contained `ml_score=...`, which proves the active path was ML-backed while the label claimed linear.

This was a truthfulness problem in the experiment record.

### After the ablation

The live ConfigMap was changed to:

- `ml.use_ml_model: false`
- `evaluation.controller_variant: linear_tuned`

After restart, the audit reasons changed from `ml_score=...` to explicit weighted terms such as:

- `cpu=...*0.55`
- `mem=...*0.55`
- `sys=...*0.55`

That means the post-change state is now a truthful linear baseline.

## 2. Live comparison summary

The table below compares the last preserved ML-on state against the refreshed linear-baseline state.

| Workload | Before (ML active, mislabeled) | After (truthful linear baseline) | What it means |
| --- | --- | --- | --- |
| `raasa-test-benign-steady` | `L1`, risk `0.318` | `L1`, risk `0.028` | Baseline idle behavior became much cleaner. |
| `raasa-test-benign-compute` | `L3`, risk `0.474` | `L3`, risk `0.283` | Still sticky, but no longer a clean ML-only issue. |
| `raasa-test-malicious-cpu` | `L3`, risk `0.596` | `L3`, risk `1.000` | Malicious workload still cleanly stays severe. |
| `raasa-net-client` | `L2`, risk `0.411` | `L1`, risk `0.097` | This is the clearest win from removing ML from the loop. |
| `raasa-net-server` | `L1`, risk `0.347` | `L1`, risk `0.031` | Benign network-side baseline also became cleaner. |

## 3. The most important nuance: benign-compute is oscillatory, not purely broken

The refreshed linear audit shows that `raasa-test-benign-compute` does not stay uniformly severe.

Examples from the same live run:

- `2026-04-26T05:52:51Z`: risk `0.329`, proposed `L1`, held at `L3` because `low-risk streak not long enough -> hold`
- `2026-04-26T05:52:56Z`: risk `0.635`, `syscall_rate=560.8`, held at `L3`
- `2026-04-26T05:53:08Z`: risk `0.283`, proposed `L1`, still held because `low-risk streak not long enough -> hold`

This matters a lot.

The post-ablation evidence says the remaining `benign-compute -> L3` behavior is a combination of:

1. syscall-rate bursts that sometimes cross the current `syscall_cap=500.0`,
2. de-escalation guardrails (`low_risk_streak_required: 4`),
3. a workload definition that may still be too close to the threat model boundary.

So the correct interpretation is not:

- "linear solved everything"

and not:

- "ML alone caused the false positive."

It is:

- **the ablation removed a controller-truthfulness problem and improved specificity for at least one workload, while exposing a deeper workload/policy calibration issue for benign compute.**

## 4. What did not improve

### A. Metrics API instability remains

Across the linear-baseline evidence, audit metadata still repeatedly reports:

- `network_status: metrics_unavailable`

and the collected pod logs still show `500 Internal Server Error` / `context deadline exceeded` failures on the Metrics API path.

So the telemetry-resilience finding remains live.

### B. Network enforcement scope is still unresolved

This ablation did not change the underlying K8s network-enforcement implementation.

The current prototype still shapes `cni0`, so the paper must not claim workload-specific network isolation until a blast-radius test proves it.

## 5. Research decision after the ablation

As the research/SWE/security lead decision for Phase 1:

1. keep the linear baseline as the primary trustworthy comparison point,
2. do not let ML become the main paper claim yet,
3. treat `benign-compute` as a workload-design plus de-escalation-policy problem,
4. next validate enforcement specificity / blast radius,
5. only reintroduce ML into the headline story if it survives that cleaner baseline.

## 6. Publication-safe claim

The strongest paper-safe statement after this live ablation is:

> On the restarted AWS K3s node, we found that the running controller had been mislabeled as `linear_tuned` while still using an ML path. After correcting the configuration to a truthful linear baseline, RAASA preserved `L3` classification for the malicious workload and removed at least one unnecessary escalation (`raasa-net-client: L2 -> L1`). The remaining `benign-compute` instability appears to be driven by probe-derived syscall bursts and de-escalation policy rather than ML alone.
