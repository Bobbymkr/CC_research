# RAASA: Risk-Aware Adaptive Sandbox Allocation for Containerized Workloads

## Abstract

Modern containerized and agentic workloads are poorly served by static
containment: permissive sandboxes underreact to malicious or runaway behavior,
while strict sandboxes overconstrain benign execution and reduce system
utility. This paper presents RAASA (Risk-Aware Adaptive Sandbox Allocation), a
research system for adaptive containment of containerized workloads. RAASA is
organized as an Observe-Assess-Decide-Act-Audit control loop that collects
runtime telemetry, converts it into bounded risk signals, selects among tiered
containment levels (`L1`, `L2`, `L3`), and records auditable reasons for each
decision, while separating unprivileged reasoning from privileged enforcement
through a constrained IPC boundary. RAASA is evaluated in local Docker-based
experiments and AWS-hosted K3s deployments. Locally, adaptive containment
outperforms static permissive and static strict baselines. In the cloud path,
fresh-account single-node replay and bounded 3-node K3s validation show
pod-specific enforcement resolution, repeated adversarial workloads, explicit
degraded/failure signaling, and worker drain/reschedule continuity. The
resulting evidence supports RAASA as a validated research prototype and
bounded cloud-security feasibility result, not as a production-ready or
EKS-ready system. Overall, the results suggest that adaptive containment is a
practical direction for modern cloud and AI-agent runtime security, while
telemetry and control-plane fragility in the live Kubernetes path remain the
clearest blockers to a stronger v2 candidate.

**Index Terms**: container security, Kubernetes security, adaptive
containment, runtime telemetry, sandboxing, cloud security, agent runtime
safety.

## 1. Introduction

Modern cloud workloads increasingly execute inside containerized environments in
which security and utility are often placed in direct tension. When containment
is too permissive, malicious or runaway workloads can consume resources,
degrade neighboring services, and enlarge the attack surface for abuse. When
containment is too strict, benign workloads suffer from the same controls
intended to stop attacks, leading to broken execution paths, unnecessary
throttling, and reduced usefulness. This trade-off becomes sharper in emerging
AI-agent runtimes, where systems may compile code, install dependencies,
execute multi-step actions, and react to changing tasks in real time [R7]-
[R10]. In such settings, fixed containment policies are often too rigid: open
configurations underreact, while strict ones overreact.

This paper argues that adaptive containment is a more suitable model for such
workloads than fixed sandbox allocation. Instead of assigning a single
containment level up front and holding it constant, an adaptive controller can
observe runtime behavior, estimate risk from bounded signals, and shift
workloads between enforcement tiers as their behavior changes. The central
question is therefore not whether a workload should always run in an open or a
strict sandbox, but whether containment can be adjusted continuously and
audibly in response to what the workload is actually doing.

To study this question, we present RAASA (Risk-Aware Adaptive Sandbox
Allocation), a research system for adaptive containment of containerized
workloads. RAASA is structured as an explicit Observe-Assess-Decide-Act-Audit
loop. It collects runtime telemetry, converts raw observations into bounded
feature signals, computes risk-oriented assessments, selects containment tiers,
and records the reasons behind those decisions. The design is modular so that
telemetry, policy reasoning, enforcement, and auditing remain separable rather
than collapsing into a monolithic control path.

An additional design concern addressed by RAASA is the relationship between
autonomous reasoning and privileged enforcement. A system that monitors
workloads and decides when to contain them may still create a security
anti-pattern if the same reasoning component is granted unrestricted host-level
control. For that reason, RAASA adopts a privilege-separated architecture in
which controller logic remains unprivileged while enforcement actions are
isolated behind a constrained inter-process communication boundary. In the
cloud-native path, this separation is realized through a privileged enforcer
sidecar that performs containment actions on behalf of the controller.

