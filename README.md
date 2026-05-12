# RAASA

RAASA (Risk-Aware Adaptive Sandbox Allocation) is a cloud-security research
system for adaptive containment of containerized workloads. It combines runtime
telemetry, bounded risk scoring, tiered policy reasoning, and enforcement to
move workloads between `L1`, `L2`, and `L3` containment states.

This repository is intentionally positioned as a research artifact with live
validation evidence, not as a finished production platform.

## Research Focus

RAASA is built around a practical security question that is becoming more
important in both cloud platforms and AI-agent infrastructure:

- how should a system safely contain suspicious workloads without statically
  over-restricting benign ones?
- how can container telemetry be turned into interpretable, auditable,
  enforcement decisions?
- how can an autonomous controller stay useful without giving an AI-driven
  component unsafe direct host privileges?

## Architecture

The control loop follows five logical roles:

1. `Observer` collects runtime evidence.
2. `Risk Assessor` converts evidence into bounded signals and risk scores.
3. `Policy Reasoner` selects `L1`, `L2`, or `L3`.
4. `Action Enforcer` applies containment.
5. `Audit Logger` records telemetry, decisions, and justification.

The repository currently contains two backend paths:

- `docker`: local experiments using Docker Desktop / Docker CLI
- `k8s`: Kubernetes-native experiments using K3s, Metrics API, cAdvisor-style
  scraping, and probe-fed syscall signals

The Kubernetes path also includes a decoupled privileged enforcer sidecar so
the reasoning/controller path can remain unprivileged while enforcement actions
operate through a constrained IPC boundary. The observer is node-local by
design and now uses bounded Metrics API degradation paths: direct pod lookup,
namespace-list fallback, and short-lived cached reuse during timeout bursts.

## Current State

The project has moved beyond initial scaffolding. The current repo includes:

- local Docker-backed experiments and analysis tooling
- Kubernetes observer and enforcer implementations
- live AWS validation artifacts and phase-by-phase engineering notes
- a tuned linear controller and a secondary Isolation Forest path
- optional LLM-assisted edge-case policy reasoning
- reproducibility guidance, result bundles, and automated tests

The most defensible current positioning is:

- strong research prototype
- truthful local and AWS-backed validation artifact
- promising basis for a paper on adaptive containment, cloud-native runtime
  security, and AI-agent safety guardrails

It should not yet be described as a production-ready security product.

## Key Evidence in This Repo

- canonical reviewer evidence map:
  [docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md)
- AWS validation playbook:
  [docs/aws_validation_playbook.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/aws_validation_playbook.md)
- local and cloud reproducibility guidance:
  [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- consolidated testing environment inventory:
  [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)
- repository hygiene and publication checklist:
  [docs/repo_hygiene.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/repo_hygiene.md)
- knowledge roadmap for continuing the work:
  [docs/knowledge_roadmap.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/knowledge_roadmap.md)
- paper submission package:
  [docs/paper_submission_package.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_submission_package.md)
- architectural and project narrative:
  [docs/project_documentation.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/project_documentation.md)
- AWS live progress tracker and containment validation:
  [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)

## Repository Layout

```text
raasa/
  analysis/      Metrics, plots, and experiment post-processing
  configs/       Tuned and baseline controller configurations
  core/          Runtime controller, policy, telemetry, logging, IPC
  experiments/   Scenario execution harness
  k8s/           Kubernetes observer, enforcer, manifests, probe scripts
  ml/            Isolation Forest training path
  scripts/       AWS/K3s deployment and validation helpers
  workloads/     Workload catalog used in experiments
tests/           Automated regression coverage
docs/            Project, evaluation, and validation documentation
```

## Recommended Reading Order

1. [docs/project_documentation.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/project_documentation.md)
2. [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
3. [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)
