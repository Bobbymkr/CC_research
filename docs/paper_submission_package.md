# Paper Submission Package

This is the compact paper-first package for preparing RAASA as a defensible
research artifact.

For the full reviewer-oriented evidence checklist covering tables, figures,
artifact bundles, negative evidence, and methodology requirements, see
[docs/paper_evidence_package.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_evidence_package.md).

For the source-controlled paper surfaces themselves, use:

- [docs/tables/README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/README.md)
- [docs/figures/README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/figures/README.md)
- [docs/paper_ieee_layout.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/paper_ieee_layout.md)

## Canonical Thesis

RAASA demonstrates that adaptive containment can improve the
security-utility trade-off for containerized workloads by combining runtime
telemetry, bounded risk scoring, policy reasoning, privilege-separated
enforcement, and auditable evidence.

## Contributions To Claim

1. A modular Observe-Assess-Decide-Act-Audit control loop for adaptive
   container containment.
2. A bounded risk-scoring pipeline that maps CPU, memory, process, network,
   and syscall signals into tier decisions.
3. A Kubernetes backend that validates pod-specific host-interface containment
   in the tested AWS/K3s environment.
4. A privilege-separated architecture where the unprivileged controller sends
   constrained IPC commands to a privileged enforcer sidecar.
5. A reproducible evaluation package spanning local Docker experiments,
   AWS/K3s validation, failure injection, adversarial workload matrices, and
   an agent-style misuse benchmark.

## Comparison Framing

- Static L1/L3: RAASA is evaluated against fixed permissive and fixed strict
  allocations to show the adaptive security-utility trade-off.
- Falco/Tetragon-style runtime detection: RAASA is complementary; it consumes
  runtime signals and focuses on adaptive tier decisions and enforcement.
- gVisor, Kata, Firecracker, Nitro Enclaves: RAASA is not a replacement for
  strong isolation. It is a control layer that could sit above stronger
  sandbox backends in future work.

## Claims To Avoid

- Production-ready platform.
- Complete defense against container escape.
- Broad exfiltration or lateral-movement prevention.
- Multi-node, multi-tenant, or EKS robustness until new evidence exists.
- ML superiority over the tuned linear controller.

## Minimum Acceptance Bar

- Every major claim points to `docs/evidence_index.md`.
- Current `L3` is described as hard containment, not general sandbox isolation.
- ML and LLM components are described as secondary extensions.
- Failure cases are preserved and discussed rather than hidden.
- The final artifact passes secret scanning and the full test suite.
- AWS evidence collection follows `docs/aws_validation_playbook.md`.
