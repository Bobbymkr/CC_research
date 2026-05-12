# RAASA Research Paper â€” Single-Location Reference Folder
**Generated**: 2026-05-05 07:46
**Project**: Risk-Aware Adaptive Sandbox Allocation (RAASA)
**Authors**: Kunj Moradiya (23DIT035), Aryan Sangani (23DIT064)
**Institution**: DEPSTAR-IT, CHARUSAT

---

## Folder Structure

```
paper/
â”œâ”€â”€ 01_draft_and_writing/       <- Start here. Main paper draft + abstract/conclusion
â”œâ”€â”€ 02_supporting_docs/         <- Architecture, evaluation, experiment notes
â”‚   â””â”€â”€ phases/                 <- Numbered AWS development phase logs
â”œâ”€â”€ 03_results_data/            <- All JSON result summaries + evidence
â”œâ”€â”€ 04_figures/                 <- All 6 publication-ready PNG figures
â”œâ”€â”€ 05_references_and_plan/     <- PLAN.md, claim boundaries, graph report
â””â”€â”€ 06_original_docs/           <- PDFs and Word documents
```

---

## Where to Start Writing

| Task | File |
|------|------|
| **Main paper draft** | `01_draft_and_writing\_draft_paper.txt` |
| **Abstract + Conclusion (v2)** | `01_draft_and_writing\paper_canonical_sections.txt` |
| **Word version** | `01_draft_and_writing\RAASA_Final_v2.docx` |
| **Reproducibility** | `01_draft_and_writing\REPRODUCIBILITY.md` |

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
| `fig1_detection_comparison.png` | Fig 1 | Precision / Recall / FPR by mode |
| `fig2_cost_comparison.png` | Fig 2 | Containment pressure + benign restriction |
| `fig3_tier_occupancy.png` | Fig 3 | L1/L2/L3 tier distribution across scenarios |
| `fig4_scalability.png` | Fig 4 | Performance vs container count (3/10/20) |
| `fig5_tier_trajectory.png` | Fig 5 | Live tier transitions over time |
| `fig6_ablation_linear_vs_ml.png` | Fig 6 | Linear vs Isolation Forest ablation |

## Architecture (from Graphify)

- **499 nodes Â· 1,172 edges Â· 26 communities**
- Top god nodes: ContainerTelemetry â†’ RiskAssessor â†’ FeatureVector â†’ Assessment â†’ PolicyReasoner
- Full graph report: `05_references_and_plan\GRAPH_REPORT.md`

## References

References [1]â€“[17] are embedded at the end of `01_draft_and_writing\_draft_paper.txt`.
