## Phase 1C Summary

Phase 1C is the first live AWS result that turns the Kubernetes enforcement story from "prototype-shaped" into "paper-relevant."

The enforcer no longer wrote every decision to `cni0`. After the Phase 1C fix, it resolved real host-side veth interfaces for target pods such as:

- `raasa-bench-client -> veth04a1b488`
- `raasa-bench-server -> vethd26b4eb3`
- `raasa-test-malicious-cpu -> veth107ee4ec`
- `raasa-test-benign-compute -> veth05e7dcdd`

Using that path, the benchmark client pod was driven through the real Unix socket IPC channel from `L1` to `L3`. In the canonical run, `L1` transfers averaged about `0.037 s`, while `L3` transfers collapsed to about `122.7 s` with `0 B/s` effective throughput and `curl: (56) Recv failure: Connection reset by peer`.

That means the Phase 1C claim is now defensible:

- RAASA can enforce network containment at a pod-specific host interface, not only at `cni0`.
- On the live AWS node, that enforcement produced decisive containment for the benchmark pod.

One important nuance for the paper:

The observed `L3` behavior looked more like hard isolation than graceful `1mbit` shaping. So the strongest honest wording is **effective L3 containment via pod-specific veth enforcement**, not polished per-tier bandwidth QoS.

Canonical artifacts:

- `results/aws_v2_2026_04_26/phase1c3_deploy_2026_04_26/`
- `results/aws_v2_2026_04_26/phase1c3_pod_specific_validation_2026_04_26_complete/`

Paper implication:

Phase 1B exposed the enforcement problem; Phase 1C fixes the core architectural flaw well enough to support a serious cloud-native paper claim.
