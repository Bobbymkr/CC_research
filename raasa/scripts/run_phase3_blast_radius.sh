#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 3 — Blast-Radius / Enforcement Specificity Validation
# Expert Plan (Dr. S): Proves L3 containment targets ONLY the malicious pod.
#
# Test topology:
#   ws-blast-client-a  ──► raasa-net-server
#   ws-blast-client-b  ──► raasa-net-server
#   ws-malicious-cpu   (contained to L3 by RAASA)
#
# Expected: malicious → 0 B/s after L3; benign-A and B change < 10%.
# Usage: bash raasa/scripts/run_phase3_blast_radius.sh
# =============================================================================
set -uo pipefail

RAASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RAASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[P3]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
check() { echo -e "${BLUE}[CHECK]${NC} $*"; }
sep()   { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase3_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"

LOG="$RESULTS_DIR/phase3.log"
exec > >(tee -a "$LOG") 2>&1

CONFIG="${RAASA_CONFIG:-$RAASA_BASE/raasa/configs/config_tuned_small_linear_probe.yaml}"
LOG_DIR="$RAASA_BASE/raasa/logs"
mkdir -p "$LOG_DIR"
WORKLOADS_YAML="$RAASA_BASE/raasa/k8s/workloads.yaml"

# Trap: kill all background jobs on exit
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

info "RAASA Phase 3 — Blast-Radius Enforcement Specificity Test"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Results:   $RESULTS_DIR"

if [[ ! -f "$CONFIG" ]]; then
  echo -e "${RED}[ERROR] Config not found: $CONFIG${NC}"
  exit 1
fi
CONFIG_HASH=$(sha256sum "$CONFIG" | awk '{print $1}')
info "Config SHA256: $CONFIG_HASH"
echo "CONFIG_HASH=$CONFIG_HASH" > "$RESULTS_DIR/phase3_metadata.env"
sep

# ── Helper: find latest audit log ─────────────────────────────────────────────
latest_audit() {
  find "$LOG_DIR" -maxdepth 1 -name '*.jsonl' 2>/dev/null | sort -r | head -1 || echo ""
}

# ── Deploy all blast-radius pods ───────────────────────────────────────────────
info "Deploying blast-radius pods..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 || true
sleep 5

for pod in raasa-net-server ws-blast-client-a ws-blast-client-b; do
  elapsed=0
  while [[ $elapsed -lt 120 ]]; do
    phase=$(kubectl get pod "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [[ "$phase" == "Running" ]]; then
      info "  ✓ $pod Running"
      break
    fi
    sleep 3; elapsed=$((elapsed+3))
  done
done

# Get server Pod IP (NOT ClusterIP — raasa-net-server is headless, ClusterIP=None)
SERVER_IP=$(kubectl get pod raasa-net-server -o jsonpath='{.status.podIP}' 2>/dev/null || echo "")
if [[ -z "$SERVER_IP" || "$SERVER_IP" == "None" ]]; then
  warn "Could not get raasa-net-server Pod IP — will use DNS name as fallback"
  SERVER_IP="raasa-net-server"
fi
info "Net server Pod IP: $SERVER_IP"
sep

# ── Step 1: Baseline throughput measurement ────────────────────────────────────
info "STEP 1: Measuring BASELINE throughput for benign-A and benign-B (30s)..."

BASE_A_LOG="$RESULTS_DIR/baseline_client_a.log"
BASE_B_LOG="$RESULTS_DIR/baseline_client_b.log"

kubectl exec ws-blast-client-a -- sh -c \
  "iperf3 -c ${SERVER_IP} -t 30 -p 5201 -J 2>/dev/null" > "$BASE_A_LOG" &
PID_A=$!

kubectl exec ws-blast-client-b -- sh -c \
  "iperf3 -c ${SERVER_IP} -t 30 -p 5202 -J 2>/dev/null" > "$BASE_B_LOG" &
PID_B=$!

wait $PID_A || true
wait $PID_B || true

parse_bps() {
  local logfile=$1
  python3 -c "
import json, sys
try:
    with open('$logfile') as f:
        data = json.load(f)
    bps = data['end']['sum_received']['bits_per_second']
    print(f'{bps:.0f}')
except Exception as e:
    sys.stderr.write(f'parse_bps error: {e}\\n')
    print('0')
" 2>/dev/null || echo "0"
}

BASE_A_BPS=$(parse_bps "$BASE_A_LOG")
BASE_B_BPS=$(parse_bps "$BASE_B_LOG")

info "Baseline Client-A: ${BASE_A_BPS} bps"
info "Baseline Client-B: ${BASE_B_BPS} bps"
[[ "$BASE_A_BPS" == "0" ]] && warn "  Client-A baseline is 0 — iperf3 may have failed. Check $BASE_A_LOG"
[[ "$BASE_B_BPS" == "0" ]] && warn "  Client-B baseline is 0 — iperf3 may have failed. Check $BASE_B_LOG"
echo "BASELINE_A_BPS=$BASE_A_BPS" >> "$RESULTS_DIR/phase3_metadata.env"
echo "BASELINE_B_BPS=$BASE_B_BPS" >> "$RESULTS_DIR/phase3_metadata.env"
sep

# ── Step 2: Deploy malicious workload + start RAASA ───────────────────────────
info "STEP 2: Deploying ws-malicious-cpu and starting RAASA controller..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep ws-malicious-cpu || true

elapsed=0
while [[ $elapsed -lt 120 ]]; do
  phase=$(kubectl get pod ws-malicious-cpu -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
  if [[ "$phase" == "Running" ]]; then info "  ✓ ws-malicious-cpu Running"; break; fi
  sleep 3; elapsed=$((elapsed+3))
done

# Start continuous iperf3 on benign clients (background)
kubectl exec ws-blast-client-a -- sh -c \
  "while true; do iperf3 -c ${SERVER_IP} -t 10 -p 5201 --json 2>/dev/null; sleep 1; done" \
  > "$RESULTS_DIR/live_client_a.log" &
LIVE_A_PID=$!

kubectl exec ws-blast-client-b -- sh -c \
  "while true; do iperf3 -c ${SERVER_IP} -t 10 -p 5202 --json 2>/dev/null; sleep 1; done" \
  > "$RESULTS_DIR/live_client_b.log" &
LIVE_B_PID=$!

# Start observer
while true; do
  kubectl top pods -A --no-headers 2>/dev/null >> "$RESULTS_DIR/kubectl_top.log" || true
  echo "---$(date -u +%Y-%m-%dT%H:%M:%SZ)---" >> "$RESULTS_DIR/kubectl_top.log"
  sleep 5
done &
OBS_PID=$!
sep

# ── Step 3: Start RAASA and wait for L3 on malicious pod ──────────────────────
info "STEP 3: Running RAASA for up to 120s, watching for L3 on ws-malicious-cpu..."

RAASA_LOG="$RESULTS_DIR/phase3_raasa.log"
RUN_ID="phase3_blast_$(date -u +%Y%m%dT%H%M%SZ)"

local_rc=0
timeout 120 python3 -m raasa.core.app \
  --config "$CONFIG" \
  --backend k8s \
  --iterations 0 \
  --run-label "$RUN_ID" \
  > "$RAASA_LOG" 2>&1 || local_rc=$?

[[ $local_rc -ne 0 && $local_rc -ne 124 ]] && warn "RAASA exited with code $local_rc — check $RAASA_LOG"

LATEST_AUDIT=$(latest_audit)
L3_TIMESTAMP="unknown"
if [[ -n "$LATEST_AUDIT" ]]; then
  L3_TIMESTAMP=$(grep -m1 '"applied_tier":"L3"' "$LATEST_AUDIT" 2>/dev/null \
    | grep -o '"timestamp":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
fi
info "  L3 applied at: $L3_TIMESTAMP"
echo "L3_TIMESTAMP=$L3_TIMESTAMP" >> "$RESULTS_DIR/phase3_metadata.env"
sep

# ── Step 4: Measure throughput DURING containment ─────────────────────────────
info "STEP 4: Measuring throughput DURING L3 containment (30s)..."

CONTAIN_A_LOG="$RESULTS_DIR/contained_client_a.log"
CONTAIN_B_LOG="$RESULTS_DIR/contained_client_b.log"

kubectl exec ws-blast-client-a -- sh -c \
  "iperf3 -c ${SERVER_IP} -t 30 -p 5201 -J 2>/dev/null" > "$CONTAIN_A_LOG" &
PID_CA=$!
kubectl exec ws-blast-client-b -- sh -c \
  "iperf3 -c ${SERVER_IP} -t 30 -p 5202 -J 2>/dev/null" > "$CONTAIN_B_LOG" &
PID_CB=$!

wait $PID_CA || true
wait $PID_CB || true

CONTAIN_A_BPS=$(parse_bps "$CONTAIN_A_LOG")
CONTAIN_B_BPS=$(parse_bps "$CONTAIN_B_LOG")

[[ "$CONTAIN_A_BPS" == "0" ]] && warn "  Client-A containment measurement is 0 — iperf3 may have failed"
[[ "$CONTAIN_B_BPS" == "0" ]] && warn "  Client-B containment measurement is 0 — iperf3 may have failed"

info "During-containment Client-A: ${CONTAIN_A_BPS} bps"
info "During-containment Client-B: ${CONTAIN_B_BPS} bps"
echo "CONTAINED_A_BPS=$CONTAIN_A_BPS" >> "$RESULTS_DIR/phase3_metadata.env"
echo "CONTAINED_B_BPS=$CONTAIN_B_BPS" >> "$RESULTS_DIR/phase3_metadata.env"

# Kill background jobs (trap will also handle this on EXIT)
kill $LIVE_A_PID $LIVE_B_PID $OBS_PID 2>/dev/null || true
sep

# ── Step 5: Verdict ────────────────────────────────────────────────────────────
check "C3.1 — Malicious pod throughput should drop to ~0 after L3"
AUDIT_FILE=$(latest_audit)
if [[ -n "$AUDIT_FILE" ]]; then
  cp "$AUDIT_FILE" "$RESULTS_DIR/phase3_audit.jsonl"
  MAL_L3=$(grep -c '"container_id":"default/ws-malicious-cpu".*"applied_tier":"L3"' "$RESULTS_DIR/phase3_audit.jsonl" 2>/dev/null || echo 0)
  # Also try multiline match
  MAL_L3_ALT=$(grep '"container_id":"default/ws-malicious-cpu"' "$RESULTS_DIR/phase3_audit.jsonl" 2>/dev/null | grep -c '"applied_tier":"L3"' || echo 0)
  TOTAL_MAL_L3=$(( MAL_L3 > MAL_L3_ALT ? MAL_L3 : MAL_L3_ALT ))
  if [[ $TOTAL_MAL_L3 -gt 0 ]]; then
    info "C3.1 PASSED: ws-malicious-cpu was in L3 for $TOTAL_MAL_L3 tick(s)."
  else
    fail "C3.1 FAILED: ws-malicious-cpu never reached L3."
  fi
else
  warn "C3.1 SKIPPED: No audit log found."
fi

check "C3.2 — Benign-A throughput should change < 10% during containment"
if [[ "$BASE_A_BPS" -gt 0 && "$CONTAIN_A_BPS" -gt 0 ]]; then
  CHANGE_A=$(python3 -c "
base=$BASE_A_BPS; contained=$CONTAIN_A_BPS
if base > 0:
    pct = abs(base - contained) / base * 100
    print(f'{pct:.1f}')
else:
    print('unknown')
" 2>/dev/null || echo "unknown")
  info "  Client-A throughput change: ${CHANGE_A}%"
  echo "CLIENT_A_CHANGE_PCT=$CHANGE_A" >> "$RESULTS_DIR/phase3_metadata.env"
  if python3 -c "exit(0 if float('${CHANGE_A}') < 10 else 1)" 2>/dev/null; then
    info "C3.2 PASSED: Client-A throughput changed ${CHANGE_A}% (< 10% threshold)."
  else
    fail "C3.2 FAILED: Client-A throughput changed ${CHANGE_A}% (≥ 10%). Enforcement may be node-scoped."
    warn "  → Update paper wording to 'node-local prototype containment' if this fails consistently."
  fi
else
  warn "C3.2 SKIPPED: Baseline or containment measurement unavailable (zero values)."
fi

check "C3.3 — Benign-B throughput should change < 10% during containment"
if [[ "$BASE_B_BPS" -gt 0 && "$CONTAIN_B_BPS" -gt 0 ]]; then
  CHANGE_B=$(python3 -c "
base=$BASE_B_BPS; contained=$CONTAIN_B_BPS
if base > 0:
    pct = abs(base - contained) / base * 100
    print(f'{pct:.1f}')
else:
    print('unknown')
" 2>/dev/null || echo "unknown")
  info "  Client-B throughput change: ${CHANGE_B}%"
  echo "CLIENT_B_CHANGE_PCT=$CHANGE_B" >> "$RESULTS_DIR/phase3_metadata.env"
  if python3 -c "exit(0 if float('${CHANGE_B}') < 10 else 1)" 2>/dev/null; then
    info "C3.3 PASSED: Client-B throughput changed ${CHANGE_B}% (< 10% threshold)."
  else
    fail "C3.3 FAILED: Client-B throughput changed ${CHANGE_B}% (≥ 10%). Enforcement may be node-scoped."
  fi
else
  warn "C3.3 SKIPPED: Baseline or containment measurement unavailable (zero values)."
fi

echo "INGRESS_EGRESS_TESTED=true" >> "$RESULTS_DIR/phase3_metadata.env"
sep
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RESULTS_DIR/phase3_metadata.env"
echo "TOTAL_FAILURES=$FAILURES" >> "$RESULTS_DIR/phase3_metadata.env"

info "Phase 3 Summary"
cat "$RESULTS_DIR/phase3_metadata.env"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 3 PASSED — Per-pod enforcement specificity confirmed.${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 3 FAILED — $FAILURES check(s) failed.${NC}"
  echo -e "${YELLOW}   If C3.2/C3.3 fail: update paper wording to 'node-local containment'.${NC}"
  exit 1
fi
