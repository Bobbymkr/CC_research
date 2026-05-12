# RAASA Paper Folder Builder
# Creates paper/ with every file needed for writing the research paper.
# Run from project root: powershell -File build_paper_folder.ps1

$root  = "."
$paper = "paper"

# ── Create folder tree ───────────────────────────────────────────────────────
$folders = @(
    "$paper\01_draft_and_writing",
    "$paper\02_supporting_docs",
    "$paper\03_results_data",
    "$paper\04_figures",
    "$paper\05_references_and_plan",
    "$paper\06_original_docs"
)
foreach ($f in $folders) {
    New-Item -ItemType Directory -Force -Path $f | Out-Null
}

# ── Helper: copy with optional rename ────────────────────────────────────────
function Copy-To($src, $dst) {
    if (Test-Path $src) {
        Copy-Item -Path $src -Destination $dst -Force
        Write-Host "  [OK] $src -> $dst"
    } else {
        Write-Host "  [--] SKIP (not found): $src"
    }
}

Write-Host "`n=== Building paper/ folder ==="

# ── 01: Draft & Writing ───────────────────────────────────────────────────────
Write-Host "`n[01] Draft and writing files..."
Copy-To "RM_practical\_draft_paper.txt"            "$paper\01_draft_and_writing\"
Copy-To "RM_practical\paper_canonical_sections.txt" "$paper\01_draft_and_writing\"
Copy-To "RAASA_Final_v2.docx"                       "$paper\01_draft_and_writing\"
Copy-To "REPRODUCIBILITY.md"                        "$paper\01_draft_and_writing\"
Copy-To "RM_practical\reproduction_commands.txt"    "$paper\01_draft_and_writing\"
Copy-To "RM_practical\README.md"                    "$paper\01_draft_and_writing\RM_practical_README.md"
Copy-To "walkthrough_25_4_2026"                     "$paper\01_draft_and_writing\walkthrough_25_4_2026.txt"

# ── 02: Supporting Documentation ─────────────────────────────────────────────
Write-Host "`n[02] Supporting documentation..."
# From docs/
$docs_files = @(
    "docs\project_documentation.md",
    "docs\live_experiment_notes.md",
    "docs\threat_matrix.md",
    "docs\tuning_notes.md",
    "docs\next_generation_roadmap.md",
    "docs\RAASA_Evaluation_Report.md",
    "docs\evaluation_report.md",
    "docs\evaluation_report_latest_23rd_april.md",
    "docs\evaluation_report_aws_friendly.md",
    "docs\RAASA_Evolution_and_Achievements.md",
    "docs\future_implementation.md",
    "docs\execution_errors.md"
)
foreach ($f in $docs_files) {
    Copy-To $f "$paper\02_supporting_docs\"
}

# From raasa_docs/
Copy-To "raasa_docs\raasa_expert_analysis.md"  "$paper\02_supporting_docs\"
Copy-To "raasa_docs\implementation_plan.md"    "$paper\02_supporting_docs\"
Copy-To "raasa_docs\task.md"                   "$paper\02_supporting_docs\"

# ── 03: Results Data ──────────────────────────────────────────────────────────
Write-Host "`n[03] Results and evidence files..."
# Core three comparison summaries
Copy-To "RM_practical\run_L1.summary.json"              "$paper\03_results_data\"
Copy-To "RM_practical\run_L3.summary.json"              "$paper\03_results_data\"
Copy-To "RM_practical\run_aws_k8s_ebpf_r3.summary.json" "$paper\03_results_data\"
Copy-To "RM_practical\artifact_manifest.json"           "$paper\03_results_data\"
Copy-To "RM_practical\paper_section_map.json"           "$paper\03_results_data\"

# All aws_v2 summary JSONs
$aws_summaries = Get-ChildItem "RM_practical\results\aws_v2\" -Filter "*.summary.json" -ErrorAction SilentlyContinue
foreach ($f in $aws_summaries) {
    Copy-To $f.FullName "$paper\03_results_data\aws_v2_$($f.Name)"
}
# Ablation and overhead special files
Copy-To "RM_practical\results\aws_v2\ablation_small_tuned_linear_vs_ml.json"        "$paper\03_results_data\"
Copy-To "RM_practical\results\aws_v2\benign_only_overhead_linear.overhead.json"     "$paper\03_results_data\"
Copy-To "RM_practical\results\aws_v2\medium_raasa_linear_mean.json"                 "$paper\03_results_data\"

# Execution results
Copy-To "execution_results.json"  "$paper\03_results_data\"

# RM_practical numbered phase docs (phases 01-14)
Write-Host "  Copying RM_practical phase docs..."
$phase_docs = Get-ChildItem "RM_practical\" -Filter "*.md" -ErrorAction SilentlyContinue
foreach ($f in $phase_docs) {
    if ($f.Name -match "^\d{2}_") {
        Copy-To $f.FullName "$paper\02_supporting_docs\phases\$($f.Name)"
    }
}

