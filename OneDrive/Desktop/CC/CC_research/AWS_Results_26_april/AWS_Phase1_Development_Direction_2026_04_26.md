# AWS Phase 1 Development Direction - April 26, 2026

This note resets Phase 1 around what the live AWS node actually shows after the instance restart. It should be treated as the primary execution direction for the next development cycle.

Related live evidence:

- `live_instance_validation_restart_2026_04_26/collection_metadata.txt`
- `live_instance_validation_restart_2026_04_26/raasa_agent_all_containers_tail_200.txt`
- `live_instance_validation_restart_2026_04_26/metrics_api_malicious_pod.json`
- `live_instance_validation_restart_2026_04_26/metrics_server_tail_200.txt`
- `live_instance_validation_restart_2026_04_26/journalctl_k3s_tail_200.txt`

## 1. What the restarted live node is telling us

### A. The system is up, but Phase 1 is not mainly an ML problem yet

On the restarted instance (`54.227.40.170`), K3s and the RAASA pod came back successfully, and the current config still has:

- `ml.use_ml_model: true`
- `evaluation.controller_variant: linear_tuned`

That means the current state is already mixing controller logic, fallback telemetry behavior, and enforcement behavior. Until those are separated, ML-specific conclusions will not be trustworthy.

### B. The Metrics API is still unstable under restart/load conditions

The live `raasa-agent` log shows:

- initial `503 Service Unavailable`
- later `500 Internal Server Error`
- repeated authorization-path timeouts against the API server

At the same time, the Metrics API can still succeed later for the malicious pod. So the right wording remains:

- **degraded / unstable control-plane telemetry**

not:

- permanently dead Metrics API.

### C. Syscall probe telemetry is alive

The same log shows live syscall-rate values being produced for pod UIDs, including the malicious pod. So the syscall probe side is no longer the weakest link in this snapshot.

### D. The biggest current correctness problem is policy + enforcement behavior

Immediately after recovery, the live enforcer log showed:

- `raasa-test-benign-compute -> L3`
- `raasa-test-malicious-cpu -> L3`
- `raasa-net-client -> L2`

That means the system is not currently demonstrating the clean threat-model separation we want for the paper.

### E. The network enforcer is explicitly node-scoped in the current code

`raasa/k8s/enforcer_sidecar.py` applies:

- `tc qdisc del dev cni0 root`
- `tc qdisc add dev cni0 root tbf ...`

and the code comments explicitly say this is effectively node-level throttling in the prototype.

This is the single most important Phase 1 development fact.

## 2. What Phase 1 should mean now

Phase 1 should not be framed as:

- "finish the Isolation Forest demo"

Phase 1 should be framed as:

- **establish cloud-native closed-loop correctness**

That means making the AWS path scientifically trustworthy before claiming model sophistication.

## 3. Correct Phase 1 priority order

### Priority 1 - Separate controller correctness from ML ambition

Immediate goal:

- run the same workload set once with `use_ml_model: false`
- run it again with `use_ml_model: true`
- compare tier decisions and containment actions directly

Why:

- right now the live node can over-escalate benign compute,
- so we must know whether that comes from the learned model, the linear policy path, the mixed config, or the telemetry inputs.

### Priority 2 - Fix or narrow the enforcement claim

Immediate goal:

- either implement more workload-specific enforcement,
- or explicitly narrow the paper claim to node-local prototype shaping.

Why:

- the current code does not support a strong per-pod network-isolation claim.

### Priority 3 - Redefine benign compute expectations

Immediate goal:

- treat benign high CPU as `L1` or `L2` behavior unless accompanied by malicious process/syscall/network patterns.

Why:

- `benign-compute -> L3` weakens the paper more than a missing ML story does.

### Priority 4 - Use the AWS box for short, controlled ablations

Immediate goal:

- do short runs that isolate one question at a time.

Recommended sequence:

1. idle baseline
2. malicious-only stress
3. benign-compute-only stress
4. malicious + benign together
5. optional ML-vs-no-ML comparison

## 4. Concrete AWS execution plan for the next development loop

### Phase 1A - Stabilize the interpretation path

1. Capture current config and logs
   - already done in `live_instance_validation_restart_2026_04_26/`

2. Export a fresh audit JSONL from the running `raasa-agent`
   - use this as the restart-era baseline

3. Record current tier outcomes for:
   - `raasa-test-benign-steady`
   - `raasa-test-benign-compute`
   - `raasa-test-malicious-cpu`
   - `raasa-net-client`
   - `raasa-net-server`

Acceptance criterion:

- we have a clean pre-change baseline tied to the restarted instance.

### Phase 1B - Controller ablation

1. run with `use_ml_model: false`
2. keep all other config constant
3. observe tier decisions for the same pod set
4. then restore `use_ml_model: true`
5. compare

Acceptance criterion:

- we can attribute over-escalation behavior to a specific controller path rather than hand-waving.

### Phase 1C - Enforcement truth test

1. keep one benign network flow active to `raasa-net-server`
2. trigger containment on the malicious pod
3. observe whether the benign flow degrades at the same time

Acceptance criterion:

- if benign throughput drops with malicious containment, the prototype is node-scoped for network shaping.

### Phase 1D - Paper-safe claim update

After the above:

- if enforcement stays node-scoped, describe it honestly,
- if controller overreaction persists, present it as an active tuning/correctness limitation,
- only then revisit the ML story.

## 5. My recommendation as the assigned research/SWE team

The fastest path to a stronger paper is:

1. **do not let ML be the headline of Phase 1**
2. **make correctness the headline**
3. **prove exactly what the current network enforcement really scopes to**
4. **only keep the ML path if it survives the ablation cleanly**

That is the research-grade move.

If we do this in order, Phase 1 becomes the point where RAASA stops looking like a promising demo and starts looking like a serious cloud-native systems prototype with honest boundaries.
