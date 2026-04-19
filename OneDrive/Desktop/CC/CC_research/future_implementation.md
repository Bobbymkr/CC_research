# RAASA v2: Production-Grade eBPF Implementation Plan

To upgrade RAASA from a CPU-only prototype to a production-grade, eBPF-powered Kubernetes security controller (RAASA v2), the architecture must transition out of the simulated Windows/Docker Desktop environment into a native Linux structure. 

Here is the exact hardware and software checklist required to build this future iteration.

## 1. Hardware & OS Requirements
Because eBPF operates natively inside the operating system kernel, development cannot easily occur on Windows or macOS.
* **Operating System**: A native Linux environment. **Ubuntu 22.04 LTS or 24.04 LTS** is the industry standard.
* **Linux Kernel**: **Kernel v5.8 or higher**. (Modern eBPF requires BTF [BPF Type Format] and CO-RE [Compile Once – Run Everywhere] support, which are standard in v5.8+).
* **Hardware/VM**: A bare-metal Linux machine or a Cloud VM (AWS EC2, Azure VM, GCP Compute). Minimum 4 vCPUs and 8GB RAM to comfortably run Kubernetes, eBPF sensors, and your test workloads.

## 2. Orchestration & Container Layer
Docker CLI is excellent for v1, but eBPF tools are designed primarily for Kubernetes.
* **Orchestrator**: A lightweight local Kubernetes cluster. Use **K3s**, **MicroK8s**, or **Minikube** for development.
* **Container Runtime**: **containerd** or **CRI-O**. (You won't use raw Docker anymore; you will use Kubernetes Pods).

## 3. The Sensory Layer (eBPF Detection)
To detect syscall abuse (container escapes, privilege escalation) and granular network violations, RAASA's `telemetry.py` must switch from polling `docker stats` to ingesting eBPF event streams.
* **Tetragon (by Cilium) OR Falco (by Sysdig)**: You do not need to write raw eBPF C code from scratch. You will deploy Tetragon or Falco onto your Kubernetes cluster as a DaemonSet.
* **What they do**: They hook directly into the kernel and stream highly structured JSON logs (e.g., *"Pod A just spawned a shell,"*, *"Pod B just read `/etc/shadow`,"*, *"Pod C just initiated outbound DNS to a Russian IP"*). 
* **Integration**: RAASA will subscribe to this gRPC or JSON stream, normalizing these kernel events into your existing Risk Score math.

## 4. The Enforcement Layer (Network & Memory Throttling)
Currently, `enforcement.py` uses `docker update --cpus`. You will replace this with native Linux and Kubernetes control mechanisms.
* **Memory Enforcement**: Linux **Cgroups v2**. You will use Kubernetes APIs (or interact directly with `/sys/fs/cgroup/`) to dynamically lower `memory.max` limits to throttle runaway memory leaks.
* **Network Enforcement**: 
  * **Traffic Control (`tc`)**: Standard Linux utility to instantly throttle bandwidth capabilities of a networking interface (e.g., slowing an exfiltration attack to 1 kbps).
  * **Cilium Network Policies**: If you use Cilium for networking, RAASA can dynamically issue API calls to inject a network firewall policy that completely isolates a suspicious pod from the internet while keeping it alive for forensic investigation.

## 5. Programming Languages & SDKs
* **Python (Existing)**: Keep the RAASA core logic (`risk_model.py`, `policy.py`) in Python. It is perfect for the fast math, ML integrations, and API interactions.
* **Kubernetes Python Client**: Install `kubernetes` via PIP so RAASA can authenticate and issue commands to the K8s API server (e.g., patching a deployment to change limits).
* **Optional (Go/Rust)**: If you eventually want to write *custom* eBPF probes rather than using Falco/Tetragon out-of-the-box, you will need the Go programming language (using the `cilium/ebpf` library) or Rust (using `Aya`).

---

### Summary of the RAASA v2 Upgrade Path
1. Stand up an Ubuntu Linux VM.
2. Install Kubernetes (K3s) and deploy Tetragon.
3. Update RAASA's **Observer** to read the Tetragon eBPF stream instead of Docker stats.
4. Update RAASA's **Enforcer** to call the Kubernetes API to update CPU/Memory limits and Network Policies instead of `docker update`.
