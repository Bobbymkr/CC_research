# RAASA v2: Production-Grade eBPF Implementation (ACHIEVED)

> **STATUS: ACHIEVED (APRIL 2026)**
> *This plan now describes a v2 research artifact. RAASA supports a dual-backend architecture (`--backend k8s`) validated on AWS EC2 using Linux Traffic Control, cgroups v2, and probe-fed runtime signals. The current evidence is promising but should be framed as controlled validation, not production proof.*

To upgrade RAASA from a CPU-only prototype to a production-grade, eBPF-powered Kubernetes security controller (RAASA v2), the architecture was successfully transitioned out of the simulated Windows/Docker Desktop environment into a native Linux structure. 

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
RAASA's `ObserverK8s` was built to ingest eBPF event streams and Kubernetes Metrics.
* **Tetragon (by Cilium)**: Deployed as a DaemonSet to the cluster via Helm.
* **What it does**: Tetragon hooks directly into the kernel and streams highly structured JSON logs for deep syscall tracking.
* **Integration**: RAASA normalizes available runtime events into the risk-score path for the tested workloads.

## 4. The Enforcement Layer (Network & Memory Throttling)
`EnforcerK8s` uses native Linux kernel mechanisms instead of `docker update`:
* **Memory Enforcement**: Linux **Cgroups v2**. RAASA dynamically lowers `memory.max` limits to throttle runaway memory leaks at the node level.
* **Network Enforcement**: 
  * **Traffic Control (`tc`)**: Standard Linux utility is used to instantly throttle bandwidth capabilities of a networking interface. RAASA successfully throttled malicious pod network throughput to `1mbit/s` without dropping the container.

## 5. Programming Languages & SDKs
* **Python (Existing)**: The RAASA core logic (`risk_model.py`, `policy.py`) remains entirely in Python, preserving all ML integration and mathematical modeling.
* **Kubernetes Python Client**: Installed `kubernetes>=29.0.0` via PIP. RAASA authentically queries the K8s API server for state and pod metadata.

---

### Summary of the Achieved v2 Upgrade Path
1. Stood up an Ubuntu Linux VM on AWS.
2. Installed Kubernetes (K3s) and deployed Tetragon + Metrics Server autonomously via bash script.
3. Added the **ObserverK8s** to read Metrics API and eBPF streams.
4. Added the **EnforcerK8s** to write limits to Cgroups v2 and use Linux `tc` for bandwidth throttling.
5. Successfully ran the `small_tuned` scenario natively on AWS EC2, confirming that the autonomous containment loops work exactly as designed on real cloud hardware.
