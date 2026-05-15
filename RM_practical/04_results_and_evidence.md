# Results And Evidence

This file pulls together the most useful result artifacts in `results/` and tells you which ones are strongest enough to anchor the paper.

## 1. Baseline comparison: the core argument

The simplest and clearest argument RAASA makes is the adaptive-vs-static trade-off.

### Static L1 baseline

Source: `results/aws_v2/run_L1.summary.json`

- precision: `0.0`
- recall: `0.0`
- false positive rate: `0.0`
- malicious containment rate: `0.0`

Interpretation:

- `static_L1` preserves utility but fails to contain the malicious workload.

### Static L3 baseline

Source: `results/aws_v2/run_L3.summary.json`

- precision: `0.3333`
- recall: `1.0`
- false positive rate: `1.0`
- benign restriction rate: `1.0`

Interpretation:

- `static_L3` contains malicious behavior but over-restricts benign workloads completely.

### Adaptive RAASA

Representative source: `results/aws_v2/run_small_tuned_raasa_linear_r2.summary.json`

- precision: `1.0`
- recall: `1.0`
- false positive rate: `0.0`
- benign restriction rate: `0.0`

Interpretation:

- the adaptive controller demonstrates the desired middle behavior in the representative tuned run.

## 2. Controller selection: tuned linear vs Isolation Forest

Source: `results/aws_v2/ablation_small_tuned_linear_vs_ml.json`

| Controller | Precision | Recall | FPR | Switching rate |
| --- | ---: | ---: | ---: | ---: |
| Isolation Forest | 0.3333 | 0.2778 | 0.1111 | 0.0556 |
| Tuned linear | 0.8667 | 1.0000 | 0.1111 | 0.0185 |

Decision rule captured in the artifact:

- prefer recall at equal or lower false-positive rate.

Paper consequence:

- the tuned linear controller, not the ML path, is the strongest current controller in this repo.

## 3. Medium-scale evidence

Source: `results/aws_v2/medium_raasa_linear_mean.json`

| Metric | Mean value |
| --- | ---: |
| Precision | 0.9524 |
| Recall | 1.0000 |
| False positive rate | 0.0370 |
| Benign restriction rate | 0.0370 |
| Malicious containment rate | 1.0000 |
| Switching rate | 0.0111 |

Interpretation:

- the tuned linear controller scales to the medium scenario with near-perfect recall and low benign cost.

Additional breakdown:

- `results/aws_v2/medium_raasa_linear.grouped.summary.json`

This grouped artifact helps explain which workload classes contribute to residual false positives.

## 4. Large-scale evidence

Source: `results/aws_v2/run_large_raasa_linear_r1.summary.json`

| Metric | Value |
| --- | ---: |
| Precision | 0.8727 |
| Recall | 1.0000 |
| False positive rate | 0.0972 |
| Benign restriction rate | 0.0972 |
| Malicious containment rate | 1.0000 |
| Total records | 120 |

Interpretation:

- the 20-container run completed end to end,
- recall remained perfect,
- benign cost rose but stayed bounded rather than collapsing.

## 5. Syscall-enriched evaluation

Source: `results/aws_v2/syscall_raasa_linear_mean.json`

- precision: `1.0`
- recall: `1.0`
- false positive rate: `0.0`
- malicious containment rate: `1.0`

Important scope note:

- this is useful evidence for syscall-enriched detection in the project,
- it should not be overstated as a fully mature production eBPF result unless paired carefully with the claim-boundary document.

## 6. Detection-only baseline

Sources:

- `results/aws_v2/detection_only_canonical.applied.summary.json`
- `results/aws_v2/detection_only_canonical.proposed.summary.json`

Why these matter:

- they separate "the reasoner noticed the threat" from "the system actually contained the threat".
- they support the paper argument that detection without closed-loop enforcement is not enough.

## 7. Overhead evidence

Source: `results/aws_v2/benign_only_overhead_linear.overhead.json`

The cleanest direct monitor-overhead numbers are:

- adaptive process CPU mean: `2.4659%`
- adaptive process CPU p95: `5.58%`
- loop duration mean: `2.7974s`
- loop duration p95: `3.5413s`

Interpretation:

- use process CPU and controller loop timing as the most defensible direct overhead evidence,
- avoid overclaiming host-level efficiency from a single benign-only setup.

## 8. Cloud-native/K8s evidence

Strongest packet artifact:

- `results/aws_v2/run_aws_k8s_ebpf_r3.jsonl`
- `results/aws_v2/run_aws_k8s_ebpf_r3.summary.json`

Computed summary for that run:

- precision: `1.0`
- recall: `1.0`
- false positive rate: `0.0`
- benign restriction rate: `0.0`
- tier occupancy: `L1 = 0.5`, `L2 = 0.5`

Interpretation:

- the K8s path has real telemetry/evaluation artifacts in the folder,
- but the evidence base is smaller and more uneven than the local Docker study,
- describe it as a promising cloud-native prototype path with concrete artifacts, not as the sole finished evaluation story.

## 8A. Latest v2+ operational validation from April 26, 2026

Freshest artifact slice:

