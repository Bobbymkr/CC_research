# Live AWS Instance Log Validation - April 26, 2026

This note adds one important thing the earlier packet did not have: direct SSH-backed confirmation from the live AWS node, not just copied result files.

Primary source bundle:

- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/host_identity.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/collection_metadata.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/raasa_agent_all_containers_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/metrics_server_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/journalctl_k3s_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/probe_volume_listing.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/metrics_api_raasa_test_malicious_cpu.json`

## What this strengthens

The April 26 cloud-native story is now stronger in one specific way:

- the Kubernetes Metrics API failure is no longer just a claim in a markdown report,
- it is directly visible in live `raasa-agent`, `metrics-server`, and `k3s` logs from the AWS instance.

That makes the following claim defensible:

- under CPU-heavy node stress in this single-node K3s setup, the in-band Metrics API path can degrade badly enough to return repeated `500` errors and authorization-path timeouts.

## What this also confirms

The live shared probe volume on the node contained per-pod files such as:

- `.cpu_usec`
- `.switches_current`
- `.pid_count`
- `syscall_rate`

For the malicious pod UID observed during the live inspection, those files were populated. This supports the claim that RAASA has a real out-of-band fallback data path on the node.

## What this does not prove

This evidence still does not justify claiming:

- `100% telemetry integrity`
- permanent control-plane blindness for the full experiment,
- full multi-signal availability across every telemetry channel.

Why not:

- the live Metrics API also returned at least one successful result for the malicious pod later in the same inspection window,
- the earlier April 26 artifact slice still contains `metrics_unavailable` and `probe_missing` caveats,
- the live inspected pod was a later pod than the archived `03:27Z` run.

## Best paper use

Use this note to support a careful systems claim:

1. the cloud-native control-plane telemetry path is fragile under node stress,
2. RAASA's per-pod probe volume provides a real fallback path,
3. the current evidence supports partial telemetry resilience, not absolute end-to-end signal guarantees.
