# RAASA: Evolution, Architectural Progression, and Key Achievements

**Author Perspective:** Top 1% Cloud Security & Sandbox Technology Researcher  
**Purpose:** Foundational material for academic research publication mapping
the iterative evolution of the Risk-Adaptive Autonomous Security Agent (RAASA)
from a local prototype to a validated cloud-native research artifact.

---

## Version 1: The AI-Driven OODA Loop Prototype (Local Simulation)

### The Problems
*   **Static Rule Limitations:** Traditional cloud security tools relied heavily on rigid, static threshold rules, which resulted in high false-positive rates when dealing with modern, ephemeral cloud workloads.
*   **The "Black Box" Execution Gap:** AI had been used for anomaly detection, but there was a significant gap in translating statistical anomalies into deterministic, safe, and context-aware *actions* without human intervention.
*   **Prototyping Constraint:** The initial conceptualization needed a safe, deterministic environment to test whether an LLM could handle the OODA (Observe, Orient, Decide, Act) loop before being exposed to real kernel risks.

### The Solutions
*   **Risk-Adaptive Framework:** Developed the core RAASA framework, integrating a tiered, multi-level containment strategy (L1: Monitor -> L2: Resource Throttle -> L3: Network Isolate -> L4: Terminate).
*   **LLM Policy Engine Integration:** Implemented a reasoning engine that leveraged Large Language Models to evaluate ambiguous risk states, utilizing contextual prompt-engineering to enforce safe security policies.
*   **Synthetic Telemetry Engine:** Built a simulated environment to safely generate benign and malicious workload patterns for the AI to ingest and process.

### The Achievements
*   **Proven AI Autonomy:** Successfully demonstrated that an autonomous agent could consistently and safely evaluate telemetry, escalate risk states, and select appropriate containment actions without human intervention.
*   **Architectural Blueprint:** Established the foundational `core/app.py` control loop, proving that machine learning (anomaly detection) and generative AI (policy reasoning) could work in tandem to create a self-regulating security posture.

---

## Version 2: Kubernetes & eBPF Telemetry Backend (Cloud Integration)

### The Problems
*   **The Reality Gap:** Moving from synthetic data to live cloud workloads introduces massive noise, non-deterministic behaviors, and complex distributed architecture mapping.
*   **Granular Visibility:** Traditional Kubernetes metrics (CPU/Memory via cAdvisor) are insufficient for detecting zero-day exploits or sophisticated evasions. Deep visibility requires kernel-level hooks.
*   **Mapping Kernel to Container:** Intercepting raw Linux system calls is straightforward, but mapping a system call originating deep in the kernel back to a specific, ephemeral Kubernetes Pod requires complex PID-to-cgroup translation.

### The Solutions
*   **eBPF Telemetry Pipeline:** Implemented an `ebpf-probe` utilizing `bpftrace` to hook directly into the Linux kernel (`tracepoint:raw_syscalls:sys_enter`). This allowed RAASA to monitor low-level behavioral anomalies (e.g., unexpected `execve`, `ptrace`, or massive network socket allocations).
*   **Kubernetes API Integration:** Developed the `observer_k8s.py` module to dynamically map kernel PIDs to Kubernetes cgroups (`/sys/fs/cgroup/...`), providing RAASA with perfect context of exactly *which* pod was executing malicious behavior.
*   **Cloud Deployment:** Transitioned the architecture into a Kubernetes DaemonSet, successfully deploying it on an AWS EC2 K3s cluster.

### The Achievements
*   **Deep Cloud Observability:** RAASA achieved real-time, low-overhead kernel visibility, effectively bridging the semantic gap between raw operating system events and higher-level Kubernetes orchestration context.
*   **Live Workload Detection:** Successfully validated the AI agent's ability to ingest live, noisy eBPF data, process it through the Machine Learning layer (Isolation Forest), and accurately escalate risk scores against real workloads running in a cloud environment.

---

## Today's Session (Phase 4): Privileged Enforcer Sidecar via IPC

### The Problems
*   **The "God-Mode" AI Vulnerability:** To physically enforce containment (e.g., dropping network packets or restricting memory), a container requires Linux `root` and `privileged` capabilities. However, granting an AI/LLM-driven agent `root` access is a catastrophic security anti-pattern. If the model hallucinates or is compromised via Prompt Injection, it could destroy the host OS.
*   **Intrusion Prevention System (IPS) Gap:** While v2 could detect controlled anomaly patterns, it remained a passive observer. It lacked the architectural safety mechanism required to physically intervene.

### The Solutions
*   **Decoupled Sidecar Architecture:** Radically refactored the RAASA pod into a multi-container DaemonSet. The primary `raasa-agent` (handling ML and LLM reasoning) was stripped of all privileges and restricted to a standard user (UID 1000). 
*   **Privileged Execution Sandbox:** Created a dedicated, highly constrained `raasa-enforcer` sidecar. This minimal Python daemon runs as `root` with `hostNetwork: true` to access physical network interfaces but contains zero AI logic.
*   **Secure IPC Communication:** Established a secure JSON-over-Unix-Domain-Socket (`/var/run/raasa/enforcer.sock`) Inter-Process Communication mechanism between the two containers. The unprivileged AI agent sends strict, schema-validated containment decisions to the enforcer.

### The Achievements
*   **Privilege-Separated Control Path:** Reduced the risk of autonomous
    enforcement by decoupling the "brain" (unprivileged controller) from the
    "brawn" (privileged enforcer). This is a defensible prototype architecture,
    not proof that a compromised controller can never influence the host.
*   **Live Cloud Enforcement:** Successfully demonstrated live, autonomous network shaping. The unprivileged controller detected malicious behavior and commanded the privileged sidecar to execute Linux Traffic Control (`tc`) on the `cni0` bridge interface, successfully throttling an AWS pod's bandwidth to `1mbit/s` without human intervention.
*   **True Closed-Loop IPS:** Transitioned RAASA from an Intrusion Detection System (IDS) to a fully autonomous Intrusion Prevention System (IPS) capable of real-time, dynamic workload isolation.
