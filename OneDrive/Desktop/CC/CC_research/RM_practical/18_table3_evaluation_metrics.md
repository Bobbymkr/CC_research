# Table 3 Draft - Evaluation Metrics and Success Criteria

This document converts the currently prose-only evaluation metrics discussion into a structured table.
It is aligned to the metrics that actually exist in the repo and can be computed from the current analysis path.

Primary code anchor:

- `raasa/analysis/metrics.py`

Primary data anchor:

- `paper/03_results_data/master_results_table.md`

## Table 3. Evaluation metrics, operational meaning, and evidence status

| Metric | What it measures | How the repo computes or reports it | Success interpretation | Current evidence status |
|---|---|---|---|---|
| Precision | Fraction of escalated workloads that are truly suspicious or malicious | `tp / (tp + fp)` | High precision means RAASA does not over-restrict benign workloads | Repeated evidence at small and medium scale |
| Recall | Fraction of suspicious or malicious workloads that are escalated | `tp / (tp + fn)` | High recall means dangerous workloads are not missed | Repeated evidence at small and medium scale |
| False Positive Rate (FPR) | Fraction of benign workloads incorrectly escalated | `fp / (fp + tn)` | Low FPR is necessary for practical deployment | Repeated evidence at small and medium scale |
| Benign Restriction Rate (BRR) | Fraction of benign rows that spend time at restrictive tiers | Derived in `metrics.py` | Low BRR means the controller preserves benign performance | Repeated evidence at small and medium scale |
| Unnecessary Escalations (UE) | Count of benign escalation events | Derived in `metrics.py` | Lower is better; complements FPR and BRR | Repeated evidence at small and medium scale |
| Switching Rate | Frequency of tier changes over time | Derived from per-container tier transitions | Lower indicates better policy stability | Repeated evidence, also useful in ablation |
| Tier Occupancy | Fraction of time spent in L1, L2, L3 | Derived from `new_tier` rows | Helps explain cost and containment behavior | Repeated evidence; also figure-backed |
| Explanation Coverage | Fraction of records with a reason string | Derived from audit records | High value supports auditability and trust | Repo-supported and structurally strong |
| Mean Time to Safe Containment | Time from first observation to expected safe tier | Derived in `metrics.py` | Lower is better, but should be discussed carefully when scenario timing differs | Computable; use when scenario setup is stable |
| Containment Pressure | Aggregate strictness / resource restriction intensity | Derived from tier-weighted CPU budget | Useful as "cost of isolation" proxy | Repo-supported summary metric |
| Average CPU Budget | Mean effective CPU allowance under active tiers | Derived from tier mapping | Lower means stronger restriction | Repo-supported |
| Overhead | Controller resource cost during benign-only operation | Separate overhead artifact | Supports practicality claims | Present, but use conservatively if not repeated broadly |

## Suggested success criteria wording

Use these as paper-safe criteria instead of over-specific universal thresholds:

- Precision should remain high enough that benign workloads are not routinely restricted.
- Recall should approach 1.0 on the curated malicious/suspicious workload set.
- FPR and BRR should stay substantially below the static L3 baseline.
- Switching rate should remain low enough to avoid oscillatory control behavior.
- Explanation coverage should remain complete or near-complete.

## Suggested manuscript paragraph

Table 3 defines the metrics used to evaluate RAASA's adaptive containment behavior. The primary security metrics are precision, recall, and false positive rate. To assess operational practicality, we also report benign restriction rate, unnecessary escalations, tier switching rate, and tier occupancy. Because RAASA is a closed-loop controller rather than a pure detector, these control-oriented metrics are necessary to characterize not only whether the system detects risky behavior, but whether it does so stably, proportionally, and with bounded cost to benign workloads.

## Caution notes for the paper

- Do not imply that every metric is equally strong across every scenario.
- Treat the small and medium repeated runs as the strongest basis for quantitative generalization.
- Treat the 20-container result and AWS result as strong supporting evidence, but still limited in repeat count.
- If you use overhead, label it clearly as benign-only controller overhead evidence, not universal system overhead across all scenarios.
