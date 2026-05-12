# REPRODUCIBILITY GUIDE — RAASA

**Project**: Risk-Aware Adaptive Sandbox Allocation (RAASA)  
**Authors**: Kunj Moradiya (23DIT035), Aryan Sangani (23DIT064)  
**Institution**: DEPSTAR-IT, CHARUSAT  

This document provides exact, step-by-step commands to reproduce all claims and figures
in the RAASA research paper.

For the consolidated record of local and AWS test resources, captured host details,
workload scales, and known documentation gaps, see
[docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md).

---

## Environment Requirements

| Component | Required Version |
|-----------|-----------------|
| Python | 3.11+ |
| Docker Engine | 24.x+ (with cgroups v2 enabled) |
| OS (local) | Linux or Windows (Docker Desktop) |
| OS (cloud) | Ubuntu 24.04 LTS on AWS EC2 |
| Python packages | See `requirements.txt` |

```powershell
# Install Python dependencies (from project root)
pip install -r requirements.txt
```

---

## Step 1 — Run the Three Baseline Modes (Local Docker)

These reproduce the core adaptive-vs-static comparison (Figures 1, 2, 3).

**Prerequisite**: Docker must be running.

```powershell
# Static L1 Baseline (no containment)
python -m raasa.experiments.run_experiment \
    --mode static_L1 \
    --scenario small_tuned \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12

# Static L3 Baseline (maximum containment)
python -m raasa.experiments.run_experiment \
    --mode static_L3 \
    --scenario small_tuned \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12

# RAASA Adaptive (linear controller, recommended)
python -m raasa.experiments.run_experiment \
    --mode raasa \
    --scenario small_tuned \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12
```

**Expected output** (RAASA run):
```
precision:             1.00
recall:                1.00
false_positive_rate:   0.00
benign_restriction_rate: 0.00
unnecessary_escalations: 0
explanation_coverage:  1.00
```

Summary JSONs are written to `raasa/logs/` automatically.

---

## Step 2 — Run the ML Ablation

Compares Isolation Forest against the tuned linear controller (Figure 6).

```powershell
# Train the Isolation Forest model first
python raasa/ml/train_iforest.py \
    --audit-log RM_practical/results/aws_v2/run_L1.jsonl \
    --output raasa/models/iforest_latest.pkl

# RAASA with ML risk model
python -m raasa.experiments.run_experiment \
    --mode raasa \
    --scenario small_tuned \
    --config raasa/configs/config_tuned_small.yaml \
    --iterations 12
```

**Key finding**: The tuned linear controller (Step 1) achieves equal or better precision/recall
than the ML model for the `small_tuned` scenario. This is discussed honestly in Section 6.

---

## Step 3 — Run Scale Tests (Medium / Large)

```powershell
# Medium scenario (10 containers)
python -m raasa.experiments.run_experiment \
    --mode raasa \
    --scenario medium \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12

# Large scenario (20 containers)
python -m raasa.experiments.run_experiment \
    --mode raasa \
    --scenario large \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12
```

---

## Step 4 — Run Agent-Like Misuse Benchmark

This benchmark adds one bounded agent-style misuse path. It uses fake token
material, repeated dependency-index/outbound transfer attempts, and bounded
process fanout; it is meant to support future-facing agent-sandbox discussion
without claiming broad exfiltration prevention.

```powershell
python -m raasa.experiments.run_experiment \
    --mode raasa \
    --scenario agent_misuse \
    --config raasa/configs/config_tuned_small_linear.yaml \
    --iterations 12
```

---

## Step 5 — Generate All Paper Figures

After running experiments, generate all 6 publication figures:

```powershell
python generate_paper_figures.py
```

Figures are written to `RM_practical/figures/`:

| File | Paper Figure | Content |
|------|-------------|---------|
| `fig1_detection_comparison.png` | Figure 1 | Precision / Recall / FPR by mode |
| `fig2_cost_comparison.png` | Figure 2 | Containment pressure / benign restriction |
| `fig3_tier_occupancy.png` | Figure 3 | L1/L2/L3 tier distribution across scenarios |
| `fig4_scalability.png` | Figure 4 | Performance vs container count |
| `fig5_tier_trajectory.png` | Figure 5 | Live tier transitions over time |
| `fig6_ablation_linear_vs_ml.png` | Figure 6 | Linear vs Isolation Forest |

---

## Step 6 — Cloud (AWS K8s + eBPF) Reproduction

The cloud validation requires AWS access. The bootstrap script provisions everything from scratch:

```bash
# On AWS EC2 Ubuntu 24.04 LTS (m7i-flex.large recommended)
chmod +x bootstrap_k8s_ebpf.sh
sudo ./bootstrap_k8s_ebpf.sh
```

This script:
1. Installs K3s (lightweight Kubernetes)
2. Deploys Tetragon (eBPF DaemonSet)
3. Deploys the RAASA DaemonSet
4. Runs the `small_tuned` scenario with `--backend k8s`

**Expected cloud result** (from `RM_practical/run_aws_k8s_ebpf_r3.summary.json`):
```
precision:               1.00
recall:                  1.00
false_positive_rate:     0.00
malicious_containment_rate: 1.00
```

Network throttling to 1 mbit/s via Linux `tc` is verified in Phase 1E/1F logs
in `AWS_Results_26_april/`.

For post-bootstrap reviewer evidence collection from a Windows workstation, keep
the SSH key outside this repository and pass it explicitly:

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-paper-key.pem"

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_repeated_adversarial_matrix_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -QuiesceBackgroundWorkloads
```

The repeated adversarial matrix now defaults to five runs and includes the
agent-style dependency/exfiltration probe alongside benign control, syscall
storm, process fanout, and network burst workloads.

---

## Step 7 — Run Hygiene Checks and the Unit Test Suite

```powershell
python -m raasa.scripts.secret_scan --root .
python -m pytest tests/ -v --tb=short
```

**Latest verified local run** (`2026-05-12`):
`123 passed, 3 skipped` with `14 warnings`.

Treat live `pytest` output as the source of truth if this changes again, and update
[docs/testing_environment_inventory.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/testing_environment_inventory.md)
alongside this file.

The secret scanner checks tracked text files for obvious private keys and cloud
API key patterns. It is a publication guardrail, not a replacement for rotating
any credential that was previously committed.

---

## Pre-computed Results Location

If Docker is not available, all pre-computed results are in:

```
RM_practical/results/aws_v2/   <- all run summary JSONs
AWS_Results_26_april/          <- live AWS audit logs and phase-by-phase evidence
```

Use these directly to regenerate figures (Step 4) without re-running experiments.

---

## Contact

For questions about reproduction, raise an issue on the project repository or
contact the authors through DEPSTAR-IT, CHARUSAT.
