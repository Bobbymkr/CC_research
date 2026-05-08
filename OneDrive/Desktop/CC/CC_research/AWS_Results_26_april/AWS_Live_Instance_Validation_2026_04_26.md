# AWS Live Instance Validation - April 26, 2026

This note records a direct SSH inspection of the live AWS instance at `34.234.83.239` on April 26, 2026. It is the reviewer-safe companion to the broader Phase 0 writeup.

## Scope

- Instance inspected directly over SSH
- Host user: `ubuntu`
- Hostname observed: `ip-172-31-16-234`
- Validation focus:
  - whether the control-plane / Metrics API degradation is real on the live node,
  - whether RAASA's out-of-band probe path is actually populated,
  - what can and cannot be claimed from this evidence.

## Raw evidence bundle

Raw outputs captured from the live node are stored in:

- `live_instance_validation_2026_04_26/host_identity.txt`
- `live_instance_validation_2026_04_26/collection_metadata.txt`
- `live_instance_validation_2026_04_26/kubectl_get_pods_all_wide.txt`
- `live_instance_validation_2026_04_26/kubectl_pod_uid_map.txt`
- `live_instance_validation_2026_04_26/raasa_agent_all_containers_tail_200.txt`
- `live_instance_validation_2026_04_26/metrics_server_tail_200.txt`
- `live_instance_validation_2026_04_26/journalctl_k3s_tail_200.txt`
- `live_instance_validation_2026_04_26/metrics_api_raasa_test_malicious_cpu.json`
- `live_instance_validation_2026_04_26/probe_volume_listing.txt`
- `live_instance_validation_2026_04_26/malicious_pod_cpu_usec.txt`
- `live_instance_validation_2026_04_26/malicious_pod_syscall_rate.txt`
- `live_instance_validation_2026_04_26/malicious_pod_switches_current.txt`
- `live_instance_validation_2026_04_26/malicious_pod_pid_count.txt`

The same evidence pull can be repeated with:

- `raasa/scripts/collect_aws_live_validation.ps1`

## What is now directly confirmed

### 1. Control-plane telemetry degradation is real

The live `raasa-agent` logs contain repeated failures of the Kubernetes Metrics API path, including:

- `500 Internal Server Error`
- `context deadline exceeded`
- `Client.Timeout exceeded while awaiting headers`

The same failure mode appears independently in:

- `metrics_server_tail_200.txt`
- `journalctl_k3s_tail_200.txt`

This is enough to support the claim that the Metrics API path can degrade under CPU-heavy node stress in this single-node K3s deployment.

### 2. The out-of-band probe volume is live and populated

The live RAASA pod exposes per-pod files under `/var/run/raasa/`, including:

- `.cpu_usec`
- `.switches_current`
- `.pid_count`
- `syscall_rate`

This is recorded in `probe_volume_listing.txt`.

### 3. The malicious pod has live out-of-band signal files

For the malicious pod UID `fb426540-0948-4317-9851-0c0e2a3d2a31`, the live probe files contained:

- `.cpu_usec = 1680099982`
- `syscall_rate = 7756.20`
- `.switches_current = 6447889`
- `.pid_count = 14`

This confirms that RAASA had direct per-pod fallback data available outside the Metrics API path.

## What is not yet proven

### 1. This is not proof of 100% telemetry integrity

The live validation proves that the fallback files exist and are populated during a period of Metrics API degradation. It does not prove that every signal remained available continuously for the entire run.

### 2. The Metrics API did recover at least once

`metrics_api_raasa_test_malicious_cpu.json` shows that the Metrics API was also able to return data for `raasa-test-malicious-cpu` at `2026-04-26T05:02:08Z`.

That means the failure mode should be described as:

- intermittent or sustained degradation under load,

not:

- permanent total blindness for the entire experiment.

### 3. This live inspection is not byte-for-byte the same run as the earlier `03:27Z` artifact slice

The live pod observed during SSH validation was `raasa-agent-jg9g6`, which is a later pod than the earlier archived run in this folder. So this evidence is best used as corroborating live validation of the same architectural phenomenon, not as an exact replay of the `03:27Z` run.

## Publication-safe wording

Use wording like:

> On a live AWS `m7i-flex.large` K3s node, we directly observed repeated Metrics API failures under CPU-heavy workload stress, including HTTP 500 responses and authorization-path timeouts. In the same environment, RAASA's shared probe volume remained populated with per-pod `.cpu_usec`, `syscall_rate`, and process metadata, demonstrating an out-of-band fallback telemetry path that remains available during control-plane degradation.

Avoid wording like:

- `100% telemetry integrity`
- `Metrics API was permanently unavailable for the whole run`
- `all standard cloud tools would be completely blinded`

## Bottom line

The strong finding survives direct inspection:

- **yes**, the control-plane telemetry path really does degrade on the live AWS node,
- **yes**, the out-of-band RAASA probe path is real and active,
- **no**, the current evidence does not justify an absolute claim of full signal integrity across all channels and all timestamps.
