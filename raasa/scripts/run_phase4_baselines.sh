#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 4 — K8s Baseline vs Adaptive Evaluation
# Expert Plan (Dr. R): Repeatable comparison of static_L1, static_L3, and
# adaptive RAASA on K8s-small and K8s-medium scenarios.
# Produces summary JSONs with mean ± std across 3 repeats.
#
# Usage: bash raasa/scripts/run_phase4_baselines.sh [small|medium|both]
# =============================================================================
set -uo pipefail

RAASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RAASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[P4]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
sep()   { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
SCENARIO="${1:-both}"
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase4_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"

LOG="$RESULTS_DIR/phase4.log"
exec > >(tee -a "$LOG") 2>&1

CONFIG_BASE="$RAASA_BASE/raasa/configs"
LOG_DIR="$RAASA_BASE/raasa/logs"
mkdir -p "$LOG_DIR"
WORKLOADS_YAML="$RAASA_BASE/raasa/k8s/workloads.yaml"

trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

info "RAASA Phase 4 — K8s Baseline vs Adaptive Evaluation"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Scenario:  $SCENARIO"
info "Results:   $RESULTS_DIR"
sep

# Pod sets per scenario
K8S_SMALL_PODS="ws-benign-idle ws-benign-compute ws-malicious-cpu ws-malicious-net"
K8S_MEDIUM_PODS="ws-benign-idle ws-benign-compute ws-benign-bursty ws-suspicious-proc ws-malicious-cpu ws-malicious-net"

# Helper: find latest audit log
latest_audit() {
  find "$LOG_DIR" -maxdepth 1 -name '*.jsonl' 2>/dev/null | sort -r | head -1 || echo ""
}

# ── Check if ConfigMap exists for mode switching ───────────────────────────────
CONFIGMAP_EXISTS=false
if kubectl get configmap raasa-config -n raasa-system 2>/dev/null | grep -q raasa-config; then
  CONFIGMAP_EXISTS=true
  info "ConfigMap raasa-config found — mode switching via patch enabled."
else
  warn "ConfigMap raasa-config NOT found in raasa-system — mode will be passed via --mode flag only."
fi

# ── Helper: set static mode ────────────────────────────────────────────────────
set_mode() {
  local mode=$1
  if [[ "$CONFIGMAP_EXISTS" == "true" ]]; then
    case "$mode" in
      static_L1)
        kubectl patch configmap raasa-config -n raasa-system \
          --type merge -p '{"data":{"mode":"static","static_tier":"L1"}}' 2>/dev/null || true ;;
      static_L3)
        kubectl patch configmap raasa-config -n raasa-system \
          --type merge -p '{"data":{"mode":"static","static_tier":"L3"}}' 2>/dev/null || true ;;
      adaptive)
        kubectl patch configmap raasa-config -n raasa-system \
          --type merge -p '{"data":{"mode":"adaptive"}}' 2>/dev/null || true ;;
    esac
  fi
  info "  Mode set to: $mode"
  sleep 3
}

