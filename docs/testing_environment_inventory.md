# Testing Environment Inventory

This document consolidates what the current project records about testing environments, execution resources, and validation scope for RAASA. It is intended to be the starting point for future stress testing.

## Short answer

The current project status does **not** state all testing-environment information in one place.

What is already documented:

- the main local test path uses Docker/Docker Desktop
- the cloud path uses AWS EC2 with Ubuntu, K3s, Tetragon eBPF, and the Kubernetes Metrics API
- the main workload scales are 3, 10, and 20 containers
- some live AWS pod inventories and host identity were captured
- a local environment snapshot is now recorded in [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)

What is missing or inconsistent:

- no single canonical document listing all local and AWS resources together
- some old docs are stale, especially the unit-test count
- several AWS console details were not preserved in the repo, such as region, AMI ID, disk size, security groups, and exact instance metadata beyond host/IP and instance family
- exact local host hardware was not recorded

## Current documentation status

The testing story is spread across:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- [docs/live_experiment_notes.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/live_experiment_notes.md)
- [docs/RAASA_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/RAASA_Evaluation_Report.md)
- [.github/workflows/pytest.yml](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/.github/workflows/pytest.yml)
- [bootstrap_aws.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/bootstrap_aws.sh)
- [bootstrap_k8s_ebpf.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/bootstrap_k8s_ebpf.sh)
- [run_aws_experiments.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/run_aws_experiments.sh)
- [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)
- live AWS capture files under [AWS_Results_26_april](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april)

That is enough to reconstruct most of the story, but not enough to say the project already had a clean testing-resource inventory.

## Local testing environment

### Confirmed local platform and tooling

- Primary local execution path: Docker-backed experiments
- Platform described in docs: Windows with Docker Desktop, using the `desktop-linux` backend
- Alternate documented support: Linux
- Local telemetry source for v1: `docker stats`
- Local enforcement path for v1: Docker resource controls via runtime container updates
- Captured local snapshot (`2026-05-11`): Windows 11 (`10.0.26200`), Python `3.13.5`, Docker `29.2.0`, `8` logical CPUs / `4` physical CPUs, `16948039680` bytes RAM

Evidence:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- [docs/live_experiment_notes.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/live_experiment_notes.md)
- [raasa/experiments/run_experiment.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/experiments/run_experiment.py)
- [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)

### Python and libraries

Confirmed runtime/development dependencies in the repo:

- Python requirement in package metadata: `>=3.11`
- `matplotlib==3.10.0`
- `seaborn==0.13.2`
- `numpy==2.4.4`
- `scikit-learn==1.6.1`
- `joblib==1.4.2`
- `psutil==6.1.1`
- `PyYAML==6.0.2`
- `pytest==8.4.1`
- `kubernetes>=29.0.0`
- `prometheus_client>=0.20.0`

Evidence:

- [pyproject.toml](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/pyproject.toml)
- [requirements.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/requirements.txt)

### Local workload scales that were tested

Confirmed scenario sizes:

- `small`: 3 containers
- `small_tuned`: 3 containers
- `agent_misuse`: 3 containers
- `medium`: 10 containers
- `large`: 20 containers

Scenario composition:

- `small_tuned`: 1 `benign_steady`, 1 `benign_bursty`, 1 `malicious_pattern_heavy`
- `agent_misuse`: 1 `benign_steady`, 1 `benign_bursty`, 1 `agent_dependency_exfiltration`
  - local smoke (`2026-05-12`): `run_codex_agent_misuse_l3_smoke.summary.json`
    reported `strict_malicious_containment_rate=1.0` over 4 Docker iterations.
- `medium`: 4 `benign_steady`, 2 `benign_bursty`, 2 `suspicious`, 2 `malicious_pattern`
- `large`: 8 `benign_steady`, 4 `benign_bursty`, 4 `suspicious`, 4 `malicious_pattern`

Evidence:

- [raasa/experiments/scenarios.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/experiments/scenarios.py)

### Local workload images used

