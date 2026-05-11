# Graph Report - CC_research  (2026-05-09)

## Corpus Check
- 107 files · ~700,398 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 553 nodes · 1302 edges · 31 communities detected
- Extraction: 65% EXTRACTED · 35% INFERRED · 0% AMBIGUOUS · INFERRED: 461 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)

- [[_COMMUNITY_Community 0|ContainerTelemetry / BaseObserver [core/base_observer.py] / ObserverK8s]]
- [[_COMMUNITY_Community 1|Assessment / PolicyReasoner / Tier]]
- [[_COMMUNITY_Community 2|FeatureVector / RiskAssessor / FeatureExtractor]]
- [[_COMMUNITY_Community 3|load_config() / load_training_data() / AppConfig]]
- [[_COMMUNITY_Community 4|Observer / FakeRunner / _parse_stats_output()]]
- [[_COMMUNITY_Community 5|run_controller() / UnixSocketClient / EnforcerK8s]]
- [[_COMMUNITY_Community 6|UnixSocketServer / _apply_network_throttle() / _resolve_pod_interface()]]
- [[_COMMUNITY_Community 7|main() [experiments/run_experiment.py] / measure_benign_only_overhead() / start_scenario()]]
- [[_COMMUNITY_Community 8|main() [core/review.py] / load_approvals() / load_overrides()]]
- [[_COMMUNITY_Community 9|AnalysisTests / compute_metrics() / write_metrics_summary()]]
- [[_COMMUNITY_Community 10|generate_all_plots() / _bar_group() / _mean_summary()]]
- [[_COMMUNITY_Community 11|build_scenario() / ScenarioTests / ConfigTests]]
- [[_COMMUNITY_Community 12|save() / load() / annotate_bars()]]
- [[_COMMUNITY_Community 13|Invoke-SSH() [k8s/run_phase1d_resolution_validation.ps1] / Copy-Remote() [k8s/run_phase1d_resolution_validation.ps1] / Send-EnforcementCommand() [k8s/run_phase1d_resolution_validation.ps1]]]
- [[_COMMUNITY_Community 14|analysis/__init__.py [analysis/__init__.py] / core/__init__.py [core/__init__.py] / experiments/__init__.py [experiments/__init__.py]]]
- [[_COMMUNITY_Community 15|Invoke-SSH() [k8s/run_phase1b_blast_radius.ps1] / Get-QdiscStats() / Invoke-Benchmark() [k8s/run_phase1b_blast_radius.ps1]]]
- [[_COMMUNITY_Community 16|Invoke-SSH() [scripts/run_closed_loop_soak_aws.ps1] / Invoke-NativeCapture() [scripts/run_closed_loop_soak_aws.ps1] / Copy-Remote() [scripts/run_closed_loop_soak_aws.ps1]]]
- [[_COMMUNITY_Community 17|Invoke-SSH() [k8s/run_phase1c_pod_specific_validation.ps1] / Send-EnforcementCommand() [k8s/run_phase1c_pod_specific_validation.ps1] / Copy-Remote() [k8s/run_phase1c_pod_specific_validation.ps1]]]
- [[_COMMUNITY_Community 18|Get-AwsBaseArgs() / Invoke-AwsJson() / Add-MarkdownLine()]]
- [[_COMMUNITY_Community 19|Copy-Remote() [k8s/deploy_agent_image_to_aws.ps1] / Invoke-SSH() [k8s/deploy_agent_image_to_aws.ps1] / New-RestrictedKeyCopy() [k8s/deploy_agent_image_to_aws.ps1]]]
- [[_COMMUNITY_Community 21|Invoke-SSH() [k8s/collect_aws_live_validation.ps1] / New-RestrictedKeyCopy() [k8s/collect_aws_live_validation.ps1] / collect_aws_live_validation.ps1 [k8s/collect_aws_live_validation.ps1]]]
- [[_COMMUNITY_Community 22|Invoke-SSH() [k8s/collect_phase1g_calibration_snapshot.ps1] / New-RestrictedKeyCopy() [k8s/collect_phase1g_calibration_snapshot.ps1] / collect_phase1g_calibration_snapshot.ps1 [k8s/collect_phase1g_calibration_snapshot.ps1]]]
- [[_COMMUNITY_Community 23|Invoke-SSH() [scripts/deep_diagnose_aws.ps1] / Save-RemoteOutput() [scripts/deep_diagnose_aws.ps1] / New-RestrictedKeyCopy() [scripts/deep_diagnose_aws.ps1]]]
- [[_COMMUNITY_Community 24|analyze_latest.py / analyze_latest.py note L1]]

