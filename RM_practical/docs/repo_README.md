# RAASA v1

RAASA v1 is a lightweight agentic prototype for adaptive container containment.
This repository is intentionally scoped as a research artifact, not a production
cloud-security platform.

## v1 Architecture

The control loop follows five logical roles:

1. `Observer` collects container runtime evidence.
2. `Risk Assessor` converts evidence into bounded signals.
3. `Policy Reasoner` selects `L1`, `L2`, or `L3`.
4. `Action Enforcer` applies CPU-based containment.
5. `Audit Logger` records evidence, decisions, and justification.

## Repository Layout

```text
raasa/
  analysis/
  configs/
  core/
  experiments/
  logs/
  workloads/
main.py
```

## Current Status

Task 1 scaffolds the repository, configuration, and controller entrypoint.
Subsequent tasks will fill in telemetry, policy logic, enforcement, experiments,
and analysis.
