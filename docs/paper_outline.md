# RAASA Paper Outline

## 1. Working Title Options

Choose one of these depending on the tone you want:

1. **RAASA: Risk-Aware Adaptive Sandbox Allocation for Containerized Workloads**
2. **RAASA: Adaptive Tiered Containment for Container and Agentic Runtime Security**
3. **RAASA: A Privilege-Separated Adaptive Containment Controller for Kubernetes Workloads**

Recommended default:

**RAASA: Risk-Aware Adaptive Sandbox Allocation for Containerized Workloads**

It is the cleanest and most academically stable option.

## 2. Target Paper Shape

Recommended section order:

1. Abstract
2. Introduction
3. Problem Statement and Threat Model
4. System Design
5. Implementation
6. Evaluation
7. Discussion and Limitations
8. Related Work
9. Future Work
10. Conclusion

This sequence best matches the current strength of the repo: clear architecture,
progressive validation, and an honest research boundary.

## 3. Abstract Outline

### Goal

The abstract should communicate:

- the problem with static containment
- the adaptive idea
- the privilege-separated design
- local and AWS/Kubernetes validation
- the strongest result
- the main limitation

### Suggested paragraph structure

1. One sentence on the problem:
   static sandboxing either underreacts or overrestricts.
2. One sentence on the proposed solution:
   RAASA introduces adaptive tiered containment.
3. One sentence on the architecture:
   telemetry, risk scoring, policy reasoning, and enforcement with privilege
   separation.
4. One sentence on evaluation:
   validated on local Docker and AWS-hosted K3s.
5. One sentence on takeaway:
   adaptive containment is practical, but Kubernetes telemetry fragility remains
   the main blocker to a stronger v2.

## 4. Introduction Outline

### 4.1 Opening problem

Write the introduction around this core argument:

Modern cloud workloads and AI-agent runtimes are poorly served by binary
containment models. Overly open sandboxes allow abuse and runaway execution.
Overly strict sandboxes break benign workloads. What is needed is a system that
can adapt containment based on observed behavior.

### 4.2 Why this matters now

Anchor the motivation in:

- containerized cloud workloads
- Kubernetes execution environments
- AI-agent runtimes with terminal and code execution capabilities
- the mismatch between static guardrails and dynamic runtime behavior

### 4.3 What RAASA does

Introduce RAASA as:

- an adaptive containment controller
- a modular Observe-Assess-Decide-Act-Audit loop
- a research system rather than a production product

### 4.4 Main contributions paragraph

End the introduction with a short contributions list:

1. RAASA introduces a modular adaptive containment architecture for
   containerized workloads.
2. RAASA maps runtime signals to bounded tier decisions with auditable reasons.
3. RAASA validates a privilege-separated enforcement path for Kubernetes.
4. RAASA provides local and AWS-backed evidence for adaptive containment.

## 5. Problem Statement and Threat Model

### 5.1 Problem definition

Explain the central trade-off:

- under-reaction leaves malicious workloads unconstrained
- over-reaction damages benign workload utility

### 5.2 Scope

Explicitly state:

- this is a single-host validated research prototype
- the goal is adaptive containment, not universal cloud defense
- the project focuses on container runtime behavior, not every attack surface

### 5.3 Threat classes

Use the workload classes already defined in
[docs/threat_matrix.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/threat_matrix.md):

- `benign_steady`
- `benign_bursty`
- `suspicious`
- `malicious_pattern`

### 5.4 What is out of scope

State clearly:

- container escape guarantees
- full lateral movement prevention
- enterprise-grade distributed robustness
- multi-node production claims

This section is where reviewer trust is won.

## 6. System Design

### 6.1 Design goals

Use a short list:

1. adapt containment rather than fix it statically
2. preserve auditability
3. separate reasoning from privileged action
4. degrade safely when telemetry is incomplete

### 6.2 High-level loop

Describe the five stages:

1. Observe
2. Assess
3. Decide
4. Act
5. Audit

### 6.3 Data flow

Explain:

- telemetry collection
- signal normalization
- bounded risk scoring
- tier selection
- enforcement action
- audit logging

### 6.4 Privilege separation

This should be a centerpiece of the paper.

Describe:

- unprivileged controller
- privileged enforcer sidecar
- constrained IPC path
- why this matters for safe autonomous enforcement

