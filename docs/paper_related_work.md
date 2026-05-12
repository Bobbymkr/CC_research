# RAASA Paper Related Work

## 1. Draft Related Work Section

RAASA sits at the intersection of container sandboxing, runtime anomaly
detection, Kubernetes-native security enforcement, and the emerging problem of
AI-agent runtime safety. The project is not a direct replacement for any one of
these lines of work. Instead, it combines ideas from each into a bounded,
adaptive containment controller whose contribution lies in the integration of
observation, decision-making, enforcement, and auditability.

### 1.1 Stronger-Than-Native Container Isolation

One major line of related work focuses on strengthening isolation beyond
standard Linux container boundaries. Systems such as gVisor and Kata
Containers pursue this goal by increasing the isolation barrier between the
workload and the host. gVisor provides an application-kernel approach that
interposes on system interfaces in userspace, aiming to reduce the risk of
container escape while preserving a more container-like operational model than
traditional virtual machines. Kata Containers take a different path by
combining container workflows with lightweight virtual machine isolation, using
hardware virtualization to give each workload stronger separation from the host.

These systems are highly relevant to RAASA, but they solve a different primary
problem. Their main goal is stronger isolation by construction. RAASA, by
contrast, is not primarily a stronger replacement for the base sandbox itself.
It assumes that workloads already execute within some container runtime or
orchestrated environment and asks a different question: once workloads are
running, how should containment adapt over time as runtime behavior changes?
The paper should therefore position RAASA as complementary to stronger sandbox
backends rather than as a direct competitor to them.

### 1.2 Static Runtime Hardening and Policy Controls

A second relevant area is static runtime hardening through mechanisms such as
seccomp, AppArmor, SELinux, cgroup limits, Kubernetes policy controls, and
admission-time policy enforcement. These approaches are foundational because
they define what a workload is allowed to do before or during execution.

RAASA differs from these approaches in two important ways. First, it is
runtime-adaptive rather than purely admission- or configuration-driven. Second,
its main object of interest is not only whether a workload should be allowed to
start, but how its containment tier should evolve after execution begins.
Static controls remain essential and are not displaced by RAASA. Instead,
RAASA should be framed as an additional control layer that becomes useful when
pre-declared policy alone is too rigid to capture dynamic runtime behavior.

### 1.3 Runtime Detection and eBPF-Based Observability

Another major body of work focuses on runtime detection and observability,
especially for container and Kubernetes workloads. Recent eBPF-based
instrumentation, enforcement, and analysis studies show that modern cloud-
native security increasingly depends on fine-grained runtime observability
rather than on static inspection alone.

RAASA is closely related to this line of work because it also depends on
runtime telemetry, including signals that are meaningful only in live
execution. However, the key distinction is that RAASA is not just a runtime
detection system. It uses observed signals as inputs to a broader control loop
that produces tiered containment decisions and drives enforcement actions.
Where detection-oriented systems often stop at alerting or policy violation
reporting, RAASA explicitly studies the next step: how to translate runtime
signal interpretation into bounded containment decisions while preserving
auditability and privilege separation.

### 1.4 Resource Controls and Enforcement Semantics

Resource throttling and containment through mechanisms such as cgroups and
Linux Traffic Control have long been used to shape workload behavior. In many
systems, however, these controls are applied statically, coarsely, or in a
manual operational manner. RAASA differs by treating these mechanisms as
enforcement outputs of an adaptive controller rather than as fixed
configuration choices. This distinction matters because the research question
is not merely whether Linux provides throttling primitives, but whether those
primitives can be invoked selectively and meaningfully in response to changing
runtime behavior.

The paper should also emphasize that RAASA's live Kubernetes path moved from a
simple "apply throttle" idea to a more precise pod-specific enforcement model.
That puts it closer to systems work on containment resolution than to generic
resource tuning. In this sense, the relevant comparison is not just with
resource-control features themselves, but with the broader problem of how
policy intent is translated into precise live action under orchestration.

