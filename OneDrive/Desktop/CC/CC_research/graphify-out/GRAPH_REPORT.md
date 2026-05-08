# Graph Report - CC_research  (2026-05-08)

## Corpus Check
- 104 files · ~378,156 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 505 nodes · 1182 edges · 21 communities detected
- Extraction: 66% EXTRACTED · 34% INFERRED · 0% AMBIGUOUS · INFERRED: 399 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]

## God Nodes (most connected - your core abstractions)
1. `ContainerTelemetry` - 48 edges
2. `RiskAssessor` - 35 edges
3. `FeatureVector` - 34 edges
4. `Assessment` - 31 edges
5. `PolicyReasoner` - 30 edges
6. `BaseObserver` - 28 edges
7. `Tier` - 26 edges
8. `ObserverK8s` - 26 edges
9. `Observer` - 23 edges
10. `PolicyDecision` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Abstract telemetry collector. All backends must implement collect().` --uses--> `ContainerTelemetry`  [INFERRED]
  RM_practical\code\core\base_observer.py → RM_practical\code\core\models.py
- `mean()` --calls--> `mean_summaries()`  [INFERRED]
  compute_means.py → generate_paper_figures.py
- `mean()` --calls--> `_mean()`  [INFERRED]
  compute_means.py → RM_practical\code\analysis\overhead.py
- `mean()` --calls--> `_mean_summary()`  [INFERRED]
  compute_means.py → RM_practical\code\analysis\plots.py
- `load()` --calls--> `load_approvals()`  [INFERRED]
  generate_paper_figures.py → RM_practical\code\core\approval.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (27): Factory function: selects and initialises the Observer + Enforcer pair     that, Collect a telemetry snapshot for the given container/pod identifiers.          P, ActionEnforcer, _default_runner(), Applies CPU-based containment for the selected tier., Enum, LLMPolicyAdvisor, LLM-Powered Policy Advisor for RAASA.  This module acts as an advanced triage ov (+19 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (28): ABC, BaseObserver, collect(), Abstract base class for RAASA telemetry observers.  This interface is the archit, Abstract telemetry collector. All backends must implement collect()., BaseObserver, ObserverK8s, _parse_prometheus_labels() (+20 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (21): mean(), Compute mean metrics across the 3 latest tuned adaptive runs., _clamp(), FeatureExtractor, Converts raw telemetry into normalized feature signals., FeatureVector, _clamp(), Computes risk and confidence from normalized signals. (+13 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (28): AppConfig, confidence_window(), controller_variant(), cooldown_seconds(), cpus_by_tier(), default_mode(), hysteresis_band(), l3_min_confidence() (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (12): _default_runner(), Observer, _parse_bytes(), _parse_float(), _parse_inspect_output(), _parse_stats_output(), _parse_top_output(), Docker CLI-based telemetry collector. Used in prototype and Docker Desktop. (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (21): _apply_memory_limit(), _apply_network_throttle(), _clear_network_throttle(), _find_host_pids_for_pod_uid(), handle_command(), _init_k8s_client(), _list_target_interfaces(), main() (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (19): _apply_mode_override(), _build_backend(), build_parser(), # NOTE: Observer and ActionEnforcer are imported lazily inside _build_backend(), run_controller(), EnforcerK8s, Kubernetes-native enforcement backend for RAASA v2.  This component now acts as, Kubernetes-native enforcement backend (Client).      Sends containment requests (+11 more)

### Community 7 - "Community 7"
Cohesion: 0.18
Nodes (21): build_run_filename(), build_run_path(), _sanitize_run_label(), _build_parser(), _cli(), _load_loop_durations(), _mean(), _measure_baseline_cpu() (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.22
Nodes (18): clear_approval(), get_approval_path(), load_approvals(), main(), save_approvals(), set_approval(), clear_override(), get_override_path() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.18
Nodes (11): compute_grouped_metrics(), compute_metrics(), _get_tier(), _grouped_summary_path_for(), load_records(), _mean(), _safe_divide(), _summary_path_for() (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.2
Nodes (19): _bar_group(), build_plot_manifest(), _cli(), generate_all_plots(), _mean_summary(), plot_cost_comparison(), plot_detection_comparison(), plot_stability_comparison() (+11 more)

### Community 11 - "Community 11"
Cohesion: 0.15
Nodes (6): WorkloadSpec, build_scenario(), ScenarioItem, ConfigTests, ModeOverrideTests, ScenarioTests

### Community 12 - "Community 12"
Cohesion: 0.29
Nodes (12): annotate_bars(), fig1_detection(), fig2_cost(), fig3_tier_occupancy(), fig4_scale(), fig5_trajectory(), fig6_ablation(), load() (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.44
Nodes (8): Capture-BenchmarkDiagnostics(), Copy-Remote(), Get-MetricSummary(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Select-ResolutionSummary(), Send-EnforcementCommand()

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (1): Experiment orchestration for RAASA.

### Community 15 - "Community 15"
Cohesion: 0.47
Nodes (7): Copy-Remote(), Get-MetricSummary(), Get-QdiscStats(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Set-QdiscRate()

### Community 16 - "Community 16"
Cohesion: 0.54
Nodes (6): Copy-Remote(), Get-MetricSummary(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Send-EnforcementCommand()

### Community 17 - "Community 17"
Cohesion: 0.6
Nodes (3): Copy-Remote(), Invoke-SSH(), New-RestrictedKeyCopy()

### Community 19 - "Community 19"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 20 - "Community 20"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): Quick diagnostic: trace malicious container risk scores from latest JSONL run.

## Knowledge Gaps
- **18 isolated node(s):** `Quick diagnostic: trace malicious container risk scores from latest JSONL run.`, `Compute mean metrics across the 3 latest tuned adaptive runs.`, `RAASA Paper Figure Generator Uses real experiment summary JSONs to produce all p`, `Plot live tier transitions from the small_tuned_raasa_r1 run.`, `Draw a grouped bar chart on *ax* — one group per label, one bar per series.` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (9 nodes): `Experiment orchestration for RAASA.`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_phase1g_calibration_snapshot.ps1`, `collect_phase1g_calibration_snapshot.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_aws_live_validation.ps1`, `collect_aws_live_validation.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `analyze_latest.py`, `Quick diagnostic: trace malicious container risk scores from latest JSONL run.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_controller()` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 7`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Why does `ContainerTelemetry` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `Tier` connect `Community 0` to `Community 11`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.087) - this node is a cross-community bridge._
- **Are the 46 inferred relationships involving `ContainerTelemetry` (e.g. with `BaseObserver` and `Abstract base class for RAASA telemetry observers.  This interface is the archit`) actually correct?**
  _`ContainerTelemetry` has 46 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `RiskAssessor` (e.g. with `Factory function: selects and initialises the Observer + Enforcer pair     that` and `Assessment`) actually correct?**
  _`RiskAssessor` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 32 inferred relationships involving `FeatureVector` (e.g. with `FeatureExtractor` and `Converts raw telemetry into normalized feature signals.`) actually correct?**
  _`FeatureVector` has 32 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `str` (e.g. with `fig5_trajectory()` and `compute_metrics()`) actually correct?**
  _`str` has 31 INFERRED edges - model-reasoned connections that need verification._