Confirmed images from the workload catalog:

- `nginx:1.27-alpine`
- `python:3.12-alpine`
- `alpine:3`

Evidence:

- [raasa/workloads/catalog.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/workloads/catalog.py)

### Local guardrails recorded in live notes

The repo explicitly records these local live-run conditions:

- guarded containers only
- initial CPU cap: `0.5`
- memory limit: `256MB`
- PID limit: `64`
- short run window: `30s`
- RAASA-managed containers cleaned up after each run

Evidence:

- [docs/live_experiment_notes.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/live_experiment_notes.md)

### Local automated test suite status

Current verified state in this workspace:

- `124 passed, 3 skipped` locally via `pytest -q` on `2026-05-14`
- 14 warnings, mainly dependency deprecation warnings from `matplotlib`/`pyparsing`
- observer regression coverage now includes node-local pod discovery and
  Metrics API timeout/cached-fallback behavior
- local secret scan is available through
  [raasa/scripts/secret_scan.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/secret_scan.py)

Documentation note:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md) was synchronized with this verified test state on `2026-05-12`
- live `pytest` output remains the source of truth if future code changes alter these numbers again

Confirmed test files present:

- `test_capture_local_environment.py`
- `test_analysis.py`
- `test_enforcement_logger.py`
- `test_enforcer_sidecar.py`
- `test_experiments.py`
- `test_ipc.py`
- `test_k8s_observer.py`
- `test_learned_model.py`
- `test_override.py`
- `test_reasoning.py`
- `test_telemetry.py`

Evidence:

- [tests](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/tests)
- [pytest.ini](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/pytest.ini)

### Local details that are still missing

The repo does **not** clearly record:

- whether all result files came from one local machine or multiple local machines

The following details are now captured explicitly:

- local host OS version in [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)
- local CPU model and logical/physical counts in [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)
- local RAM size in [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)
- local Docker version in [docs/local_environment_snapshot.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/local_environment_snapshot.json)

## AWS testing environment

### Latest free-tier single-host campaign

The 2026-05-13/2026-05-14 free-tier campaign used one cleaned AWS account state
and one single-node EC2/K3s host:

- AWS region captured via CloudShell: `us-east-1`
- intended retained EC2 instance: `raasa-free-tier-node` (`i-0588bfb84f8c0215e`)
- extra stopped instance removed before restart: `RAASA-Research-VM`
  (`i-0a151cd7eef140ee3`)
- active load balancer removed before restart: `startup-web-app`
- Elastic IP allocations removed before restart
- remaining attached volume after cleanup: `vol-091e4b66e4f23a92e`, `30 GiB`, `gp3`
- instance family selected by the user: `m7i-flex.large`
- node hostname across both public-IP windows: `ip-172-31-34-138`
- public host/IP during fresh bootstrap window: `54.224.245.180`
- public host/IP after restart for the mini-campaign: `54.164.19.115`
- OS reported by K3s: Ubuntu 26.04 LTS
- kernel string: `Linux ip-172-31-34-138 7.0.0-1004-aws ... x86_64 GNU/Linux`
- K3s version: `v1.35.4+k3s1`
- container runtime: `containerd://2.2.3-k3s1`
- security group captured during restart: `sg-0d7d64818ce5c0302`
- RAASA agent pods observed during the campaign: `raasa-agent-klsbr`,
  `raasa-agent-w6bgk`, and post-restart `raasa-agent-hxm96`

Evidence:

