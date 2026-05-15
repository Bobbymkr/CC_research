# RAASA Paper Tables

This directory stores source-controlled paper tables and the script that
renders them into reusable formats.

## Outputs

Running the renderer produces:

- Markdown tables for paper drafting and review
- CSV tables for spreadsheet or plotting workflows
- IEEE-oriented LaTeX tables for manuscript integration

All generated outputs are written to:

- [docs/tables/generated](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/tables/generated)

## Current tables

- `local_baseline_comparison`
  - adaptive vs static local evidence
- `cloud_evidence_ladder`
  - the main cloud-validation progression table
- `failure_degraded_mode_summary`
  - explicit degraded and fail-closed behavior
- `scope_nonclaims`
  - what the paper supports and does not support

## Render

```powershell
python docs/tables/render_paper_tables.py
```

The generated `.tex` files are intended to be `\input{...}`-ready inside an
IEEE-style manuscript and assume these preamble packages:

```latex
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage{array}
```

## Why this exists

Tables are one of the main claim-bearing surfaces in the paper. Keeping them as
rendered artifacts from source data helps avoid manual drift between the draft,
the evidence bundles, and later paper revisions.
