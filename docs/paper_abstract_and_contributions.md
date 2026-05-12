# RAASA Abstract and Contributions

## 1. Purpose

This document provides paper-ready starting text for:

- the abstract
- the contribution list
- short summary blurbs for proposals, forms, or oral presentations

It should remain aligned with:

- [docs/paper_positioning.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_positioning.md)
- [docs/paper_outline.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_outline.md)

## 2. Primary Abstract

Modern containerized and agentic workloads are poorly served by static
containment models: permissive sandboxes underreact to malicious or runaway
behavior, while strict sandboxes overconstrain benign execution and reduce
system utility. We present RAASA (Risk-Aware Adaptive Sandbox Allocation), a
research system for adaptive containment of containerized workloads. RAASA is
structured as a modular Observe-Assess-Decide-Act-Audit loop that collects
runtime telemetry, converts it into bounded risk signals, selects among tiered
containment levels (`L1`, `L2`, `L3`), and records auditable reasons for each
decision. The architecture also separates unprivileged reasoning logic from
privileged enforcement through a constrained inter-process communication
boundary, reducing the risk of coupling autonomous decision-making directly to
host-level control.

We evaluate RAASA across both local Docker-based experiments and a live
AWS-hosted K3s deployment. The local path demonstrates the core adaptive
containment trade-off against static baselines, while the cloud-native path
shows that the controller can carry over into a Kubernetes setting with
pod-specific enforcement resolution and closed-loop containment behavior. The
current strongest evidence supports RAASA as a validated research prototype for
adaptive containment rather than a production-ready security platform. Our
results indicate that adaptive containment is a practical and defensible
direction for modern cloud and AI-agent runtime security, while also revealing
that telemetry and control-plane fragility in the live Kubernetes path remain
the main blockers to a stronger v2 candidate.

## 3. Shorter Abstract Variant

Static containment is a poor fit for modern containerized and agentic
workloads: open sandboxes underreact to abuse, while strict sandboxes damage
benign execution. We present RAASA (Risk-Aware Adaptive Sandbox Allocation), a
research system for adaptive container containment that combines runtime
telemetry, bounded risk scoring, policy reasoning, and tiered enforcement.
RAASA is built as a modular Observe-Assess-Decide-Act-Audit loop and preserves
privilege separation by decoupling unprivileged reasoning from privileged
enforcement through a constrained IPC boundary. We validate the approach on
both local Docker experiments and a live AWS-hosted K3s environment, where the
system demonstrates pod-specific containment behavior and repeatable closed-loop
operation. The current evidence supports RAASA as a validated research
prototype and shows that adaptive containment is a promising direction for
cloud and AI-agent runtime security, while telemetry/control-plane fragility in
the Kubernetes path remains the key limitation.

## 4. Main Contributions

Recommended contribution list for the paper:

1. We present RAASA, a modular adaptive containment architecture for
   containerized workloads that replaces fixed sandbox decisions with tiered,
   risk-aware runtime control.
2. We introduce a bounded runtime decision pipeline that maps telemetry into
   interpretable risk assessments, auditable tier transitions, and explicit
   enforcement outcomes.
3. We demonstrate a privilege-separated enforcement design in which
   unprivileged controller logic is decoupled from privileged containment
   actions through a constrained IPC boundary.
4. We extend the architecture from local Docker-based experiments to a live
   AWS-hosted Kubernetes environment and validate pod-specific containment
   behavior in the cloud-native path.
5. We provide a reproducible research artifact with local and AWS-backed
   evaluation material, while identifying telemetry and control-plane fragility
   as the key remaining blocker between the current prototype and a stronger v2
   candidate.

## 5. Short Contribution Bullets

Use these when the paper needs a tighter list:

1. Adaptive tiered containment for container workloads.
2. Auditable runtime risk-to-enforcement decision pipeline.
3. Privilege-separated Kubernetes enforcement architecture.
4. Local and live AWS/Kubernetes validation.

## 6. Intro Contribution Paragraph

You can use this almost directly near the end of the introduction:

This paper makes five main contributions. First, it introduces RAASA, a
modular adaptive containment architecture for containerized workloads. Second,
it presents a bounded decision pipeline that converts runtime telemetry into
auditable tier transitions and enforcement actions. Third, it demonstrates a
privilege-separated enforcement model that decouples unprivileged reasoning
from privileged control through a constrained IPC boundary. Fourth, it extends
the architecture into a live AWS-hosted Kubernetes path with pod-specific
containment behavior. Fifth, it provides a reproducible research artifact and
an honest evaluation boundary that identifies telemetry/control-plane fragility
as the main remaining blocker to a stronger v2 candidate.

## 7. Oral Summary Version

Use this for a presentation, viva, or reviewer conversation:

RAASA is a validated research prototype for adaptive containment of
containerized workloads. Instead of fixing the sandbox at one extreme, it
observes runtime behavior, scores risk, shifts workloads across containment
tiers, and keeps an auditable record of why those decisions were made. Its key
architectural idea is privilege separation: the reasoning path remains
unprivileged, while privileged enforcement is isolated behind a constrained IPC
boundary. The system is validated locally and on AWS-hosted Kubernetes, where
it demonstrates pod-specific containment, but the main limitation remains
telemetry and control-plane fragility in the live cloud-native path.

## 8. Phrases That Are Safe to Reuse

These phrases are strong and still aligned with current evidence:

- "validated research prototype"
- "adaptive containment controller"
- "privilege-separated enforcement architecture"
- "live AWS-hosted Kubernetes validation"
- "pod-specific containment behavior"
- "auditable tiered runtime control"

## 9. Phrases to Avoid

Avoid these unless new evidence is collected:

- "production-ready security platform"
- "complete runtime defense"
- "generalized zero-day prevention"
- "enterprise-grade Kubernetes security system"
- "ML outperforms the tuned baseline"
- "full protection against exfiltration or lateral movement"

## 10. Recommended Next Writing Move

After this document, the best next drafting step is the introduction, because
the abstract and contribution set now establish the paper's voice and boundary.