- [AWS_Results_26_april/bootstrap_freetier_instance_2026_05_13_082837](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/bootstrap_freetier_instance_2026_05_13_082837)
- [AWS_Results_26_april/live_instance_validation_2026_05_13_083219](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_13_083219)
- [AWS_Results_26_april/closed_loop_soak_2026_05_13_083459](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_13_083459)
- [AWS_Results_26_april/adversarial_matrix_repeated_freetier_resumed_2026_05_13_094157](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/adversarial_matrix_repeated_freetier_resumed_2026_05_13_094157)
- [AWS_Results_26_april/failure_injection_2026_05_13_104329](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/failure_injection_2026_05_13_104329)
- [AWS_Results_26_april/metrics_api_stress_probe_2026_05_13_105523](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/metrics_api_stress_probe_2026_05_13_105523)
- [AWS_Results_26_april/phase1d_resolution_validation_2026_05_13_105824](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1d_resolution_validation_2026_05_13_105824)
- [AWS_Results_26_april/live_instance_validation_2026_05_14_082835](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_14_082835)
- [AWS_Results_26_april/closed_loop_soak_2026_05_14_082943](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_14_082943)
- [AWS_Results_26_april/adversarial_matrix_repeated_2026_05_14_083925](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/adversarial_matrix_repeated_2026_05_14_083925)
- [AWS_Results_26_april/failure_injection_2026_05_14_091158](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/failure_injection_2026_05_14_091158)
- [AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_091656](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_091656)
- [AWS_Results_26_april/cleanup_verification_2026_05_14_092254](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/cleanup_verification_2026_05_14_092254)

Results:

- live sanity capture succeeded against default test pods
- closed-loop soak passed `5 / 5` cycles
- repeated adversarial matrix passed `5 / 5` runs, with all five workloads
  passing each run
- failure injection captured explicit partial telemetry during Metrics API
  outage and syscall probe pause, then recovered the agent pod
- the 2026-05-14 harness-tightened rerun recorded the fake-pod IPC response
  as clean `ERR` without a manual retry note
- Metrics API stress ran for `45 s` with `8` workers and `total_failures=0`
- L3 containment validation resolved pod interfaces with `fallback_count=0`
  and collapsed measured L3 traffic to `0 B/s`
- after an account cleanup and host restart, the bounded mini-campaign on
  `54.164.19.115` revalidated live sanity, passed a `3 / 3` soak, passed a
  `1 / 1` five-workload matrix smoke, preserved `45` complete metrics-stress
  audit rows with `total_failures=0`, and ended with only K3s system pods plus
  `raasa-agent-hxm96` running
- post-test cleanup was verified in
  [AWS_Results_26_april/cleanup_verification_2026_05_13_121927](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/cleanup_verification_2026_05_13_121927):
  no adversarial/demo/benchmark/default test workloads remained, and only K3s
  system pods plus the RAASA DaemonSet were running

Interpretation:

- this is useful evidence that the project can be bootstrapped and validated
  as a single-node free-tier-conscious EC2/K3s research prototype
- this is not production-readiness evidence and does not support multi-node,
  multi-tenant, or EKS-scale claims
- account-level preflight/cleanup inventory was captured through operator-run
  AWS CloudShell output rather than this workstation's expired local AWS
  credentials

### Fresh-account credits-only replay and bounded multi-node K3s campaign

The 2026-05-14 fresh-account expansion campaign advanced the evidence from a
single-node replay to a bounded 3-node K3s validation path on a clean AWS Free
plan account.

Fresh-account gate:

- AWS plan state captured in CloudShell: `FREE`, `ACTIVE`
- remaining AWS-issued credits at preflight: `139.92 USD`
- initial CloudShell inventory was clean: no EC2 instances, EBS volumes,
  Elastic IPs, NAT Gateways, load balancers, or EKS clusters

Fresh-account single-node replay:

- instance ID: `i-0ae832987f61bf5e2`
- public host/IP: `13.219.221.75`
- instance type: `m7i-flex.large`
- root EBS: `30 GiB gp3`, delete on termination
- security group: `sg-0a235c5878f10a800`
- key name: `raasa-fresh-single`
- live replay evidence:
  [AWS_Results_26_april/live_instance_validation_2026_05_14_111436](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_14_111436)
- stable replay soak evidence:
  [AWS_Results_26_april/closed_loop_soak_2026_05_14_112413](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_14_112413)
- result: the clean-account single-node replay passed after a steady-state
  rerun, preserving a `2 / 2` soak bundle; the first attempt showed a
  warm-start wobble and is retained as historical evidence

