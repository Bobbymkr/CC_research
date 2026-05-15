# RAASA Knowledge Roadmap

Use this as the learning order for continuing RAASA toward a defensible paper
and stronger v2 research artifact.

## Level 1: Required To Continue Safely

- Python testing and packaging: `pytest`, fixtures, CLI entrypoints, dependency
  pinning, and reproducible runs.
- Linux containment basics: processes, cgroups v2, namespaces, veth pairs,
  `tc`, seccomp, and AppArmor.
- Kubernetes runtime model: pods, DaemonSets, service accounts, RBAC,
  metrics-server, node-local agents, and pod lifecycle.
- AWS EC2 basics: SSH hygiene, key rotation, security groups, AMIs, instance
  sizing, cost control, and evidence capture.
- Research discipline: threat models, non-claims, ablation studies,
  reproducibility, and limitation-first writing.

## Level 2: Needed For Strong Paper Review

- Runtime security tooling: Falco, Tetragon, eBPF event streams, Kubernetes
  audit signals, and alert-to-enforcement gaps.
- Metrics failure modes: Metrics API outages, stale samples, partial telemetry,
  degraded-mode policy, and audit provenance.
- Experiment design: precision, recall, false positives, containment latency,
  tier churn, repeated trials, and preserving failed runs.
- Sandbox comparison: why RAASA is a control layer, while gVisor, Kata,
  Firecracker, and Nitro Enclaves are stronger isolation boundaries.

## Level 3: Needed Before Production Claims

- Multi-node Kubernetes and EKS operations.
- Secure supply chain: secret scanning, SBOMs, image scanning, signed releases,
  and dependency vulnerability review.
- Kernel/eBPF depth: BPF verifier limits, tracing policy design, BPF LSM,
  cgroup hooks, and kernel monitor failure modes.
- Platform hardening: least-privilege sidecars, constrained IPC, observability,
  upgrades, rollbacks, and incident response.

## Recommended Team Shape

- Cloud/AWS engineer for EC2, K3s/EKS, IAM, networking, and cost-safe testbeds.
- Systems/SWE engineer for Python architecture, tests, CI, packaging, and
  reproducibility.
- Security researcher for threat models, adversarial scenarios, related work,
  and claim boundaries.
- Sandbox/kernel specialist for gVisor, Kata, Firecracker, eBPF, cgroups, and
  Linux enforcement semantics.
