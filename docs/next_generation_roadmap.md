# Next-Generation RAASA Roadmap

This document converts the current project review into an engineering roadmap.
It is intentionally focused on the non-paper work that most improves RAASA's
real relevance and defensibility.

The main principle is simple:

do not expand scope faster than the evidence base.

## Progress update

As of May 11, 2026, the first `NOW` block has materially advanced:

- Kubernetes telemetry hardening is no longer just planned. The observer now
  records per-signal source and freshness, supports bounded stale Metrics API
  fallback, and distinguishes degraded states in audit metadata.
- Degraded-mode policy is now explicit in controller decisions: partial
  telemetry can cap fresh `L3` escalation and block relaxation until signals
  recover, rather than silently collapsing into ambiguous behavior.
- The truthful default story is frozen in config and AWS deployment flow:
  tuned linear control, probe-backed syscall telemetry, and ML disabled by
  default for the main paper path.
- The `L3` contract is now explicit as hard containment in policy, logging,
  and threat-model documentation.
- Two live AWS fixes were validated end to end:
  the cAdvisor Prometheus timestamp parser bug was corrected, restoring
  `telemetry_status=complete`, and the controller now waits for privileged
  sidecar readiness before the first loop to avoid startup IPC failures.

This means the next highest-value work has shifted from basic telemetry truth
to benchmark expansion and broader validation discipline.

## 1. What "v2 candidate" means

RAASA should be treated as a stronger v2 candidate only after it satisfies all
of the following:

- the Kubernetes observer path behaves predictably when `metrics.k8s.io`
  becomes slow, unavailable, or inconsistent
- degraded-mode behavior is explicit, tested, and visible in audit logs
- the tuned linear controller is frozen as the truthful default path across
  configs, scripts, and docs
- `L3` is described and implemented consistently as the current live
  hard-containment contract
- AWS validation can be rerun without experimental ambiguity
- the next benchmark suite includes agent-like threat behavior, not only
  generic CPU abuse

Until then, RAASA is a strong research prototype, but not yet a clean v2.

## 2. Execution Order

The work should happen in this order:

1. telemetry hardening
2. degraded-mode policy
3. truthful default configuration
4. `L3` contract cleanup
5. AI-agent benchmark expansion
6. broader AWS validation
7. privileged-boundary hardening
8. packaging and operator polish

This order matters. The project should not push the ML or LLM story further
until the observer and enforcement path are more stable.

## 3. NOW

These are the highest-priority tasks.

### 3.1 Harden Kubernetes telemetry

Goal:

make the Kubernetes observer path resilient enough that controller behavior is
still interpretable when the control plane is unhealthy.

Primary repo areas:

- [raasa/k8s/observer_k8s.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/k8s/observer_k8s.py)
- [tests/test_k8s_observer.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/tests/test_k8s_observer.py)
- [AWS_Results_26_april/AWS_Phase0_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/AWS_Phase0_Evaluation_Report.md)
- [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)

Concrete tasks:

- define a strict source-priority order for each signal:
  direct probe or cgroup path, Metrics API, cached prior value, safe fallback
- tag each collected signal with freshness and source status
- distinguish these cases in code and logs:
  `metrics_ok`, `metrics_stale`, `metrics_timeout`, `metrics_missing`,
  `probe_ok`, `probe_missing`
- avoid collapsing all failure modes into `0.0`
- keep observer output bounded and explicit when a source is degraded

Exit criteria:

- observer outputs remain structurally valid under metrics failure
- audit rows clearly show which signals were live, stale, or unavailable
- unit coverage exists for timeout, missing-data, and mixed-source cases

### 3.2 Define degraded-mode policy

Goal:

make controller behavior deterministic when telemetry is partial.

Primary repo areas:

- [raasa/core/config.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/config.py)
- [raasa/core/telemetry.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/telemetry.py)
- [raasa/core/approval.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/approval.py)
- [raasa/core/override.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/override.py)

Concrete tasks:

- decide what the controller should do under each degraded-mode condition
- encode that behavior in config rather than leaving it implicit in heuristics
- define whether the system should:
  hold tier, relax tier, or require stronger evidence before escalation
- log degraded-mode decisions as first-class audit reasons
- preserve operator override and approval behavior even when telemetry is weak

Exit criteria:

- degraded-mode policy is documented and testable
- audit logs explain why a tier was held or relaxed under partial telemetry
- no reviewer needs to infer degraded behavior from source code alone

### 3.3 Freeze the truthful default story in code

Goal:

prevent the repo from drifting into misleading controller or backend states.

Primary repo areas:

- [raasa/core/config.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/config.py)
- [raasa/scripts/apply_raasa_config_to_aws.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/apply_raasa_config_to_aws.ps1)
- [raasa/scripts/collect_phase1g_calibration_snapshot.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/collect_phase1g_calibration_snapshot.ps1)
- [README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/README.md)

Concrete tasks:

- make the tuned linear controller the explicit default path
- ensure cloud scripts do not accidentally roll the wrong config or image
- make probe-path defaults match the live K8s deployment reality
- expose one canonical local path and one canonical AWS path
- reject or loudly log contradictory runtime states, such as ML enabled while
  audit records report linear control

Exit criteria:

- default configs, scripts, and docs tell the same story
- a fresh user can reproduce the main path without guessing which controller is
  the real baseline

### 3.4 Turn `L3` into a formal enforcement contract

Goal:

make `L3` semantics stable, explicit, and testable.

Primary repo areas:

