# RAASA Evolution and Achievements: Pathway to a Research Paper

This document outlines the evolutionary phases of the RAASA (Risk-Aware Autonomous Security Agent) architecture. It traces the specific problems encountered in each phase, the technical solutions implemented, and the core achievements that contribute to the novelty and defensibility of the final research paper.

---

## Phase 1 (v1): The Local Docker Prototype

**What were the problems?**
- **Static Telemetry:** Early versions relied on mock data or static logs, making it impossible to evaluate dynamic system behavior in real-time.
- **Rules-Based Rigidity:** The initial risk engine was heavily dependent on hardcoded thresholds, lacking the contextual reasoning required for complex, ambiguous security events.
- **No Enforcement Loop:** The system could "observe" but had no mechanism to automatically enforce isolation or throttling without manual human intervention.

**How were they solved?**
- **Docker-Native Observer:** Implemented `DockerObserver` to fetch live CPU, memory, and networking stats via the Docker Daemon API, creating a continuous telemetry stream.
- **LLM-Powered Risk Assessor:** Integrated an LLM Advisor (using LangChain and a specialized System Prompt) to analyze ambiguous edge cases and output structured `L1/L2/L3` mitigation recommendations.
- **Automated Enforcer:** Built `DockerEnforcer` to autonomously apply `docker update` (CPU/Mem throttling) and `docker network disconnect` commands based on the LLM's final verdict.

**What were the achievements?**
- **First Closed-Loop Autonomous Security:** Successfully proved that an AI agent could observe telemetry, reason about risk, and autonomously enforce a quarantine on a live Docker container within seconds.
- **Prototype Validation:** Created a functional sandbox demonstrating the viability of integrating LLMs into the critical path of infrastructure security operations.

---

## Phase 2 (v2): The Kubernetes & eBPF Dual-Backend

**What were the problems?**
- **Architecture Limitations:** Docker API is not used in modern enterprise cloud environments; the industry standard is Kubernetes. The V1 prototype was not representative of real-world deployments.
- **Granular Observability Gaps:** Standard container APIs only provide high-level metrics (CPU/Mem) but lack deep system introspection (e.g., syscall rates) necessary to detect sophisticated evasion or zero-day behavior.
- **Host-Level Privileges:** Attempting to enforce traffic shaping (`tc`) or read raw kernel metrics required dangerous host-level privileges that violate cloud-native security principles.

**How were they solved?**
- **Dual-Backend Refactoring:** Abstracted the core `Engine` and built a `K8sBackend` containing `ObserverK8s` and `EnforcementK8s`, enabling the exact same AI risk model to operate seamlessly across both Docker and Kubernetes.
- **eBPF Syscall Probes:** Engineered a custom `bpftrace`-based sidecar to monitor kernel context switches and exact syscall rates, attributing them directly to Kubernetes pods using cgroup mapping.
- **Privileged Sidecar Pattern:** Isolated all dangerous, high-privilege operations (eBPF probes, `tc` network shaping) into a tightly scoped DaemonSet sidecar (`raasa-enforcer`), communicating via secure IPC with the unprivileged LLM reasoning agent.

**What were the achievements?**
- **Cloud-Native Production Readiness:** Elevated the project from a localized script to a distributed Kubernetes DaemonSet capable of running on AWS clusters.
- **Deep Kernel Introspection:** Integrated eBPF to achieve deep observability, allowing the agent to detect malicious behavior (like process fan-outs) that standard API metrics miss.
- **Architectural Security:** Established a defensible, principle-of-least-privilege architecture that separates the vulnerable AI reasoning layer from the highly privileged execution layer.

---

## Today's Session (v3): AWS Phase 0 Validation & Telemetry Resilience

**What were the problems?**
- **eBPF Probe Instability:** The `bpftrace` implementation in V2 suffered from race conditions, restricted `debugfs` access in isolated containers, and missing PID attributions, causing a complete loss of syscall telemetry.
- **Kubernetes Metrics API Fragility:** During live stress-testing on AWS (`m7i-flex.large`), the malicious workload (`stress-ng`) caused severe node resource starvation. This caused the Kubernetes API Server and `metrics-server` to completely fail (`500 Internal Server Error`, `context deadline exceeded`), blinding the security agent.
- **Data Parsing Failures:** The K8s Metrics API returned inconsistent bare-integer formats for un-resourced pods, breaking the Python telemetry parser.

**How were they solved?**
- **`/proc`-based eBPF Fallback:** Replaced the unreliable `bpftrace` scripts with an ultra-resilient, direct `/proc/stat` and cgroup traversal mechanism that accurately counts context switches across nested `cri-containerd` namespaces.
- **Direct Cgroup Telemetry Bypass:** Modified `observer_k8s.py` to bypass the overloaded Kubernetes API Server entirely, reading CPU metrics directly from the eBPF sidecar's shared memory volume.
- **Parser Hardening:** Rewrote the Python metrics parser to handle edge-case bare integers and nanocore conversions robustly, logging detailed diagnostics.

**What were the achievements?**
- **Discovered a Major Cloud Vulnerability:** Empirically proved that standard cloud-native telemetry (K8s Metrics API) is fragile and acts as a single point of failure under resource-exhaustion attacks. 
- **Proved RAASA's Architectural Superiority:** Demonstrated that RAASA's hybrid out-of-band architecture (direct cgroup/eBPF polling) maintains 100% signal integrity and continues to monitor the node even when the Kubernetes control plane is completely paralyzed.
- **Achieved Baseline Stability:** Successfully established a clean, high-integrity telemetry baseline on an AWS EC2 instance, readying the project for the final Isolation Forest ML integration and publication-grade evaluation data gathering.