RAASA is intentionally positioned as a validated research prototype rather than
as a finished production platform. The goal is not to claim complete defense
against container escape, lateral movement, or all classes of cloud abuse.
Instead, the goal is to show that an adaptive containment loop can be built
honestly, instrumented clearly, and validated across both local and
cloud-native execution paths. The strongest current evidence supports the claim
that RAASA can observe runtime behavior, produce auditable tiered decisions,
and enforce pod-specific containment in live Kubernetes environments, with
support from both fresh-account single-node replay and bounded 3-node K3s
validation on AWS. At the same time, the live cloud-native path reveals the
clearest remaining weakness: telemetry and control-plane fragility, especially
around `metrics.k8s.io` timeout behavior under stress.

The contributions of this paper are fivefold:

1. It introduces RAASA, a modular adaptive containment architecture for
   containerized workloads that replaces fixed sandbox decisions with tiered,
   risk-aware runtime control.
2. It presents a bounded decision pipeline that converts runtime telemetry into
   auditable tier transitions and enforcement actions.
3. It demonstrates a privilege-separated enforcement model that decouples
   unprivileged reasoning from privileged control through a constrained IPC
   boundary.
4. It extends the architecture into a live AWS-hosted Kubernetes path with
   pod-specific containment behavior across both fresh-account single-node
   replay and bounded 3-node K3s validation.
5. It provides a reproducible research artifact and an honest evaluation
   boundary that identifies telemetry/control-plane fragility and lack of
   managed-cluster evidence as the main remaining blockers to a stronger v2
   candidate.

The rest of the paper is organized as follows. Section 2 defines the problem
statement and threat model. Section 3 presents the system design. Section 4
describes the implementation. Section 5 evaluates the local and cloud-native
paths. Section 6 discusses the results and limitations. Section 7 situates the
work relative to prior systems. Section 8 outlines future work, and Section 9
concludes.

## 2. Problem Statement and Threat Model

The problem addressed by RAASA is the mismatch between static containment and
dynamic runtime behavior. In conventional container execution, containment is
often assigned once and then left unchanged. This creates a binary design
space. If the sandbox is permissive, workloads retain agility, but malicious or
runaway behavior may continue without meaningful interruption. If the sandbox
is strict, the environment becomes safer at the cost of benign utility. The
core hypothesis of this paper is that this binary framing is unnecessarily
rigid.

RAASA studies a bounded alternative: adaptive containment. Under this model, a
controller observes runtime behavior continuously, maps observations into
interpretable risk signals, and adjusts containment only when the behavior of a
workload justifies doing so. The system therefore treats containment as a
runtime control problem rather than a one-time configuration decision.

The threat model is deliberately limited to workload classes that can be
measured and discussed honestly in the current research artifact. In the local
path, these include benign steady-state, benign bursty, suspicious, and
malicious-pattern workloads. In the cloud-native path, they expand into a
bounded adversarial matrix that includes benign control, syscall storm,
process fanout, network burst, and agent dependency/exfiltration behaviors. The
goal is not to prove comprehensive protection against every possible cloud
attack, but to make the adaptive-versus-static trade-off observable and
measurable across a truthful set of bounded workload families.

The paper also maintains clear non-claims. RAASA does not claim complete
defense against container escape, full prevention of exfiltration or lateral
movement, enterprise-grade production readiness, or EKS robustness. The
current live validation includes fresh-account single-node replay and bounded
3-node K3s evidence, but not multi-tenant or managed-control-plane validation.
These boundaries are essential to the credibility of the work.

For artifact review and rebuttal hygiene, the explicit scope boundary is also
tracked in the standalone non-claims table:
[docs/tables/generated/scope_nonclaims.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/scope_nonclaims.md).

## 3. System Design

RAASA is designed as an Observe-Assess-Decide-Act-Audit loop. The Observe phase
collects runtime telemetry relevant to workload behavior. The Assess phase
converts observations into bounded features and risk-oriented assessments. The
Decide phase maps those assessments into containment tiers. The Act phase
translates tier decisions into enforcement behavior. The Audit phase records
both observations and the reasons behind the chosen actions.

**Fig. 1.** RAASA Observe-Assess-Decide-Act-Audit control loop, showing
telemetry collection, bounded risk assessment, tiered policy reasoning,
privilege-separated enforcement, and audit logging.

*Paper asset source:* [docs/figures/raasa_control_loop.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_control_loop.dot)

