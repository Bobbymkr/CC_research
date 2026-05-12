# Decision Record: Free-Tier Realism Track

Date: 2026-05-12

## Decision

Stay on the current single-node AWS K3s deployment for the next research increment.

Do not add a second EC2 node yet. The current free-tier-constrained node is already CPU-bound during RAASA experiments, and adding a node would increase EC2, EBS, and public IPv4 cost risk before the project has exhausted same-node evidence.

## Current Capacity

- Instance: `m7i-flex.large`
- Node capacity: 2 vCPU, ~7.6 GiB memory
- Disk after cleanup: 19 GiB root volume, 11 GiB used, 8.0 GiB free, 57% used
- Baseline CPU after cleanup: ~79%
- Main CPU users: malicious test pod, Tetragon, RAASA agent
- Memory headroom: acceptable
- Disk headroom: acceptable after cleanup, but should be watched

## Actions Taken

- Removed stale RAASA image tarballs from `/tmp`.
- Pruned unused Docker images and build cache.
- Preserved live K3s/containerd workload state.
- Verified all K3s pods remained running after cleanup.
- Ran pod churn realism test: 16 short-lived pods over 4 cycles.
- Ran CPU pressure cadence test with two bounded pressure pods.
- Removed temporary `raasa-churn` and `raasa-pressure` namespaces after tests.

## Evidence

- Capacity cleanup: `AWS_Results_26_april/capacity_cleanup_2026_05_12_112052`
- Pod churn realism: `AWS_Results_26_april/pod_churn_realism_2026_05_12_112231`
- CPU pressure cadence: `AWS_Results_26_april/cpu_pressure_cadence_2026_05_12_112741`
- Post-realism cleanup: `AWS_Results_26_april/post_realism_cleanup_2026_05_12_113028`

## Findings

Pod churn result:
- 16 / 16 churn pods were observed by RAASA.
- 121 audit rows were captured.
- All churn pods remained at L1.
- Enforcer resolved all 16 pod-specific veth interfaces.
- No enforcer fallback/refusal lines occurred for churn pods.
- Early churn samples had partial telemetry while metrics/probe caught up; later samples reached complete telemetry.

CPU pressure result:
- RAASA remained live under pressure.
- Control-loop interval for pressure pods stayed bounded: p50 6.298s, p95 6.968s, max 6.968s.
- Two expected-L2 benign pressure pods were overcontained to L3.
- This is a calibration/research finding, not an infrastructure failure.

## Next Engineering Decision

Policy calibration for benign CPU/syscall-heavy workloads has now passed the closed-loop AWS contract.

Keep the next increment on the same single-node deployment, but shift from basic responsiveness to adversarial workload quality and evidence hardening.

Specifically:
- Keep `expected_tier=L2` benign CPU pressure below L3 unless a decisive attack signal joins it.
- Add stronger adversarial workloads that are not just CPU stress: syscall storms, process fanout, network scan paths, and mixed multi-signal abuse.
- Preserve fast L3 for malicious workloads with confirmed extreme syscall, network, memory, or process evidence.
- Keep fail-closed behavior for missing/stale telemetry unchanged.

## Calibration Update

Evidence added after the initial decision:

- Deployed `raasa/agent:phase1u-syscall-context-calibrated`.
- Local tests: `112 passed, 3 skipped`.
- Graphify updated after policy/script changes: 756 nodes, 1798 edges, 35 communities.
- Closed-loop soak: `AWS_Results_26_april/closed_loop_soak_2026_05_12_122004`.
- Deployment evidence: `AWS_Results_26_april/deploy_agent_image_2026_05_12_121553`.

Closed-loop result:
- 1 / 1 cycle passed.
- Malicious pod reached and held L3.
- Benign expected-L2 stress reached L2 within 45s.
- Benign expected-L2 stress had 0 applied L3 decisions.
- Benign stress de-escalated back to L1.
- Moderate 30% CPU load stayed at or below L2.

Resource status after cleanup:
- Root disk: 19 GiB total, 11 GiB used, 8.0 GiB free, 57% used.
- Memory: 7.6 GiB total, 4.7 GiB available.
- CPU remains the limiting resource during active experiments.

## Adversarial Matrix Update

Evidence added after the adversarial/free-tier calibration pass:

- Deployed `raasa/agent:phase1aa-evidence-aware-partial-telemetry`.
- Deployment evidence: `AWS_Results_26_april/deploy_agent_image_2026_05_12_150246`.
- Local tests: `121 passed, 3 skipped`.
- Graphify updated after code changes: 793 nodes, 1917 edges, 35 communities.
- Closed-loop soak: `AWS_Results_26_april/closed_loop_soak_2026_05_12_150632`.
- Adversarial matrix: `AWS_Results_26_april/adversarial_matrix_2026_05_12_150954`.