- [raasa/k8s/enforcer_sidecar.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/k8s/enforcer_sidecar.py)
- [tests/test_enforcer_sidecar.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/tests/test_enforcer_sidecar.py)
- [docs/threat_matrix.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/threat_matrix.md)
- [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)

Concrete tasks:

- document `L1`, `L2`, and `L3` as explicit enforcement profiles
- align code comments, docs, and scripts with the live finding that current
  `L3` acts as hard containment
- verify that `L2` and `L3` remain distinct in both logic and effect
- stop describing current `L3` as graceful shaping unless a future validation
  proves that again

Exit criteria:

- `L3` has one current meaning in code, tests, docs, and results
- reviewers can tell the difference between `L2` degradation and `L3`
  containment

## 4. NEXT

These tasks should start only after the NOW block is stable.

### 4.1 Build agent-specific benchmark scenarios

Goal:

make RAASA relevant to the next wave of runtime-security problems rather than
only to generic container abuse.

Primary repo areas:

- [raasa/experiments/scenarios.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/experiments/scenarios.py)
- [raasa/workloads/catalog.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/workloads/catalog.py)
- [raasa/experiments/run_experiment.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/experiments/run_experiment.py)
- [docs/threat_matrix.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/threat_matrix.md)

Concrete tasks:

- add workloads for destructive shell behavior
- add suspicious dependency-install patterns
- add CI/CD-style network exfiltration behavior
- add prompt-driven tool misuse or runaway automation loops
- define expected tier transitions for those workloads before running them

Exit criteria:

- the benchmark suite includes at least one credible agent-like misuse path
- threat classes are still bounded and measurable, not hand-wavy

### 4.2 Expand validation breadth on AWS

Goal:

turn one strong live success path into repeatable validation, not a single
hero run.

Primary repo areas:

- [raasa/scripts/run_closed_loop_soak_aws.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/run_closed_loop_soak_aws.ps1)
- [raasa/scripts/closed_loop_test.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/closed_loop_test.sh)
- [raasa/scripts/run_phase1d_resolution_validation.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/run_phase1d_resolution_validation.ps1)
- [AWS_Results_26_april](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april)

Concrete tasks:

- rerun the canonical AWS validation after telemetry fixes
- preserve both success and failure bundles with the same structure
- measure whether the tuned controller still keeps benign workloads at the
  intended tier under stress
- explicitly capture overhead, false positives, and tier churn in live runs

Exit criteria:

- AWS evidence bundles become comparable across reruns
- changes in behavior are diagnosable from preserved artifacts, not memory

### 4.3 Harden the privileged boundary

Goal:

make the sidecar architecture as defensible operationally as it is
conceptually.

Primary repo areas:

- [raasa/k8s/enforcer_sidecar.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/k8s/enforcer_sidecar.py)
- [raasa/core/approval.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/approval.py)
- [raasa/core/override.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/core/override.py)

Concrete tasks:

- narrow the accepted IPC schema to the smallest useful action set
- make rejected or malformed commands auditable
- review container privileges, host mounts, and network assumptions
- confirm that the enforcer can do its job without hidden extra privilege

Exit criteria:

- the privileged boundary is easy to explain and difficult to misuse
- every privileged action is attributable to a narrow, explicit request

### 4.4 Clean packaging and canonical execution

Goal:

reduce repo friction so engineering progress is easier to validate.

Primary repo areas:

- [pyproject.toml](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/pyproject.toml)
- [README.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/README.md)
- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- [docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)

Concrete tasks:

- keep dependency metadata synchronized
- remove stale or conflicting run instructions
- document one canonical result path per major experiment type
- reduce duplicate narrative docs where possible

Exit criteria:

- the code is no longer ahead of the packaging story
- reproducibility friction is lower for both reviewers and future you

## 5. LATER

These are worthwhile, but they should not preempt the higher-value blockers.

### 5.1 Revisit the ML path

Only revisit Isolation Forest or richer learned models after the primary
telemetry and controller path are stable.

Why:

- current evidence still favors the tuned linear controller
- otherwise the project risks optimizing a secondary path before stabilizing
  the main system

### 5.2 Add richer Kubernetes-native controls

Potential future controls:

- NetworkPolicy integration
- quarantine namespaces
- OPA or Kyverno policy hooks
- seccomp or AppArmor profiles
- more explicit egress isolation modes

These are valuable, but they should extend a stable control plane, not distract
from fixing it.

### 5.3 Move beyond single-node validation

Longer-term validation should include:

- multi-node K3s or Kubernetes
- more realistic pod placement variation
- more explicit tenant separation assumptions
- stronger interference testing

### 5.4 Operator-facing surfaces

Only after the controller path is cleaner:

- dashboards
- approval consoles
- richer audit review tools
- experiment replay tooling

## 6. What Not To Do Yet

These are tempting but premature:

- do not lead with the ML story
- do not lead with the LLM advisor story
- do not broaden into generic "AI security platform" claims
- do not add many new enforcement backends before the observer path is stable
- do not treat one AWS success bundle as broad production evidence

## 7. Suggested Working Cadence

The best practical cadence is:

1. local unit and logic hardening
2. one targeted AWS rerun
3. artifact capture
4. interpretation and config adjustment
5. repeat

This is better than running long exploratory cloud loops without first
stabilizing the local logic and harness.

## 8. Short Version

If the project is judged by relevance to today and tomorrow, the most important
remaining work is not "add more AI." It is:

- make telemetry resilient
- make degraded behavior explicit
- freeze one truthful default path
- formalize `L3`
- test agent-like misuse workloads

That is the shortest path from strong prototype to serious next-stage system.
