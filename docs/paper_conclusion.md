# RAASA Paper Conclusion

## 1. Draft Conclusion

This paper presented RAASA, a research system for adaptive containment of
containerized workloads. The work began from a practical systems problem:
static containment models force an undesirable trade-off between security and
utility. Permissive sandboxes underreact to malicious or runaway behavior,
while uniformly strict sandboxes overconstrain benign execution and make
legitimate workloads absorb the same penalties as obviously harmful ones. In
modern cloud and agentic runtime environments, where execution behavior is
often dynamic and difficult to characterize in advance, this binary model is
increasingly inadequate.

RAASA was introduced as an alternative to that static model. Rather than
holding every workload at a fixed restriction level, it treats containment as
an adaptive runtime control problem. The architecture collects telemetry,
converts runtime behavior into bounded risk signals, selects among tiered
containment states, and records auditable reasons for each decision. Equally
important, it preserves privilege separation by decoupling unprivileged
reasoning logic from privileged enforcement actions through a constrained IPC
boundary. This design makes the system not only easier to reason about as a
research artifact, but also more defensible as a model for safe autonomous
containment.

The evaluation supports the paper's central thesis within a bounded but
meaningful scope. In the local path, RAASA demonstrates that adaptive
containment can outperform both permissive and over-restrictive static
baselines by preserving benign utility while still escalating malicious
behavior into stricter containment tiers. In the cloud-native path, the project
shows that the same architectural ideas can carry over into a live
AWS-hosted Kubernetes environment with pod-specific containment behavior and a
privilege-separated enforcement model. These results support RAASA as a
validated research prototype rather than as a finished production-ready
security platform.

At the same time, the paper has deliberately maintained a narrow and truthful
claim boundary. RAASA does not claim to solve container runtime security in
full. It does not establish complete defense against container escape, lateral
movement, or all forms of cloud abuse. It does not yet provide multi-node or
enterprise-grade evidence. Most importantly, the live Kubernetes path reveals
that telemetry and control-plane fragility, especially around `metrics.k8s.io`
timeout behavior under stress, remain the main blockers between the current
system and a stronger v2 candidate. Stating this explicitly is not a weakness
of the paper; it is part of what makes the contribution credible.

Within those boundaries, RAASA still offers an important result. It shows that
adaptive containment can be implemented as a modular, auditable, and
privilege-separated control loop that is more practically balanced than static
sandbox allocation for modern containerized workloads. It also establishes a
useful research direction for future work on cloud-native runtime security and
AI-agent execution safety, where dynamic workload behavior makes fixed
containment increasingly insufficient.

The broader conclusion of the paper is therefore modest but strong: adaptive
containment is not yet a complete answer to runtime security, but it is already
a defensible and practically meaningful direction. RAASA demonstrates that this
direction can be built, evaluated honestly, and extended from local experiments
into live Kubernetes validation. That result is sufficient to justify both the
research contribution of the current system and the continued development of a
more operationally robust v2.

## 2. Shorter Conclusion Variant

RAASA was developed to address a central weakness of static sandboxing:
permissive containment underreacts, while strict containment overreacts.
Instead of fixing workloads at one extreme, RAASA treats containment as an
adaptive runtime control problem built around telemetry, bounded risk scoring,
tiered enforcement, and auditable decisions. The project further strengthens
this idea through a privilege-separated architecture that decouples
unprivileged reasoning from privileged enforcement.

Across its bounded evaluation scope, the system demonstrates that adaptive
containment can preserve benign utility while still escalating malicious
behavior, and that the architecture can carry over into a live
AWS-hosted Kubernetes environment with pod-specific containment behavior. The
main remaining limitation is not the adaptive-containment concept itself, but
telemetry and control-plane fragility in the cloud-native path. For that
reason, RAASA should be understood as a validated research prototype with a
clear systems contribution and a credible path toward a stronger v2, rather
than as a finished production platform.

## 3. Notes for Revision

When this conclusion is moved into the final paper:

- keep the tone restrained and evidence-first
- preserve the limitation paragraph
- avoid adding new claims that were not developed in the evaluation
- shorten the opening if the venue requires a tighter conclusion
