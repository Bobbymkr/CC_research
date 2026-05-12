# CC_research Project Documentation

## 1. Project Name

**Project:** RAASA v1  
**Full name:** Risk-Aware Adaptive Sandbox Allocation  
**Project type:** Cloud and sandbox security research prototype  
**Main focus:** adaptive containment for container workloads

RAASA is a research system. It watches containers, scores risk, chooses a sandbox tier, applies CPU limits, and writes audit logs. It is built for honest prototype research, not for full production use.

For the consolidated list of test environments, local/AWS resources, captured pod
inventories, and currently missing infrastructure details, see
[docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md).

## 2. Main Problem

Modern cloud workloads and AI agent workloads often run in containers. A static sandbox is a problem:

- If the sandbox is too open, a bad workload can use too much CPU or act in a risky way.
- If the sandbox is too strict, a good workload becomes slow or breaks.

The project tries to solve this trade-off with **adaptive containment**.

## 3. Main Goal

The goal is to prove this idea:

1. A controller can watch runtime behavior.
2. It can turn telemetry into a bounded risk score.
3. It can move a container between `L1`, `L2`, and `L3`.
4. It can do this safely, with logs and repeatable tests.

## 4. Scope and Safety Limits

The project uses strict scope control. This is important in cloud security research.

- It runs on a **single host**.
- It mainly uses **Docker Desktop / Docker CLI** for live work.
- The main enforcement is **CPU throttling**.
- It does not claim full protection from escape, exfiltration, or lateral movement.
- It does not claim full production readiness.

### Why this scope was chosen

The team needed a system that could be built, tested, and defended with real evidence. A smaller scope made the work honest and measurable.

### Files

- `PLAN.md`
- `docs/threat_matrix.md`
- `docs/next_generation_roadmap.md`
- `README.md`

## 5. End-to-End Architecture

RAASA uses a simple control loop:

1. **Observe**
2. **Assess**
3. **Decide**
4. **Act**
5. **Audit**

### Main modules

- `raasa/core/telemetry.py` -> Observer
- `raasa/core/features.py` -> Feature extractor
- `raasa/core/risk_model.py` -> Risk assessor
- `raasa/core/policy.py` -> Policy reasoner
- `raasa/core/enforcement.py` -> Action enforcer
- `raasa/core/logger.py` -> Audit logger
- `raasa/core/app.py` -> Controller entrypoint

## 6. Start-to-Finish Project Story

This section explains each major step, the reason for it, and the approach used.

## 6.1 Step 1: Define the threat model

### Challenge

The system could not protect against every attack type in v1.

### Why this step was needed

In cloud security, a weak or vague threat model creates bad claims. The project needed a small and testable set of workload classes.

### Approach used

The project created a compact **threat-to-signal-to-action matrix**:

- `benign_steady`
- `benign_bursty`
- `suspicious`
- `malicious_pattern`

Each class was linked to:

- observable signals
- expected risk pattern
- intended tier response
- known residual limits

### Result

The project got a clean research frame. This made the experiments easier to design and easier to explain.

### Files

- `docs/threat_matrix.md`

## 6.2 Step 2: Build a modular security controller

### Challenge

A security controller can become hard to change if telemetry, reasoning, and enforcement are mixed together.

### Why this step was needed

The project needed clear separation of duties. This is a key design rule in secure cloud systems.

### Approach used

RAASA split the logic into five roles:

- Observer
- Risk Assessor
- Policy Reasoner
- Action Enforcer
- Audit Logger

The shared data contracts are stored in `raasa/core/models.py`.

### Result

The code became easier to test, easier to extend, and easier to move toward Kubernetes later.

### Files

- `raasa/core/models.py`
- `raasa/core/app.py`

## 6.3 Step 3: Add YAML configuration and guardrails

### Challenge

The system needed repeatable settings for policy, telemetry, and live experiments.

### Why this step was needed

Security research needs controlled runs. Hard-coded values make tuning and comparison difficult.

### Approach used

The project stores settings in YAML files and loads them with `PyYAML`.

Important config areas:

- controller timing
- risk weights
- policy thresholds
- CPU caps by tier
- live run guardrails
- optional ML model path

### Result

The project can switch between baseline and tuned profiles without changing code.

### Files

- `raasa/core/config.py`
- `raasa/configs/config.yaml`
- `raasa/configs/config_tuned_small.yaml`
- `raasa/configs/config_tuned_small_linear.yaml`

## 6.4 Step 4: Collect runtime telemetry from Docker

### Challenge

The controller needed real signals from live containers.

### Why this step was needed

Without runtime telemetry, the system cannot do adaptive sandboxing.

### Approach used

The Docker observer calls:

- `docker stats`
- `docker inspect`
- `docker top`