This structure serves both technical and research purposes. Technically, it
keeps telemetry, reasoning, enforcement, and logging separate so each can be
tuned or replaced without collapsing the whole system. As a research artifact,
it makes the decision path easier to explain and evaluate because each stage of
the control loop remains explicit.

The tier model centers on three containment states: `L1`, `L2`, and `L3`. `L1`
represents minimal restriction, `L2` represents degraded or precautionary
containment, and `L3` represents the strongest containment state available in
the evaluated path. In the refined live Kubernetes evidence, `L3` should be
understood as hard containment rather than as simple bandwidth shaping.

Privilege separation is a core part of the design. The controller logic that
observes, assesses, and decides does not directly hold unrestricted host-level
power. Instead, privileged actions are isolated behind a constrained
communication boundary and executed by a dedicated enforcement component. This
is especially important for cloud-native and agentic settings, where coupling
autonomous reasoning directly to broad host privileges would create a dangerous
security anti-pattern.

## 4. Implementation

RAASA currently includes two main backend paths: a local Docker-based path and
a Kubernetes-native path.

In the local path, the controller operates over Docker-backed workloads and
supports direct comparison between adaptive behavior and static baselines. This
path is the simplest environment for demonstrating the central adaptive
containment trade-off.

In the cloud-native path, the architecture is extended into AWS-hosted K3s
environments. Here, the observer and enforcement logic operate within a more
realistic orchestration context where pod identity, namespace context,
node-local agent selection, and pod-specific enforcement resolution become
central concerns. The implementation uses a privilege-separated sidecar model
so that containment actions are performed through a dedicated enforcement
component rather than through a fully privileged controller.

The controller stack itself is intentionally framed around one truthful default
story. The tuned linear controller is the primary controller for the paper. The
Isolation Forest path is implemented and explored as a secondary extension. The
LLM advisor exists as an optional bounded edge-case resolver and should not be
treated as the main reasoning engine in the current paper.

**Fig. 2.** AWS-hosted K3s deployment view of RAASA, showing the unprivileged
controller, privileged enforcer sidecar, probe path, and pod-specific
host-veth enforcement boundary.

*Paper asset source:* [docs/figures/raasa_multinode_k3s.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_multinode_k3s.dot)

## 5. Evaluation

This section evaluates whether adaptive containment provides a more balanced
security-utility trade-off than fixed sandbox allocation, and whether the same
architectural approach can carry over from a local container environment into a
live Kubernetes deployment. The evaluation is intentionally bounded. The goal
is not to claim universal cloud-runtime protection, but to test whether RAASA
can 1) outperform static baselines locally, 2) preserve benign utility while
still containing malicious behavior, and 3) demonstrate pod-specific
containment behavior and bounded multi-node continuity in a live AWS-hosted
K3s path.

### 5.1 Evaluation Questions

The evaluation is organized around four questions:

1. Can adaptive containment outperform static baselines in a controlled local
   environment?
2. Can RAASA preserve benign workload utility while still containing malicious
   behavior?
3. Can the architecture carry over from local Docker-based execution into a
   live Kubernetes environment?
4. What currently limits the cloud-native path, even when the core containment
   idea appears to work?

### 5.2 Experimental Framing

The local evaluation compares three control modes over identical workload
profiles:

- `static_L1`, representing a permissive baseline with no meaningful
  containment response
- `static_L3`, representing an over-restrictive baseline that applies strict
  containment unconditionally
- `raasa`, representing the adaptive controller

The primary local scenario used for the paper is `small_tuned`, which captures
the core adaptive-versus-static trade-off without introducing unnecessary scale
complexity into the main story. The cloud evaluation proceeds in two bounded
phases. First, the architecture is replayed on a fresh AWS Free-plan account
as a single-node K3s bootstrap and short soak. Second, it is exercised on a
3-node K3s cluster where the local Docker telemetry path is replaced by a
Kubernetes-oriented observer path and enforcement is routed through a
privilege-separated sidecar.