### 1.5 Anomaly Detection for Container Workloads

Machine learning has frequently been explored as a way to detect anomalous
runtime behavior in cloud workloads. Isolation-based approaches, clustering,
statistical profiling, and sequence-aware telemetry models have all been used
to identify deviations from expected process, network, or resource patterns.
This literature is relevant because RAASA includes an Isolation Forest path and
shares the broader goal of distinguishing benign from malicious or suspicious
behavior under runtime noise.

At the same time, RAASA should not be framed primarily as an ML anomaly
detection paper. In the current evidence, the tuned linear controller remains
the strongest and most truthful primary controller, while the ML path is a
secondary extension. That actually helps position the work more clearly. The
paper can acknowledge anomaly-detection literature as influential while making
clear that RAASA's central contribution lies in adaptive containment as a
control architecture, not in claiming a new state-of-the-art anomaly detector.

### 1.6 Autonomous Decision-Making and AI-Agent Runtime Safety

A more recent area of related work concerns the security of LLM-powered and
agentic systems. Recent benchmark and runtime-defense papers such as
AgentDojo, Agent Security Bench, information-flow-control-based agent
hardening, and SafeAgent show that excessive agency, insecure tool use,
improper output handling, and unsafe action execution are now first-class
security concerns. This emerging literature is directly relevant to RAASA
because many of the same challenges appear when systems are allowed to execute
code, invoke tools, or modify live state in response to model-driven
decisions.

RAASA differs from most application-layer LLM safety work by focusing on the
runtime environment rather than the prompt or model interface alone. Its
relevance to agentic systems is therefore architectural: it studies how a
runtime can react when observed execution drifts into suspicious or harmful
behavior. The project does not yet provide a complete agent-security framework,
but it offers a systems-oriented path for grounding agent-runtime safety in
containment, telemetry, and auditable control transitions.

### 1.7 Positioning Relative to Existing Work

Taken together, the related work suggests that RAASA should be positioned as a
synthesis rather than as a direct replacement for any one prior system class.
It is not simply:

- a stronger sandbox like gVisor or Kata Containers
- a static hardening policy like seccomp or admission control
- a runtime detector or observability stack
- an anomaly-detection model for container telemetry
- an application-layer LLM safety checklist

Instead, RAASA combines insights from these areas into a narrower but distinct
research contribution: an adaptive, auditable, privilege-separated containment
controller for containerized workloads that is validated locally and in a live
Kubernetes setting.

That framing is important because it prevents the paper from overstating
novelty in any single subfield while still making a defensible case for the
overall contribution. The novelty is not that RAASA invents sandboxing,
runtime telemetry, or anomaly scoring in isolation. The novelty is that it
integrates these pieces into an explicit control loop whose purpose is adaptive
containment rather than static isolation or passive observation alone.

## 2. Suggested 2021-2026 Reference Set

To keep the IEEE draft aligned with the current scope, the cleanest citation
set is a paper-only list from 2021-2026:

- [R1] RunC / gVisor / Kata performance and isolation comparison
- [R2] Confine for fine-grained syscall attack-surface reduction
- [R3] Kubernetes cluster security-hardening implementation study
- [R4] eBPF-based Kubernetes runtime instrumentation and enforcement
- [R5] cloud-native eBPF security-tool analysis
- [R6] container-attack detection with eBPF and machine learning
- [R7] AgentDojo benchmark
- [R8] Agent Security Bench
- [R9] information-flow control for AI agents
- [R10] SafeAgent runtime protection

## 3. Notes for Revision

When this section is integrated into the final paper:

- keep the comparisons crisp and non-defensive
- do not overclaim novelty against mature sandbox systems
- preserve the distinction between adaptive containment and passive detection
- keep the AI-agent connection future-facing unless more direct benchmarks are
  added
- keep the cited literature restricted to research papers from 2021-2026