It collects:

- CPU percent
- memory percent
- process count
- network receive bytes
- network transmit bytes
- metadata labels

It also keeps the previous network counters, so it can compute **per-tick delta** instead of raw totals.

When Docker is not available, the observer returns safe fallback values.

### Result

The project can read live container behavior and still fail safely if telemetry breaks.

### Files

- `raasa/core/telemetry.py`

## 6.5 Step 5: Normalize telemetry into bounded signals

### Challenge

Raw telemetry uses different units. CPU is in percent, network is in bytes, and process count is an integer.

### Why this step was needed

A risk engine needs comparable inputs.

### Approach used

`FeatureExtractor` converts raw values into bounded signals in `[0,1]`:

- `cpu_signal`
- `memory_signal`
- `process_signal`
- `network_signal`
- `syscall_signal`

Caps are used for process, network, and syscall values.

### Result

The next stage gets simple, bounded, and stable input.

### Files

- `raasa/core/features.py`

## 6.6 Step 6: Build the first risk model

### Challenge

The project needed a risk score that is easy to explain and easy to test.

### Why this step was needed

For a v1 prototype, a simple model is safer than a complex black box. It also gives clearer audit explanations.

### Approach used

The first path uses a **weighted linear model**:

`risk = sum(weight * feature)`

The module also computes:

- `confidence_score`
- `risk_trend`

Confidence is based on recent history. Trend shows if risk is going up or down.

### Result

The system can explain why a container looks risky and can use history, not only one single tick.

### Files

- `raasa/core/risk_model.py`

## 6.7 Step 7: Add safe policy reasoning

### Challenge

A naive controller can oscillate between tiers and harm good workloads.

### Why this step was needed

Adaptive security is only useful if it is also stable and safe.

### Approach used

The policy engine uses several safety controls:

- **hysteresis**
- **cooldown**
- **L3 confidence gate**
- **low-risk streak requirement**
- **safe hold on invalid data**

It maps risk into three tiers:

- `L1` -> baseline
- `L2` -> moderate containment
- `L3` -> strict containment

It also supports **operator overrides** from a JSON file.

### Result

The system avoids many false moves and keeps the controller predictable.

### Files

- `raasa/core/policy.py`
- `raasa/core/override.py`

## 6.8 Step 8: Enforce containment with CPU throttling

### Challenge

The project needed a real action, not only a score.

### Why this step was needed

Detection-only systems can see a problem but still leave the workload free to run.

### Approach used

The action enforcer runs:

- `docker update --cpus`

Tier mapping:

- `L1` -> `1.0`
- `L2` -> `0.5`
- `L3` -> `0.2`

The enforcer is idempotent. It skips repeated actions if the same tier is already applied.

### Result

RAASA closes the control loop and becomes an actual containment system.

### Files

- `raasa/core/enforcement.py`

## 6.9 Step 9: Add full audit logging

### Challenge

Security systems need evidence. A decision without a log is hard to trust.

### Why this step was needed

Auditability is critical in cloud security, incident review, and research papers.

### Approach used

The logger writes one JSONL record per container per tick. Each record includes:

- raw telemetry
- normalized features
- risk
- confidence
- trend
- previous tier
- proposed tier
- applied tier
- reason
- metadata

### Result

The project has strong traceability. This also powers metrics, plots, and later analysis.

### Files

- `raasa/core/logger.py`
- `raasa/logs/`

## 6.10 Step 10: Design realistic workload scenarios

### Challenge

A controller cannot be judged without controlled workload mixes.

### Why this step was needed

The project needed repeatable, labeled scenarios for baseline and adaptive comparison.

### Approach used

The project built workload specs and scenario layouts:

- `small`
- `small_tuned`
- `network_test`
- `syscall_test`
- `benign_only`
- `medium`
- `large`

The workloads use labeled Docker containers with expected tiers.

### Result

The project can run the same security story many times and compare modes fairly.

### Files

- `raasa/workloads/catalog.py`
- `raasa/experiments/scenarios.py`

## 6.11 Step 11: Build the experiment runner

### Challenge

Manual testing is slow and error-prone.

### Why this step was needed

Research artifacts need consistent start, run, cleanup, and summary steps.

### Approach used

`run_experiment.py`:

- starts labeled containers
- applies live guardrails
- runs the controller for a fixed number of iterations
- cleans up all managed containers
- writes summary metrics
- appends a manifest row

Supported modes:

- `static_L1`
- `static_L3`
- `detection_only`
- `raasa`

### Result

The whole pipeline became reproducible.

### Files

- `raasa/experiments/run_experiment.py`

## 6.12 Step 12: Measure results with metrics and plots

### Challenge

The project needed proof, not only logs.