The evaluated envelope is therefore explicit and narrow: local Docker for the
adaptive-versus-static comparison, fresh-account single-node K3s for replay
and short soak, and bounded 3-node K3s for soak, repeated adversarial matrix,
failure/stress behavior, and worker drain/reschedule continuity. It does not
include EKS, multi-tenant isolation, long-duration soak, or high-availability
claims.

### 5.3 Local Results

The `static_L1` baseline represents under-reaction. In the primary local
baseline capture, this mode reports `0.00 / 0.00` precision and recall with a
`0.0%` malicious containment rate. It establishes the lower bound of the
design space: maximum short-term utility, but no credible runtime response to
harmful behavior.

The `static_L3` baseline represents over-reaction. In the same comparison, it
achieves full recall against malicious behavior, but with precision `0.33`,
false positive rate `1.00`, benign restriction rate `1.00`, and `24`
unnecessary escalations. It therefore secures the environment by treating
every workload as hostile.

The adaptive `raasa` mode is the primary local result. The strongest paper
presentation is to report both the best captured run and the repeated
small-scenario mean. In the best captured `small_tuned` run, the tuned linear
controller achieves `1.00 / 1.00` precision and recall with zero false
positives, zero benign restriction, and zero unnecessary escalations. Across
three `small_tuned` linear runs, the mean result is precision `0.87`, recall
`1.00`, false positive rate `0.11`, benign restriction rate `0.11`, and mean
unnecessary escalations `1.3`. These results still support the central thesis
of the paper: adaptive containment can outperform both static permissiveness
and static strictness by selectively escalating only the workloads whose
behavior justifies tighter control.

Table I summarizes the primary local comparison.

*Canonical table source:* [docs/tables/generated/local_baseline_comparison.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/local_baseline_comparison.md)<br>
*Companion plot:* [docs/figures/generated/local_baseline_tradeoff.svg](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/local_baseline_tradeoff.svg)<br>
*Editable plot source:* [docs/figures/plot_local_baseline_tradeoff.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/plot_local_baseline_tradeoff.py)

| Mode | Scenario | Precision | Recall | FPR | BRR | UE |
|------|----------|-----------|--------|-----|-----|----|
| `static_L1` | small baseline | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| `static_L3` | small baseline | 0.33 | 1.00 | 1.00 | 1.00 | 24 |
| `raasa` linear | `small_tuned` best run | 1.00 | 1.00 | 0.00 | 0.00 | 0 |
| `raasa` linear | `small_tuned` 3-run mean | 0.87 | 1.00 | 0.11 | 0.11 | 1.3 |

### 5.4 Cloud-Native Results

To evaluate whether the architecture remains meaningful outside the local
Docker-based path, RAASA is extended into AWS-hosted K3s environments. The
strongest paper-safe cloud claim is not that the entire Kubernetes path is
production-ready. Rather, it is that RAASA can perform pod-specific
containment in live Kubernetes environments while maintaining a
privilege-separated controller/enforcer architecture, and that this claim is
reproducible on a fresh account and remains coherent in a bounded 3-node K3s
setting.

The AWS results show that the cloud-native path progressed from early
enforcement ambiguity toward pod-specific host-veth resolution and validated
containment against benchmark workloads. One of the most important findings is
that `L3` in the refined live path should be described as hard containment
rather than as simple throughput reduction. Under refined validation, service
resolution fails and direct reachability is disrupted, making containment the
more accurate description of the observed semantics.

The canonical authoring version of the cloud-evidence ladder is maintained in
[docs/tables/generated/cloud_evidence_ladder.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/cloud_evidence_ladder.md),
with the chronological companion figure sourced from
[docs/figures/raasa_validation_progression.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_validation_progression.dot).

The strongest cloud story in the repository now has two layers. The first is a
fresh-account single-node replay that reproduced bootstrap and soak behavior on
an AWS Free-plan account, showing that the system can be re-established from a
clean account state rather than only on a long-lived host. The second is a
bounded 3-node K3s campaign that passed a `3 / 3` closed-loop soak, a `2 / 2`
repeated five-workload adversarial matrix, a failure-injection sequence with
clean fake-pod `ERR` handling, a `30 s / 6` worker Metrics API stress probe
with `62` complete audit rows and `0` worker failures, and a worker
drain/reschedule continuity test. Earlier single-node soak evidence remains
useful as a historical repeatability point, but the bounded 3-node results are
the strongest current support for distributed K3s claims. The AWS artifacts
also show that the tuned linear controller remained the most truthful primary
controller once the live evidence was reconciled against the ML path.

