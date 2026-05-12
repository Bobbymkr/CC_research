# RAASA v2 Candidate: Kubernetes/eBPF Implementation Progress

> **STATUS: VALIDATED RESEARCH PROTOTYPE (APRIL-MAY 2026)**
> RAASA supports a dual-backend architecture (`--backend k8s`) validated on
> AWS EC2/K3s using Kubernetes metrics, cAdvisor-style scraping, probe-fed
> syscall signals, Linux `tc`, and cgroups v2. This is strong single-node
> prototype evidence, not a production-readiness claim.

To upgrade RAASA from a CPU-only prototype toward a cloud-native Kubernetes
research artifact, the architecture was transitioned out of the simulated
Windows/Docker Desktop environment into a native Linux structure.

Here is the exact hardware and software stack that was built for this iteration:

## 1. Hardware & OS Requirements
Because eBPF operates natively inside the operating system kernel, the environment was moved to AWS.
* **Operating System**: A native Linux environment. **Ubuntu 24.04 LTS**.
* **Linux Kernel**: **Kernel v6.x** with BTF and CO-RE support confirmed.
* **Hardware/VM**: An AWS EC2 `m7i-flex.large` (2 vCPUs, 8GB RAM).

## 2. Orchestration & Container Layer
Docker CLI was abstracted away using an Adapter Pattern.
* **Orchestrator**: A lightweight local Kubernetes cluster (**K3s**) was deployed via an automated bootstrap script.
* **Metrics API**: The standard Kubernetes Metrics Server was deployed to allow RAASA to fetch cluster-wide telemetry natively.

## 3. The Sensory Layer (eBPF Detection)
RAASA's `ObserverK8s` was built to ingest Kubernetes metrics and probe-fed
runtime signals.
* **Tetragon (by Cilium)**: Deployed as a DaemonSet to the cluster via Helm.
* **What it does**: Tetragon can hook into the kernel and stream structured
  runtime events for syscall tracking.
* **Integration**: RAASA normalizes runtime signals into bounded risk features,
  while the paper should distinguish live probe evidence from future richer
  Tetragon policy integration.

## 4. The Enforcement Layer (Network & Memory Throttling)
`EnforcerK8s` uses native Linux kernel mechanisms instead of `docker update`:
* **Memory Enforcement**: Linux **Cgroups v2**. RAASA dynamically lowers `memory.max` limits to throttle runaway memory leaks at the node level.
* **Network Enforcement**: 
  * **Traffic Control (`tc`)**: Standard Linux utility is used to apply
    pod-specific network containment. Current L3 validation is best described
    as hard containment, not graceful bandwidth shaping.

## 5. Programming Languages & SDKs
* **Python (Existing)**: The RAASA core logic (`risk_model.py`, `policy.py`) remains entirely in Python, preserving all ML integration and mathematical modeling.
* **Kubernetes Python Client**: Installed `kubernetes>=29.0.0` via PIP. RAASA authentically queries the K8s API server for state and pod metadata.

---

### Summary of the v2 Candidate Upgrade Path
1. Stood up an Ubuntu Linux VM on AWS.
2. Installed Kubernetes (K3s) and deployed Tetragon + Metrics Server autonomously via bash script.
3. Added the **ObserverK8s** to read Metrics API and eBPF streams.
4. Added the **EnforcerK8s** to write limits to Cgroups v2 and use Linux `tc` for bandwidth throttling.
5. Successfully ran AWS EC2/K3s validation bundles that support the current
   paper claim: adaptive tier decisions and pod-specific containment are
   feasible in the tested single-node cloud setting.
