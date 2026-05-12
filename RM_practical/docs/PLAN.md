# RAASA v1 Plan: Lightweight Agentic Prototype With Results and Research Roadmap

## Summary
Build RAASA v1 as a **single-host Ubuntu prototype** that demonstrates a modern autonomous containment loop for container workloads. The artifact is not positioned as a complete cloud-security product; it is positioned as a **research prototype** that proves a new direction: workloads can be monitored continuously, assessed through bounded risk logic, acted on through adaptive containment, and evaluated with reproducible evidence.

The system should be framed as a **lightweight agentic security controller** with explicit components for observation, reasoning, action, and audit. The paper should present this as a proof-of-concept with measurable benefits over static baselines and a clear roadmap for stronger future systems.

## Key Changes
### 1. System framing and claim discipline
The v1 paper must make only these claims:
- A lightweight autonomous control loop for container containment can be built and run on real workloads.
- The system can observe runtime behavior, compute bounded risk/confidence values, and adapt containment without manual intervention.
- Adaptive containment can improve the trade-off between permissive and overly restrictive static policies in the tested environment.
- The prototype establishes a practical starting point for future adaptive sandboxing research.

The v1 paper must not claim:
- validated research-prototype cloud defense
- complete sandbox allocation across all attack classes
- strong syscall-level threat detection
- comprehensive protection against escape, exfiltration, or lateral movement
- cluster-scale validation

### 2. Lightweight agentic architecture
Implement the controller as five logical modules:
- `Observer`: collects runtime evidence per container.
- `Risk Assessor`: converts evidence into normalized features, risk score, and confidence score.
- `Policy Reasoner`: chooses `L1/L2/L3` using thresholds plus safety rules.
- `Action Enforcer`: applies containment changes through runtime CPU control.
- `Audit Logger`: records evidence, reasoning, action, and justification for each decision.

Internal decision record per loop should include:
- current signals
- normalized features
- risk score
- confidence score
- previous tier
- proposed tier
- final applied tier
- reason for action or non-action

### 3. Threat-to-signal-to-action design
Define a compact v1 threat matrix covering only what the prototype can honestly test:
- benign steady workload -> low resource/runtime deviation -> remain `L1`
- benign bursty workload -> temporary CPU/process deviation -> maybe `L2`, avoid repeated overreaction
- suspicious workload -> sustained abnormal CPU/process behavior -> `L2`
- malicious-pattern workload -> strong sustained abnormal behavior -> `L3`

For each class, specify:
- observable signals
- expected risk pattern
- intended tier response
- expected residual limitation of v1

### 4. Runtime signals and enforcement scope
Use only signals that are reliable in a first prototype:
- CPU utilization
- memory utilization
- process count or process growth behavior
- limited container/runtime metadata if easy to collect

Use a bounded linear model in v1:
- `risk = weighted sum of normalized features`
- `confidence = stability/consistency of recent evidence`
- clamp both to `[0,1]`

Containment for v1:
- `L1`: baseline runtime
- `L2`: moderate CPU restriction
- `L3`: strict CPU restriction

Do not implement seccomp, CRIU, or advanced network controls in v1. Reserve them for future phases and state that clearly.

### 5. Safe autonomy rules
The policy reasoner must include:
- hysteresis to avoid oscillation near thresholds
- cooldown window before relaxing containment
- minimum evidence consistency before escalation to `L3`
- safe default when signals are missing or inconsistent
- rollback/relaxation rule after sustained low-risk observations

This is required so the prototype demonstrates not only adaptation, but **safe autonomous adaptation**.

### 6. Experiment design
Use three operating modes:
- static `L1`
- static `L3`
- adaptive RAASA v1

Use workload groups:
- benign steady
- benign bursty
- suspicious
- malicious-pattern

Run experiments at small scale first, then moderate scale:
- `3` containers
- `10` containers
- `20` containers

Repeat each scenario at least `3` times under identical config.

### 7. Result metrics
Core metrics:
- precision
- recall
- false positive rate
- adaptation latency
- average resource cost
- tier occupancy over time
- switching rate / oscillation rate

Autonomy-specific metrics:
- unnecessary escalations per benign container-hour
- mean time to safe containment for malicious-pattern workloads
- percentage of actions with a clear audit explanation
- rollback correctness after transient spikes

### 8. Research-roadmap integration
The paper must include a short “next-generation RAASA” roadmap tied directly to v1 limits:
- syscall-derived behavioral signals
- network-aware anomaly signals
- richer enforcement backends
- stronger policy reasoning
- cluster/Kubernetes deployment
- integration with runtime detection tools

This roadmap should be presented as a direct extension of the v1 architecture, not as disconnected future ideas.

## Test Plan
- Observer collects valid metrics repeatedly for all running containers.
- Risk and confidence always remain within `[0,1]`.
- Tier transitions obey hysteresis and cooldown rules.
- Benign steady workloads stay mostly in `L1`.
- Benign bursty workloads do not thrash repeatedly between tiers.
- Suspicious workloads trigger moderate containment.
- Malicious-pattern workloads escalate to strict containment faster than benign workloads.
- Audit logs explain every escalation and relaxation decision.
- Adaptive mode shows a better trade-off than static `L1` and static `L3` in at least one meaningful scenario.

## Assumptions and Defaults
- Target environment is a single Ubuntu VM using Docker.
- v1 is a **prototype + roadmap** paper, not a production system paper.
- v1 uses **resource + basic runtime signals** only.
- v1 implements a **lightweight agentic controller**, not a full LLM-based or planner-heavy autonomous system.
- CPU-based containment is the only required enforcement mechanism in v1.
- Stronger security semantics are future work and must be treated that way in the paper.
