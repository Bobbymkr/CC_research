# RAASA Paper Introduction

## 1. Draft Introduction

Modern cloud workloads increasingly execute inside containerized runtime
environments where security and utility are often placed in direct tension.
When containment is too permissive, malicious or runaway workloads can consume
resources, degrade neighboring services, and create a wider attack surface for
abuse. When containment is too strict, benign workloads suffer from the same
controls intended to stop attacks, leading to broken execution paths,
unnecessary throttling, and reduced system usefulness. This trade-off becomes
even sharper in emerging AI-agent runtimes, where systems are expected to
compile code, install dependencies, execute multi-step actions, and react to
dynamic tasks in real time. In these environments, static sandboxing policies
are often too rigid: open configurations underreact, while strict ones
overreact.

This paper argues that adaptive containment is a more suitable model for such
workloads than fixed sandbox allocation. Instead of assigning a single
containment level in advance and holding it constant throughout execution, an
adaptive controller can observe runtime behavior, estimate risk from bounded
signals, and shift workloads between enforcement tiers as their behavior
changes. The central question is therefore not whether a workload should always
run in an unrestricted or highly constrained sandbox, but whether containment
can be adjusted continuously and audibly in response to what the workload is
actually doing.

To investigate this question, we present RAASA (Risk-Aware Adaptive Sandbox
Allocation), a research system for adaptive containment of containerized
workloads. RAASA is structured as an explicit Observe-Assess-Decide-Act-Audit
loop. It collects runtime telemetry, converts raw observations into bounded
feature signals, computes risk-oriented assessments, selects containment tiers,
and records the reasons behind those decisions. The design is modular so that
telemetry, policy reasoning, enforcement, and auditing remain separable
components rather than a monolithic control path. This separation is important
not only for implementation clarity, but also for experimental truthfulness and
system safety: each stage can be evaluated, tuned, and bounded independently.

An additional design concern addressed by RAASA is the relationship between
autonomous reasoning and privileged enforcement. A system that monitors
workloads and decides when to contain them may still create a security
anti-pattern if the same reasoning component is given unrestricted host-level
control. For that reason, RAASA adopts a privilege-separated architecture in
which the controller logic remains unprivileged while enforcement actions are
isolated behind a constrained inter-process communication boundary. In the
cloud-native path, this separation is realized through a privileged enforcer
sidecar that performs containment actions on behalf of the controller. This
design allows the project to study adaptive enforcement without collapsing the
research question into an unsafe all-powerful agent model.

RAASA is intentionally positioned as a validated research prototype rather than
as a finished production platform. The goal of the project is not to claim
complete defense against container escape, lateral movement, or all classes of
cloud abuse. Instead, the goal is to show that an adaptive containment loop can
be built honestly, instrumented clearly, and validated across both local and
cloud-native execution paths. The project therefore focuses on a bounded threat
model and a bounded set of workload classes, using these to study the trade-off
between under-reaction and over-reaction in containment decisions.

The evaluation follows this bounded philosophy. RAASA is first exercised in a
local Docker-backed setting where adaptive behavior can be compared directly
against static baselines. It is then extended into a live AWS-hosted K3s
environment in order to test whether the same architectural ideas can carry
over into a Kubernetes setting with pod-specific containment behavior and a
privilege-separated enforcement path. The strongest current evidence supports
the claim that RAASA can observe runtime behavior, produce auditable tiered
decisions, and enforce pod-specific containment in a live Kubernetes
environment. At the same time, the live cloud-native path also reveals the
project's clearest remaining weakness: telemetry and control-plane fragility,
especially around `metrics.k8s.io` timeout behavior under stress.

This combination of positive result and explicit limitation is central to the
paper's position. The contribution of RAASA is not that it solves container
runtime security in full, nor that it provides a universally superior
AI-enabled security layer. Its contribution is that it makes a narrower and
more defensible case: adaptive containment can be implemented as an auditable
control loop, it can be validated across both local and live Kubernetes
settings, and it offers a more balanced alternative to static sandbox
allocation for modern cloud and agentic workloads.

This paper makes five main contributions. First, it introduces RAASA, a modular
adaptive containment architecture for containerized workloads that replaces
fixed sandbox decisions with tiered, risk-aware runtime control. Second, it
presents a bounded decision pipeline that converts runtime telemetry into
auditable tier transitions and enforcement actions. Third, it demonstrates a
privilege-separated enforcement model that decouples unprivileged reasoning
from privileged control through a constrained inter-process communication
boundary. Fourth, it extends the architecture into a live AWS-hosted Kubernetes
path with pod-specific containment behavior. Fifth, it provides a reproducible
research artifact and an honest evaluation boundary that identifies
telemetry/control-plane fragility as the main remaining blocker to a stronger
v2 candidate.

The rest of the paper is organized as follows. Section 2 defines the problem
statement and threat model. Section 3 presents the system design. Section 4
describes the implementation across local and Kubernetes-backed execution
paths. Section 5 evaluates the system against static baselines and live
cloud-native validation scenarios. Section 6 discusses the results and their
limitations. Section 7 situates the work relative to existing research, and
Section 8 outlines future work before concluding.

## 2. Notes for Revision

When this introduction is moved into the final paper:

- keep the tone concrete and technical rather than promotional
- retain the limitation paragraph; it increases credibility
- align section numbering with the final paper structure
- shorten the introduction slightly if the venue has a tight page limit