Fresh-account multi-node K3s cluster:

- control-plane instance: `i-0dc58aea73b59ef3c`
  - public IP: `44.200.44.207`
  - private IP: `172.31.12.91`
- worker-a instance: `i-0eec377ced93d4c30`
  - public IP: `52.1.139.250`
  - private IP: `172.31.87.199`
- worker-b instance: `i-03a4f55da55687a29`
  - public IP: `3.90.41.117`
  - private IP: `172.31.27.62`
- instance type on all three nodes: `m7i-flex.large`
- root EBS on all three nodes: `30 GiB gp3`
- shared security group: `sg-0615be39526b79716`
- required security-group shape:
  - SSH `22/tcp` from the workstation `/32`
  - self-referencing `All traffic` ingress so K3s nodes can talk to each other
- K3s version: `v1.35.4+k3s1`
- OS image: Ubuntu `24.04.4 LTS`
- kernel version: `6.17.0-1013-aws`
- container runtime: `containerd://2.2.3-k3s1`

Evidence:

- node inventory before drain:
  [AWS_Results_26_april/multinode_reschedule_validation_2026_05_14_151103/nodes_before.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/multinode_reschedule_validation_2026_05_14_151103/nodes_before.txt)
- multi-node soak:
  [AWS_Results_26_april/closed_loop_soak_2026_05_14_142154](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_14_142154)
- repeated adversarial matrix:
  [AWS_Results_26_april/adversarial_matrix_repeated_2026_05_14_143056](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/adversarial_matrix_repeated_2026_05_14_143056)
- failure injection:
  [AWS_Results_26_april/failure_injection_2026_05_14_145348](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/failure_injection_2026_05_14_145348)
- Metrics API stress:
  [AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_145915](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_145915)
- node-drain reschedule validation:
  [AWS_Results_26_april/multinode_reschedule_validation_2026_05_14_151103](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/multinode_reschedule_validation_2026_05_14_151103)

Results:

- bounded multi-node soak passed `3 / 3`
- repeated adversarial matrix passed `2 / 2` runs with all `5 / 5` workloads
  per run and benign total L3 count `0`
- failure injection preserved explicit degraded telemetry, recorded fake-pod IPC
  response `ERR`, and observed agent restart recovery from `raasa-agent-9st2t`
  to `raasa-agent-2qgvr`
- Metrics API stress ran for `30 s` with `6` workers and preserved `62`
  complete audit rows with `total_failures=0`
- the reschedule validation proved cross-node placement, drained worker-a,
  rescheduled the benign pod onto worker-b, preserved the malicious pod on
  worker-b, and captured post-drain interpretable audit rows from the worker-b
  RAASA agent
- after the reschedule proof, the temporary `raasa-resched` namespace was
  removed and the cluster returned to the intended RAASA system pods plus the
  default phase-0 test pods

Interpretation:

- this is the repo's strongest current evidence for a bounded multi-node K3s
  research prototype under Free-plan AWS credits
- it supports distributed K3s claims only within the observed 3-node,
  single-control-plane scope
- it still does not support EKS robustness, broad multi-tenant safety, or
  production-readiness claims
- final CloudShell teardown inventory for this fresh-account 3-node campaign
  still needs to be preserved in-repo to close the billing-discipline loop

### Latest live stress status

Current strongest live closed-loop result recorded in this repo:

- target host used in the latest session: `3.87.238.207`
- test shape: repeated closed-loop soak against `raasa-test-benign-compute` and `raasa-test-malicious-cpu`
- current strongest stability result: `10 / 10` passing soak cycles on the single-node AWS testbed under the observer-hardened `phase1o` image
- evidence bundle: [AWS_Results_26_april/closed_loop_soak_2026_05_11_163258](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_11_163258)
- summary: [summary.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_11_163258/summary.md)
- current strongest containment validation result: override-pinned `L3` hard containment on the benchmark path under `raasa/agent:phase1p`
- canonical containment evidence bundle: [AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905)
- containment summary: [summary.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905/summary.txt)