## God Nodes (most connected - your core abstractions)
1. `ContainerTelemetry` - 55 edges
2. `Assessment` - 42 edges
3. `FeatureVector` - 40 edges
4. `PolicyReasoner` - 38 edges
5. `BaseObserver` - 35 edges
6. `RiskAssessor` - 35 edges
7. `Tier` - 31 edges
8. `ObserverK8s` - 29 edges
9. `PolicyDecision` - 27 edges
10. `Observer` - 23 edges

## Surprising Connections (you probably didn't know these)
- `mean()` --calls--> `mean_summaries()`  [INFERRED]
  compute_means.py → generate_paper_figures.py
- `mean()` --calls--> `_mean()`  [INFERRED]
  compute_means.py → RM_practical\code\analysis\overhead.py
- `mean()` --calls--> `_mean_summary()`  [INFERRED]
  compute_means.py → RM_practical\code\analysis\plots.py
- `load()` --calls--> `load_approvals()`  [INFERRED]
  generate_paper_figures.py → RM_practical\code\core\approval.py
- `load()` --calls--> `load_overrides()`  [INFERRED]
  generate_paper_figures.py → RM_practical\code\core\override.py

## Communities

### Community 0 - "ContainerTelemetry / BaseObserver [core/base_observer.py] / ObserverK8s"
Cohesion: 0.06
Nodes (84): ContainerTelemetry, BaseObserver [core/base_observer.py], ObserverK8s, ObserverK8sMetricsTests, ._get_pod_metrics(), .collect() [k8s/observer_k8s.py], ._make_observer_with_mock_k8s(), ObserverK8sSyscallProbeTests (+76 more)

### Community 1 - "Assessment / PolicyReasoner / Tier"
Cohesion: 0.07
Nodes (77): Assessment, PolicyReasoner, Tier, PolicyDecision, .decide(), LLMPolicyAdvisor, PolicyReasonerTests, AuditLogger (+69 more)

### Community 2 - "FeatureVector / RiskAssessor / FeatureExtractor"
Cohesion: 0.1
Nodes (50): FeatureVector, RiskAssessor, FeatureExtractor, .assess(), IsolationForestRiskTests, FeatureExtractorTests, LLMPolicyAdvisorTests, RiskAssessorTests (+42 more)

### Community 3 - "load_config() / load_training_data() / AppConfig"
Cohesion: 0.11
Nodes (34): load_config(), load_training_data(), AppConfig, controller_variant(), default_mode(), pytest_configure(), syscall_probe_directory(), syscall_source() (+26 more)

### Community 4 - "Observer / FakeRunner / _parse_stats_output()"
Cohesion: 0.12
Nodes (32): Observer, FakeRunner, _parse_stats_output(), .collect() [core/telemetry.py], ObserverTests, TelemetryParsingTests, _parse_inspect_output(), _parse_bytes() (+24 more)

### Community 5 - "run_controller() / UnixSocketClient / EnforcerK8s"
Cohesion: 0.11
Nodes (31): run_controller(), UnixSocketClient, EnforcerK8s, _build_backend(), start_metrics_server(), .apply() [k8s/enforcement_k8s.py], record_iteration(), _apply_mode_override() (+23 more)

### Community 6 - "UnixSocketServer / _apply_network_throttle() / _resolve_pod_interface()"
Cohesion: 0.14
Nodes (31): UnixSocketServer, _apply_network_throttle(), _resolve_pod_interface(), handle_command(), _list_target_interfaces(), _read_target_iflink(), _resolve_host_interface_for_pid(), _run_tc() (+23 more)

### Community 7 - "main() [experiments/run_experiment.py] / measure_benign_only_overhead() / start_scenario()"
Cohesion: 0.18
Nodes (28): main() [experiments/run_experiment.py], measure_benign_only_overhead(), start_scenario(), _measure_controller_cpu(), _measure_baseline_cpu(), cleanup_scenario(), summarize_overhead_report(), build_run_filename() (+20 more)

### Community 8 - "main() [core/review.py] / load_approvals() / load_overrides()"
Cohesion: 0.22
Nodes (24): main() [core/review.py], load_approvals(), load_overrides(), set_approval(), set_override(), clear_approval(), clear_override(), save_approvals() (+16 more)

