# Abstract and Contributions Rewrite

This rewrite is grounded in the current repo evidence and removes the biggest manuscript/code mismatches.
Use this instead of the older abstract in `_draft_paper.txt`.

## Paper-safe abstract draft

Modern cloud platforms run many containerized workloads from different tenants on shared physical infrastructure. Static sandboxing policies force an undesirable trade-off: weak isolation leaves risky workloads under-constrained, while uniformly strict isolation unnecessarily restricts benign workloads. This paper presents RAASA, a research prototype for risk-aware adaptive containment of containerized workloads. RAASA implements a closed-loop control architecture that continuously collects runtime telemetry, converts it into normalized behavioral signals, computes a bounded risk score, and moves workloads between containment tiers using explicit safety rules including hysteresis, cooldown, and confidence gating.

The current prototype uses five implemented telemetry-derived signals: CPU usage, memory pressure, process count, network throughput, and a syscall-rate signal. These inputs drive a modular controller that supports both local Docker enforcement and a cloud-native prototype path with decoupled privileged enforcement through Unix-domain-socket IPC. In the local path, RAASA applies real CPU throttling through `docker update --cpus`; in the Kubernetes-oriented path, it delegates enforcement to a privileged sidecar that performs network shaping and cgroup-level restriction.

We evaluate RAASA against static L1 and static L3 baselines across repeated small- and medium-scale experiments, plus supporting large-scale and AWS/Kubernetes runs. On the strongest repeated evidence, RAASA achieves a 3-run mean precision of 0.87 and recall of 1.00 in the small tuned scenario, and 0.95 precision and 1.00 recall in the medium scenario, while static L1 misses malicious workloads and static L3 over-restricts benign ones. An ablation study further shows that the tuned linear controller outperforms the current Isolation Forest path on recall at equal false-positive rate. These results support the core claim that adaptive containment, rather than fixed-policy sandboxing, is the main source of RAASA's advantage on the evaluated workload mix.

## Contributions rewrite

Use a contribution list like this in the introduction.

1. We present RAASA, a modular closed-loop adaptive containment prototype for containerized workloads that connects telemetry, risk scoring, policy reasoning, enforcement, and audit logging in one controller.

2. We define and implement a practical five-signal runtime feature path based on CPU usage, memory pressure, process count, network throughput, and syscall-rate telemetry, together with explicit safety controls such as hysteresis, cooldown, confidence gating, and operator override support.

3. We show experimentally that adaptive containment outperforms static weak and static strong baselines on the evaluated workload mix, especially by reducing benign over-restriction while maintaining high malicious containment.

4. We contribute a cloud-native prototype architecture that separates unprivileged reasoning from privileged enforcement through a zero-trust sidecar pattern using Unix domain socket IPC.

5. We provide an honest controller ablation showing that, in the current system, the tuned linear controller is more reliable than the current Isolation Forest variant, indicating that the adaptive control design is more important than ML novelty in the present prototype.

## Shorter abstract option

If you need a more compressed abstract for page limits:

RAASA is a research prototype for adaptive containment of containerized workloads. Rather than applying a fixed sandbox policy at launch time, RAASA continuously observes runtime behavior, computes a bounded risk score from five implemented signals (CPU, memory, process count, network throughput, and syscall-rate signal), and moves workloads between containment tiers using a safety-aware policy engine. The system includes both a local Docker enforcement path and a cloud-native prototype path that separates unprivileged reasoning from privileged enforcement through Unix-domain-socket IPC. Across repeated small- and medium-scale experiments, RAASA outperforms static L1 and static L3 baselines by preserving high recall while substantially reducing benign over-restriction. An ablation study further shows that the tuned linear controller outperforms the current Isolation Forest variant on recall at equal false-positive rate. These results support the central claim that adaptive containment is the main source of advantage over static sandboxing on the evaluated workload mix.

## Usage notes

- If the final paper foregrounds repeated evidence, use the small and medium mean values in the abstract.
- If you mention AWS in the abstract, label it as supporting cloud-native validation rather than universal proof.
- Avoid any line that implies perfect metrics "in all scenarios."
- Avoid describing seccomp downgrade or CRIU as implemented contributions.