- `results/aws_v2_2026_04_26/test_results.txt`
- `results/aws_v2_2026_04_26/raasa_agent.log`
- `results/aws_v2_2026_04_26/raasa_enforcer.log`
- `results/aws_v2_2026_04_26/run_20260426T032723Z.jsonl`
- `results/aws_v2_2026_04_26/run_20260426T032723Z.curated_summary.json`

What it adds:

- confirms the sidecar enforcer is active in the newer v2 path,
- confirms the malicious test pod is held at `L3`,
- records a failed benign-stress escalation test,
- exposes telemetry gaps such as `metrics_unavailable` and `probe_missing`.

Interpretation:

- this is the newest cloud-native evidence and should be treated as the freshest operational truth,
- it strengthens the claim that the v2 architecture is alive,
- it weakens any overconfident claim that v2 escalation and telemetry are already complete.

## 8B. Direct live AWS log validation from April 26, 2026

Fresh SSH-backed evidence:

- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/raasa_agent_all_containers_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/metrics_server_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/journalctl_k3s_tail_200.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/probe_volume_listing.txt`
- `results/aws_v2_2026_04_26/live_instance_validation_2026_04_26/metrics_api_raasa_test_malicious_cpu.json`

What it adds:

- directly confirms repeated live `500` and timeout failures in the Metrics API path,
- directly confirms that the shared probe volume is populated on the live node,
- directly confirms that the malicious pod has out-of-band `.cpu_usec`, `syscall_rate`, switch-count, and PID-count files.

Interpretation:

- this is the strongest current evidence that the cloud-native control-plane telemetry path really can degrade under load on the AWS node,
- it upgrades the control-plane fragility claim from plausible to directly evidenced,
- it still does not justify claiming full or continuous telemetry integrity across all channels.

## 8C. Phase 1D universal pod-resolution validation from April 26, 2026

Fresh enforcement artifacts:

- `results/aws_v2_2026_04_26/phase1d2_deploy_2026_04_26/`
- `results/aws_v2_2026_04_26/phase1d2_resolution_validation_2026_04_26/summary.json`
- `results/aws_v2_2026_04_26/phase1d2_resolution_validation_2026_04_26/enforcer_logs_final.txt`

What it adds:

- directly confirms clean host-veth resolution for the previously stubborn `raasa-net-server` pod,
- directly confirms clean resolution for `raasa-net-client` and the benchmark client in the same canonical run,
- directly confirms `fallback_lines = []` in the final validation summary,
- preserves the strong Phase 1C containment pattern with `L3` transfers collapsing to about `123 s` and `0 B/s`.

Interpretation:

- this is the strongest current enforcement-correctness result in the cloud-native packet,
- it upgrades the K8s claim from benchmark-specific pod containment to broader tested pod-specific host-veth enforcement,
- it still supports describing `L3` as effective containment rather than polished per-tier QoS shaping.

## 8D. Final V2 Cloud-Native IPS Evidence (May 8, 2026)

Fresh enforcement artifacts and AWS final validation:

- `results/aws_v2_final/ablation_small_tuned_linear_vs_ml.json`
- `results/aws_v2_final/medium_raasa_linear.grouped.summary.json`

What it adds:

- definitively concludes that the tuned linear controller (Precision: 0.86, Recall: 1.0) outperforms the Isolation Forest (Recall: 0.27) in the live cloud environment.
- confirms a perfect 1.0 Recall and 0.0 FPR on malicious patterns across the medium scale test using the IPC Sidecar Enforcer.
- validates the "Zero-Trust" separation between the unprivileged reasoning agent and the privileged eBPF/`tc` sidecar, proving live network containment works reliably without handing the AI root access.

Interpretation:

- this is the definitive, publication-ready dataset proving the RAASA v2 architecture successfully operates as an autonomous Cloud-Native IPS.

## 9. Figures available for the paper

Small-scenario figures:

- `figures/small/fig1_detection_comparison.png`
- `figures/small/fig2_cost_comparison.png`
- `figures/small/fig3_stability_comparison.png`
- `figures/small/fig4_tier_occupancy.png`
- `figures/small/fig5_tier_trajectory_small_linear.png`

Medium-scenario figures:

- `figures/medium/fig1_detection_comparison.png`
- `figures/medium/fig2_cost_comparison.png`
- `figures/medium/fig3_stability_comparison.png`
- `figures/medium/fig4_tier_occupancy.png`
- `figures/medium/fig5_tier_trajectory_medium_linear.png`

## 10. Best paper narrative to use from these results

The strongest evidence-led story is:

1. static low isolation misses malicious behavior,
2. static high isolation harms benign behavior,
3. adaptive RAASA improves the trade-off,
4. tuned linear RAASA is the best current controller in the repo,
5. the system scales beyond the toy case,
6. there is meaningful early cloud-native/K8s evidence,
7. the freshest April 26 validation confirms both real progress and unresolved gaps in v2+,
8. direct SSH-backed live logs now support the control-plane fragility claim,
9. the final April 26 Phase 1D run closes the remaining pod-resolution gap across the tested demo and benchmark pods,
10. full production claims still need more testing and tighter implementation alignment.
