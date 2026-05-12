# Adversarial Workload Matrix Summary

- Host: 54.172.163.87
- Duration seconds per workload: 60
- Background workloads quiesced: True
- Collected at: 2026-05-12T15:43:38.0525295+05:30

## benign-control
- Namespace: raasa-adv-control
- Pod ref: raasa-adv-control/raasa-adv-benign-control
- Expected L3: False
- Result: PASS
- Audit rows: 16
- New tiers: L1:16
- Proposed tiers: L1:16
- L3 applied count: 0
- Max signals: cpu=0, proc=0.1, net=0.0014, sys=0
- Telemetry statuses: complete:12,partial:4
- Syscall statuses: probe_missing:2,probe_ok:14

## syscall-storm
- Namespace: raasa-adv-sys
- Pod ref: raasa-adv-sys/raasa-adv-syscall-storm
- Expected L3: True
- Result: PASS
- Audit rows: 15
- New tiers: L3:15
- Proposed tiers: L2:8,L3:7
- L3 applied count: 15
- Max signals: cpu=100, proc=1, net=0.002, sys=0.2848
- Telemetry statuses: complete:13,partial:2
- Syscall statuses: probe_missing:1,probe_ok:14

## process-fanout
- Namespace: raasa-adv-proc
- Pod ref: raasa-adv-proc/raasa-adv-process-fanout
- Expected L3: True
- Result: PASS
- Audit rows: 16
- New tiers: L3:16
- Proposed tiers: L2:10,L3:6
- L3 applied count: 16
- Max signals: cpu=100, proc=1, net=0.002, sys=0.1082
- Telemetry statuses: complete:12,partial:4
- Syscall statuses: probe_missing:3,probe_ok:13

## network-burst
- Namespace: raasa-adv-net
- Pod ref: raasa-adv-net/raasa-adv-net-client
- Expected L3: True
- Result: PASS
- Audit rows: 15
- New tiers: L2:9,L3:6
- Proposed tiers: L1:11,L3:4
- L3 applied count: 6
- Max signals: cpu=30.2463, proc=0.2, net=1, sys=0.0184
- Telemetry statuses: complete:11,partial:4
- Syscall statuses: probe_missing:1,probe_ok:14

## Overall
- Passing workloads: 4 / 4