Latest observer-hardened live session:

- image/config state: `raasa/agent:phase1o` with live config entries `k8s_metrics_failure_cooldown_seconds=15` and `k8s_namespace_metrics_cache_max_age_seconds=15`
- immediate validation evidence: [AWS_Results_26_april/live_instance_validation_2026_05_11_160545](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_11_160545)
- closed-loop soak result: `4 / 4` passing cycles in [AWS_Results_26_april/closed_loop_soak_2026_05_11_160723](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_11_160723)
- extended comparative soak result: `10 / 10` passing cycles in [AWS_Results_26_april/closed_loop_soak_2026_05_11_163258](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_11_163258)
- refined containment validation: [AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_162228](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_162228)
- focused `L3` semantic check: [AWS_Results_26_april/l3_overwrite_spotcheck_2026_05_11_172046](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/l3_overwrite_spotcheck_2026_05_11_172046)
- direct observations from that session: sampled audit rows showed `telemetry_status=complete`, `degraded_signals=none`, `metrics_api_status=metrics_ok`, and `network_status=metrics_ok`; the captured metrics-server tail windows contained no observed `subjectaccessreviews` timeout bursts
- additional direct observation from the `L3` spot-check: at both `T+1s` and about `T+22s` after a manual `L3` send, the live host qdisc on `vethe94db0ec` still showed `netem loss 100%`, and direct bench-client curls to the service host failed with DNS-resolution timeout (`curl: (28)`)

Latest override-path and harness-hardened live session:

- image/runtime state: `raasa/agent:phase1p` with `RAASA_OVERRIDE_PATH=/app/raasa/logs/overrides.json`
- daemonset env apply evidence: [AWS_Results_26_april/daemonset_env_apply_2026_05_11_183828](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/daemonset_env_apply_2026_05_11_183828)
- refined containment validation: [AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905)
- direct observations from that session: `overrides_before_measurements.json` was `{}`, `overrides_l1_window.json` pinned both benchmark pods to `L1`, `overrides_l3_window.json` pinned the benchmark client to `L3` while holding the benchmark server at `L1`, and `overrides_after_benchmark_restore.json` returned to `{}`
- containment outcome from that session: under the pinned `L3` window, service DNS, service `ClusterIP`, and direct pod-IP benchmark traffic all collapsed to `0 B/s`, with `fallback_count=0`

Latest bounded Metrics API stress probe session:

- harness: [raasa/scripts/run_metrics_api_stress_probe.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/run_metrics_api_stress_probe.ps1)
- strongest raw-pressure bundle in this repo: [AWS_Results_26_april/metrics_api_stress_probe_2026_05_11_192103](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/metrics_api_stress_probe_2026_05_11_192103)
- strongest raw-pressure result: `90 s`, `24` workers, `total_failures=0` across the direct `metrics.k8s.io` pod and list endpoints exercised by the harness
- canonical end-to-end bundle with repaired controller-audit capture: [AWS_Results_26_april/metrics_api_stress_probe_2026_05_11_193215](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/metrics_api_stress_probe_2026_05_11_193215)
- canonical end-to-end result: `30 s`, `12` workers, `total_failures=0`, empty failure-head file, and `48` captured audit rows
- direct controller-side observations from the canonical bundle: all `48` rows for `default/raasa-test-benign-compute`, `default/raasa-test-benign-steady`, and `default/raasa-test-malicious-cpu` preserved `telemetry_status=complete`, `metrics_api_status=metrics_ok`, `memory_status=metrics_ok`, and `cpu_status=probe_ok`
- truthful interpretation: the hardened timeout-to-cooldown fallback path exists in source and is still locally regression-covered, but the May 11 bounded live stress probes did not trigger fallback on the current single-node AWS host

Important scope note:

- this is strong evidence for the current single-node K3s prototype under the current tuned controller and harness
- it is not yet the same thing as multi-node, multi-tenant, or broad production-readiness validation

