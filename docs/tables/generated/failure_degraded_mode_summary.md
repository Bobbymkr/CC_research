# Table C. Failure and Degraded-Mode Summary

| Injected condition | Observed status | Containment outcome | Interpretation | Evidence bundle |
| --- | --- | --- | --- | --- |
| Metrics API outage | 10 audit rows; telemetry complete:1, partial:9; metrics_ok:1, metrics_error:9; memory metrics_ok:1, cadvisor_fallback:9 | New tiers L3:10 | The controller exposes degraded telemetry instead of silently masking the outage | AWS_Results_26_april/failure_injection_2026_05_14_145348 |
| Syscall probe pause | 11 audit rows; telemetry complete:4, partial:7; probe_ok:4, probe_stale:7 | New tiers L3:11 | Probe degradation is explicitly surfaced rather than hidden behind a false clean reading | AWS_Results_26_april/failure_injection_2026_05_14_145348 |
| Fake-pod IPC fail-closed check | IPC response ERR | Rejected as expected | The privileged path fails closed for an invalid target | AWS_Results_26_april/failure_injection_2026_05_14_145348 |
| Agent restart recovery | Agent changed from raasa-agent-9st2t to raasa-agent-2qgvr | Recovery observed after restart | The bounded experiment shows post-restart continuity, not high-availability | AWS_Results_26_april/failure_injection_2026_05_14_145348 |
| Metrics API bounded stress | 30 s, 6 workers, 62 audit rows, telemetry complete:62, metrics_ok:62, total_failures=0 | Controller held risk within current tier band for all captured rows | Bounded stress remained interpretable without forcing a collapse in the cloud path | AWS_Results_26_april/metrics_api_stress_probe_2026_05_14_145915 |

## Notes

- This table is especially useful in discussion/limitations or an appendix.
- Its purpose is to show that degraded behavior is explicit rather than silently hidden.