Table II summarizes the main AWS/K3s milestones that support the current
paper-safe cloud claim.

*Canonical table source:* [docs/tables/generated/cloud_evidence_ladder.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/cloud_evidence_ladder.md)<br>
*Companion progression figure source:* [docs/figures/raasa_validation_progression.dot](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/raasa_validation_progression.dot)

| Date | Milestone | Evidence | Paper Interpretation |
|------|-----------|----------|----------------------|
| 2026-04-26 | Phase 1D universal resolution validation | `raasa-net-server`, `raasa-net-client`, and `raasa-bench-client` resolved cleanly to host-side veth interfaces; benchmark `L1` stayed near `0.014 s`, while `L3` stretched to about `123.05 s` with `0 B/s` | Pod-specific containment works in live K3s rather than only in local Docker |
| 2026-04-26 | Phase 1F refined semantics | Under `L3`, DNS lookups fail, `ClusterIP` traffic fails, and direct pod-IP traffic also fails with `0 B/s` | `L3` should be described as hard containment, not just bandwidth shaping |
| 2026-05-14 | Fresh-account single-node replay | Fresh AWS Free-plan account, `m7i-flex.large` bootstrap, live sanity capture, and stable `2 / 2` replay soak on a clean-account K3s host | The cloud path is reproducible from a clean account state, not only on a previously prepared host |
| 2026-05-14 | Bounded 3-node K3s soak and repeated adversarial matrix | `3 / 3` closed-loop soak passed and `2 / 2` repeated five-workload matrix runs passed with benign total L3 count `0` | The current cloud path remains coherent beyond single-node replay in a bounded multi-node K3s setting |
| 2026-05-14 | Failure handling, stress, and reschedule continuity | Failure injection recorded explicit degraded telemetry and fake-pod `ERR`; Metrics API stress preserved `62` complete rows with `0` worker failures; worker drain rescheduled the benign pod while preserving post-drain audit continuity on the surviving worker | The architecture tolerates bounded degraded-mode events and worker drain/reschedule in the current 3-node K3s envelope |
| 2026-05-09 and 2026-05-14 | Diagnostic control-plane failures and corrections | repeated `metrics.k8s.io` errors, timeout-driven telemetry gaps, and node-local agent-resolution assumptions required explicit handling in the harness | The main blocker is telemetry/control-plane fragility and cloud-path operational complexity, not the basic containment idea |

### 5.5 Main Limitation Exposed by Evaluation

The most important limitation revealed by the evaluation is not that adaptive
containment fails conceptually. It is that the cloud-native telemetry and
control-plane path remains operationally fragile under stress. In the AWS
artifacts, repeated `metrics.k8s.io` timeout behavior appears as the dominant
technical blocker, and the bounded 3-node campaign further showed that
node-local agent resolution and workload placement assumptions must be handled
explicitly for multi-node evidence to remain trustworthy. This issue matters
because even a correct containment policy loses practical strength if the
telemetry path or node-local control assumptions used to support it become
unstable in live execution.

The degraded-mode evidence behind this conclusion is summarized in
[docs/tables/generated/failure_degraded_mode_summary.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated/failure_degraded_mode_summary.md)
and the companion plot
[docs/figures/generated/cloud_degraded_mode_summary.svg](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/generated/cloud_degraded_mode_summary.svg),
with the editable plotting source in
[docs/figures/plot_degraded_mode_summary.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/plot_degraded_mode_summary.py).

Table III gives the compact degraded-mode summary used for paper-facing
interpretation.