# ── 04: Figures ───────────────────────────────────────────────────────────────
Write-Host "`n[04] Paper figures (PNG)..."
$figs = Get-ChildItem "RM_practical\figures\" -Filter "*.png" -ErrorAction SilentlyContinue
foreach ($f in $figs) {
    Copy-To $f.FullName "$paper\04_figures\"
}

# ── 05: References and Plan ───────────────────────────────────────────────────
Write-Host "`n[05] References and project plan..."
Copy-To "PLAN.md"                           "$paper\05_references_and_plan\"
Copy-To "AGENTS.md"                         "$paper\05_references_and_plan\"
Copy-To "graphify-out\GRAPH_REPORT.md"      "$paper\05_references_and_plan\GRAPH_REPORT.md"
Copy-To "RM_practical\06_paper_alignment_and_claim_boundaries.md" "$paper\05_references_and_plan\"
Copy-To "RM_practical\08_stronger_paper_test_plan_aws_m7i_flex_large.md" "$paper\05_references_and_plan\"

# ── 06: Original Source PDFs / Office docs ────────────────────────────────────
Write-Host "`n[06] Original PDFs and office docs..."
Copy-To "23DIT035.pdf"  "$paper\06_original_docs\"
Copy-To "RM.pdf"        "$paper\06_original_docs\"
Copy-To "RAASA_Final_v2.docx" "$paper\06_original_docs\"  # keep original here too

# ── Write README index ────────────────────────────────────────────────────────
Write-Host "`n[README] Writing paper/README.md index..."

$readme = @"
# RAASA Research Paper — Single-Location Reference Folder
**Generated**: $(Get-Date -Format 'yyyy-MM-dd HH:mm')
**Project**: Risk-Aware Adaptive Sandbox Allocation (RAASA)
**Authors**: Kunj Moradiya (23DIT035), Aryan Sangani (23DIT064)
**Institution**: DEPSTAR-IT, CHARUSAT

---

## Folder Structure

``````
paper/
├── 01_draft_and_writing/       <- Start here. Main paper draft + abstract/conclusion
├── 02_supporting_docs/         <- Architecture, evaluation, experiment notes
│   └── phases/                 <- Numbered AWS development phase logs
├── 03_results_data/            <- All JSON result summaries + evidence
├── 04_figures/                 <- All 6 publication-ready PNG figures
├── 05_references_and_plan/     <- PLAN.md, claim boundaries, graph report
└── 06_original_docs/           <- PDFs and Word documents
``````

---

## Where to Start Writing

| Task | File |
|------|------|
| **Main paper draft** | ``01_draft_and_writing\_draft_paper.txt`` |
| **Abstract + Conclusion (v2)** | ``01_draft_and_writing\paper_canonical_sections.txt`` |
| **Word version** | ``01_draft_and_writing\RAASA_Final_v2.docx`` |
| **Reproducibility** | ``01_draft_and_writing\REPRODUCIBILITY.md`` |

## Key Results at a Glance

| Mode | Precision | Recall | FPR | Benign Restriction |
|------|-----------|--------|-----|--------------------|
| Static L1 | 0.00 | 0.00 | 0.00 | 0.00 |
| Static L3 | 0.33 | 1.00 | 1.00 | 1.00 |
| **RAASA (Adaptive)** | **0.87*** | **1.00** | **0.11*** | **0.11*** |
| RAASA (AWS K8s) | **1.00** | **1.00** | **0.00** | **0.00** |

*3-run mean of small_tuned scenario. AWS run hits 1.0 across all metrics.

## Figures

| File | Figure No. | Caption |
|------|-----------|---------|
| ``fig1_detection_comparison.png`` | Fig 1 | Precision / Recall / FPR by mode |
| ``fig2_cost_comparison.png`` | Fig 2 | Containment pressure + benign restriction |
| ``fig3_tier_occupancy.png`` | Fig 3 | L1/L2/L3 tier distribution across scenarios |
| ``fig4_scalability.png`` | Fig 4 | Performance vs container count (3/10/20) |
| ``fig5_tier_trajectory.png`` | Fig 5 | Live tier transitions over time |
| ``fig6_ablation_linear_vs_ml.png`` | Fig 6 | Linear vs Isolation Forest ablation |

## Architecture (from Graphify)

- **499 nodes · 1,172 edges · 26 communities**
- Top god nodes: ContainerTelemetry → RiskAssessor → FeatureVector → Assessment → PolicyReasoner
- Full graph report: ``05_references_and_plan\GRAPH_REPORT.md``

## References

References [1]–[17] are embedded at the end of ``01_draft_and_writing\_draft_paper.txt``.
"@

$readme | Out-File -FilePath "$paper\README.md" -Encoding utf8
Write-Host "  [OK] paper\README.md"

# ── Final summary ─────────────────────────────────────────────────────────────
Write-Host "`n=== DONE ==="
$total = (Get-ChildItem $paper -Recurse | Where-Object {!$_.PSIsContainer}).Count
Write-Host "  Total files in paper/: $total"
Write-Host "  Location: $(Resolve-Path $paper)"
