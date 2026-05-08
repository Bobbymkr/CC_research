# RAASA v1 Tuning Notes

The initial live small-scenario run showed the correct qualitative behavior, but the malicious-pattern workload reached `L2` more reliably than `L3`.

To strengthen separation without changing the prototype architecture, a tuned small-scenario configuration was added:

- [config_tuned_small.yaml](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/configs/config_tuned_small.yaml)

## Tuning changes

- `l1_max`: `0.40 -> 0.35`
- `l2_max`: `0.70 -> 0.45`
- `l3_min_confidence`: `0.65 -> 0.50`

## Tuning intent

- Keep benign steady workloads in `L1`
- Preserve low benign escalation rate
- Let sustained malicious CPU abuse reach `L3` under stable evidence

This file should be used for tuning runs only, not for rewriting the original baseline configuration.
