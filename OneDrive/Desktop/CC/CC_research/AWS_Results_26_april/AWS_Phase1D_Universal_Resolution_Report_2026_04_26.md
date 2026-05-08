## AWS Phase 1D Universal Resolution Report

Date: 2026-04-26  
Target host: `54.227.40.170`  
Node type: single-node K3s on AWS `m7i-flex.large`

### Executive verdict

Phase 1D succeeded.

RAASA now resolves the remaining Kubernetes demo and benchmark pods to real host-side veth interfaces on the live AWS node without falling back to `cni0` in the canonical validation bundle.

Canonical artifacts:

- `phase1d2_deploy_2026_04_26/`
- `phase1d2_resolution_validation_2026_04_26/`

### Why Phase 1D was needed

Phase 1C proved pod-specific containment on the benchmark path, but it still left one visible gap:

- `raasa-net-server` fell back to `cni0`

That meant the paper could claim benchmark-backed pod-specific enforcement, but not yet a stronger statement about broader resolver correctness across the live K8s workload set.

### Root cause analysis

The remaining failure was not random.

The earlier resolver used `nsenter -n -m sh -lc ...` to inspect the target pod network namespace. That works only when the target image has a shell available in its mount namespace. The live `hashicorp/http-echo:1.0.0` server pod does not.

Direct live inspection showed:

- the pod was healthy and running,
- `nsenter -t <pid> -n ip -o link show` worked,
- but `nsenter -t <pid> -n -m sh -lc ...` failed because `sh` was missing.

The first Phase 1D correction removed the shell dependency but leaned on `/sys/class/net/.../iflink` after entering only the network namespace. That produced a false mapping to `lo`, which was also wrong.

The final fix was better:

1. enter only the target network namespace,
2. run `ip -o link show`,
3. parse peer indices directly from strings like `eth0@if6`,
4. map that peer ifindex back to the host-side interface name through host `/sys/class/net/*/ifindex`.

This avoids both failure modes:

- no dependence on a shell inside the target image,
- no misleading `iflink` read from the wrong namespace context.

### Implementation changes

The final Phase 1D behavior is implemented in:

- `raasa/k8s/enforcer_sidecar.py`
- `raasa/scripts/run_phase1d_resolution_validation.ps1`

The live deployment used:

- image tag: `raasa/agent:phase1d`
- deployed pod after final rollout: `raasa-agent-4hq5z`

### Validation design

The canonical validation bundle is `phase1d2_resolution_validation_2026_04_26/`.

It did four things:

1. applied the benchmark and demo manifests,
2. forced live RAASA IPC commands against:
   - `raasa-demo/raasa-net-server-79c9b5b7d6-5jfk2`
   - `raasa-demo/raasa-net-client-669f7c4cf8-2d9w8`
   - `raasa-bench/raasa-bench-client-5fd64dcfbf-hvl28`
3. captured enforcer logs before and after those actions,
4. reran the benchmark `L1` vs `L3` transfer comparison.

### Key live results

From `enforcer_logs_final.txt` and `summary.json`:

- `raasa-net-server -> veth3018bd1d via PID 2108`
- `raasa-net-client -> vethb9f7d033 via PID 2195`
- `raasa-bench-client -> veth04a1b488 via PID 3438752`
- `fallback_lines = []`

The broader live log also showed clean resolution for:

- `raasa-test-benign-compute -> veth05e7dcdd`
- `raasa-test-benign-steady -> veth5444b8b2`
- `raasa-test-malicious-cpu -> veth107ee4ec`
- `raasa-bench-server -> vethd26b4eb3`

### Benchmark preservation

Phase 1D did not sacrifice the benchmark containment path.

From `summary.json`:

- `L1` average time: `0.014134 s`
- `L1` average speed: `629,724,863 B/s`
- `L3` average time: `123.051984 s`
- `L3` average speed: `0 B/s`
- time ratio `L3/L1`: `8705.89x`
- speed ratio `L3/L1`: `0`

The three `L3` transfers again ended in:

- `curl: (56) Recv failure: Connection reset by peer`

So the strongest honest interpretation remains:

> RAASA's `L3` behavior on the live AWS node is effective pod-specific containment, not polished bandwidth shaping.

### What Phase 1D changes in the paper

Before Phase 1D, the strongest safe claim was:

> RAASA demonstrates pod-specific containment on the benchmark path, but interface resolution is not yet universal across all tested pod types.

After Phase 1D, the stronger safe claim is:

> On a live single-node AWS K3s deployment, RAASA resolves tested workload pods to host-side veth interfaces and applies pod-specific `L2/L3` enforcement without `cni0` fallback in the canonical validation run.

That is a materially stronger systems result.

### Remaining nuance

Two important caveats still matter:

1. `L3` acts like hard isolation in the current setup, not graceful QoS.
2. The resolver may use the infra/pause PID for a pod rather than the app PID, but that is acceptable because pod containers share the same network namespace.

### Research-grade conclusion

Phase 1D closes the most visible remaining Phase 1C ambiguity.

The Kubernetes enforcement story now has a much cleaner arc:

- Phase 1B exposed the `cni0` weakness,
- Phase 1C proved pod-specific containment on the benchmark path,
- Phase 1D generalized that resolver correctness across the live demo and benchmark pods and preserved the benchmark containment result.

That makes the cloud-native enforcement claim substantially more defensible.
