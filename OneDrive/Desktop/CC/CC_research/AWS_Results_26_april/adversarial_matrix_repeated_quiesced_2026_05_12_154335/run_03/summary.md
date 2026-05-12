# Adversarial Workload Matrix Summary

- Host: 54.172.163.87
- Duration seconds per workload: 60
- Background workloads quiesced: True
- Collected at: 2026-05-12T16:02:19.1669507+05:30

## benign-control
- Namespace: raasa-adv-control
- Pod ref: raasa-adv-control/raasa-adv-benign-control
- Expected L3: False
- Result: PASS
- Audit rows: 15
- New tiers: L1:15
- Proposed tiers: L1:15
- L3 applied count: 0
- Max signals: cpu=0, proc=0.1, net=0.002, sys=0
- Telemetry statuses: complete:11,partial:4
- Syscall statuses: probe_missing:2,probe_ok:13

## syscall-storm
- Namespace: raasa-adv-sys
- Pod ref: raasa-adv-sys/raasa-adv-syscall-storm
- Expected L3: True
- Result: PASS
- Audit rows: 16
- New tiers: L3:16
- Proposed tiers: L2:12,L3:4
- L3 applied count: 16
- Max signals: cpu=100, proc=1, net=0.002, sys=0
- Telemetry statuses: complete:12,partial:4
- Syscall statuses: probe_missing:2,probe_ok:14

## process-fanout
- Namespace: raasa-adv-proc
- Pod ref: raasa-adv-proc/raasa-adv-process-fanout
- Expected L3: True
- Result: PASS
- Audit rows: 16
- New tiers: L3:16
- Proposed tiers: L1:1,L2:11,L3:4
- L3 applied count: 16
- Max signals: cpu=100, proc=1, net=0.002, sys=0.0259
- Telemetry statuses: complete:9,partial:7
- Syscall statuses: probe_missing:3,probe_ok:9,probe_stale:4

## network-burst
- Namespace: raasa-adv-net
- Pod ref: raasa-adv-net/raasa-adv-net-client
- Expected L3: True
- Result: PASS
- Audit rows: 17
- New tiers: L2:12,L3:5
- Proposed tiers: L1:14,L3:3
- L3 applied count: 5
- Max signals: cpu=33.8696, proc=0.2, net=1, sys=0.0177
- Telemetry statuses: complete:12,partial:5
- Syscall statuses: probe_missing:2,probe_ok:15

## Overall
- Passing workloads: 4 / 4