| Injected condition | Observed status | Paper interpretation |
|--------------------|-----------------|----------------------|
| Metrics API outage | `10` audit rows, `9` partial telemetry rows, `metrics_error:9`, new tiers `L3:10` | The controller exposes degraded telemetry instead of silently masking the outage |
| Syscall probe pause | `11` audit rows, `7` partial telemetry rows, `probe_stale:7`, new tiers `L3:11` | Probe degradation is surfaced explicitly rather than hidden behind a false clean reading |
| Fake-pod IPC fail-closed check | IPC response `ERR` | The privileged path rejects an invalid target and fails closed |
| Agent restart recovery | agent pod changed after restart and recovery was observed | The bounded experiment shows post-restart continuity, not high availability |
| Metrics API bounded stress | `30 s`, `6` workers, `62` complete audit rows, `0` worker failures | Bounded stress remained interpretable without collapsing the cloud path |

### 5.6 Evaluation Summary

Taken together, the evaluation supports four main conclusions. First, adaptive
containment is superior to both static permissive and static strict baselines
under the bounded workload model used in the paper. Second, RAASA can preserve
benign utility while still containing malicious behavior in the local path.
Third, the architecture can carry over into live AWS-hosted K3s paths with
fresh-account reproducibility, pod-specific containment behavior, and bounded
multi-node continuity evidence. Fourth, the strongest remaining limitation lies
in the telemetry/control-plane path rather than in the core adaptive-
containment idea itself.

## 6. Discussion and Limitations

The evaluation suggests that RAASA is best understood as a validated research
prototype for adaptive containment rather than as a finished cloud-security
product. The strongest contribution of the project is not that it solves
runtime security in full, but that it demonstrates a more balanced model of
containment than static sandbox allocation.

Adaptive containment appears to occupy a useful middle ground between
permissive and over-restrictive execution models. The local results show that
the trade-off between security and utility is not necessarily fixed. The system
can preserve benign execution while still escalating the workloads that warrant
tighter control. The architecture itself is also part of the contribution:
RAASA is not merely a detector attached to a logger, nor simply a privileged
throttling wrapper. Its Observe-Assess-Decide-Act-Audit structure makes the
artifact easier to reason about and supports safer system design through
privilege separation.

The AWS-hosted Kubernetes result matters because it validates that the core
idea survives outside a local harness. However, the cloud-native validation is
still bounded: it now includes fresh-account single-node replay and a 3-node
K3s deployment, but not multi-tenant or managed-control-plane evidence. The
workload model is also intentionally bounded, and the strongest validated
controller story remains the tuned linear controller, not the ML path. The LLM
advisor is similarly optional and secondary.

The clearest limitation of the current system is the live Kubernetes telemetry
and control-plane path. The strongest evidence in the repository indicates that
the main blocker is not the basic containment idea, but instability around the
telemetry/control-plane interface, especially repeated `metrics.k8s.io`
timeouts under stress. This limitation should be presented directly rather than
softened, because it improves the credibility of the paper.

Within these boundaries, the results remain meaningful. The local experiments
support the adaptive-containment thesis directly. The cloud-native path shows
that the architecture can move beyond local runtime control into live
pod-specific containment behavior, fresh-account reproducibility, and bounded
multi-node continuity. The limitations then explain what still separates the
current system from a stronger v2 candidate.

## 7. Related Work

RAASA sits at the intersection of container sandboxing, runtime anomaly
detection, Kubernetes-native security enforcement, and the emerging problem of
AI-agent runtime safety. The project is not a direct replacement for any one of
these lines of work. Instead, it combines ideas from each into a bounded,
adaptive containment controller whose contribution lies in the integration of
observation, decision-making, enforcement, and auditability.

Recent secure-runtime studies comparing RunC, gVisor, and Kata Containers [R1]
show the value of strengthening isolation by increasing the barrier between the
workload and the host. These systems are highly relevant, but they solve a
different primary problem. Their main goal is stronger isolation by
construction. RAASA, by contrast, studies how containment should adapt over
time as runtime behavior changes. The paper therefore positions RAASA as
complementary to stronger sandbox backends rather than as a direct competitor.

Static runtime hardening through mechanisms such as seccomp, AppArmor, SELinux,
cgroup limits, and Kubernetes policy controls is also foundational. Confine
[R2] shows how container attack surface can be reduced through fine-grained
system call filtering, while recent Kubernetes security-hardening studies [R3]
illustrate the continued importance of explicit cluster-level controls. RAASA
differs from these approaches because it is runtime-adaptive rather than
purely admission- or configuration-driven.