Code-level fixes validated:
- K8s process telemetry now resolves K3s pod cgroup paths from the controller host mount at `/host/sys/fs/cgroup`, including underscored pod UID variants and recursive fallback under `kubepods`.
- Ordinary L3 escalation now requires decisive L3 evidence rather than aggregate risk alone, preventing benign CPU plus borderline local syscall pressure from entering hard containment.
- Network saturation confirmation tolerates short quiet gaps because live network samples alternate between burst and idle windows on the free-tier node.
- Partial telemetry no longer suppresses L3 when the degraded signal is unrelated to the decisive evidence, such as syscall probe staleness during confirmed network saturation or process fanout.

Closed-loop result:
- 1 / 1 cycle passed.
- Malicious pod held L3.
- Benign expected-L2 stress reached L2 and did not enter L3.
- Benign stress de-escalated back to L1.
- Moderate 30% CPU stayed at or below L2.
- Benign audit tiers: L1:15, L2:9, L3:0.

Adversarial matrix result:
- 4 / 4 workloads passed.
- Benign control: L1:14, L3 applied count 0.
- Syscall storm: L2:4, L3:9.
- Process fanout: L2:7, L3:7.
- Network burst: L1:2, L2:4, L3:7.

Resource status after cleanup:
- Root disk: 19 GiB total, 11 GiB used, 7.8 GiB free, 58% used.
- Node CPU remains about 79% at rest because the persistent `raasa-test-malicious-cpu` pod consumes roughly one core.
- Memory remains acceptable at about 41-43% used.

Updated verdict:
- The current single-node approach is still viable for the next increment.
- The dominant limit is no longer local policy logic; it is free-tier CPU contention and single-node realism.
- Before adding another EC2 node, add repeated-run evidence and a harness mode that can intentionally quiesce background demo/test pods when the experiment is not meant to include permanent contention.

## Controlled Repeatability Update

Evidence added after adding controlled harness mode:

- Added `-QuiesceBackgroundWorkloads` to `raasa/scripts/run_adversarial_matrix_aws.ps1`.
- Added `raasa/scripts/run_repeated_adversarial_matrix_aws.ps1` for repeated matrix runs with aggregate evidence.
- Repeated controlled matrix: `AWS_Results_26_april/adversarial_matrix_repeated_quiesced_2026_05_12_154335`.

Controlled run conditions:
- Each matrix run temporarily deleted `default` phase0 test pods and scaled `raasa-demo` plus `raasa-bench` deployments to zero.
- The harness restored phase0 pods and scaled demo/bench deployments back to one replica after each run.
- Quiesced node CPU dropped from the contended ~79-89% range to a low-load range before matrix workloads.
- After final restore, phase0/demo/bench workloads were running again, and the RAASA DaemonSet was rolled out.

Repeated matrix result:
- 3 / 3 matrix runs passed.
- 12 / 12 workload checks passed.
- Benign control: 3 / 3 passed, total L3 count 0.
- Syscall storm: 3 / 3 passed, total L3 count 47.
- Process fanout: 3 / 3 passed, total L3 count 47.
- Network burst: 3 / 3 passed, total L3 count 18.

Updated interpretation:
- Under controlled single-node conditions, the current approach is repeatable across multiple adversarial runs.
- Under restored/free-tier-contended conditions, the system still runs, but CPU contention remains the main experimental noise source.
- The next credible research step is not a bigger instance by default; it is paired evidence: controlled matrix runs plus deliberately contended matrix runs, with resource state captured before and after each run.

## RBAC Minimization Assessment

Current live service account permissions are narrower than cluster-admin but still broader than the current code path requires.

Observed code/API needs:
- `pods get/list`: discover pods on the current node and read pod UID/labels for telemetry and pod-specific veth resolution.
- `nodes/proxy get`: read cAdvisor metrics through the node proxy.
- `metrics.k8s.io pods get/list`: read pod CPU/memory metrics and namespace fallback lists.

Permissions not currently required by the controller/enforcer code path:
- core `nodes get/list/watch`
- core `nodes/metrics get`
- `metrics.k8s.io nodes get/list`
- core `events create/patch`
- any pod create/update/delete permission

Manifest update staged, not yet deployed:
- `raasa/k8s/daemonset.yaml` now narrows the ClusterRole to pod read/list, node proxy get, and pod metrics get/list.
- `raasa/k8s/daemonset.network-only.yaml` now carries the same least-privilege shape and includes `nodes/proxy get`, which the observer needs for cAdvisor.

Deployment recommendation:
- Apply the reduced RBAC only as a dedicated rollout.
- Before rollout, capture `kubectl auth can-i` for the old role.
- After rollout, run one closed-loop soak and one controlled matrix run.
- Keep the old ClusterRole YAML in the evidence bundle as rollback material.

## Multi-Node Gate

Only attempt multi-node testing after these gates are met:

- Disk remains below 70% after experiments.
- Single-node CPU pressure no longer produces unexplained L3 overcontainment for expected-L2 benign workloads.
- AWS Billing/Free Tier/Credits page confirms enough remaining budget for additional EC2, EBS, and public IPv4 usage.
- A fixed-duration multi-node test plan is ready, with teardown commands prepared before launch.
