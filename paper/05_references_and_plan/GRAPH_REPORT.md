# Graph Report - .  (2026-05-05)

## Corpus Check
- Large corpus: 687 files · ~303,717 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 499 nodes · 1172 edges · 21 communities detected
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 393 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_ContainerTelemetry  ObserverK8s  BaseObserver|ContainerTelemetry / ObserverK8s / BaseObserver]]
- [[_COMMUNITY_PolicyDecision  run_controller()  AuditLogger|PolicyDecision / run_controller() / AuditLogger]]
- [[_COMMUNITY_Assessment  PolicyReasoner  Tier|Assessment / PolicyReasoner / Tier]]
- [[_COMMUNITY_RiskAssessor  FeatureVector  .assess()|RiskAssessor / FeatureVector / .assess()]]
- [[_COMMUNITY_Observer  FakeRunner  telemetry.py|Observer / FakeRunner / telemetry.py]]
- [[_COMMUNITY_str  config.py  config.py|str / config.py / config.py]]
- [[_COMMUNITY_enforcer_sidecar.py  enforcer_sidecar.py  UnixSocketServer|enforcer_sidecar.py / enforcer_sidecar.py / UnixSocketServer]]
- [[_COMMUNITY_main()  load_approvals()  set_approval()|main() / load_approvals() / set_approval()]]
- [[_COMMUNITY_compute_metrics()  metrics.py  metrics.py|compute_metrics() / metrics.py / metrics.py]]
- [[_COMMUNITY_measure_benign_only_overh  main()  overhead.py|measure_benign_only_overh / main() / overhead.py]]
- [[_COMMUNITY_plots.py  plots.py  generate_all_plots()|plots.py / plots.py / generate_all_plots()]]
- [[_COMMUNITY_build_scenario()  ScenarioTests  ScenarioItem|build_scenario() / ScenarioTests / ScenarioItem]]
- [[_COMMUNITY_generate_paper_figures.py  save()  load()|generate_paper_figures.py / save() / load()]]
- [[_COMMUNITY_run_phase1d_resolution_va  run_phase1d_resolution_va  Invoke-SSH()|run_phase1d_resolution_va / run_phase1d_resolution_va / Invoke-SSH()]]
- [[_COMMUNITY_Experiment orchestration   __init__.py  __init__.py|Experiment orchestration  / __init__.py / __init__.py]]
- [[_COMMUNITY_run_phase1b_blast_radius.  run_phase1b_blast_radius.  Invoke-SSH()|run_phase1b_blast_radius. / run_phase1b_blast_radius. / Invoke-SSH()]]
- [[_COMMUNITY_run_phase1c_pod_specific_  run_phase1c_pod_specific_  Invoke-SSH()|run_phase1c_pod_specific_ / run_phase1c_pod_specific_ / Invoke-SSH()]]
- [[_COMMUNITY_deploy_agent_image_to_aws  deploy_agent_image_to_aws  Copy-Remote()|deploy_agent_image_to_aws / deploy_agent_image_to_aws / Copy-Remote()]]
- [[_COMMUNITY_Invoke-SSH()  New-RestrictedKeyCopy()  collect_aws_live_validati|Invoke-SSH() / New-RestrictedKeyCopy() / collect_aws_live_validati]]
- [[_COMMUNITY_Invoke-SSH()  New-RestrictedKeyCopy()  collect_phase1g_calibrati|Invoke-SSH() / New-RestrictedKeyCopy() / collect_phase1g_calibrati]]
- [[_COMMUNITY_analyze_latest.py  Quick diagnostic trace m|analyze_latest.py / Quick diagnostic: trace m]]

## God Nodes (most connected - your core abstractions)
1. `ContainerTelemetry` - 45 edges
2. `RiskAssessor` - 35 edges
3. `FeatureVector` - 34 edges
4. `Assessment` - 31 edges
5. `PolicyReasoner` - 30 edges
6. `Tier` - 26 edges
7. `ObserverK8s` - 26 edges
8. `BaseObserver` - 25 edges
9. `Observer` - 23 edges
10. `PolicyDecision` - 22 edges

