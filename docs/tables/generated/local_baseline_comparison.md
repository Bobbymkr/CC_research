# Table A. Local Baseline Comparison

| Mode | Environment | Scenario | Precision | Recall | FPR | BRR | UE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| static_L1 | Local Docker | small baseline | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| static_L3 | Local Docker | small baseline | 0.33 | 1.00 | 1.00 | 1.00 | 24 |
| raasa linear | Local Docker | small_tuned best run | 1.00 | 1.00 | 0.00 | 0.00 | 0 |
| raasa linear | Local Docker | small_tuned 3-run mean | 0.87 | 1.00 | 0.11 | 0.11 | 1.3 |

## Notes

- Values are taken from the current paper draft and local evaluation materials.
- FPR = false positive rate, BRR = benign restriction rate, UE = unnecessary escalations.