### Community 9 - "AnalysisTests / compute_metrics() / write_metrics_summary()"
Cohesion: 0.18
Nodes (23): AnalysisTests, compute_metrics(), write_metrics_summary(), compute_grouped_metrics(), write_grouped_metrics_summary(), load_records(), _get_tier(), _grouped_summary_path_for() (+15 more)

### Community 10 - "generate_all_plots() / _bar_group() / _mean_summary()"
Cohesion: 0.2
Nodes (21): generate_all_plots(), _bar_group(), _mean_summary(), plot_cost_comparison(), plot_detection_comparison(), plot_stability_comparison(), plot_tier_trajectory(), _cli() [analysis/plots.py] (+13 more)

### Community 11 - "build_scenario() / ScenarioTests / ConfigTests"
Cohesion: 0.15
Nodes (20): build_scenario(), ScenarioTests, ConfigTests, ModeOverrideTests, ScenarioItem, .test_static_override_forces_tier(), WorkloadSpec, .test_benign_only_scenario_has_expected_mix() (+12 more)

### Community 12 - "save() / load() / annotate_bars()"
Cohesion: 0.29
Nodes (14): save(), load(), annotate_bars(), fig4_scale(), fig5_trajectory(), fig6_ablation(), mean_summaries(), fig1_detection() (+6 more)

### Community 13 - "Invoke-SSH() [k8s/run_phase1d_resolution_validation.ps1] / Copy-Remote() [k8s/run_phase1d_resolution_validation.ps1] / Send-EnforcementCommand() [k8s/run_phase1d_resolution_validation.ps1]"
Cohesion: 0.32
Nodes (13): Invoke-SSH() [k8s/run_phase1d_resolution_validation.ps1], Copy-Remote() [k8s/run_phase1d_resolution_validation.ps1], Send-EnforcementCommand() [k8s/run_phase1d_resolution_validation.ps1], Capture-BenchmarkDiagnostics(), Invoke-Benchmark() [k8s/run_phase1d_resolution_validation.ps1], Invoke-NativeCapture() [scripts/run_phase1d_resolution_validation.ps1], Get-MetricSummary() [k8s/run_phase1d_resolution_validation.ps1], New-RestrictedKeyCopy() [k8s/run_phase1d_resolution_validation.ps1] (+5 more)

### Community 14 - "analysis/__init__.py [analysis/__init__.py] / core/__init__.py [core/__init__.py] / experiments/__init__.py [experiments/__init__.py]"
Cohesion: 0.22
Nodes (9): analysis/__init__.py [analysis/__init__.py], core/__init__.py [core/__init__.py], experiments/__init__.py [experiments/__init__.py], raasa/__init__.py, workloads/__init__.py, experiments/__init__.py note L1 (+3 more)

### Community 15 - "Invoke-SSH() [k8s/run_phase1b_blast_radius.ps1] / Get-QdiscStats() / Invoke-Benchmark() [k8s/run_phase1b_blast_radius.ps1]"
Cohesion: 0.47
Nodes (9): Invoke-SSH() [k8s/run_phase1b_blast_radius.ps1], Get-QdiscStats(), Invoke-Benchmark() [k8s/run_phase1b_blast_radius.ps1], Set-QdiscRate(), Copy-Remote() [k8s/run_phase1b_blast_radius.ps1], Get-MetricSummary() [k8s/run_phase1b_blast_radius.ps1], New-RestrictedKeyCopy() [k8s/run_phase1b_blast_radius.ps1], run_phase1b_blast_radius.ps1 [k8s/run_phase1b_blast_radius.ps1] (+1 more)

### Community 16 - "Invoke-SSH() [scripts/run_closed_loop_soak_aws.ps1] / Invoke-NativeCapture() [scripts/run_closed_loop_soak_aws.ps1] / Copy-Remote() [scripts/run_closed_loop_soak_aws.ps1]"
Cohesion: 0.43
Nodes (8): Invoke-SSH() [scripts/run_closed_loop_soak_aws.ps1], Invoke-NativeCapture() [scripts/run_closed_loop_soak_aws.ps1], Copy-Remote() [scripts/run_closed_loop_soak_aws.ps1], Get-RemoteAuditLines(), Get-RemoteAuditState(), Save-RemoteOutput() [scripts/run_closed_loop_soak_aws.ps1], New-RestrictedKeyCopy() [scripts/run_closed_loop_soak_aws.ps1], run_closed_loop_soak_aws.ps1

