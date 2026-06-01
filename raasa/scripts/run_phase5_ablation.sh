#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 5 — Telemetry Ablation Study
# Expert Plan (Dr. R): Shows marginal contribution of each signal.
# Condition A: CPU+mem+process only
# Condition B: +network
# Condition C: +syscall
# Condition D: Full (all signals)
# Usage: bash raasa/scripts/run_phase5_ablation.sh
# =============================================================================
set -uo pipefail

RAASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RAASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[P5]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
sep()  { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase5_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/phase5.log"
exec > >(tee -a "$LOG") 2>&1

CONFIG="$RAASA_BASE/raasa/configs/config_tuned_small_linear_probe.yaml"
LOG_DIR="$RAASA_BASE/raasa/logs"
mkdir -p "$LOG_DIR"
WORKLOADS_YAML="$RAASA_BASE/raasa/k8s/workloads.yaml"

trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

info "RAASA Phase 5 — Telemetry Ablation Study"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Results:   $RESULTS_DIR"
sep

if [[ ! -f "$CONFIG" ]]; then
  echo -e "${RED}[ERROR] Config not found: $CONFIG${NC}"
  exit 1
fi

# Generate ablation config by patching weights
generate_ablation_config() {
  local condition=$1
  local out_config="$RESULTS_DIR/config_ablation_${condition}.yaml"
  cp "$CONFIG" "$out_config"

  # Verify keys exist before patching (flexible indent regex)
  case "$condition" in
    A)  # CPU + memory + process only (zero network + syscall)
      sed -i '/^[[:space:]]*network:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*syscall:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*syscall_jsd:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*network_entropy:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*dns_entropy:/s/:.*$/: 0.0/' "$out_config" || true
      ;;
    B)  # + network (zero syscall only)
      sed -i '/^[[:space:]]*syscall:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*syscall_jsd:/s/:.*$/: 0.0/' "$out_config" || true
      ;;
    C)  # + syscall (zero network only)
      sed -i '/^[[:space:]]*network:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*network_entropy:/s/:.*$/: 0.0/' "$out_config" || true
      sed -i '/^[[:space:]]*dns_entropy:/s/:.*$/: 0.0/' "$out_config" || true
      ;;
    D)  # Full — no changes
      ;;
  esac

  # Verify at least one patch happened for non-D conditions
  if [[ "$condition" != "D" ]]; then
    local zero_count
    zero_count=$(grep -c ': 0.0' "$out_config" 2>/dev/null || echo 0)
    [[ $zero_count -eq 0 ]] && warn "  Condition $condition: no weights were zeroed — config may not have expected keys!"
  fi

  echo "$out_config"
}

# Deploy ablation workloads
info "Deploying ablation workloads..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep -E 'ws-benign-compute|ws-malicious|raasa-net-server' || true
sleep 10

for pod in ws-benign-compute ws-malicious-cpu ws-malicious-net raasa-net-server; do
  elapsed=0
  while [[ $elapsed -lt 120 ]]; do
    phase=$(kubectl get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    [[ "$phase" == "Running" ]] && { info "  ✓ $pod Running"; break; }
    sleep 3; elapsed=$((elapsed+3))
  done
done

# Run each ablation condition
for condition in A B C D; do
  sep
  info "=== ABLATION CONDITION $condition ==="
  case "$condition" in
    A) info "Signals: CPU + Memory + Process (network=0, syscall=0)" ;;
    B) info "Signals: CPU + Memory + Process + Network (syscall=0)" ;;
    C) info "Signals: CPU + Memory + Process + Syscall (network=0)" ;;
    D) info "Signals: FULL (all signals active)" ;;
  esac

  ablation_config=$(generate_ablation_config "$condition")
  config_hash=$(sha256sum "$ablation_config" | awk '{print $1}')
  info "Ablation config: $ablation_config"
  info "Config hash:     $config_hash"

  exp_id="phase5_ablation${condition}_$(date -u +%Y%m%dT%H%M%SZ)"
  exp_dir="$RESULTS_DIR/ablation_${condition}"
  mkdir -p "$exp_dir"

  # Independent observer
  while true; do
    kubectl top pods -A --no-headers 2>/dev/null >> "$exp_dir/kubectl_top.log" || true
    sleep 5
  done &
  OBS_PID=$!

  local_rc=0
  timeout 240 python3 -m raasa.core.app \
    --config "$ablation_config" \
    --backend k8s \
    --iterations 0 \
    --run-label "$exp_id" \
    > "$exp_dir/raasa.log" 2>&1 || local_rc=$?

  [[ $local_rc -ne 0 && $local_rc -ne 124 ]] && warn "  RAASA exited $local_rc for condition $condition"

  kill $OBS_PID 2>/dev/null || true

  # Collect audit — pre-compute path before heredoc
  LATEST_AUDIT=$(find "$LOG_DIR" -maxdepth 1 -name '*.jsonl' 2>/dev/null | sort -r | head -1 || echo "")
  [[ -n "$LATEST_AUDIT" ]] && cp "$LATEST_AUDIT" "$exp_dir/${exp_id}.jsonl" || true

  # Compute per-workload tier distribution
  AUDIT_FOR_PYTHON="${LATEST_AUDIT:-}"
  python3 - >> "$exp_dir/tier_distribution.txt" 2>/dev/null <<PYEOF || true
import json, collections, sys
audit_file = '$AUDIT_FOR_PYTHON'
if not audit_file:
    print(f'No audit log found for condition $condition')
    sys.exit(0)
try:
    tiers_by_pod = collections.defaultdict(lambda: collections.Counter())
    with open(audit_file) as f:
        for line in f:
            try:
                rec = json.loads(line.strip())
                pod = rec.get('container_id', '?')
                tier = rec.get('applied_tier', '?')
                tiers_by_pod[pod][tier] += 1
            except:
                pass
    print(f'Ablation Condition $condition:')
    for pod, counts in sorted(tiers_by_pod.items()):
        total = sum(counts.values())
        for tier, count in sorted(counts.items()):
            pct = count / total * 100 if total > 0 else 0
            print(f'  {pod} {tier}: {count}/{total} ({pct:.0f}%)')
except Exception as e:
    print(f'Error: {e}')
PYEOF

  printf '{"condition":"%s","config_hash":"%s","exp_id":"%s"}\n' \
    "$condition" "$config_hash" "$exp_id" > "$exp_dir/metadata.json"
  info "Condition $condition complete. Results: $exp_dir"
done

# Cleanup
for pod in ws-benign-compute ws-malicious-cpu ws-malicious-net raasa-net-server; do
  kubectl delete pod "$pod" --ignore-not-found=true 2>/dev/null || true
done

sep
info "Phase 5 Ablation Summary"
echo "See $RESULTS_DIR/ablation_*/tier_distribution.txt for per-condition results"
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 5 COMPLETE${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 5 had $FAILURES failures${NC}"
  exit 1
fi