### Why this step was needed

Security research needs measurable outcomes.

### Approach used

The metrics module computes:

- precision
- recall
- false positive rate
- adaptation latency
- containment pressure
- benign restriction rate
- malicious containment rate
- switching rate
- explanation coverage
- tier occupancy

The plotting module generates paper-ready PNG figures.

### Result

The project can compare adaptive RAASA against static baselines in a clear way.

### Files

- `raasa/analysis/metrics.py`
- `raasa/analysis/plots.py`
- `raasa/plots/`
- `raasa/plots_medium/`

## 6.13 Step 13: Fix the first recall gap

### Challenge

Early live runs showed a key gap: the malicious workload often reached `L2` but not `L3`.

### Why this step was needed

If a clear malicious pattern does not reach strict containment, the controller is under-reacting.

### Approach used

The project used log analysis and found two main issues:

- config values were not always passed into the inner controller
- the confidence gate and thresholds were too tight for the bounded workload

The team then tuned:

- `l2_max`
- `l3_min_confidence`
- `cooldown_seconds`
- `low_risk_streak_required`
- `hysteresis_band`

### Result

The tuned profile improved recall while keeping benign cost low.

### Files

- `docs/live_experiment_notes.md`
- `docs/tuning_notes.md`
- `raasa/configs/config_tuned_small.yaml`

## 6.14 Step 14: Prove that detection alone is not enough

### Challenge

A reviewer can ask: “What if logging is enough? Why act?”

### Why this step was needed

The project needed to isolate the value of **actionable adaptation**.

### Approach used

The team added `detection_only` mode. In this mode:

- the reasoner still proposes a tier
- the applied tier is forced to stay at the old level
- no real containment action happens

### Result

This mode showed an important lesson: detection without enforcement behaves like an undefended `L1` path.

### Files

- `raasa/core/app.py`
- `docs/live_experiment_notes.md`

## 6.15 Step 15: Add network-aware detection

### Challenge

CPU-only signals can miss low-CPU, high-network abuse.

### Why this step was needed

In cloud and sandbox security, data movement is a major threat. A system that ignores network behavior has a serious blind spot.

### Approach used

The project added:

- `network_rx_bytes`
- `network_tx_bytes`
- normalized `network_signal`
- a `malicious_network_heavy` workload

### Result

The controller could now react to bandwidth-heavy abuse, not only CPU abuse.

### Files

- `raasa/core/telemetry.py`
- `raasa/core/features.py`
- `raasa/workloads/catalog.py`
- `docs/live_experiment_notes.md`

## 6.16 Step 16: Try a learned risk model

### Challenge

Linear weights are easy to explain, but they may not capture all behavior patterns.

### Why this step was needed

A learned model can, in theory, detect unknown or unusual combinations of signals.

### Approach used

The project trained an **Isolation Forest** on benign feature vectors:

- training script in `raasa/ml/train_iforest.py`
- model file in `raasa/models/iforest_latest.pkl`
- optional ML path in `RiskAssessor`

The code also includes graceful fallback to the linear model.

### Result

The ML path works as an implementation feature, but the project documentation is honest: the current live ablation showed that the tuned linear controller performed better than the Isolation Forest for the key evaluation story.

This is an important research decision. The team did not keep a weak claim just because ML sounded advanced.

### Files

- `raasa/ml/train_iforest.py`
- `raasa/models/iforest_latest.pkl`
- `tests/test_learned_model.py`
- `docs/live_experiment_notes.md`
- `raasa/configs/config_tuned_small_linear.yaml`

## 6.17 Step 17: Prepare a Kubernetes path

### Challenge

A Docker-only prototype has limited cloud relevance.

### Why this step was needed

Real cloud security work often needs a Kubernetes design.

### Approach used

The project created:

- `BaseObserver` abstraction
- `ObserverK8s` backend
- `DaemonSet` deployment file
- an eBPF syscall integration contract
- node-local pod discovery through `spec.nodeName`
- bounded telemetry degradation paths for Metrics API failures

The Kubernetes path keeps the same upper-layer controller logic.

### Result

The architecture now has a clear path from single-host prototype to node-level cloud deployment.

### Files

- `raasa/core/base_observer.py`
- `raasa/k8s/observer_k8s.py`
- `raasa/k8s/daemonset.yaml`
- `raasa/k8s/Dockerfile`

## 6.18 Step 18: Add bounded LLM advice for edge cases

### Challenge

Some risk cases sit near policy boundaries.

### Why this step was needed

The team wanted a path for higher-level reasoning without letting the LLM control the whole system.

### Approach used

The project added `LLMPolicyAdvisor`:

- only used on ambiguous cases
- strict timeout
- fallback path
- mock logic for local testing