### Community 17 - "Invoke-SSH() [k8s/run_phase1c_pod_specific_validation.ps1] / Send-EnforcementCommand() [k8s/run_phase1c_pod_specific_validation.ps1] / Copy-Remote() [k8s/run_phase1c_pod_specific_validation.ps1]"
Cohesion: 0.54
Nodes (8): Invoke-SSH() [k8s/run_phase1c_pod_specific_validation.ps1], Send-EnforcementCommand() [k8s/run_phase1c_pod_specific_validation.ps1], Copy-Remote() [k8s/run_phase1c_pod_specific_validation.ps1], Invoke-Benchmark() [k8s/run_phase1c_pod_specific_validation.ps1], Get-MetricSummary() [k8s/run_phase1c_pod_specific_validation.ps1], New-RestrictedKeyCopy() [k8s/run_phase1c_pod_specific_validation.ps1], run_phase1c_pod_specific_validation.ps1 [k8s/run_phase1c_pod_specific_validation.ps1], run_phase1c_pod_specific_validation.ps1 [scripts/run_phase1c_pod_specific_validation.ps1]

### Community 18 - "Get-AwsBaseArgs() / Invoke-AwsJson() / Add-MarkdownLine()"
Cohesion: 0.4
Nodes (6): Get-AwsBaseArgs(), Invoke-AwsJson(), Add-MarkdownLine(), Convert-ToPercent(), Get-ValueOrDefault(), check_aws_free_tier.ps1

### Community 19 - "Copy-Remote() [k8s/deploy_agent_image_to_aws.ps1] / Invoke-SSH() [k8s/deploy_agent_image_to_aws.ps1] / New-RestrictedKeyCopy() [k8s/deploy_agent_image_to_aws.ps1]"
Cohesion: 0.6
Nodes (5): Copy-Remote() [k8s/deploy_agent_image_to_aws.ps1], Invoke-SSH() [k8s/deploy_agent_image_to_aws.ps1], New-RestrictedKeyCopy() [k8s/deploy_agent_image_to_aws.ps1], deploy_agent_image_to_aws.ps1 [k8s/deploy_agent_image_to_aws.ps1], deploy_agent_image_to_aws.ps1 [scripts/deploy_agent_image_to_aws.ps1]

### Community 21 - "Invoke-SSH() [k8s/collect_aws_live_validation.ps1] / New-RestrictedKeyCopy() [k8s/collect_aws_live_validation.ps1] / collect_aws_live_validation.ps1 [k8s/collect_aws_live_validation.ps1]"
Cohesion: 0.67
Nodes (4): Invoke-SSH() [k8s/collect_aws_live_validation.ps1], New-RestrictedKeyCopy() [k8s/collect_aws_live_validation.ps1], collect_aws_live_validation.ps1 [k8s/collect_aws_live_validation.ps1], collect_aws_live_validation.ps1 [scripts/collect_aws_live_validation.ps1]

### Community 22 - "Invoke-SSH() [k8s/collect_phase1g_calibration_snapshot.ps1] / New-RestrictedKeyCopy() [k8s/collect_phase1g_calibration_snapshot.ps1] / collect_phase1g_calibration_snapshot.ps1 [k8s/collect_phase1g_calibration_snapshot.ps1]"
Cohesion: 0.67
Nodes (4): Invoke-SSH() [k8s/collect_phase1g_calibration_snapshot.ps1], New-RestrictedKeyCopy() [k8s/collect_phase1g_calibration_snapshot.ps1], collect_phase1g_calibration_snapshot.ps1 [k8s/collect_phase1g_calibration_snapshot.ps1], collect_phase1g_calibration_snapshot.ps1 [scripts/collect_phase1g_calibration_snapshot.ps1]

### Community 23 - "Invoke-SSH() [scripts/deep_diagnose_aws.ps1] / Save-RemoteOutput() [scripts/deep_diagnose_aws.ps1] / New-RestrictedKeyCopy() [scripts/deep_diagnose_aws.ps1]"
Cohesion: 0.67
Nodes (4): Invoke-SSH() [scripts/deep_diagnose_aws.ps1], Save-RemoteOutput() [scripts/deep_diagnose_aws.ps1], New-RestrictedKeyCopy() [scripts/deep_diagnose_aws.ps1], deep_diagnose_aws.ps1

