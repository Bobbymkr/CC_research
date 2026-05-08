# Research Snapshot

## One-sentence thesis

RAASA explores whether container containment can be made adaptive instead of static by continuously observing runtime behavior, converting it into bounded risk, and applying a tiered response that tries to preserve benign utility while containing risky workloads.

## Problem being solved

Static sandboxing is usually a poor fit for modern cloud and agentic workloads:

- a weak sandbox underreacts and leaves malicious or runaway behavior too free,
- a strong sandbox overreacts and harms benign workloads all the time.

RAASA exists to test a middle path: runtime-aware, evidence-driven, closed-loop containment.

## Repo-supported system story

In the current repository, the strongest supportable implementation story is:

1. collect container telemetry,
2. normalize it into bounded features,
3. compute a risk score and confidence,
4. map that signal to `L1`, `L2`, or `L3`,
5. apply containment,
6. write auditable logs,
7. compute metrics and generate plots,
8. repeat across baseline and adaptive experiments.

## What is actually implemented most clearly

### Local Docker path

- Docker-backed telemetry via `docker stats`, `docker inspect`, and `docker top`
- normalized CPU, memory, process, network, and syscall-derived signals
- weighted linear risk scoring, plus an optional Isolation Forest path
- safe policy logic with hysteresis, cooldown, low-risk streaks, optional approval, and optional bounded LLM advice
- containment through `docker update --cpus`
- JSONL audit logs
- experiment runner and metrics summaries

### Cloud-native path

- Kubernetes observer abstraction
- K8s Metrics API and cAdvisor-based telemetry collection
- privileged sidecar enforcement architecture via Unix socket IPC
- `tc` and cgroup-oriented enforcement prototype
- DaemonSet deployment artifacts

This K8s path is meaningful and useful, but the local Docker evaluation remains the cleanest and strongest evidence base in the folder.

## Best-supported evaluation story

The most defensible evaluation narrative in this repo is:

- `static_L1` underreacts,
- `static_L3` overreacts,
- adaptive RAASA performs better on the security-vs-utility trade-off,
- the tuned linear controller currently outperforms the optional Isolation Forest path for the core evaluation story,
- the project scales beyond the smallest case to medium and large scenario runs,
- the K8s/eBPF direction is prototyped and partially evidenced, but should be described more carefully than the local Docker path.

## Strongest headline numbers to reuse carefully

From the curated summaries in `results/aws_v2/`:

- `run_L1.summary.json`: recall `0.0`, malicious containment `0.0`
- `run_L3.summary.json`: recall `1.0`, benign restriction `1.0`
- `ablation_small_tuned_linear_vs_ml.json`: tuned linear beats the ML arm on the main selection rule
- `medium_raasa_linear_mean.json`: precision `0.9524`, recall `1.0`, false positive rate `0.0370`
- `run_large_raasa_linear_r1.summary.json`: precision `0.8727`, recall `1.0`, false positive rate `0.0972`
- `syscall_raasa_linear_mean.json`: precision `1.0`, recall `1.0`, false positive rate `0.0`

## Why this project matters beyond the class/research artifact

If extended properly, the project points toward:

- safer AI code-execution sandboxes,
- adaptive multi-tenant cloud containment,
- auditable autonomous security agents,
- node-local prevention systems that react before a human review loop can.

## Use this claim style in the paper

Good framing:

- "RAASA is a research prototype for adaptive containment."
- "The strongest current evidence comes from Docker-based live experiments."
- "The tuned linear controller is the best-performing current controller in the repo."
- "The Kubernetes/eBPF path is a promising prototype direction with partial evidence."

Avoid overclaiming:

- do not imply the current repo is a finished production platform,
- do not imply the ML path is better than the linear path,
- do not imply every mechanism described in the draft paper is already implemented end to end.
