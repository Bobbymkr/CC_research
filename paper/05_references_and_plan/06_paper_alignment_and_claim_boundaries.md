# Paper Alignment And Claim Boundaries

This is the most important safeguard file in the packet.

The draft paper in `paper_draft/RAASA_Final_v2.docx` is useful, but parts of it are more ambitious than the cleanest repo-backed implementation story. Use this file to keep the final paper defensible.

## 1. Claims that are strongly supported by this repo

These are safe, strong claims:

- RAASA is a research prototype for adaptive containment of containerized workloads.
- The controller follows an observe -> assess -> decide -> act -> audit loop.
- The repo implements a Docker-backed local path with telemetry, normalized features, risk scoring, policy reasoning, CPU-based containment, logging, and experiment analysis.
- The repo also contains a Kubernetes-oriented prototype path with observer abstraction and privileged sidecar enforcement architecture.
- Static `L1` underreacts and static `L3` overreacts on the curated evaluation story.
- The tuned linear controller is the strongest current controller in the repo evidence.
- The project includes auditability through JSONL records and derived summaries.

## 2. Claims that are only partially supported or prototype-only

These can be mentioned, but carefully:

- K8s/eBPF cloud-native evaluation exists, but the evidence base is smaller and less even than the local Docker path.
- The privileged sidecar pattern is implemented as a meaningful prototype, but still needs broader operational validation.
- The optional LLM advisor exists in the code, but it is not the central source of the strongest evaluation results.
- The Isolation Forest path exists, but the current ablation says it is not the preferred controller.

## 3. Claims in the draft that should be treated as future-facing unless re-implemented and re-evidenced

Be careful with these themes from the draft:

### A. Feature semantics mismatch

The draft describes a five-feature vector centered on:

- syscall distribution anomaly,
- privileged syscall rate,
- file I/O entropy,
- network egress anomaly,
- CPU burst index.

The current repo implementation more clearly uses:

- CPU,
- memory,
- process count,
- network volume,
- syscall-rate signal.

This means the paper should either:

1. revise the feature description to match the actual repo, or
2. clearly say that the broader feature design is the intended future formulation while the present prototype uses a simpler signal set.

### B. Enforcement semantics mismatch

The draft talks about:

- seccomp filter updates,
- cgroups v2 resource changes,
- network namespace rules,
- CRIU-assisted downgrade handling.

The strongest clearly implemented local path in the repo is:

- `docker update --cpus`

and the K8s prototype path adds:

- pod-specific host-veth `tc` enforcement,
- cgroup memory updates through a privileged sidecar.

Unless these richer mechanisms are fully re-implemented and re-evidenced, they should not be presented as equally mature current capabilities.

### C. Telemetry source mismatch

The draft uses language around:

- auditd,
- cgroups v2 statistics,
- iptables counters,
- host-level syscall distributions.

The repo's current strongest local path uses Docker CLI-derived telemetry with optional syscall probe files and simulated syscall estimation when probes are not present.

The newest April 26 v2 validation adds another important caution:

- the captured K8s run shows `network_status=metrics_unavailable`,
- the captured K8s run shows `syscall_status=probe_missing`,
- some test pods are missing workload labels needed for clean automated metrics.

The new direct SSH-backed live validation adds one strong point:

- repeated Metrics API `500` and timeout failures are now directly evidenced from the AWS node logs,
- the shared `/var/run/raasa/` probe volume is also directly evidenced as populated on the live node.

So the paper should not imply that the full intended telemetry stack was consistently active in the latest v2+ run.
What it can now say, safely, is that the control-plane telemetry path is fragile under load and that RAASA has a real out-of-band fallback path on the node.

### D. ML superiority claim mismatch

The draft can sound like the learned model is the next clear improvement. The current repo evidence does not support that claim. The packet results favor the tuned linear controller.

## 4. Best wording strategy for the final paper

Use a layered phrasing style:

### Safe wording

- "The current prototype implements..."
- "The strongest evaluation evidence in this study comes from..."
- "The cloud-native path is prototyped through..."
- "The tuned linear controller served as the primary evaluation controller because..."

### Risky wording to avoid

- "RAASA fully implements dynamic seccomp relaxation..."
- "The ML controller outperforms the linear controller..."
- "The production cloud-native system has been comprehensively validated..."

## 5. A practical way to revise the draft paper

If you edit the draft, make these adjustments:

1. align the feature description with the current codebase,
2. present richer enforcement ideas as roadmap or future work unless directly evidenced,
3. keep the tuned linear controller as the main experimental system,
4. describe the K8s/eBPF path as a concrete prototype extension,
5. preserve the adaptive-vs-static thesis because that is the repo's strongest contribution.

## 6. Final paper position I would recommend

Present RAASA as a carefully scoped, evidence-led adaptive containment prototype with:

- a fully understandable modular controller,
- strong local Docker evaluation,
- meaningful scale progression,
- honest ML ablation,
- a promising but still maturing cloud-native enforcement path with live pod-specific host-veth containment evidence,
- and fresh April 26 operational evidence that shows both live progress and unresolved telemetry/escalation gaps.

That version is still strong research. It is also much easier to defend in review.