Another major line of related work focuses on runtime instrumentation,
observability, and enforcement. Recent eBPF-based enforcement work for
Kubernetes [R4] and analyses of eBPF security tooling in cloud-native
environments [R5] show that modern cloud security increasingly depends on
fine-grained live telemetry. RAASA is closely related to this work, but its
contribution is not simply runtime detection. It uses runtime signals as
inputs to a broader control loop that produces tiered containment decisions
and drives enforcement actions.

Machine learning has also been explored for anomaly detection in cloud
workloads, including recent container-attack detection work that combines
eBPF-derived telemetry with supervised learning [R6]. That literature is
relevant because RAASA includes an Isolation Forest path. However, the project
should not be framed primarily as an ML anomaly-detection paper. In the
current evidence, the tuned linear controller remains the strongest and most
truthful primary path.

Finally, emerging work on LLM and agent-runtime security is increasingly
important. Recent benchmark and runtime-protection studies such as AgentDojo
[R7], Agent Security Bench [R8], information-flow-control-based agent
hardening [R9], and SafeAgent [R10] make clear that excessive agency, unsafe
tool use, and insecure action execution are serious concerns. RAASA differs
from most application-layer AI safety work by focusing on the runtime
environment rather than the prompt or model interface alone.

Taken together, the related work suggests that RAASA should be positioned as a
synthesis rather than as a direct replacement for any single prior system. The
novelty is not that RAASA invents sandboxing, telemetry, or anomaly scoring in
isolation. The novelty is that it integrates these pieces into an explicit
control loop whose purpose is adaptive containment rather than static isolation
or passive observation alone.

## 8. Future Work

The clearest next step is to harden the Kubernetes telemetry and control-plane
path, since this is the strongest current blocker between the validated
prototype and a stronger v2 candidate. Beyond that, the most credible future
direction is not unrestricted scope expansion but careful extension of the
current architecture and evidence base.

Five near-term directions are especially well aligned with the current paper.
First, the live telemetry path should be made more resilient under stress and
its degraded-mode behavior should be measured more explicitly. Second, the
cloud-native evaluation should move from bounded 3-node K3s into a tightly
scoped EKS smoke path and only then toward broader managed-cluster evidence.
Third, enforcement semantics and observability should be made easier to
interpret at paper level through clearer degraded-mode metrics and preserved
before/after cloud inventory artifacts. Fourth, the project should benchmark
AI-agent-specific threat scenarios such as destructive command execution, CI/CD
exfiltration, suspicious dependency-install behavior, and runaway automation.
Fifth, the ML path should be revisited only after the primary controller and
telemetry path are more stable, so that future ablation claims rest on a
stronger systems foundation.

## 9. Conclusion

This paper presented RAASA, a research system for adaptive containment of
containerized workloads. The starting point was a practical systems problem:
static containment models force an undesirable trade-off between security and
utility. RAASA was introduced as an alternative that treats containment as an
adaptive runtime control problem grounded in telemetry, bounded risk scoring,
tiered enforcement, and auditable decisions.

The evaluation supports the paper's central thesis within a bounded but
meaningful scope. In the local path, RAASA demonstrates that adaptive
containment can outperform both permissive and over-restrictive static
baselines by preserving benign utility while still escalating malicious
behavior into stricter containment tiers. In the cloud-native path, the project
shows that the same architectural ideas can carry over into AWS-hosted K3s
environments through fresh-account single-node replay and bounded 3-node
validation with pod-specific containment behavior and a privilege-separated
enforcement model. These results support RAASA as a validated research
prototype rather than as a finished production-ready security platform.

At the same time, the paper has deliberately maintained a narrow and truthful
claim boundary. RAASA does not claim to solve container runtime security in
full, and it does not yet provide EKS, multi-tenant, or enterprise-grade
evidence. The live Kubernetes path reveals that telemetry and control-plane
fragility remain the main blockers between the current system and a stronger v2
candidate.

