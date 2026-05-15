# RAASA Paper Positioning

## 1. Purpose of This Document

This document defines the canonical paper-facing position for RAASA in its
current state. It is meant to keep the project honest, technically defensible,
and focused on the strongest validated claims already supported by the repo.

Use this file as the source of truth when writing:

- the abstract
- introduction
- contributions
- evaluation claims
- limitations
- future work

## 2. One-Sentence Positioning

RAASA is a validated research prototype for adaptive containment of
containerized workloads that combines runtime telemetry, bounded risk scoring,
policy reasoning, and enforcement to shift workloads between containment tiers,
with evidence spanning local Docker, fresh-account single-node AWS/K3s
reproducibility, and bounded 3-node K3s validation under AWS Free-plan
credits.

## 3. Primary Paper Claim

The strongest current paper-safe claim is:

RAASA demonstrates that a modular adaptive containment controller can observe
container behavior, produce auditable risk-based tier decisions, and enforce
pod-specific containment in live Kubernetes environments, while preserving a
clear separation between unprivileged reasoning logic and privileged
enforcement actions; this claim is now supported by both single-node replay
and bounded 3-node K3s evidence on AWS.

This should remain the main claim unless new live evidence materially expands
the validated scope.

## 4. Recommended Storyline

The recommended narrative for the paper is:

1. Static containment creates a real trade-off between safety and usability.
2. RAASA proposes adaptive containment instead of always-open or always-locked
   execution.
3. The system is built as an explicit Observe-Assess-Decide-Act-Audit loop.
4. The design separates the "brain" from the privileged enforcement path.
5. The idea is validated first locally, then on a clean-account single-node
   AWS/K3s replay, then on a bounded 3-node K3s cluster.
6. The truthful primary controller is the tuned linear path.
7. The ML and LLM paths are secondary extensions, not the main experimental
   foundation.

This storyline is stronger than presenting the project as a generic AI security
platform or as an ML-first anomaly detector.

## 5. Canonical Contributions

The paper should emphasize the following contributions:

1. A modular adaptive containment architecture for container workloads.
2. A bounded risk-scoring pipeline that maps runtime telemetry into tiered
   enforcement decisions.
3. A cloud-native Kubernetes path with pod-specific enforcement resolution.
4. A privilege-separated enforcement architecture using a constrained IPC path.
5. A reproducible evaluation path spanning local Docker, clean-account AWS
   single-node replay, and bounded multi-node AWS-hosted K3s validation.

These contributions are already better supported than broader claims about full
production readiness, generalized zero-day defense, or autonomous enterprise
security orchestration.

The reviewer-facing evidence map for these contributions is
[docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md).
If a claim is not listed there, it should be treated as future work or removed
from the paper.

## 6. Truthful Default Configuration

For the paper, the default story should be frozen around one truthful path:

- primary controller: tuned linear controller
- primary local backend: Docker-based experiment flow
- primary cloud backend: K3s on AWS EC2
- primary cloud evidence: Kubernetes observer + privileged enforcer sidecar on
  both single-node and bounded 3-node K3s
- primary telemetry story: bounded multi-signal runtime telemetry with a probe
  path and fallback handling

The ML path should be described as an implemented extension whose role is
secondary until a stronger ablation shows it materially improves the primary
controller story.

The LLM advisor should be described as optional edge-case assistance, not the
main reasoning engine.

## 7. Validated Scope

The following scope is currently defensible from the repo evidence:

- local validation exists through Docker-backed experiments
- cloud validation exists through AWS-hosted K3s experiments
- fresh-account single-node replay evidence exists under AWS Free-plan credits
- bounded 3-node K3s evidence exists for soak stability, repeated adversarial
  workloads, failure handling, Metrics API stress, and worker drain/reschedule
- the controller can process telemetry and assign `L1`, `L2`, and `L3`
- the live Kubernetes path has validated pod-specific containment behavior
- the project includes reproducibility guidance, result bundles, and tests

The following wording is appropriate:

- "validated research prototype"
- "cloud-native research artifact"
- "adaptive containment controller"
- "live AWS/Kubernetes validation"
- "bounded multi-node K3s validation"
- "fresh-account credits-only reproducibility"

## 8. Non-Claims and Boundaries

The paper should explicitly avoid claiming:

- full production readiness
- complete defense against container escape
- comprehensive prevention of exfiltration or lateral movement
- broad multi-tenant validation
- EKS robustness or managed-control-plane validation
- high-availability guarantees from the current 3-node results
- enterprise-grade observability robustness
- superiority of the ML path over the tuned linear controller

Avoiding these claims strengthens the credibility of the paper.

## 9. L3 Semantics

The L3 story must be precise.

Do not describe current L3 behavior merely as "bandwidth throttling."

The more accurate current description is:

L3 acts as hard containment in the validated live path, disrupting direct
network reachability and service-resolution behavior rather than only reducing
throughput.

This matters because reviewers may otherwise assume a weaker containment model
than the evidence actually supports.

## 10. Current Technical Limitation

The main engineering limitation is not the core containment idea.

The main limitation is telemetry and control-plane fragility in the live
Kubernetes path, especially instability around `metrics.k8s.io`, node-local
agent resolution assumptions, and related timeout behavior under stress.

This should be stated clearly in the paper as the main blocker between the
current prototype and a stronger v2 candidate.

## 11. Canonical Evaluation Flow

The paper should describe evaluation in this order:

1. Local Docker validation of the adaptive-vs-static control story.
2. Scenario-based containment behavior across benign and malicious workload
   classes.
3. Fresh-account single-node AWS/K3s replay showing clean-account
   reproducibility.
4. Bounded 3-node K3s validation of live pod-specific enforcement,
   repeated adversarial workloads, degraded-mode handling, and
   drain/reschedule continuity.
5. Calibration discussion showing why the tuned linear controller is currently
   the most truthful primary path.

This ordering helps the paper read as progressive validation rather than as a
collection of disconnected experiments.

## 12. How to Present ML and LLM Components

The safest framing is:

- Isolation Forest is implemented and evaluated as an extension path.
- The tuned linear controller remains the primary validated controller.
- The LLM advisor exists as an optional bounded edge-case resolver.

This keeps the paper aligned with the strongest evidence while still showing
forward-looking depth.

## 13. Recommended Future Work Boundary

Future work should stay close to the current architecture and evidence:

1. Harden the Kubernetes telemetry/control-plane path.
2. Preserve before/after cloud inventory artifacts as first-class evidence in
   every credits-constrained AWS campaign.
3. Expand validation from bounded 3-node K3s to EKS smoke and then broader
   managed-cluster experiments.
3. Add more explicit degraded-mode metrics and observability.
4. Benchmark AI-agent-specific threat scenarios such as destructive command
   execution, CI/CD exfiltration, and runaway automation.
5. Revisit the ML path only after the primary controller and telemetry path are
   stabilized.

This is a better near-term direction than adding broad new features that
increase paper scope without improving defensibility.

## 14. Suggested Abstract Shape

If you later write the abstract, it should roughly follow this shape:

1. Problem: static containment is too rigid for modern containerized and
   agentic workloads.
2. Method: RAASA introduces adaptive tiered containment using telemetry,
   risk scoring, policy reasoning, and enforcement.
3. Architecture: the system preserves privilege separation between reasoning
   and enforcement.
4. Evaluation: the approach is validated locally, replayed on a fresh AWS
   account, and exercised on a bounded 3-node K3s cluster.
5. Result: RAASA shows that adaptive containment is practical and defensible as
   a cloud-security research direction, while highlighting telemetry-path
   fragility and bounded cloud-ops complexity as the key remaining blockers.

## 15. Short Version for Oral or Reviewer Discussion

If you need a concise verbal description:

RAASA is a validated research prototype for adaptive container containment. Its
main contribution is not "AI security magic," but a truthful, modular,
cloud-aware control loop that can make auditable tier decisions and enforce
pod-specific containment in live Kubernetes settings, including a bounded
multi-node K3s deployment.
