# Testing Environment Inventory

This document consolidates what the current project records about testing environments, execution resources, and validation scope for RAASA. It is intended to be the starting point for future stress testing.

## Short answer

The current project status does **not** state all testing-environment information in one place.

What is already documented:

- the main local test path uses Docker/Docker Desktop
- the cloud path uses AWS EC2 with Ubuntu, K3s, Tetragon eBPF, and the Kubernetes Metrics API
- the main workload scales are 3, 10, and 20 containers
- some live AWS pod inventories and host identity were captured

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

Evidence:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md)
- [docs/live_experiment_notes.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/live_experiment_notes.md)
- [raasa/experiments/run_experiment.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/experiments/run_experiment.py)

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
- `medium`: 10 containers
- `large`: 20 containers

Scenario composition:

- `small_tuned`: 1 `benign_steady`, 1 `benign_bursty`, 1 `malicious_pattern_heavy`
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

- `62 passed` locally via `pytest`
- 14 warnings, mainly dependency deprecation warnings from `matplotlib`/`pyparsing`

Important correction:

- [REPRODUCIBILITY.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/REPRODUCIBILITY.md) still says `41 passing, 3 failing`
- that statement is now outdated relative to the current workspace

Confirmed test files present:

- `test_analysis.py`
- `test_enforcement_logger.py`
- `test_enforcer_sidecar.py`
- `test_experiments.py`
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

- exact local host OS version
- exact local CPU model/core count
- exact local RAM size
- exact Docker Desktop version
- whether all result files came from one local machine or multiple local machines

## AWS testing environment

### Latest live stress status

Current strongest live closed-loop result recorded in this repo:

- target host used in the latest session: `34.226.205.95`
- test shape: repeated closed-loop soak against `raasa-test-benign-compute` and `raasa-test-malicious-cpu`
- current strongest stability result: `10 / 10` passing soak cycles on the single-node AWS testbed
- evidence bundle: [AWS_Results_26_april/closed_loop_soak_2026_05_09_163219](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_09_163219)
- summary: [summary.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/closed_loop_soak_2026_05_09_163219/summary.md)

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
- captured live host OS: Ubuntu kernel `6.17.0-1012-aws`
- instance family used/documented: `m7i-flex.large`
- documented capacity for that instance: `2 vCPU`, `8 GiB RAM`
- cluster model: single-node K3s

Evidence:

- [bootstrap_k8s_ebpf.sh](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/bootstrap_k8s_ebpf.sh)
- [docs/RAASA_Evaluation_Report.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/RAASA_Evaluation_Report.md)
- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt)

### Confirmed live AWS host identity

Captured from live evidence:

- public host/IP: `54.227.40.170`
- node hostname: `ip-172-31-16-234`
- remote user: `ubuntu`
- kernel string: `Linux ip-172-31-16-234 6.17.0-1012-aws ... x86_64 GNU/Linux`

Evidence:

- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/host_identity.txt)
- [AWS_Results_26_april/live_instance_validation_restart_2026_04_26/collection_metadata.txt](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/AWS_Results_26_april/live_instance_validation_restart_2026_04_26/collection_metadata.txt)

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

- AWS region
- availability zone
- EC2 AMI ID
- EBS volume size/type
- security group rules
- VPC/subnet IDs
- exact K3s version
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
