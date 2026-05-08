## AWS Phase 1B Blast Radius and Calibration Report

Date: 2026-04-26  
Target host: `54.227.40.170`  
Node type: single-node K3s on AWS `m7i-flex.large`

### Executive verdict

Phase 1B produced two important findings:

1. The current Kubernetes network enforcement path is **not yet paper-safe as a true isolation claim**. We can successfully change `tc` state on `cni0`, but the measured pod-to-pod benchmark traffic does not slow down in a way that matches a real `1mbit` cap.
2. The remaining controller issue is now much more specific: `benign-compute` is not a general controller collapse. It is a **syscall-threshold plus de-escalation calibration problem**.

This is exactly the kind of result a serious systems paper should surface honestly.

### Goal

Phase 1B was meant to answer two questions:

- Does the current `raasa-enforcer` path have acceptable enforcement specificity and observable blast radius?
- Is `benign-compute` still misbehaving because of ML, or because of the tuned linear controller plus workload telemetry profile?

### Experiment design

The benchmark artifacts are in `phase1b_blast_radius_2026_04_26_refined/`.

- A dedicated namespace `raasa-bench` was created with:
  - `raasa-bench-server`: nginx serving a `4 MiB` payload
  - `raasa-bench-client`: curl client pod
- Both pods landed on the same node.
- The existing live RAASA agent pod was used to reach the privileged `raasa-enforcer` container.
- We changed the host-side `cni0` qdisc through the same mechanism the prototype uses:
  - `L1` proxy rate: `1000mbit`
  - `L3` proxy rate: `1mbit`
- For each tier we fetched the `4 MiB` payload three times and captured:
  - measured transfer time and download speed
  - `tc -s qdisc show dev cni0` after the benchmark

### Blast-radius result

The configured `tc` state definitely changed:

- `qdisc_l1.txt`: `rate 1Gbit`
- `qdisc_l3.txt`: `rate 1Mbit`

But the traffic behavior does not match a real `1mbit` enforcement result.

#### Measured throughput

From `summary.json`:

- `L1` average time: `0.00836 s`
- `L1` average speed: `764,286,421 B/s`
- `L3` average time: `0.17005 s`
- `L3` average speed: `500,705,824 B/s`

One `L3` sample slowed to about `0.498 s`, but that is still nowhere close to the roughly `32 s` lower bound expected if a `4 MiB` object were actually constrained to `1mbit`.

#### Qdisc counters

Post-benchmark counters are even more revealing:

- `qdisc_l1_post_benchmark.txt`: `Sent 26752 bytes`
- `qdisc_l3_post_benchmark.txt`: `Sent 59380 bytes`, `dropped 23`, `overlimits 33`

That means the qdisc saw only a few tens of kilobytes, not the multi-megabyte data path we intended to police.

### Interpretation

The strongest defensible interpretation is:

- the prototype can mutate host `tc` state from the enforcer sidecar,
- the current `cni0` root TBF hook is **node-scoped by construction**,
- but this specific hook is **not meaningfully enforcing same-node pod-to-pod service traffic** in the tested path.

Inference: the current shaping point is either off the main payload path, or only seeing a small subset of bridge/control traffic rather than the application data stream itself.

### Benign-compute calibration result

To keep Phase 1B from becoming only a networking story, we also quantified the linear-controller behavior from `after_audit_linear_refreshed.jsonl`. The summary is saved in `phase1b_blast_radius_2026_04_26_refined/benign_compute_calibration_summary.json`.

#### `default/raasa-test-benign-compute`

- samples: `49`
- average risk: `0.4201`
- average syscall rate: `370.12`
- syscall range: `103.4 -> 936.4`
- proposed tiers: `L1:19, L2:12, L3:18`
- actual new tiers: `L1:3, L2:6, L3:40`
- held due to `low-risk streak` logic: `19`

#### `default/raasa-test-malicious-cpu`

- samples: `49`
- average risk: `0.8770`
- average syscall rate: `6910.41`
- proposed tiers: `L3:49`
- actual new tiers: `L3:49`

#### `raasa-net-client`

- samples: `49`
- average risk: `0.1037`
- average syscall rate: `47.87`
- proposed tiers: `L1:49`
- actual new tiers: `L1:49`

### What this means

`benign-compute` is not failing because the controller cannot separate benign from malicious workloads at all. The contrast with `malicious-cpu` and `raasa-net-client` is too clean for that. The problem is narrower:

- `benign-compute` sometimes proposes `L1` or `L2`,
- but its syscall bursts are still high enough to revisit `L3`,
- and the de-escalation guardrail keeps it sticky once elevated.

So the next tuning target is the syscall feature and de-escalation policy, not a blind return to "just add more ML."

### Research-grade decision

As a publication decision, we should now say:

- telemetry resilience: strong and improving
- controller diagnosis: strong enough to guide tuning
- Kubernetes network enforcement: **prototype-only and not yet validated as workload-specific containment**

### Immediate next move

Phase 1C should focus on enforcement correctness, in this order:

1. move from `cni0` root shaping to a pod-specific attachment point or pod-aware enforcement mechanism,
2. rerun the exact same benchmark until `1mbit` produces an unmistakable multi-second slowdown,
3. only then revisit stronger network-containment claims in the paper.
