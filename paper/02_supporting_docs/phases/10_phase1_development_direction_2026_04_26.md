# Phase 1 Development Direction - April 26, 2026

This note is the practical answer to: "what should Phase 1 development actually be now?"

Use it together with:

- `08_stronger_paper_test_plan_aws_m7i_flex_large.md`
- `09_live_aws_instance_log_validation_2026_04_26.md`
- `results/aws_v2_2026_04_26/live_instance_validation_restart_2026_04_26/`

## Bottom line

Phase 1 should now focus on **cloud-native correctness**, not just ML enablement.

The restarted AWS instance shows three simultaneous realities:

1. the system comes back and runs,
2. control-plane telemetry is still unstable under stress/restart conditions,
3. the current controller/enforcer behavior is still too ambiguous to support a strong paper claim without more careful ablation.

## What changed my recommendation

From the live restarted instance:

- `raasa-agent` still shows early Metrics API `503` and later `500` failures,
- the malicious pod still has live telemetry available,
- the syscall probe path is active,
- but the live enforcer behavior includes `benign-compute -> L3`,
- and the current K8s enforcer implementation applies `tc` at `cni0` root, which is effectively node-scoped in this prototype.

That means the next serious development step is not "make the ML path look exciting."

It is:

- separate controller effects,
- verify enforcement scope,
- tighten threat-model expectations,
- then revisit the ML story.

## The right Phase 1 order

1. capture a clean restart-era baseline,
2. run a no-ML vs ML comparison with the same workloads,
3. test whether malicious containment also harms benign traffic,
4. fix or narrow the enforcement claim,
5. only then decide whether the ML path deserves to stay in the main paper story.

## Most important development task

The single most important current task is:

- **enforcement specificity / blast-radius validation**

Why:

- if network shaping is effectively node-wide, that must shape both the implementation roadmap and the paper wording.

## Best interpretation for the paper

If Phase 1 succeeds, the paper can say:

- the control-plane telemetry path is fragile under load,
- RAASA provides an out-of-band fallback signal path,
- the controller behavior was tested under restart and stress conditions,
- and the cloud-native enforcement path was characterized honestly for its current scope.

That is a much stronger paper than one that simply says:

- "we turned on Isolation Forest."
