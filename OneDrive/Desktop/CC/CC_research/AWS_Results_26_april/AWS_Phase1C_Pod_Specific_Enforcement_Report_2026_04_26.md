## AWS Phase 1C Pod-Specific Enforcement Report

Date: 2026-04-26  
Target host: `54.227.40.170`  
Node type: single-node K3s on AWS `m7i-flex.large`

### Executive verdict

Phase 1C succeeded.

RAASA now resolves real pod-specific host veth interfaces on the live AWS node and applies containment to those interfaces instead of writing every network action to `cni0`.

The strongest evidence is in:

- `phase1c3_deploy_2026_04_26/`
- `phase1c3_pod_specific_validation_2026_04_26_complete/`

### What changed

The Kubernetes enforcer was upgraded to:

1. resolve `namespace/pod-name` through the in-cluster Kubernetes API,
2. find candidate host PIDs for the pod UID,
3. enter the target process namespaces with `nsenter -n -m`,
4. read the pod-side `eth0` peer relationship,
5. map that peer to a host-side veth interface,
6. apply `tc` to that veth rather than to `cni0`.

This required:

- `raasa/k8s/enforcer_sidecar.py`
- `raasa/k8s/Dockerfile` (added `util-linux` for `nsenter`)
- new deployment and validation helpers under `raasa/scripts/`

### Deployment evidence

The canonical deployment evidence is in `phase1c3_deploy_2026_04_26/`.

Important points:

- image deployed: `raasa/agent:phase1c3`
- DaemonSet image update succeeded
- rollout succeeded
- new live pod after deploy: `raasa-agent-jk9vz`

### Validation design

The canonical validation evidence is in `phase1c3_pod_specific_validation_2026_04_26_complete/`.

The Phase 1C validator:

- applied the same `raasa-bench` benchmark namespace used in Phase 1B,
- targeted the benchmark client pod via the real Unix socket IPC path,
- forced `L1`, ran three transfers of the `4 MiB` payload,
- forced `L3`, ran the same three transfers,
- restored `L1` at the end.

### The key breakthrough

Unlike earlier runs, the enforcer logs now show pod-specific resolution:

- `raasa-bench-client-... -> veth04a1b488`
- `raasa-bench-server-... -> vethd26b4eb3`
- `raasa-test-malicious-cpu -> veth107ee4ec`
- `raasa-test-benign-compute -> veth05e7dcdd`

This is the first live AWS proof that the enforcer is no longer only a node-scoped `cni0` prototype.

### Quantitative result

From `phase1c3_pod_specific_validation_2026_04_26_complete/summary.json`:

- `L1` average time: `0.037154 s`
- `L1` average speed: `191,817,444.67 B/s`
- `L3` average time: `122.718363 s`
- `L3` average speed: `0 B/s`
- time ratio `L3/L1`: `3302.94x`

The three `L3` runs were:

- `121.976374 s, 0 B/s`
- `123.222834 s, 0 B/s`
- `122.955880 s, 0 B/s`

The shell also reported:

- `curl: (56) Recv failure: Connection reset by peer`

### Interpretation

This is stronger than the Phase 1B result.

Phase 1B proved that `cni0` shaping was not meaningfully on the intended data path.  
Phase 1C proves that:

- pod-specific veth attachment is possible on the live node,
- the enforcer can target that veth through the real RAASA IPC path,
- the benchmark pod can be driven from a normal `L1` state into an effectively isolated `L3` state.

One important nuance:

The observed `L3` behavior is not a clean "1mbit graceful slowdown." In this setup it behaved more like hard containment, with connection resets and zero measured throughput. That is still a strong security result, but it should be described as **effective containment**, not as stable QoS shaping.

### Remaining caveat

Not every pod resolved cleanly in every case. For example, `raasa-net-server` still fell back to `cni0` in the captured logs. So the Phase 1C claim should be:

> RAASA now demonstrates live pod-specific network enforcement for key workloads on AWS, with benchmark-backed evidence of effective L3 containment, but interface resolution is not yet universal across all pod types.

### Research-grade conclusion

This materially improves the paper:

- Phase 0 / latest AWS work: telemetry resilience under control-plane degradation
- Phase 1A: truthful controller baseline and ML correction
- Phase 1B: honest exposure of node-scoped enforcement weakness
- Phase 1C: concrete architectural correction with live pod-specific containment evidence

That is a strong systems-paper arc.