### Current soak harness and diagnostics

The current AWS soak path is now instrumented to preserve per-cycle decision evidence, not just PASS/FAIL summaries.

Current harness:

- orchestrator: [raasa/scripts/run_closed_loop_soak_aws.ps1](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/run_closed_loop_soak_aws.ps1)
- in-node test script: [raasa/scripts/closed_loop_test.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/scripts/closed_loop_test.sh)

Per-cycle artifacts now captured:

- `cycle_XX_closed_loop_output.txt`
- `cycle_XX_benign_audit_rows.jsonl`
- `cycle_XX_benign_audit_capture.json`
- `cycle_XX_top_nodes.txt`
- `cycle_XX_top_pods.txt`
- `cycle_XX_raasa_tail.txt`
- `cycle_XX_metrics_server_tail.txt`

Why this matters for future AWS credit use:

- failures can now be tuned from exact RAASA decision rows instead of only reading tail logs
- shorter diagnostic soaks can be used first to conserve credits before running longer stability passes

### Confirmed AWS platform

The AWS/K8s path is well evidenced as:

- provider: AWS EC2
- OS family: Ubuntu
- documented target OS: Ubuntu 24.04 LTS
- captured live host OS examples: Ubuntu kernel `6.17.0-1012-aws` on the older
  host and Ubuntu kernel `7.0.0-1004-aws` on the 2026-05-13 free-tier host
- instance family used/documented: `m7i-flex.large`
- documented capacity for that instance: `2 vCPU`, `8 GiB RAM`
- cluster models now evidenced: single-node K3s and bounded 3-node K3s

Evidence:

- [bootstrap_k8s_ebpf.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/bootstrap_k8s_ebpf.sh)
- [docs/RAASA_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/RAASA_Evaluation_Report.md)
- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt)
- [AWS_Results_26_april/live_instance_validation_2026_05_13_083219/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_13_083219/host_identity.txt)

### Confirmed live AWS host identity

Captured from live evidence:

- public host/IP: `54.227.40.170`
- node hostname: `ip-172-31-16-234`
- remote user: `ubuntu`
- kernel string: `Linux ip-172-31-16-234 6.17.0-1012-aws ... x86_64 GNU/Linux`

Evidence:

- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt)
- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/collection_metadata.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/collection_metadata.txt)

Fresh-host capture from 2026-05-13:

- public host/IP: `54.224.245.180`
- node hostname: `ip-172-31-34-138`
- remote user: `ubuntu`
- kernel string: `Linux ip-172-31-34-138 7.0.0-1004-aws ... x86_64 GNU/Linux`

Evidence:

- [AWS_Results_26_april/live_instance_validation_2026_05_13_083219/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_13_083219/host_identity.txt)
- [AWS_Results_26_april/live_instance_validation_2026_05_13_083219/collection_metadata.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_13_083219/collection_metadata.txt)

Restarted-host capture from 2026-05-14:

- public host/IP: `54.164.19.115`
- node hostname: `ip-172-31-34-138`
- remote user: `ubuntu`
- kernel string: `Linux ip-172-31-34-138 7.0.0-1004-aws ... x86_64 GNU/Linux`

Evidence:

- [AWS_Results_26_april/live_instance_validation_2026_05_14_082835/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_14_082835/host_identity.txt)
- [AWS_Results_26_april/live_instance_validation_2026_05_14_082835/collection_metadata.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_2026_05_14_082835/collection_metadata.txt)

### Confirmed AWS/K8s technologies

The cloud-native stack recorded in the repo includes:

- K3s
- Kubernetes Metrics API / Metrics Server
- Tetragon
- eBPF-based syscall telemetry
- Linux `tc` for network shaping
- cgroup-based enforcement
- privileged enforcer sidecar
- Unix socket / shared-volume style coordination between agent and enforcer

Evidence:

- [bootstrap_k8s_ebpf.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/bootstrap_k8s_ebpf.sh)
- [run_aws_experiments.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/run_aws_experiments.sh)
- [docs/RAASA_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/RAASA_Evaluation_Report.md)
- [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)