This is a bounded design. The main policy engine still owns the default decision path.

### Result

The project now includes a next-step reasoning layer, while keeping the core controller deterministic.

### Files

- `raasa/core/llm_advisor.py`
- `raasa/core/policy.py`

## 6.19 Step 19: Build a strong test suite

### Challenge

Security logic can fail in small ways that are hard to see by eye.

### Why this step was needed

The project needed tests for:

- bounded signals
- risk math
- policy safety rules
- experiment layouts
- metrics
- ML fallback
- Kubernetes adapter behavior

### Approach used

The repo includes unit tests across the main subsystems.

### Result

The project has wide functional coverage and faster regression detection.

### Files

- `tests/test_reasoning.py`
- `tests/test_analysis.py`
- `tests/test_experiments.py`
- `tests/test_learned_model.py`
- `tests/test_k8s_observer.py`
- `tests/test_override.py`

## 7. Current Results Summary

Based on the project notes and artifacts:

- `static_L1` is too weak. It misses malicious behavior.
- `static_L3` is too strict. It harms benign workloads.
- Adaptive RAASA gives a better balance.
- The strongest current evaluation profile is the **tuned linear** controller, not the current ML profile.
- The project was evaluated at `3`, `10`, and `20` containers.

### Small scenario

The tuned adaptive profile improved recall and kept low benign cost.

### Medium scenario

The tuned linear controller scaled better than the earlier ML-oriented path.

### Large scenario

The project completed a `20` container live run with full logs and bounded benign cost.

### Key lesson

The main value of RAASA is not “ML by itself.”  
The main value is the **closed-loop adaptive containment design**.

## 8. Why the Design Is Strong for Cloud and Sandbox Security

The project has several strong design choices:

- **bounded tiers** make action predictable
- **safe defaults** reduce unsafe failure states
- **audit logs** support review and trust
- **guardrails** reduce experiment risk
- **modular architecture** supports later cloud growth
- **detection + action** closes the loop

These are good security engineering choices for a research prototype.

## 9. Current Gaps and Limits

The project is strong, but not complete.

### Technical limits

- main live enforcement is CPU-only
- Kubernetes validation is still single-node and not yet multi-tenant
- Kubernetes telemetry is stronger now, but the Metrics API path still needs more repeated live-stress evidence
- syscall input in Docker mode is simulated, not true eBPF capture
- the LLM advisor is optional and not the main decision engine

### Research limits

- v1 is not a full production platform
- the current learned model does not beat the tuned linear controller in the key ablation
- some attack classes still need richer network and kernel signals

## 10. Verification Status in This Workspace

I checked the repo and its test suite state.

### What is present

- source code for controller, experiments, analysis, ML, and Kubernetes path
- research notes and roadmap documents
- generated plots and model artifacts
- unit tests across core areas

### Test run note

A bundled Python runtime was used to run the suite in this workspace on `2026-05-11`.

Observed result:

- `97` tests passed
- `3` tests were skipped
- `14` warnings were emitted, mainly dependency deprecation warnings from `matplotlib` and `pyparsing`

The observer coverage now includes node-local pod discovery and timeout-driven Metrics API cooldown fallback, so the current suite is a much better regression guard for the Kubernetes path than before.

## 11. Practical Run Flow

This is the project flow from start to finish in simple form:

1. Define scope and threat classes.
2. Start containers for a chosen scenario.
3. Collect Docker telemetry.
4. Normalize telemetry into bounded signals.
5. Compute risk, confidence, and trend.
6. Apply safe policy rules.
7. Enforce `L1`, `L2`, or `L3`.
8. Write JSONL audit logs.
9. Compute summary metrics.
10. Generate plots and compare modes.
11. Tune thresholds if the behavior is weak.
12. Record limits and roadmap items honestly.

## 12. Recommended Next Steps

These are the most useful next moves:

1. Deploy the latest observer hardening to the live AWS node and measure whether it reduces repeated Metrics API timeout pressure.
2. Keep the tuned linear controller as the main evaluation baseline.
3. Expand from single-node validation to multi-node and multi-tenant testing.
4. Replace simulated syscall input with real eBPF data in live runs.
5. Add operator-facing review tools such as a dashboard or approval path.
6. Continue large-scale and adversarial testing.

## 13. Final Assessment

RAASA is a well-structured security research prototype. It solves a real cloud and sandbox security problem: static containment is too weak or too strict. The project answers this with a closed-loop controller that observes workload behavior, reasons about risk, applies adaptive containment, and records every decision.

The most important success is not just the code. The real success is the **research discipline**:

- narrow scope
- real evidence
- clear audit trail
- safe control logic
- honest reporting when one approach is weaker than another

That makes this project useful for both academic work and future cloud-security engineering.
