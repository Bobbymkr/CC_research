# Architecture And Project Flow

## Core architecture

RAASA is organized as a closed control loop:

```text
Observe -> Extract Features -> Assess Risk -> Reason About Policy -> Enforce -> Audit -> Analyze
```

### Module mapping

| Role | Main file(s) | What it does |
| --- | --- | --- |
| Observer | `code/core/telemetry.py`, `code/k8s/observer_k8s.py` | Collects runtime evidence from Docker or Kubernetes |
| Feature extraction | `code/core/features.py` | Normalizes raw telemetry into bounded signals |
| Risk assessment | `code/core/risk_model.py` | Produces risk, confidence, and trend |
| Policy reasoning | `code/core/policy.py` | Chooses `L1`, `L2`, or `L3` with safety rules |
| Enforcement | `code/core/enforcement.py`, `code/k8s/enforcement_k8s.py`, `code/k8s/enforcer_sidecar.py` | Applies or delegates containment |
| Audit logging | `code/core/logger.py` | Writes JSONL records for each decision tick |
| Experiment orchestration | `code/experiments/run_experiment.py`, `code/experiments/scenarios.py` | Starts scenarios, runs controller, writes summaries |
| Analysis | `code/analysis/metrics.py`, `code/analysis/plots.py`, `code/analysis/overhead.py` | Computes metrics and builds plots |

## Practical architecture by backend

### 1. Local Docker research path

This is the clearest end-to-end path in the repo.

```text
Docker containers
  -> docker stats / inspect / top
  -> normalized features
  -> linear or optional ML risk
  -> policy engine
  -> docker update --cpus
  -> JSONL audit log
  -> summary metrics and plots
```

### 2. Kubernetes/cloud-native path

This is the next-generation path the repo has already started to prototype.

```text
Kubernetes pods on a node
  -> Metrics API + cAdvisor + syscall probe files
  -> ObserverK8s
  -> same feature/risk/policy layers
  -> EnforcerK8s IPC client
  -> privileged sidecar
  -> tc / cgroup enforcement
```

The important architectural idea is that the upper layers are intentionally shared across backends.

## Project flow from start to finish

### Stage 1. Scope and threat framing

- define threat classes,
- decide what is in scope for v1,
- keep the problem measurable.

Supporting files:

- `docs/project_documentation.md`
- `docs/threat_matrix.md`
- `docs/PLAN.md`

### Stage 2. Build the controller skeleton

- create data models,
- create configuration loading,
- create app entrypoint,
- split responsibilities by module.

Supporting files:

- `code/core/models.py`
- `code/core/config.py`
- `code/core/app.py`

### Stage 3. Add telemetry and bounded features

- Docker path first,
- later add K8s observer abstraction,
- convert raw values to bounded signals.

Supporting files:

- `code/core/telemetry.py`
- `code/core/features.py`
- `code/k8s/observer_k8s.py`

### Stage 4. Add risk and policy logic

- weighted linear risk path,
- optional ML path,
- stability and safety logic in the reasoner.

Supporting files:

- `code/core/risk_model.py`
- `code/core/policy.py`
- `code/core/llm_advisor.py`

### Stage 5. Add enforcement and auditing

- local CPU throttling path,
- K8s delegated enforcement path,
- JSONL evidence per tick.

Supporting files:

- `code/core/enforcement.py`
- `code/k8s/enforcement_k8s.py`
- `code/k8s/enforcer_sidecar.py`
- `code/core/logger.py`

### Stage 6. Create scenarios and experiments

- define benign, suspicious, and malicious workloads,
- automate scenario startup, controller execution, and cleanup,
- compare adaptive vs static baselines.

Supporting files:

- `code/workloads/catalog.py`
- `code/experiments/scenarios.py`
- `code/experiments/run_experiment.py`

### Stage 7. Evaluate, tune, and document honestly

- compute metrics,
- generate plots,
- compare controllers,
- record where the first ideas were weaker than expected.

Supporting files:

- `code/analysis/metrics.py`
- `code/analysis/plots.py`
- `docs/live_experiment_notes.md`
- `04_results_and_evidence.md`

## Architectural strengths worth highlighting in the paper

- modular control loop,
- backend abstraction,
- bounded tier system,
- auditable decision trail,
- explicit safety logic around policy switching,
- separation of unprivileged reasoning from privileged enforcement in the K8s path.

## Architectural limitations to mention honestly

- local v1 enforcement is mainly CPU throttling,
- the K8s path is promising but less completely evidenced than the Docker path,
- some draft-paper mechanisms are design ambitions rather than current repo reality,
- the strongest results are tied to the tuned linear controller.