### 6.5 Tier semantics

Define `L1`, `L2`, and `L3` carefully.

Important paper note:

Current `L3` should be described as hard containment in the validated live
path, not merely as throughput throttling.

## 7. Implementation

### 7.1 Local path

Explain the Docker-based path:

- Docker telemetry
- local scenarios
- adaptive-vs-static comparison

### 7.2 Cloud path

Explain the Kubernetes path:

- K3s deployment on AWS EC2
- observer
- enforcer sidecar
- pod-specific resolution logic
- telemetry probe path

### 7.3 Controller options

Present the controller stack honestly:

- tuned linear controller as primary
- Isolation Forest as secondary extension
- optional LLM advisor for ambiguous edge cases

### 7.4 Reproducibility

Reference:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)

## 8. Evaluation

### 8.1 Evaluation questions

Structure the section around four questions:

1. Can adaptive containment outperform static baselines locally?
2. Can RAASA preserve benign utility while containing malicious behavior?
3. Can the architecture carry over into a live Kubernetes environment?
4. What currently limits the cloud-native path?

### 8.2 Local evaluation

Cover:

- `static_L1`
- `static_L3`
- `raasa`
- the `small_tuned` scenario

Focus on:

- adaptive-vs-static trade-off
- false positives
- benign restriction
- containment quality

### 8.3 Cloud evaluation

Cover:

- AWS-hosted K3s validation
- pod-specific enforcement resolution
- containment semantics
- closed-loop soak evidence

This is where you bring in the strongest live result bundles.

### 8.4 Calibration and controller truthfulness

This subsection is important.

Explain:

- why the tuned linear controller is the truthful primary controller
- why the ML path is currently secondary
- how calibration changed the live controller story

This is a strength, not a weakness, if written honestly.

### 8.5 Summary table

Include a table comparing:

- local static L1
- local static L3
- local adaptive RAASA
- AWS/K8s adaptive path

Columns should include:

- environment
- controller
- containment quality
- benign utility
- main limitation

## 9. Discussion and Limitations

This section should be explicit and mature.

### 9.1 What the results mean

Main message:

RAASA shows adaptive containment is feasible and more balanced than static
baseline approaches.

### 9.2 Main limitation

State clearly:

the key blocker is not the containment concept, but telemetry/control-plane
fragility in the Kubernetes path, especially around `metrics.k8s.io` timeouts.

### 9.3 Other limitations

List:

- single-node live validation
- limited threat class scope
- secondary ML path not yet the dominant controller
- optional LLM path not central to the main evaluation

### 9.4 Why the limitations are acceptable

Explain that the project is intentionally scoped as a research artifact and
that its claims are bounded accordingly.

## 10. Related Work

Suggested subsections:

1. Static container sandboxing and resource controls
2. Runtime anomaly detection for containers
3. Kubernetes-native security enforcement
4. AI-agent runtime safety and adaptive guardrails

The related work section should position RAASA as a synthesis:

- not just a detector
- not just a throttle
- not just an AI wrapper
- but an adaptive, auditable containment controller

## 11. Future Work

Keep future work disciplined:

1. harden Kubernetes telemetry/control-plane behavior
2. extend beyond the current single-node live setup
3. expose degraded-mode behavior more explicitly
4. benchmark AI-agent-specific threat scenarios
5. revisit stronger ML adaptation only after the base path is stable

Do not let future work turn into a second project proposal.

## 12. Conclusion

The conclusion should restate:

- the problem with static containment
- the adaptive contribution
- the privilege-separated architecture
- the local and cloud validation
- the honest remaining blocker

Recommended closing note:

RAASA does not claim to finish the container security problem. It shows that
adaptive containment can be built, reasoned about, and validated honestly as a
practical research direction for modern cloud and agentic runtimes.

## 13. Writing Priorities

Write these sections first, in this order:

1. Introduction
2. System Design
3. Evaluation
4. Discussion and Limitations
5. Abstract
6. Related Work
7. Conclusion

This order works best because the strongest parts of the project are already
the architecture and evidence story.

## 14. Immediate Next Drafting Tasks

After this outline, the next best writing sequence is:

1. draft the abstract
2. draft the contribution bullets
3. draft the introduction
4. draft the evaluation section skeleton with subsection headings

That will give you a paper-shaped draft quickly without overcommitting to fine
wording too early.
