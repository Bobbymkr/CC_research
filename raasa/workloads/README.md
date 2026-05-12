# Workload Profiles

RAASA v1 uses four controlled workload classes:

- `benign_steady`: low-variance web workload, expected to remain mostly `L1`
- `benign_bursty`: transient CPU spikes, should avoid repeated overreaction
- `suspicious`: sustained moderate abnormal behavior, expected around `L2`
- `malicious_pattern`: strong sustained abuse pattern, expected to reach `L3`

The definitions live in [catalog.py](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/raasa/workloads/catalog.py).