### Community 24 - "analyze_latest.py / analyze_latest.py note L1"
Cohesion: 1.0
Nodes (2): analyze_latest.py, analyze_latest.py note L1

## Knowledge Gaps
- **72 isolated node(s):** `.__call__() [tests/test_enforcement_logger.py]`, `.__call__() [tests/test_telemetry.py]`, `.__init__() [core/enforcement.py]`, `.__init__() [core/features.py]`, `.__init__() [core/ipc.py]` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `analysis/__init__.py [analysis/__init__.py] / core/__init__.py [core/__init__.py] / experiments/__init__.py [experiments/__init__.py]`** (9 nodes): `analysis/__init__.py [analysis/__init__.py], core/__init__.py [core/__init__.py], experiments/__init__.py [experiments/__init__.py], raasa/__init__.py, workloads/__init__.py, experiments/__init__.py note L1 (+3 more)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Get-AwsBaseArgs() / Invoke-AwsJson() / Add-MarkdownLine()`** (6 nodes): `Get-AwsBaseArgs(), Invoke-AwsJson(), Add-MarkdownLine(), Convert-ToPercent(), Get-ValueOrDefault(), check_aws_free_tier.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `collect_aws_live_validation.ps1 [k8s/collect_aws_live_validation.ps1] / collect_aws_live_validation.ps1 [scripts/collect_aws_live_validation.ps1] / Invoke-SSH() [k8s/collect_aws_live_validation.ps1]`** (4 nodes): `collect_aws_live_validation.ps1 [k8s/collect_aws_live_validation.ps1], collect_aws_live_validation.ps1 [scripts/collect_aws_live_validation.ps1], Invoke-SSH() [k8s/collect_aws_live_validation.ps1], New-RestrictedKeyCopy() [k8s/collect_aws_live_validation.ps1]`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `collect_phase1g_calibration_snapshot.ps1 [k8s/collect_phase1g_calibration_snapshot.ps1] / collect_phase1g_calibration_snapshot.ps1 [scripts/collect_phase1g_calibration_snapshot.ps1] / Invoke-SSH() [k8s/collect_phase1g_calibration_snapshot.ps1]`** (4 nodes): `collect_phase1g_calibration_snapshot.ps1 [k8s/collect_phase1g_calibration_snapshot.ps1], collect_phase1g_calibration_snapshot.ps1 [scripts/collect_phase1g_calibration_snapshot.ps1], Invoke-SSH() [k8s/collect_phase1g_calibration_snapshot.ps1], New-RestrictedKeyCopy() [k8s/collect_phase1g_calibration_snapshot.ps1]`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Invoke-SSH() [scripts/deep_diagnose_aws.ps1] / Save-RemoteOutput() [scripts/deep_diagnose_aws.ps1] / New-RestrictedKeyCopy() [scripts/deep_diagnose_aws.ps1]`** (4 nodes): `Invoke-SSH() [scripts/deep_diagnose_aws.ps1], Save-RemoteOutput() [scripts/deep_diagnose_aws.ps1], New-RestrictedKeyCopy() [scripts/deep_diagnose_aws.ps1], deep_diagnose_aws.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `analyze_latest.py / analyze_latest.py note L1`** (2 nodes): `analyze_latest.py, analyze_latest.py note L1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_controller()` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 7`?**
  _High betweenness centrality (0.144) - this node is a cross-community bridge._
- **Why does `ContainerTelemetry` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `Tier` connect `Community 1` to `Community 11`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 53 inferred relationships involving `ContainerTelemetry` (e.g. with `BaseObserver` and `Abstract base class for RAASA telemetry observers.  This interface is the archit`) actually correct?**
  _`ContainerTelemetry` has 53 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `Assessment` (e.g. with `LLMPolicyAdvisor` and `LLM-Powered Policy Advisor for RAASA.  This module acts as an advanced triage ov`) actually correct?**
  _`Assessment` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `FeatureVector` (e.g. with `FeatureExtractor` and `Converts raw telemetry into normalized feature signals.`) actually correct?**
  _`FeatureVector` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `PolicyReasoner` (e.g. with `Factory function: selects and initialises the Observer + Enforcer pair     that` and `LLMPolicyAdvisor`) actually correct?**
  _`PolicyReasoner` has 23 INFERRED edges - model-reasoned connections that need verification._