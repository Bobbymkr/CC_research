# Implementation Map

## What to treat as the canonical implementation

If someone asks "what code best represents RAASA as implemented in this repo?", start with these files:

- `code/core/app.py`
- `code/core/telemetry.py`
- `code/core/features.py`
- `code/core/risk_model.py`
- `code/core/policy.py`
- `code/core/enforcement.py`
- `code/core/logger.py`
- `code/experiments/run_experiment.py`
- `code/analysis/metrics.py`
- `code/workloads/catalog.py`

## Main implementation components

### Controller entrypoint

- File: `code/core/app.py`
- Purpose: wires config, observer, feature extractor, risk assessor, policy reasoner, enforcer, logger, and metrics into one controller loop.

### Configuration

- File: `code/core/config.py`
- Supporting YAMLs: `configs/*.yaml`
- Purpose: keep thresholds, weights, enforcement caps, and experiment guardrails adjustable without code edits.

### Telemetry collection

- File: `code/core/telemetry.py`
- Current Docker signals:
  - CPU percent
  - memory percent
  - process count
  - network receive/transmit deltas
  - syscall rate from either simulated estimates or probe files

### Feature extraction

- File: `code/core/features.py`
- Current normalized signals:
  - `cpu_signal`
  - `memory_signal`
  - `process_signal`
  - `network_signal`
  - `syscall_signal`

### Risk scoring

- File: `code/core/risk_model.py`
- Current paths:
  - weighted linear score,
  - optional Isolation Forest loaded from `environment/iforest_latest.pkl`
- Also computes:
  - confidence score,
  - risk trend.

### Policy reasoning

- File: `code/core/policy.py`
- Important implemented controls:
  - hysteresis,
  - cooldown,
  - low-risk streak requirement,
  - L3 confidence gate,
  - optional approval gate,
  - optional bounded LLM advisor.

### Enforcement

- Local Docker:
  - File: `code/core/enforcement.py`
  - Mechanism: `docker update --cpus`

- K8s path:
  - File: `code/k8s/enforcement_k8s.py`
  - Delegates to `code/k8s/enforcer_sidecar.py`
  - Prototype mechanisms: `tc` shaping and cgroup memory updates

### Audit logging

- File: `code/core/logger.py`
- Output shape: one JSON object per decision tick per container.

### Workloads and scenarios

- Files:
  - `code/workloads/catalog.py`
  - `code/experiments/scenarios.py`
- Purpose:
  - define workload classes,
  - specify expected tiers,
  - build scenario layouts such as `small_tuned`, `medium`, `large`, `network_test`, and `syscall_test`.

### Experiment runner

- File: `code/experiments/run_experiment.py`
- Purpose:
  - start scenario containers,
  - run the controller,
  - clean up,
  - write summary metrics,
  - append experiment manifest rows.

### Analysis and plots

- Files:
  - `code/analysis/metrics.py`
  - `code/analysis/plots.py`
  - `code/analysis/overhead.py`
- Purpose:
  - compute precision/recall/FPR and related metrics,
  - measure overhead,
  - generate paper-ready figures.

## Configs that matter most

### `configs/config.yaml`

Base/default configuration.

### `configs/config_tuned_small.yaml`

Tuned configuration used in earlier adaptive tuning work.

### `configs/config_tuned_small_linear.yaml`

Most important current paper config. This is the tuned linear profile that the repo evidence currently favors.

### `configs/config_tuned_small_linear_probe.yaml`

Probe-oriented variation for syscall-enriched runs.

### `configs/config_tuned_small_linear_probe_approval.yaml`

Approval-gated variation.

## Verification assets included here

The `verification/tests/` folder contains the source tests for:

- analysis,
- telemetry/enforcement behavior,
- experiments,
- K8s observer behavior,
- learned model behavior,
- overrides,
- policy reasoning.

### Important note

This packet includes the tests, but this packaging pass did not rerun them in the bundled runtime because that runtime did not include `pytest`. Treat the tests as verification assets present in the repo, not as freshly re-executed proof from this packaging step.

## Reproducibility support

Use:

- `environment/requirements.txt`
- `environment/pyproject.toml`
- `environment/pytest.ini`
- `reproduction_commands.txt`

to reconstruct the environment and rerun the study.
