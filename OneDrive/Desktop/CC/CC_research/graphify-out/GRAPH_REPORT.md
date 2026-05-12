# Graph Report - CC_research  (2026-05-12)

## Corpus Check
- 115 files · ~1,101,799 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 795 nodes · 1918 edges · 29 communities detected
- Extraction: 59% EXTRACTED · 41% INFERRED · 0% AMBIGUOUS · INFERRED: 781 edges (avg confidence: 0.64)
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
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]

## God Nodes (most connected - your core abstractions)
1. `ContainerTelemetry` - 98 edges
2. `BaseObserver` - 77 edges
3. `Assessment` - 74 edges
4. `PolicyReasoner` - 67 edges
5. `FeatureVector` - 55 edges
6. `Tier` - 50 edges
7. `PolicyDecision` - 47 edges
8. `ObserverK8s` - 47 edges
9. `LLMPolicyAdvisor` - 40 edges
10. `RiskAssessor` - 38 edges

## Surprising Connections (you probably didn't know these)
- `FeatureVector` --uses--> `test_learned_model.py note L21`  [INFERRED]
  RM_practical\code\core\models.py → tests\test_learned_model.py
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
Cohesion: 0.03
Nodes (81): ABC, BaseObserver, collect(), base_observer.py note L1, base_observer.py note L24, base_observer.py note L28, ContainerTelemetry, ObserverK8s (+73 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (44): enforcement.py note L18, Enum, LLMPolicyAdvisor, llm_advisor.py note L1, llm_advisor.py note L132, llm_advisor.py note L48, llm_advisor.py note L51, llm_advisor.py note L72 (+36 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (40): _apply_mode_override(), _build_backend(), build_parser(), _containment_profile_for_tier(), app.py note L16, app.py note L182, Factory function: selects and initialises the Observer + Enforcer pair     that, Factory function: selects and initialises the Observer + Enforcer pair     that (+32 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (40): pytest_configure(), _allow_default_interface_fallback(), _apply_memory_limit(), _apply_network_throttle(), _clear_network_throttle(), _find_host_pids_for_pod_uid(), handle_command(), _init_k8s_client() (+32 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (30): compute_grouped_metrics(), compute_metrics(), _get_tier(), _grouped_summary_path_for(), load_records(), _mean(), _safe_divide(), _summary_path_for() (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (18): mean(), compute_means.py note L1, _clamp(), FeatureExtractor, features.py note L13, _clamp(), RiskAssessor, IsolationForestRiskTests (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (25): AppConfig, confidence_window(), controller_variant(), cooldown_seconds(), cpus_by_tier(), default_mode(), hysteresis_band(), l3_min_confidence() (+17 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (11): BaseObserver, _default_runner(), Observer, _parse_bytes(), _parse_float(), _parse_inspect_output(), _parse_stats_output(), _parse_top_output() (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (19): clear_approval(), get_approval_path(), load_approvals(), main(), save_approvals(), set_approval(), clear_override(), get_override_path() (+11 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (21): Capture-AgentAuditWindow(), Capture-AgentOverrides(), Capture-BenchmarkDiagnostics(), Clear-AgentOverride(), Copy-Remote(), Format-MapSummary(), Get-AgentOverrideTier(), Get-AuditRowsSummary() (+13 more)

### Community 10 - "Community 10"
Cohesion: 0.25
Nodes (18): _build_parser(), _cli(), _load_loop_durations(), _mean(), _measure_baseline_cpu(), measure_benign_only_overhead(), _measure_controller_cpu(), _percentile() (+10 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (5): WorkloadSpec, build_scenario(), ScenarioItem, ModeOverrideTests, ScenarioTests

### Community 12 - "Community 12"
Cohesion: 0.29
Nodes (12): annotate_bars(), fig1_detection(), fig2_cost(), fig3_tier_occupancy(), fig4_scale(), fig5_trajectory(), fig6_ablation(), load() (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.32
Nodes (10): Add-MapCount(), Capture-AuditDelta(), Format-MapSummary(), Get-AgentPod(), Get-AuditSummary(), Get-RemoteAuditLines(), Get-RemoteAuditState(), Invoke-NativeCapture() (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.3
Nodes (10): Copy-Remote(), Format-MapSummary(), Get-AuditRowsSummary(), Get-RemoteAuditCursor(), Get-RemoteAuditLines(), Get-ShellSingleQuoted(), Invoke-AgentPython(), Invoke-NativeCapture() (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.3
Nodes (8): build_parser(), build_snapshot(), _docker_info(), _git_info(), _kubectl_info(), main(), _run_command(), CaptureLocalEnvironmentTests

### Community 16 - "Community 16"
Cohesion: 0.31
Nodes (9): Add-MapCount(), Copy-Remote(), Format-MapSummary(), Get-AuditSummary(), Get-RemoteAuditLines(), Get-RemoteAuditState(), Invoke-NativeCapture(), Invoke-SSH() (+1 more)

### Community 17 - "Community 17"
Cohesion: 0.2
Nodes (1): experiments/__init__.py note L1

### Community 18 - "Community 18"
Cohesion: 0.47
Nodes (7): Copy-Remote(), Get-MetricSummary(), Get-QdiscStats(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Set-QdiscRate()

### Community 19 - "Community 19"
Cohesion: 0.43
Nodes (6): Copy-Remote(), Get-RemoteAuditLines(), Get-RemoteAuditState(), Invoke-NativeCapture(), Invoke-SSH(), Save-RemoteOutput()

### Community 20 - "Community 20"
Cohesion: 0.54
Nodes (6): Copy-Remote(), Get-MetricSummary(), Invoke-Benchmark(), Invoke-SSH(), New-RestrictedKeyCopy(), Send-EnforcementCommand()

### Community 21 - "Community 21"
Cohesion: 0.4
Nodes (2): Get-AwsBaseArgs(), Invoke-AwsJson()

### Community 22 - "Community 22"
Cohesion: 0.6
Nodes (3): Copy-Remote(), Invoke-SSH(), New-RestrictedKeyCopy()

### Community 24 - "Community 24"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 25 - "Community 25"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), New-RestrictedKeyCopy()

### Community 26 - "Community 26"
Cohesion: 0.67
Nodes (2): Invoke-SSH(), Save-RemoteOutput()

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): analyze_latest.py note L1

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Server used by the privileged sidecar to receive commands.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Start the socket listener in a background thread.

## Knowledge Gaps
- **28 isolated node(s):** `analyze_latest.py note L1`, `compute_means.py note L1`, `generate_paper_figures.py note L1`, `generate_paper_figures.py note L233`, `plots.py note L64` (+23 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (10 nodes): `experiments/__init__.py note L1`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`, `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (6 nodes): `Add-MarkdownLine()`, `Convert-ToPercent()`, `Get-AwsBaseArgs()`, `Get-ValueOrDefault()`, `Invoke-AwsJson()`, `check_aws_free_tier.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_aws_live_validation.ps1`, `collect_aws_live_validation.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `collect_phase1g_calibration_snapshot.ps1`, `collect_phase1g_calibration_snapshot.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (4 nodes): `Invoke-SSH()`, `New-RestrictedKeyCopy()`, `Save-RemoteOutput()`, `deep_diagnose_aws.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (2 nodes): `analyze_latest.py`, `analyze_latest.py note L1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Server used by the privileged sidecar to receive commands.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Start the socket listener in a background thread.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ContainerTelemetry` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 7`?**
  _High betweenness centrality (0.147) - this node is a cross-community bridge._
- **Why does `run_controller()` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 5`, `Community 6`, `Community 10`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `Tier` connect `Community 1` to `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 11`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `ContainerTelemetry` (e.g. with `BaseObserver` and `base_observer.py note L1`) actually correct?**
  _`ContainerTelemetry` has 96 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `BaseObserver` (e.g. with `ContainerTelemetry` and `Observer`) actually correct?**
  _`BaseObserver` has 73 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `Assessment` (e.g. with `LLMPolicyAdvisor` and `llm_advisor.py note L1`) actually correct?**
  _`Assessment` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 39 inferred relationships involving `PolicyReasoner` (e.g. with `Factory function: selects and initialises the Observer + Enforcer pair     that` and `LLMPolicyAdvisor`) actually correct?**
  _`PolicyReasoner` has 39 INFERRED edges - model-reasoned connections that need verification._