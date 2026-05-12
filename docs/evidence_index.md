# RAASA Evidence Index

This file is the canonical reviewer-facing map from paper claims to evidence.
It should be updated whenever a new claim is added or a stronger evidence
bundle replaces an older one.

## Current Local Evidence

| Claim | Date | Workload / scope | Expected behavior | Result | Limitations |
| --- | --- | --- | --- | --- | --- |
| Unit and regression suite passes | 2026-05-12 | `tests/` on local Windows/Python 3.13 | Core risk, policy, observer, IPC, override, analysis, and harness tests pass | `123 passed, 3 skipped`, 14 warnings | Local test suite is not a substitute for live K8s or kernel enforcement validation |
| Local Docker adaptive-vs-static path is reproducible | See `REPRODUCIBILITY.md` | `small_tuned`, `medium`, `large` Docker scenarios | RAASA should reduce under/over-containment relative to static modes | Repro commands and precomputed summaries are preserved | Docker syscall signal can be simulated unless probe mode is explicitly used |
| Agent-like misuse benchmark launches locally | 2026-05-12 | `agent_misuse` Docker smoke, 4 iterations | Bounded dependency/exfiltration plus process fanout should reach L3 without benign over-containment | `strict_malicious_containment_rate=1.0`, `under_containment_rate=0.0` in `raasa/logs/run_codex_agent_misuse_l3_smoke.summary.json` | Local Docker smoke uses simulated syscall signal; AWS/K3s evidence still required |

## Current AWS/Kubernetes Evidence

| Claim | Date | Host | Workload / scope | Expected behavior | Result | Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| Closed-loop controller stability | 2026-05-11 | `3.87.238.207` | Repeated soak against benign and malicious test pods | Benign remains low tier while malicious escalates and recovers | `10 / 10` cycles passed in `AWS_Results_26_april/closed_loop_soak_2026_05_11_163258/summary.md` | Single-node K3s, not EKS or multi-tenant |
| Override-pinned L3 hard containment | 2026-05-11 | `3.87.238.207` | Benchmark service DNS, service IP, and pod IP | Pinned L3 should collapse benchmark traffic without broad fallback | `0 B/s` under L3 with `fallback_count=0` in `AWS_Results_26_april/phase1d_resolution_validation_2026_05_11_183905/summary.txt` | Measures current hard-containment semantics, not general sandbox isolation |
| Metrics API stress remains interpretable | 2026-05-11 | `3.87.238.207` | 30 s/12 worker stress and 90 s/24 worker raw pressure | Controller audit rows should preserve signal status | Canonical run captured complete telemetry rows; raw pressure reported `total_failures=0` | Did not force the timeout fallback path on this host |
| Failure injection fails closed | 2026-05-12 | `54.172.163.87` | Metrics API outage, syscall probe pause, fake-pod IPC request, agent restart | Partial telemetry remains explicit; fake-pod command rejected | `AWS_Results_26_april/failure_injection_2026_05_12_110019/summary.md` shows partial telemetry rows and IPC `ERR` | Single-node failure modes; no multi-node controller partition test |
| Adversarial matrix handles bounded attack classes | 2026-05-12 | `54.172.163.87` | Benign control, syscall storm, process fanout, network burst | Benign should avoid L3; adversarial workloads should reach L3 | `4 / 4` workloads passed in `AWS_Results_26_april/adversarial_matrix_2026_05_12_150954/summary.md` | Some telemetry was partial; classes are synthetic |
| Repeated adversarial matrix is stable | 2026-05-12 | `54.172.163.87` | Three quiesced adversarial matrix runs | All four workload classes should pass repeatedly | `3 / 3` runs passed in `AWS_Results_26_april/adversarial_matrix_repeated_quiesced_2026_05_12_154335/summary.md` | Paper target is at least five runs before final submission |
| Pod churn does not cause broad enforcement fallback | 2026-05-12 | `54.172.163.87` | 16 churn pods | Low-risk churn pods should remain L1; enforcer should resolve pod interfaces | 16/16 churn pods observed; no fallback/refusal lines | Churn was benign; not a multi-node churn experiment |

## Claims This Evidence Does Not Support

- Full production readiness.
- Complete defense against container escape.
- Broad prevention of exfiltration or lateral movement.
- Multi-node, multi-tenant, or EKS-scale robustness.
- ML superiority over the tuned linear controller.
- Replacement of gVisor, Kata, Firecracker, Nitro Enclaves, or other strong
  isolation backends.

## Next Evidence Needed

- Fresh five-run repeated adversarial matrix using the updated five-workload
  script and the same summary schema.
- AWS evidence for the new agent-like dependency/exfiltration benchmark.
- Multi-node K3s validation before making any distributed claim.
- EKS validation only after the single-node and multi-node K3s story is clean.
