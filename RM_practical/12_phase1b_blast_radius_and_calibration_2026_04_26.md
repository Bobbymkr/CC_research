## Phase 1B Summary

Phase 1B sharpened the AWS story in a very useful way.

The good news is that the controller side is now much clearer: `benign-compute` is a calibration problem, not a total failure. In the truthful linear baseline, `malicious-cpu` stayed `L3` for all `49` samples, `raasa-net-client` stayed `L1` for all `49`, and `benign-compute` sat in the middle with `L1:19`, `L2:12`, and `L3:18` proposed tiers before de-escalation logic made it sticky at higher tiers.

The sobering result is on enforcement. On the live AWS node, we changed the enforcer-side `tc` root qdisc on `cni0` from `1000mbit` to `1mbit` and fetched a `4 MiB` payload between two benchmark pods on the same node. The qdisc state changed exactly as expected, but the benchmark traffic did not. `L3` average transfer time was about `0.170 s`, not the roughly `32 s` expected under a true `1mbit` cap, and post-benchmark `tc -s` counters only saw `59380` bytes.

That means the current Kubernetes enforcement path should be described carefully in the paper:

- RAASA can drive host-side `tc` changes from the privileged enforcer sidecar.
- The current hook is node-scoped by design.
- The tested `cni0` shaping path is **not yet validated as effective workload-specific network containment**.

Canonical artifacts:

- `results/aws_v2_2026_04_26/phase1b_blast_radius_2026_04_26_refined/`
- `AWS_Results_26_april/AWS_Phase1B_Blast_Radius_Report_2026_04_26.md`

Paper implication:

Use this phase to strengthen honesty, not just novelty. The paper gets better if it says the telemetry/control-plane story is strong, the controller story is diagnosable, and the network-enforcement path is still an active prototype area that needs a more precise pod-level attachment point.