Within those boundaries, RAASA still offers an important result. It shows that
adaptive containment can be implemented as a modular, auditable, and
privilege-separated control loop that is more practically balanced than static
sandbox allocation for modern containerized workloads. The broader conclusion
of the paper is therefore modest but strong: adaptive containment is not yet a
complete answer to runtime security, but it is already a defensible and
practically meaningful direction, and one that now carries bounded
fresh-account and multi-node Kubernetes evidence rather than only a
single-node proof-of-concept.

## Provisional IEEE Reference List (2021-2026 Research Papers Only)

[R1] X. Wang, J. Du, and H. Liu, "Performance and isolation analysis of RunC,
gVisor and Kata Containers runtimes," *Cluster Computing*, vol. 25, no. 2,
pp. 1497-1513, 2022, doi: 10.1007/s10586-021-03517-8.

[R2] M. Rostamipoor, S. Ghavamnia, and M. Polychronakis, "Confine:
Fine-grained system call filtering for container attack surface reduction,"
*Computers & Security*, vol. 132, Art. no. 103325, 2023,
doi: 10.1016/j.cose.2023.103325.

[R3] A. Ali, M. Imran, V. Kuznetsov, S. Trigazis, A. Pervaiz, A. Pfeiffer,
and M. Mascheroni, "Implementation of New Security Features in CMSWEB
Kubernetes Cluster at CERN," *EPJ Web of Conferences*, vol. 295, Art. no.
07026, 2024, doi: 10.1051/epjconf/202429507026.

[R4] S. Gwak, T.-P. Doan, and S. Jung, "Container Instrumentation and
Enforcement System for Runtime Security of Kubernetes Platform with eBPF,"
*Intelligent Automation & Soft Computing*, vol. 37, no. 2, pp. 1773-1786,
2023, doi: 10.32604/iasc.2023.039565.

[R5] J. Her, J. Kim, J. Kim, and S. Lee, "An In-Depth Analysis of eBPF-Based
System Security Tools in Cloud-Native Environments," *IEEE Access*, vol. 13,
pp. 155588-155604, 2025, doi: 10.1109/ACCESS.2025.3605432.

[R6] H. Shin, M. Jo, H. Yoo, Y. Lee, and B. Tak, "A Technique for Accurate
Detection of Container Attacks with eBPF and AdaBoost," *Journal of The Korea
Society of Computer and Information*, vol. 29, no. 6, pp. 39-51, 2024,
doi: 10.9708/jksci.2024.29.06.039.

[R7] E. Debenedetti, J. Zhang, M. Balunovic, L. Beurer-Kellner, M. Fischer,
and F. Tramer, "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection
Attacks and Defenses for LLM Agents," in *Advances in Neural Information
Processing Systems 37: Datasets and Benchmarks Track*, 2024,
doi: 10.52202/079017-2636.

[R8] H. Zhang, J. Huang, K. Mei, Y. Yao, Z. Wang, C. Zhan, H. Wang, and
Y. Zhang, "Agent Security Bench (ASB): Formalizing and Benchmarking Attacks
and Defenses in LLM-based Agents," in *International Conference on Learning
Representations (ICLR)*, 2025.

[R9] M. Costa, B. Kopf, A. Kolluri, A. Paverd, M. Russinovich, A. Salem,
S. Tople, L. Wutschitz, and S. Zanella-Beguelin, "Securing AI Agents with
Information-Flow Control," *arXiv preprint* arXiv:2505.23643, 2025.

[R10] H. Liu, E. Ilyushin, J. Ni, and M. Zhu, "SafeAgent: A Runtime Protection
Architecture for Agentic Systems," *arXiv preprint* arXiv:2604.17562, 2026.

## Notes for Next Revision

The next editing pass on this IEEE-oriented draft should focus on:

1. wiring the citation commands to [paper_references_2021_2026.bib](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_references_2021_2026.bib) and confirming the final venue versions
2. turning `Fig. 1` and `Fig. 2` into rendered architecture diagrams that
   match the current caption text
3. converting the Markdown tables into IEEE-style table environments
4. reducing any remaining repetition and shaping paragraph lengths to the final
   IEEE page budget
