#!/usr/bin/env bash
# =============================================================================
# RAASA AWS Testing Campaign — Master Orchestrator
# Expert Plan: One-button reproducible execution of all phases.
#
# Usage: bash raasa/scripts/run_all_phases_aws.sh
#   (must be run from CC_research/ directory, OR script will self-relocate)
# =============================================================================
set -uo pipefail

# Self-relocate: ensure we always run from CC_research/ regardless of caller CWD
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC_RESEARCH_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$CC_RESEARCH_DIR"

# ── Environment ───────────────────────────────────────────────────────────────
export RAASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RAASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[ORCHESTRATOR]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
sep()   { echo ''; echo '======================================================='; echo ''; }

export RESULTS_BASE="$(pwd)/AWS_Results_v3_Campaign_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RESULTS_BASE"
LOG="$RESULTS_BASE/orchestrator.log"
exec > >(tee -a "$LOG") 2>&1

info "RAASA AWS Testing Campaign Started"
info "Working dir:  $(pwd)"
info "RAASA_BASE:   $RAASA_BASE"
info "KUBECONFIG:   $KUBECONFIG"
info "PYTHONPATH:   $PYTHONPATH"
info "Results Base: $RESULTS_BASE"
sep

run_phase() {
  local phase_script=$1
  local phase_name=$2

  if [[ ! -f "$phase_script" ]]; then
    error "Script $phase_script not found!"
    exit 1
  fi

  export RESULTS_DIR="$RESULTS_BASE/$phase_name"
  mkdir -p "$RESULTS_DIR"
  info "Starting $phase_name..."
  if bash "$phase_script"; then
    info "✅ $phase_name completed successfully."
  else
    error "❌ $phase_name failed. Campaign aborted."
    exit 1
  fi
  sep
}

# Run phases sequentially
run_phase "raasa/scripts/run_phase0_foundation.sh"        "phase0_foundation"
run_phase "raasa/scripts/run_phase1_workload_validation.sh" "phase1_workload_validation"
run_phase "raasa/scripts/run_phase2_correctness.sh"       "phase2_correctness"
run_phase "raasa/scripts/run_phase3_blast_radius.sh"      "phase3_blast_radius"
run_phase "raasa/scripts/run_phase4_baselines.sh"         "phase4_baselines"
run_phase "raasa/scripts/run_phase5_ablation.sh"          "phase5_ablation"
run_phase "raasa/scripts/run_phase6_overhead.sh"          "phase6_overhead"
run_phase "raasa/scripts/run_phase7_failure_injection.sh" "phase7_failure_injection"

info "🎉 All Phases Completed Successfully!"
info "Results collected in: $RESULTS_BASE"