# ── Helper: deploy scenario pods ──────────────────────────────────────────────
deploy_scenario() {
  local pods=$1
  kubectl apply -f "$WORKLOADS_YAML" 2>&1 || true
  sleep 10
  for pod in $pods; do
    local elapsed=0
    while [[ $elapsed -lt 120 ]]; do
      local phase
      phase=$(kubectl get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
      [[ "$phase" == "Running" ]] && break
      sleep 3; elapsed=$((elapsed+3))
    done
    info "  Pod $pod: $(kubectl get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo unknown)"
  done
}

# ── Helper: tear down scenario pods ───────────────────────────────────────────
teardown_scenario() {
  local pods=$1
  for pod in $pods; do
    kubectl delete pod "$pod" --ignore-not-found=true 2>/dev/null || true
  done
  sleep 5
}

# ── Helper: run one experiment ─────────────────────────────────────────────────
run_exp() {
  local mode=$1 scenario=$2 repeat=$3 duration=${4:-300}
  local exp_id="aws_k8s_${scenario}_${mode}_r${repeat}"
  local exp_dir="$RESULTS_DIR/$exp_id"
  mkdir -p "$exp_dir"

  sep
  info "RUN: $exp_id | duration=${duration}s"

  # Independent observer
  while true; do
    kubectl top pods -A --no-headers 2>/dev/null >> "$exp_dir/kubectl_top.log" || true
    echo "---$(date -u +%Y-%m-%dT%H:%M:%SZ)---" >> "$exp_dir/kubectl_top.log"
    sleep 5
  done &
  OBS_PID=$!

  CONFIG_FILE="$CONFIG_BASE/config_tuned_small_linear_probe.yaml"
  local rc=0
  timeout "$duration" python3 -m raasa.core.app \
    --config "$CONFIG_FILE" \
    --backend k8s \
    --mode "$mode" \
    --iterations 0 \
    --run-label "$exp_id" \
    > "$exp_dir/raasa.log" 2>&1 || rc=$?

  [[ $rc -ne 0 && $rc -ne 124 ]] && warn "  RAASA exited with code $rc for $exp_id — check $exp_dir/raasa.log"

  kill $OBS_PID 2>/dev/null || true

  # Collect artifacts
  AUDIT=$(latest_audit)
  [[ -n "$AUDIT" ]] && cp "$AUDIT" "$exp_dir/${exp_id}.jsonl" || true
  SUMMARY=$(find "$LOG_DIR" -maxdepth 1 -name '*.summary.json' 2>/dev/null | sort -r | head -1 || echo "")
  [[ -n "$SUMMARY" ]] && cp "$SUMMARY" "$exp_dir/${exp_id}.summary.json" || true

  CONFIG_HASH=$(sha256sum "$CONFIG_FILE" | awk '{print $1}')
  kubectl get configmap raasa-config -n raasa-system -o yaml > "$exp_dir/configmap_snapshot.yaml" 2>/dev/null || true
  printf '{"run_id":"%s","mode":"%s","scenario":"%s","repeat":%s,"config_hash":"%s","timestamp":"%s"}\n' \
    "$exp_id" "$mode" "$scenario" "$repeat" "$CONFIG_HASH" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$exp_dir/run_metadata.json"

  info "  Artifacts saved to: $exp_dir"
}

# ── Run K8s-small ─────────────────────────────────────────────────────────────
if [[ "$SCENARIO" == "small" || "$SCENARIO" == "both" ]]; then
  sep
  info "=== K8s-SMALL SCENARIO ==="
  info "Pods: $K8S_SMALL_PODS"

  for mode in static_L1 static_L3 adaptive; do
    for repeat in 1 2 3; do
      sep
      info "Deploying K8s-small pods for $mode repeat $repeat..."
      deploy_scenario "$K8S_SMALL_PODS"
      set_mode "$mode"
      run_exp "$mode" "small" "$repeat" 300
      teardown_scenario "$K8S_SMALL_PODS"
      sleep 10
    done
  done
fi

# ── Run K8s-medium ────────────────────────────────────────────────────────────
if [[ "$SCENARIO" == "medium" || "$SCENARIO" == "both" ]]; then
  sep
  info "=== K8s-MEDIUM SCENARIO ==="
  info "Pods: $K8S_MEDIUM_PODS"

  for mode in static_L1 static_L3 adaptive; do
    for repeat in 1 2 3; do
      sep
      info "Deploying K8s-medium pods for $mode repeat $repeat..."
      deploy_scenario "$K8S_MEDIUM_PODS"
      set_mode "$mode"
      run_exp "$mode" "medium" "$repeat" 360
      teardown_scenario "$K8S_MEDIUM_PODS"
      sleep 15
    done
  done
fi

sep
# ── Aggregate results ─────────────────────────────────────────────────────────
info "Aggregating results across all runs..."
RD="$RESULTS_DIR"
python3 - <<PYEOF 2>/dev/null || warn "Aggregation script error — check results manually"
import json, os, glob, statistics

results_dir = os.environ.get('RESULTS_DIR', '$RD')
runs = []
for summary_file in glob.glob(f'{results_dir}/**/*.summary.json', recursive=True):
    try:
        with open(summary_file) as f:
            data = json.load(f)
        meta_path = os.path.join(os.path.dirname(summary_file), 'run_metadata.json')
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        runs.append({**meta, **data})
    except Exception as e:
        print(f'  Skip {summary_file}: {e}')

grouped = {}
for r in runs:
    key = f"{r.get('scenario','?')}_{r.get('mode','?')}"
    grouped.setdefault(key, []).append(r)

print('\n=== Phase 4 Aggregated Results ===')
print(f"{'Scenario':<12} {'Mode':<12} {'N':<4} {'Recall':<12} {'Precision':<12} {'FPR':<10}")
print('-' * 62)
for key in sorted(grouped):
    group = grouped[key]
    scenario = group[0].get('scenario', '?')
    mode = group[0].get('mode', '?')
    n = len(group)
    for rkey in ['recall', 'malicious_recall', 'detection_recall']:
        vals = [g.get(rkey) for g in group if g.get(rkey) is not None]
        if vals:
            recall_mean = statistics.mean(vals)
            recall_std = statistics.stdev(vals) if len(vals) > 1 else 0
            break
    else:
        recall_mean, recall_std = 0, 0
    for pkey in ['precision', 'detection_precision']:
        vals = [g.get(pkey) for g in group if g.get(pkey) is not None]
        if vals:
            prec_mean = statistics.mean(vals)
            break
    else:
        prec_mean = 0
    for fkey in ['fpr', 'false_positive_rate']:
        vals = [g.get(fkey) for g in group if g.get(fkey) is not None]
        if vals:
            fpr_mean = statistics.mean(vals)
            break
    else:
        fpr_mean = 0
    print(f'{scenario:<12} {mode:<12} {n:<4} {recall_mean:.3f}+/-{recall_std:.3f}  {prec_mean:.3f}       {fpr_mean:.3f}')

with open(os.path.join(results_dir, 'phase4_aggregated.json'), 'w') as f:
    json.dump({'groups': {k: v for k,v in grouped.items()}, 'run_count': len(runs)}, f, indent=2, default=str)
print(f'\nAggregated JSON saved to {results_dir}/phase4_aggregated.json')
PYEOF

echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RESULTS_DIR/phase4.log"
echo "TOTAL_FAILURES=$FAILURES" >> "$RESULTS_DIR/phase4.log"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 4 COMPLETE — Results in $RESULTS_DIR${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 4 had $FAILURES failures. Check logs.${NC}"
  exit 1
fi
