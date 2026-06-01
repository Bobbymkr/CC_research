#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 7 — Failure Injection and Safe Degradation
# Expert Plan (Dr. S): Tests system robustness when components fail.
# Critical test: F7.3 — enforcer restart during active L3 containment.
# Does the tc rule persist (pod stays contained) or clear (pod escapes)?
# Usage: bash run_phase7_failure_injection.sh
# =============================================================================
set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[P7]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
sep()  { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase7_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/phase7.log"
exec > >(tee -a "$LOG") 2>&1

RAASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RAASA_BASE}"
CONFIG="${RAASA_CONFIG:-$RAASA_BASE/raasa/configs/config_tuned_small_linear_probe.yaml}"
LOG_DIR="$RAASA_BASE/raasa/logs"
WORKLOADS_YAML="$RAASA_BASE/raasa/k8s/workloads.yaml"

latest_audit() {
  find "$LOG_DIR" -maxdepth 1 -name '*.jsonl' 2>/dev/null | sort -r | head -1 || echo ""
}

info "RAASA Phase 7 — Failure Injection Tests"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Results: $RESULTS_DIR"
sep

# ── Helper: start RAASA with malicious workload and wait for L3 ────────────────
start_raasa_with_malicious() {
  local test_id=$1
  local exp_dir="$RESULTS_DIR/$test_id"
  mkdir -p "$exp_dir"

  # Deploy malicious pod
  kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep ws-malicious-cpu || true
  local elapsed=0
  while [[ $elapsed -lt 120 ]]; do
    local phase
    phase=$(kubectl get pod ws-malicious-cpu -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    [[ "$phase" == "Running" ]] && break
    sleep 3; elapsed=$((elapsed+3))
  done
  info "  ws-malicious-cpu Running"

  # Start RAASA
  timeout 300 python3 -m raasa.core.app \
    --config "$CONFIG" --backend k8s --iterations 0 \
    --run-label "${test_id}" \
    > "$exp_dir/raasa.log" 2>&1 &
  echo $! > "$exp_dir/raasa.pid"
  info "  RAASA started (PID: $(cat $exp_dir/raasa.pid))"

  # Wait for L3 (up to 90s)
  info "  Waiting for L3 containment on ws-malicious-cpu..."
  elapsed=0
  while [[ $elapsed -lt 90 ]]; do
    LATEST=$(latest_audit)
    if [[ -n "$LATEST" ]] && grep -q '"applied_tier":"L3"' "$LATEST" 2>/dev/null; then
      info "  ✓ L3 containment active at $(date -u +%H:%M:%SZ)"
      echo "L3_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$exp_dir/l3_timing.env"
      return 0
    fi
    sleep 3; elapsed=$((elapsed+3))
  done
  warn "  L3 not reached within 90s — proceeding anyway"
  return 1
}

# ── TEST F7.1: Kill Metrics Server mid-run ─────────────────────────────────────
sep
info "=== TEST F7.1: Metrics Server Kill ==="
check_c71_dir="$RESULTS_DIR/f7.1"; mkdir -p "$check_c71_dir"

kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep ws-benign-idle || true
sleep 10

# Start RAASA
timeout 120 python3 -m raasa.core.app \
  --config "$CONFIG" --backend k8s --iterations 0 \
  --run-label f7_1_metrics_kill \
  > "$check_c71_dir/raasa.log" 2>&1 &
RAASA_F71_PID=$!

# Wait 20s then kill Metrics Server
sleep 20
METRICS_POD=$(kubectl get pod -n kube-system -l k8s-app=metrics-server --no-headers 2>/dev/null | head -1 | awk '{print $1}' || echo "")
if [[ -n "$METRICS_POD" ]]; then
  info "  Killing Metrics Server pod: $METRICS_POD"
  kubectl delete pod -n kube-system "$METRICS_POD" 2>/dev/null || true
  echo "METRICS_KILLED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$check_c71_dir/injection.env"
else
  warn "  Metrics Server pod not found"
fi

# Wait for RAASA to complete
wait $RAASA_F71_PID 2>/dev/null || true

# Check: RAASA should NOT have crashed
if kill -0 $RAASA_F71_PID 2>/dev/null; then
  info "  RAASA process still running after Metrics kill."
elif grep -q 'Traceback\|CRITICAL\|killed' "$check_c71_dir/raasa.log" 2>/dev/null; then
  fail "C7.1 FAILED: RAASA crashed after Metrics Server kill."
else
  info "C7.1 PASSED: RAASA completed gracefully after Metrics Server kill."
fi

# Check: logs should show degraded telemetry, not silence
if grep -qi 'metrics_unavailable\|degraded\|fallback\|partial_telemetry' "$check_c71_dir/raasa.log" 2>/dev/null; then
  info "C7.1 PASSED: RAASA logged degraded telemetry state."
else
  warn "C7.1 PARTIAL: No explicit degraded telemetry logging found."
fi

# Collect audit
AUDIT=$(latest_audit)
[[ -n "$AUDIT" ]] && cp "$AUDIT" "$check_c71_dir/audit.jsonl" || true

kubectl delete pod ws-benign-idle --ignore-not-found=true 2>/dev/null || true

# ── TEST F7.2: Remove syscall probe file mid-run ───────────────────────────────
sep
info "=== TEST F7.2: Syscall Probe Removal ==="
check_c72_dir="$RESULTS_DIR/f7.2"; mkdir -p "$check_c72_dir"

kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep ws-malicious-cpu || true
sleep 10

timeout 120 python3 -m raasa.core.app \
  --config "$CONFIG" --backend k8s --iterations 0 \
  --run-label f7_2_probe_remove \
  > "$check_c72_dir/raasa.log" 2>&1 &
RAASA_F72_PID=$!

# Wait 20s then remove probe files
sleep 20
PROBE_FILES=$(find /var/run/raasa -path '*/syscall_rate' -type f -print 2>/dev/null || echo "")
if [[ -n "$PROBE_FILES" ]]; then
  find /var/run/raasa -path '*/syscall_rate' -type f -delete 2>/dev/null || true
  info "  Removed probe files: $PROBE_FILES"
  echo "PROBES_REMOVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$check_c72_dir/injection.env"
  echo "PROBES_REMOVED=$PROBE_FILES" >> "$check_c72_dir/injection.env"
else
  warn "  No probe files found to remove."
  echo "PROBES_REMOVED=none" > "$check_c72_dir/injection.env"
fi

wait $RAASA_F72_PID 2>/dev/null || true

# Check: observer should report probe_missing, not crash
if grep -qi 'probe_missing\|syscall_status\|fallback' "$check_c72_dir/raasa.log" 2>/dev/null; then
  info "C7.2 PASSED: RAASA fell back gracefully after probe removal."
else
  warn "C7.2 PARTIAL: No explicit probe_missing logging found."
fi

AUDIT=$(latest_audit)
[[ -n "$AUDIT" ]] && cp "$AUDIT" "$check_c72_dir/audit.jsonl" || true

kubectl delete pod ws-malicious-cpu --ignore-not-found=true 2>/dev/null || true

# ── TEST F7.3: Enforcer restart DURING active L3 (Dr. S critical test) ────────
sep
info "=== TEST F7.3: Enforcer Restart During L3 (CRITICAL) ==="
warn "  Dr. S: This reveals whether tc rules PERSIST (safe) or CLEAR (escape) on enforcer death."
check_c73_dir="$RESULTS_DIR/f7.3"; mkdir -p "$check_c73_dir"

if ! start_raasa_with_malicious "f7_3_enforcer_restart"; then
  fail "C7.3 PRECHECK FAILED: L3 was not confirmed before enforcer restart injection."
fi

# Record tc state BEFORE killing enforcer
INTERFACES=$(ip link show | grep 'veth' | awk -F': ' '{print $2}' | awk '{print $1}' || echo "")
for iface in $INTERFACES; do
  tc -s qdisc show dev "$iface" 2>/dev/null >> "$check_c73_dir/tc_before_kill.txt" || true
done
info "  tc state before enforcer kill saved."

# Kill enforcer sidecar
ENFORCER_POD=$(kubectl get pod -n raasa-system -l app=raasa-agent --no-headers 2>/dev/null | head -1 | awk '{print $1}' || echo "")
if [[ -n "$ENFORCER_POD" ]]; then
  info "  Restarting enforcer pod: $ENFORCER_POD"
  kubectl delete pod -n raasa-system "$ENFORCER_POD" 2>/dev/null || true
  echo "ENFORCER_KILLED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$check_c73_dir/injection.env"
else
  warn "  No enforcer pod found in raasa-system."
  echo "ENFORCER_KILLED_AT=not_found" > "$check_c73_dir/injection.env"
fi

# Wait 5s then check tc state AFTER kill
sleep 5
for iface in $INTERFACES; do
  tc -s qdisc show dev "$iface" 2>/dev/null >> "$check_c73_dir/tc_after_kill.txt" || true
done

# Compare tc states
TC_BEFORE=$(grep -c 'netem\|tbf\|loss' "$check_c73_dir/tc_before_kill.txt" 2>/dev/null || true)
TC_AFTER=$(grep -c 'netem\|tbf\|loss' "$check_c73_dir/tc_after_kill.txt" 2>/dev/null || true)
TC_BEFORE=${TC_BEFORE:-0}
TC_AFTER=${TC_AFTER:-0}

info "  tc netem/tbf rules BEFORE kill: $TC_BEFORE"
info "  tc netem/tbf rules AFTER kill:  $TC_AFTER"
echo "TC_RULES_BEFORE=$TC_BEFORE" >> "$check_c73_dir/injection.env"
echo "TC_RULES_AFTER=$TC_AFTER" >> "$check_c73_dir/injection.env"

if [[ $TC_BEFORE -gt 0 && $TC_AFTER -gt 0 ]]; then
  info "C7.3 RESULT: tc rules PERSISTED after enforcer kill — pod remains contained (SAFE)."
  info "  Paper claim: containment persists through enforcer restart."
  echo "TC_OUTCOME=persisted_safe" >> "$check_c73_dir/injection.env"
elif [[ $TC_BEFORE -gt 0 && $TC_AFTER -eq 0 ]]; then
  warn "C7.3 RESULT: tc rules CLEARED after enforcer kill — pod ESCAPED containment."
  warn "  Paper claim: must note that enforcer restart causes temporary containment gap."
  echo "TC_OUTCOME=cleared_escape" >> "$check_c73_dir/injection.env"
else
  warn "C7.3 RESULT: Could not determine tc state (no L3 tc rules found before kill)."
  echo "TC_OUTCOME=unknown" >> "$check_c73_dir/injection.env"
fi

# Kill RAASA and cleanup
RAASA_PID=$(cat "$RESULTS_DIR/f7_3_enforcer_restart/raasa.pid" 2>/dev/null || echo "")
[[ -n "$RAASA_PID" ]] && kill $RAASA_PID 2>/dev/null || true
kubectl delete pod ws-malicious-cpu --ignore-not-found=true 2>/dev/null || true

# ── TEST F7.4: IPC socket removal ─────────────────────────────────────────────
sep
info "=== TEST F7.4: IPC Socket Removal ==="
check_c74_dir="$RESULTS_DIR/f7.4"; mkdir -p "$check_c74_dir"

# Check if socket can be found and removed
SOCKET_PATH="/var/run/raasa/raasa.sock"
if [[ -S "$SOCKET_PATH" ]]; then
  rm -f "$SOCKET_PATH" 2>/dev/null || true
  echo "SOCKET_REMOVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$check_c74_dir/injection.env"
  info "  IPC socket removed."
  sleep 5
  if [[ -S "$SOCKET_PATH" ]]; then
    info "C7.4 PASSED: Socket recreated by enforcer within 5s."
    echo "SOCKET_RECREATED=true" >> "$check_c74_dir/injection.env"
  else
    warn "C7.4 PARTIAL: Socket not recreated within 5s — check enforcer restart policy."
    echo "SOCKET_RECREATED=false" >> "$check_c74_dir/injection.env"
  fi
else
  warn "C7.4 SKIPPED: IPC socket not found at $SOCKET_PATH — enforcer may not be running."
  echo "SOCKET_FOUND=false" > "$check_c74_dir/injection.env"
fi

# ── Summary ────────────────────────────────────────────────────────────────────
sep
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
echo "TOTAL_FAILURES=$FAILURES" >> "$LOG"

info "Phase 7 Summary:"
echo "  F7.1: Metrics Server kill — see $RESULTS_DIR/f7.1/"
echo "  F7.2: Probe removal — see $RESULTS_DIR/f7.2/"
echo "  F7.3: Enforcer restart (CRITICAL) — see $RESULTS_DIR/f7.3/injection.env"
echo "  F7.4: IPC socket removal — see $RESULTS_DIR/f7.4/"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 7 COMPLETE${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 7 had $FAILURES failures${NC}"
  exit 1
fi