### Confirmed probe/eBPF data path

The live syscall/probe directory used on AWS was:

- `/var/run/raasa`

Captured per-pod files include:

- `.cpu_usec`
- `.pid_count`
- `.switches_current`
- `.switches_prev`
- `syscall_rate`

Evidence:

- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/probe_volume_listing.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/probe_volume_listing.txt)

### Confirmed AWS pod inventory from live capture

The live restart capture shows these running pods on the single node:

- workload/demo pods: `raasa-test-benign-compute`, `raasa-test-benign-steady`, `raasa-test-malicious-cpu`, `raasa-net-client`, `raasa-net-server`
- system pods: `coredns`, `local-path-provisioner`, `metrics-server`, `tetragon`, `tetragon-operator`
- RAASA control pod: `raasa-agent-jg9g6`

That capture represents 11 running pods total, all scheduled on `ip-172-31-16-234`.

Evidence:

- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/kubectl_get_pods_all_wide.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/kubectl_get_pods_all_wide.txt)

### Confirmed AWS benchmark resources

The pod-specific validation bundle records separate benchmark pods:

- `raasa-bench-client-5fd64dcfbf-hvl28`
- `raasa-bench-server-7c49558994-2nmcp`

Evidence:

- [AWS_Results_26_april/phase1c_pod_specific_validation_2026_04_26_final4/bench_pods.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/phase1c_pod_specific_validation_2026_04_26_final4/bench_pods.txt)

### Confirmed AWS metrics sample

The repo includes a captured Metrics API response for the malicious pod:

- namespace: `default`
- pod: `raasa-test-malicious-cpu`
- label `raasa.class=malicious`
- example usage sample: CPU `992936887n`, memory `397524Ki`

Evidence:

- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/metrics_api_malicious_pod.json](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/metrics_api_malicious_pod.json)

### Confirmed AWS experiment plan and scales

The automated AWS experiment runner documents:

- `static_L1` baseline on K8s
- `static_L3` baseline on K8s
- `small_tuned` repeated 3 times
- `medium` repeated 3 times
- `large` run once

Durations in the runner:

- `small_tuned`: 120s
- `medium`: 150s
- `large`: 180s

Evidence:

- [run_aws_experiments.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/run_aws_experiments.sh)

### Confirmed AWS enforcement semantics

The repo records two important AWS containment stories:

- network shaping / throttling to `1mbit/s` using `tc`
- later live evidence showing some `L3` paths behaved more like hard containment than gentle bandwidth shaping

This means future stress tests should not assume a single stable `L3` meaning without revalidation.

Evidence:

- [docs/RAASA_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/RAASA_Evaluation_Report.md)
- [AWS_Results_26_april/Progress_Tracker.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/Progress_Tracker.md)

### AWS details that are still missing

The repo does **not** clearly preserve:

- availability zone
- EC2 AMI ID
- full security group rule history
- VPC/subnet IDs
- exact Tetragon version
- exact Docker/containerd versions on the EC2 host
- exact EC2 instance launch timestamp and termination history

## Stress-test preparation notes

Before future stress testing, the minimum environment facts to record for each run should be:

- date and run ID
- local or AWS
- host OS and kernel
- instance type or local hardware
- CPU count and RAM
- Docker/K3s/Kubernetes/Tetragon versions
- workload scenario and exact pod/container counts
- test duration
- telemetry sources used
- enforcement mode used
- whether the Metrics API was healthy
- whether `/var/run/raasa` probe files were populated
- resulting logs and summary artifact paths

## Recommended source of truth going forward

Use this file as the inventory page, and update it whenever:

- local test hardware or platform changes
- AWS instance shape changes
- cluster topology changes
- telemetry source changes
- test counts or pytest status change
- stress-testing infrastructure is introduced

For deeper reproduction steps, keep using:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)

For cloud proof artifacts, keep using:

- [AWS_Results_26_april](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april)
