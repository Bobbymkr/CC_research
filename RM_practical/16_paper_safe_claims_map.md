# RAASA Paper-Safe Claims Map

This document turns the repo state into a paper-safe claim set.
Use it as the first filter before writing or revising any manuscript section.

## Recommended paper position

Present RAASA as:

- a research prototype for adaptive containment of containerized workloads,
- implemented as a closed-loop controller with observe -> assess -> decide -> act -> audit stages,
- validated strongly on local Docker experiments,
- extended meaningfully into a cloud-native Kubernetes prototype path,
- and architecturally strengthened by a zero-trust privileged sidecar enforcement design.

Do **not** present RAASA as a fully mature production system.
Do **not** center the paper on seccomp hot-swapping, CRIU downgrade, or feature semantics that are not implemented in the repo.

## Strong claims the repo supports well

- RAASA implements a modular adaptive containment loop in code.
  Source anchors:
  - `raasa/core/app.py`
  - `raasa/core/telemetry.py`
  - `raasa/core/features.py`
  - `raasa/core/risk_model.py`
  - `raasa/core/policy.py`
  - `raasa/core/enforcement.py`
  - `raasa/core/logger.py`

- The current implemented telemetry-to-decision path uses five signals:
  - CPU
  - memory
  - process count
  - network throughput / byte deltas
  - syscall-rate signal

- RAASA includes explicit safety controls in the policy engine:
  - hysteresis,
  - cooldown,
  - low-risk streak gating,
  - confidence-based L3 gating,
  - optional approval gating,
  - optional operator override.

- The strongest current evaluation evidence favors the tuned linear controller over static L1 and static L3 baselines.

- The current ablation evidence favors the tuned linear controller over the Isolation Forest path.

- The project implements auditable decision traces via JSONL logs and derived summaries.

- The Kubernetes-oriented path includes a meaningful architectural contribution:
  decoupling unprivileged reasoning from privileged enforcement through Unix domain socket IPC.

## Claims that are valid, but must be framed carefully

- The Kubernetes / AWS path is real and meaningful, but the evidence base is smaller than the Docker path.
- The eBPF / probe-oriented cloud path is promising, but the telemetry stack is not uniformly complete across all captured runs.
- The sidecar architecture is a strong architectural contribution, but it should still be described as a prototype rather than broad operational proof.
- The optional LLM advisor exists in code, but it is not the center of the strongest reported empirical results.

## Claims that should be downgraded to future work

These should not be described as currently implemented paper contributions unless re-implemented and re-evidenced:

- dynamic seccomp relaxation,
- CRIU-backed downgrade handling,
- host-level auditd-based syscall distribution modeling,
- file I/O entropy features,
- privileged syscall-rate features as currently measured in the main path,
- iptables-based network namespace enforcement as a mature repo-backed mechanism.

## Writing rules by section

### Abstract

Use aggregate or explicitly scoped results, not universal perfection claims.

Best safe framing:

- Small tuned 3-run mean:
  - Precision = 0.87
  - Recall = 1.00
  - FPR = 0.11
- Medium 3-run mean:
  - Precision = 0.95
  - Recall = 1.00
  - FPR = 0.04
- Large and AWS cloud-native results:
  - present as single-run evidence,
  - not as universal proof.

### Contributions

Anchor contributions around:

1. adaptive containment vs static baselines,
2. modular closed-loop controller design,
3. policy safety rules and full auditability,
4. zero-trust sidecar enforcement architecture for cloud-native deployment,
5. honest ablation showing design value exceeds ML novelty.

### Architecture

Describe the implemented feature vector exactly as the code uses it:

- `cpu_signal`
- `memory_signal`
- `process_signal`
- `network_signal`
- `syscall_signal`

### Evaluation

Primary evidence hierarchy:

1. Docker baseline comparison and repeated tuned runs,
2. scalability progression from 3 to 10 to 20 containers,
3. ablation of linear vs Isolation Forest,
4. AWS / Kubernetes prototype validation.

### Limitations

Explicitly disclose:

- single-run evidence for some scenarios,
- Kubernetes telemetry fragility under load,
- incomplete parity between intended telemetry architecture and every observed live run,
- prototype-level operational maturity.

## Best one-sentence thesis

RAASA shows that a closed-loop adaptive containment controller can outperform static sandbox policies on the evaluated workload mix, while a zero-trust sidecar design makes cloud-native enforcement architecturally defensible.

## Risky wording to avoid

- "RAASA fully implements dynamic seccomp downgrade."
- "RAASA universally achieves perfect precision and recall."
- "The learned model outperforms the linear controller."
- "The cloud-native path has been comprehensively validated in production."

## Safe wording patterns

- "The current prototype implements..."
- "The strongest evidence in this study comes from..."
- "The cloud-native path is prototyped through..."
- "Single-run AWS evidence suggests..."
- "The tuned linear controller served as the primary evaluated controller because..."
