# Latest V2 Validation - April 26, 2026

For direct SSH-backed validation from the live AWS node, also use `09_live_aws_instance_log_validation_2026_04_26.md`.

This note captures the newest results found in:

- `results/aws_v2_2026_04_26/test_results.txt`
- `results/aws_v2_2026_04_26/raasa_agent.log`
- `results/aws_v2_2026_04_26/raasa_enforcer.log`
- `results/aws_v2_2026_04_26/run_20260426T032723Z.jsonl`
- `results/aws_v2_2026_04_26/run_20260426T032723Z.curated_summary.json`

## Why this matters

These are the freshest v2+ results currently available in the workspace. They are very helpful, not because they inflate the paper story, but because they give a more honest operational picture of the cloud-native path.

## Manual test outcomes

The human-written `test_results.txt` records:

- `PASS`: malicious pod correctly held at `L3`
- `FAIL`: stressed benign pod did not escalate to `L3` within 45 seconds
- `PASS`: benign pod de-escalated back to `L1` after stress ended
- `PASS`: moderate 30% CPU load did not trigger `L3`

Overall:

- `3 passed`
- `1 failed`

## What the audit log confirms

### Strong point

The malicious pod path is real in the audit evidence:

- `default/raasa-test-malicious` entered and stayed in `L3`
- max recorded CPU: `100.0`
- max recorded risk: `0.8416`
- one containment action was required and then the pod remained held

### Weak point

The stressed benign test did not show actual escalation in the captured records:

- `default/raasa-test-benign` stayed `L1` for all 6 recorded ticks
- max recorded CPU: `0.0`
- max recorded risk: `0.0291`

That means the failure is not just a note in `test_results.txt`; it is consistent with the audit trail we copied into this packet.

## What the sidecar log confirms

The privileged enforcer is not hypothetical in this run. The log shows actual `tc` actions such as:

- benign pod -> `L1`
- malicious pod -> `L3`
- demo client/server pods -> `L1`

So the sidecar architecture itself is active. The gap is not "enforcer never ran"; the gap is "signal and escalation path did not behave as desired for the stressed benign case."

## Important telemetry caveats exposed by this run

The latest v2 validation also reveals operational blind spots:

- `network_status = metrics_unavailable` throughout the captured audit records
- `syscall_status = probe_missing` throughout the captured audit records
- some default test pods have empty `workload_class` and `expected_tier` metadata

These matter because they limit:

- metric automation,
- richer feature coverage,
- the strength of any claim that the K8s path was using full intended telemetry.

## Best way to use this in the paper

Use this run as evidence that:

1. the v2 sidecar-based cloud-native control path is alive,
2. malicious containment can be observed in the newer environment,
3. the newest testing also uncovered remaining detection/escalation gaps,
4. the cloud-native story should be framed as promising and partially validated, not fully solved.

## Best wording

Good wording:

- "The latest cloud-native validation on April 26, 2026 confirmed successful L3 containment of the malicious test pod and live privileged-sidecar enforcement, while also exposing an unresolved benign-stress escalation gap and missing telemetry channels."

Avoid wording like:

- "The v2 cloud-native path is fully validated."
- "All dynamic escalation tests passed."
- "The K8s/eBPF telemetry path was fully active across all signals."

## Practical conclusion

These latest results make the packet better. They do not replace the older Docker evidence as the strongest overall quantitative study, but they do become the freshest operational truth for v2+ and should shape the final paper's cloud-native claims.
