#!/bin/bash
# =============================================================================
# RAASA AWS K8s Experiment Runner — Full Homogeneous Cloud Validation
# Runs: L1 baseline, L3 baseline, small_tuned x3, medium x3, large x1
# Backend: k8s (Tetragon eBPF + cadvisor) — NO simulated signals
# Config: config_tuned_small_linear.yaml (use_ml_model: false, linear controller)
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[RAASA-EXP]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
sep()   { echo ''; echo '===================================================='; echo ''; }

# ── Environment ───────────────────────────────────────────────────────────────
cd ~/CC_research
source venv/bin/activate
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export PYTHONPATH=.

CONFIG=raasa/configs/config_tuned_small_linear.yaml
LOG_DIR=raasa/logs
RESULTS=/tmp/aws_new_results
mkdir -p "$RESULTS"

# ── Pre-flight ────────────────────────────────────────────────────────────────
sep
info "PRE-FLIGHT CHECKS"
info "Kernel:  $(uname -r)"
info "Config:  $(grep use_ml_model $CONFIG)"
info "Backend: k8s (Tetragon eBPF + cadvisor)"
info "Disk free: $(df -h / | tail -1 | awk '{print $4}')"
info "Memory free: $(free -h | grep Mem | awk '{print $4}')"
info "Pods:"
kubectl get pods -A --no-headers | grep Running
sep

# Confirm linear controller — hard fail if ML is on
ML_ON=$(grep use_ml_model "$CONFIG" | grep -c "true" || true)
if [ "$ML_ON" -gt 0 ]; then
    fail "use_ml_model is TRUE in config. Switch to false before running."
fi
info "use_ml_model: false CONFIRMED"

# ── Experiment function ───────────────────────────────────────────────────────
run_exp() {
    local MODE=$1
    local SCENARIO=$2
    local RUN_ID=$3
    local DURATION=${4:-120}

    sep
    info "START: mode=$MODE | scenario=$SCENARIO | run_id=$RUN_ID | duration=${DURATION}s"
    info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

    NODE_NAME=$(kubectl get nodes --no-headers -o custom-columns='NAME:.metadata.name' | head -1)
    sudo -E env PYTHONPATH=. \
        KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
        NODE_NAME="$NODE_NAME" \
        ~/CC_research/venv/bin/python -m raasa.experiments.run_experiment \
        --mode "$MODE" \
        --scenario "$SCENARIO" \
        --backend k8s \
        --run-id "$RUN_ID" \
        --config "$CONFIG" \
        --duration "$DURATION" \
        2>&1

    # Copy outputs to staging
    for f in "$LOG_DIR"/${RUN_ID}*.jsonl "$LOG_DIR"/${RUN_ID}*.summary.json; do
        [ -f "$f" ] && cp "$f" "$RESULTS/" && info "Saved: $(basename $f)"
    done

    info "DONE: $RUN_ID at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    info "Cooldown 25s..."
    sleep 25
}

# =============================================================================
# PHASE 1 — Baselines (L1 and L3 — on K8s/eBPF, same env as all other runs)
# =============================================================================
sep
info "PHASE 1 — BASELINES: static_L1 and static_L3 on K8s eBPF"
sep

run_exp static_L1 small_tuned aws_k8s_baseline_L1_r1 90
run_exp static_L3 small_tuned aws_k8s_baseline_L3_r1 90

# =============================================================================
# PHASE 2 — small_tuned: 3 containers, 3 independent runs
# =============================================================================
sep
info "PHASE 2 — small_tuned: 3 containers, 3 runs"
sep

run_exp raasa small_tuned aws_k8s_small_linear_r1 120
run_exp raasa small_tuned aws_k8s_small_linear_r2 120
run_exp raasa small_tuned aws_k8s_small_linear_r3 120

# =============================================================================
# PHASE 3 — medium: 10 containers, 3 independent runs
# =============================================================================
sep
info "PHASE 3 — medium: 10 containers, 3 runs"
sep

run_exp raasa medium aws_k8s_medium_linear_r1 150
run_exp raasa medium aws_k8s_medium_linear_r2 150
run_exp raasa medium aws_k8s_medium_linear_r3 150

# =============================================================================
# PHASE 4 — large: 20 containers, 1 run
# =============================================================================
sep
info "PHASE 4 — large: 20 containers, 1 run"
sep

run_exp raasa large aws_k8s_large_linear_r1 180

# =============================================================================
# SUMMARY
# =============================================================================
sep
info "ALL EXPERIMENTS COMPLETE"
info "Results staged in: $RESULTS"
echo ''
ls -lh "$RESULTS/"
echo ''
info "To pull results to Windows:"
info "  scp -i /path/to/untracked/raasa-paper-key.pem ubuntu@<AWS_IPV4>:/tmp/aws_new_results/* RM_practical/results/aws_v2/"
sep