## Surprising Connections (you probably didn't know these)
- `mean_summaries()` --calls--> `mean()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\generate_paper_figures.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\compute_means.py
- `_mean()` --calls--> `mean()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\overhead.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\compute_means.py
- `_mean_summary()` --calls--> `mean()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\plots.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\compute_means.py
- `load_approvals()` --calls--> `load()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\core\approval.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\generate_paper_figures.py
- `load_overrides()` --calls--> `load()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\core\override.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\generate_paper_figures.py
- `plot_tier_trajectory()` --calls--> `load_records()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\plots.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\metrics.py
- `main()` --calls--> `write_metrics_summary()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\experiments\run_experiment.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\metrics.py
- `measure_benign_only_overhead()` --calls--> `load_config()`  [INFERRED]
  C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\analysis\overhead.py → C:\Users\Admin\OneDrive\Desktop\CC\CC_research\RM_practical\code\core\config.py

## Communities

### Community 0 - "ContainerTelemetry / ObserverK8s / BaseObserver"
Cohesion: 0.06
Nodes (30): ABC, BaseObserver, collect(), Abstract base class for RAASA telemetry observers.  This interface is the archit, Abstract telemetry collector. All backends must implement collect()., Collect a telemetry snapshot for the given container/pod identifiers.          P, _clamp(), FeatureExtractor (+22 more)

### Community 1 - "PolicyDecision / run_controller() / AuditLogger"
Cohesion: 0.06
Nodes (34): _apply_mode_override(), _build_backend(), build_parser(), # NOTE: Observer and ActionEnforcer are imported lazily inside _build_backend(), Factory function: selects and initialises the Observer + Enforcer pair     that, run_controller(), ActionEnforcer, _default_runner() (+26 more)

### Community 2 - "Assessment / PolicyReasoner / Tier"
Cohesion: 0.12
Nodes (14): LLMPolicyAdvisor, LLM-Powered Policy Advisor for RAASA.  This module acts as an advanced triage ov, Simulated LLM reasoning based on deterministic rules so CI/CD tests can pass, Consults an LLM to resolve ambiguous risk policy decisions., Initialize the advisor.                  Parameters         ----------         t, Consult the LLM to confirm or override a proposed tier.                  Returns, Assessment, Tier (+6 more)

### Community 3 - "RiskAssessor / FeatureVector / .assess()"
Cohesion: 0.14
Nodes (16): mean(), Compute mean metrics across the 3 latest tuned adaptive runs., FeatureVector, _clamp(), Computes risk and confidence from normalized signals., RiskAssessor, IsolationForestRiskTests, Unit tests for the Isolation Forest ML risk scoring path in RiskAssessor. (+8 more)

### Community 4 - "Observer / FakeRunner / telemetry.py"
Cohesion: 0.11
Nodes (13): BaseObserver, _default_runner(), Observer, _parse_bytes(), _parse_float(), _parse_inspect_output(), _parse_stats_output(), _parse_top_output() (+5 more)

### Community 5 - "str / config.py / config.py"
Cohesion: 0.11
Nodes (28): AppConfig, confidence_window(), controller_variant(), cooldown_seconds(), cpus_by_tier(), default_mode(), hysteresis_band(), l3_min_confidence() (+20 more)

### Community 6 - "enforcer_sidecar.py / enforcer_sidecar.py / UnixSocketServer"
Cohesion: 0.14
Nodes (21): _apply_memory_limit(), _apply_network_throttle(), _clear_network_throttle(), _find_host_pids_for_pod_uid(), handle_command(), _init_k8s_client(), _list_target_interfaces(), main() (+13 more)

### Community 7 - "main() / load_approvals() / set_approval()"
Cohesion: 0.22
Nodes (18): clear_approval(), get_approval_path(), load_approvals(), main(), save_approvals(), set_approval(), clear_override(), get_override_path() (+10 more)

### Community 8 - "compute_metrics() / metrics.py / metrics.py"
Cohesion: 0.18
Nodes (11): compute_grouped_metrics(), compute_metrics(), _get_tier(), _grouped_summary_path_for(), load_records(), _mean(), _safe_divide(), _summary_path_for() (+3 more)

### Community 9 - "measure_benign_only_overh / main() / overhead.py"
Cohesion: 0.25
Nodes (18): _build_parser(), _cli(), _load_loop_durations(), _mean(), _measure_baseline_cpu(), measure_benign_only_overhead(), _measure_controller_cpu(), _percentile() (+10 more)

### Community 10 - "plots.py / plots.py / generate_all_plots()"
Cohesion: 0.2
Nodes (19): _bar_group(), build_plot_manifest(), _cli(), generate_all_plots(), _mean_summary(), plot_cost_comparison(), plot_detection_comparison(), plot_stability_comparison() (+11 more)

### Community 11 - "build_scenario() / ScenarioTests / ScenarioItem"
Cohesion: 0.15
Nodes (6): WorkloadSpec, build_scenario(), ScenarioItem, ConfigTests, ModeOverrideTests, ScenarioTests

### Community 12 - "generate_paper_figures.py / save() / load()"
Cohesion: 0.29
Nodes (12): annotate_bars(), fig1_detection(), fig2_cost(), fig3_tier_occupancy(), fig4_scale(), fig5_trajectory(), fig6_ablation(), load() (+4 more)

### Community 13 - "run_phase1d_resolution_va / run_phase1d_resolution_va / Invoke-SSH()"
Cohesion: 0.44
Nodes (8): Capture-BenchmarkDiagnostics(), Copy-Remote(), Get-MetricSummary(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Select-ResolutionSummary(), Send-EnforcementCommand()

### Community 14 - "Experiment orchestration  / __init__.py / __init__.py"
Cohesion: 0.22
Nodes (1): Experiment orchestration for RAASA.

### Community 15 - "run_phase1b_blast_radius. / run_phase1b_blast_radius. / Invoke-SSH()"
Cohesion: 0.47
Nodes (7): Copy-Remote(), Get-MetricSummary(), Get-QdiscStats(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Set-QdiscRate()

### Community 16 - "run_phase1c_pod_specific_ / run_phase1c_pod_specific_ / Invoke-SSH()"
Cohesion: 0.54
Nodes (6): Copy-Remote(), Get-MetricSummary(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Send-EnforcementCommand()

### Community 17 - "deploy_agent_image_to_aws / deploy_agent_image_to_aws / Copy-Remote()"
Cohesion: 0.6
Nodes (3): Copy-Remote(), Invoke-SSH(), New-RestrictedKeyCopy()

### Community 19 - "Invoke-SSH() / New-RestrictedKeyCopy() / collect_aws_live_validati"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 20 - "Invoke-SSH() / New-RestrictedKeyCopy() / collect_phase1g_calibrati"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 21 - "analyze_latest.py / Quick diagnostic: trace m"
Cohesion: 1.0
Nodes (1): Quick diagnostic: trace malicious container risk scores from latest JSONL run.

## Knowledge Gaps
- **18 isolated node(s):** `Quick diagnostic: trace malicious container risk scores from latest JSONL run.`, `Compute mean metrics across the 3 latest tuned adaptive runs.`, `RAASA Paper Figure Generator Uses real experiment summary JSONs to produce all p`, `Plot live tier transitions from the small_tuned_raasa_r1 run.`, `Draw a grouped bar chart on *ax* — one group per label, one bar per series.` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Experiment orchestration  / __init__.py / __init__.py`** (9 nodes): `Experiment orchestration for RAASA.`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Invoke-SSH() / New-RestrictedKeyCopy() / collect_aws_live_validati`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_aws_live_validation.ps1`, `collect_aws_live_validation.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Invoke-SSH() / New-RestrictedKeyCopy() / collect_phase1g_calibrati`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_phase1g_calibration_snapshot.ps1`, `collect_phase1g_calibration_snapshot.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `analyze_latest.py / Quick diagnostic: trace m`** (2 nodes): `analyze_latest.py`, `Quick diagnostic: trace malicious container risk scores from latest JSONL run.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_controller()` connect `PolicyDecision / run_controller() / AuditLogger` to `ContainerTelemetry / ObserverK8s / BaseObserver`, `Assessment / PolicyReasoner / Tier`, `RiskAssessor / FeatureVector / .assess()`, `str / config.py / config.py`, `measure_benign_only_overh / main() / overhead.py`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `ContainerTelemetry` connect `ContainerTelemetry / ObserverK8s / BaseObserver` to `PolicyDecision / run_controller() / AuditLogger`, `Assessment / PolicyReasoner / Tier`, `Observer / FakeRunner / telemetry.py`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `Tier` connect `Assessment / PolicyReasoner / Tier` to `ContainerTelemetry / ObserverK8s / BaseObserver`, `PolicyDecision / run_controller() / AuditLogger`, `build_scenario() / ScenarioTests / ScenarioItem`, `str / config.py / config.py`?**
  _High betweenness centrality (0.089) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `ContainerTelemetry` (e.g. with `BaseObserver` and `Abstract base class for RAASA telemetry observers.  This interface is the archit`) actually correct?**
  _`ContainerTelemetry` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `RiskAssessor` (e.g. with `Factory function: selects and initialises the Observer + Enforcer pair     that` and `Assessment`) actually correct?**
  _`RiskAssessor` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `FeatureVector` (e.g. with `FeatureExtractor` and `Converts raw telemetry into normalized feature signals.`) actually correct?**
  _`FeatureVector` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `str` (e.g. with `fig5_trajectory()` and `compute_metrics()`) actually correct?**
  _`str` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `Assessment` (e.g. with `LLMPolicyAdvisor` and `LLM-Powered Policy Advisor for RAASA.  This module acts as an advanced triage ov`) actually correct?**
  _`Assessment` has 29 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Quick diagnostic: trace malicious container risk scores from latest JSONL run.`, `Compute mean metrics across the 3 latest tuned adaptive runs.`, `RAASA Paper Figure Generator Uses real experiment summary JSONs to produce all p` to the rest of the system?**
  _18 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ContainerTelemetry / ObserverK8s / BaseObserver` be split into smaller, more focused modules?**
  _Cohesion score 0.06 - nodes in this community are weakly interconnected._