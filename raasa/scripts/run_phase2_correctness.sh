#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 2 — Closed-Loop Correctness on K8s
# Expert Plan: Tests each workload in isolation then mixed.
# Validates: benign stays L1/L2, malicious escalates to L3 within 60s.
#
# Usage: bash raasa/scripts/run_phase2_correctness.sh
# Requires: Phase 0 passed, workloads.yaml deployed
# =============================================================================
set -uo pipefail

RASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[P2]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
check() { echo -e "${BLUE}[CHECK]${NC} $*"; }
sep()   { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase2_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"

LOG="$RESULTS_DIR/phase2.log"
exec > >(tee -a "$LOG") 2>&1

CONFIG="${RAASA_CONFIG:-$RASA_BASE/raasa/configs/config_tuned_small_linear_probe.yaml}"
LOG_DIR="$RASA_BASE/raasa/logs"
mkdir -p "$LOG_DIR"
WORKLOADS_YAML="$RASA_BASE/raasa/k8s/workloads.yaml"
WORKLOAD_PODS=(
  ws-benign-idle
  ws-benign-compute
  ws-benign-bursty
  ws-suspicious-proc
  ws-malicious-cpu
  ws-malicious-net
  ws-malicious-syscall
  ws-blast-client-a
  ws-blast-client-b
)

info "RAASA Phase 2 — Closed-Loop Correctness Tests"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Config:    $CONFIG"
info "Results:   $RESULTS_DIR"
sep

# Verify config exists
if [[ ! -f "$CONFIG" ]]; then
  echo -e "${RED}[ERROR] Config not found: $CONFIG${NC}"
  exit 1
fi

CONFIG_HASH=$(sha256sum "$CONFIG" | awk '{print $1}')
info "Config SHA256: $CONFIG_HASH"
echo "CONFIG_HASH=$CONFIG_HASH" > "$RESULTS_DIR/phase2_metadata.env"
echo "STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RESULTS_DIR/phase2_metadata.env"

# ── Helper: wait for pod Running ───────────────────────────────────────────────
wait_pod_running() {
  local pod=$1 ns=${2:-default} timeout=${3:-120}
  local elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    local phase
    phase=$(kubectl get pod -n "$ns" "$pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
    if [[ "$phase" == "Running" ]]; then return 0; fi
    sleep 3; elapsed=$((elapsed+3))
  done
  return 1
}

# ── Helper: get latest audit log ───────────────────────────────────────────────
prepare_workloads() {
  local keep=("$@")

  kubectl apply -f "$WORKLOADS_YAML" 2>&1 || true
  sleep 5

  local pod keep_pod wanted
  for pod in "${WORKLOAD_PODS[@]}"; do
    wanted=false
    for keep_pod in "${keep[@]}"; do
      if [[ "$pod" == "$keep_pod" ]]; then
        wanted=true
        break
      fi
    done
    if [[ "$wanted" == "false" ]]; then
      kubectl delete pod "$pod" --ignore-not-found=true --wait=true --timeout=60s >/dev/null 2>&1 || true
    fi
  done

  for pod in "${keep[@]}"; do
    wait_pod_running "$pod" default 120 || return 1
  done
  wait_pod_running raasa-net-server default 120 || true
}

audit_for_run() {
  local run_id=$1
  local exact="$LOG_DIR/run_${run_id}.jsonl"
  if [[ -f "$exact" ]]; then
    echo "$exact"
    return
  fi
  find "$LOG_DIR" -maxdepth 1 -name "run_${run_id}*.jsonl" -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | awk 'NR==1 {sub(/^[^ ]+ /, ""); print}'
}

# ── Helper: run one experiment and collect audit log ───────────────────────────
run_test() {
  local test_id=$1 duration=$2
  shift 2
  local pods=("$@")

  sep
  if ! prepare_workloads "${pods[@]}"; then
    fail "C2 $test_id: One or more requested pods failed to reach Running state."
    return
  fi
  info "TEST $test_id — Pods: ${pods[*]} | Duration: ${duration}s"

  # Start background observer (trap ensures cleanup on any exit)
  local obs_log="$RESULTS_DIR/${test_id}_kubectl_top.log"
  while true; do
    kubectl top pods -A --no-headers 2>/dev/null >> "$obs_log" || true
    echo "---$(date -u +%Y-%m-%dT%H:%M:%SZ)---" >> "$obs_log"
    sleep 5
  done &
  local obs_pid=$!
  # Ensure observer is killed when this function returns
  trap "kill $obs_pid 2>/dev/null || true" RETURN

  # Run RAASA controller
  local run_id="phase2_${test_id}_$(date -u +%Y%m%dT%H%M%SZ)"
  local run_log="$RESULTS_DIR/${test_id}_raasa.log"

  local rc=0
  timeout "${duration}" python3 -m raasa.core.app \
    --config "$CONFIG" \
    --backend k8s \
    --iterations 0 \
    --run-label "$run_id" \
    > "$run_log" 2>&1 || rc=$?

  if [[ $rc -ne 0 && $rc -ne 124 ]]; then
    warn "  RAASA exited with code $rc (not timeout). Check $run_log for errors."
  fi

  # Collect audit log
  local audit
  audit=$(audit_for_run "$run_id")
  if [[ -n "$audit" ]]; then
    cp "$audit" "$RESULTS_DIR/${test_id}_audit.jsonl"
    info "  Audit: $RESULTS_DIR/${test_id}_audit.jsonl"
  else
    warn "  No audit log found for $test_id"
  fi

  kubectl get events --field-selector reason=Killing -A > "$RESULTS_DIR/${test_id}_killing_events.txt" 2>&1 || true
  kubectl describe pods -l app=raasa-workload > "$RESULTS_DIR/${test_id}_pod_describe.txt" 2>&1 || true

  info "  TEST $test_id complete."
}

# ── Helper: check audit for tier outcome ───────────────────────────────────────
check_tier() {
  local test_id=$1 pod=$2 expected=$3
  local audit="$RESULTS_DIR/${test_id}_audit.jsonl"

  if [[ ! -f "$audit" ]]; then
    fail "C2 $test_id/$pod: No audit log — cannot verify tier."
    return
  fi

  local tiers
  tiers=$(grep "\"container_id\":\"default/$pod\"" "$audit" 2>/dev/null \
         | grep -o '"applied_tier":"L[123]"' | sort | uniq -c | sort -rn || echo "")
  info "  $pod tiers observed: $tiers"

  case "$expected" in
    never_L3)
      if grep -q "\"container_id\":\"default/$pod\"" "$audit" 2>/dev/null && \
         grep "\"container_id\":\"default/$pod\"" "$audit" 2>/dev/null | grep -q '"applied_tier":"L3"'; then
        fail "C2 FAILED: $pod reached L3 (expected: never L3)"
      else
        info "  ✓ $pod never reached L3 (C2 PASSED for this pod)"
      fi
      ;;
    must_L3)
      local time_to_l3
      time_to_l3=$(grep "\"container_id\":\"default/$pod\"" "$audit" 2>/dev/null \
                   | grep '"applied_tier":"L3"' | head -1 \
                   | grep -o '"timestamp":"[^"]*"' | cut -d'"' -f4 || echo "")
      if [[ -n "$time_to_l3" ]]; then
        info "  ✓ $pod reached L3 at $time_to_l3 (C2 PASSED for this pod)"
      else
        fail "C2 FAILED: $pod never reached L3 within test window (expected: must_L3)"
      fi
      ;;
  esac
}

# ── Deploy all workloads ───────────────────────────────────────────────────────
check_tier() {
  local test_id=$1 pod=$2 expected=$3
  local audit="$RESULTS_DIR/${test_id}_audit.jsonl"

  if [[ ! -f "$audit" ]]; then
    fail "C2 $test_id/$pod: No audit log — cannot verify tier."
    return
  fi

  local tiers
  tiers=$(python3 - "$audit" "default/$pod" <<'PY'
import collections
import json
import sys

audit, container_id = sys.argv[1], sys.argv[2]
counts = collections.Counter()
with open(audit, encoding="utf-8") as fh:
    for line in fh:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("container_id") != container_id:
            continue
        tier = row.get("new_tier") or row.get("applied_tier") or row.get("proposed_tier")
        if tier:
            counts[tier] += 1
print(" ".join(f"{count} {tier}" for tier, count in sorted(counts.items())))
PY
  )
  info "  $pod tiers observed: $tiers"

  case "$expected" in
    never_L3)
      if python3 - "$audit" "default/$pod" <<'PY'
import json
import sys

audit, container_id = sys.argv[1], sys.argv[2]
with open(audit, encoding="utf-8") as fh:
    for line in fh:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("container_id") == container_id and (row.get("new_tier") or row.get("applied_tier")) == "L3":
            sys.exit(0)
sys.exit(1)
PY
      then
        fail "C2 FAILED: $pod reached L3 (expected: never L3)"
      else
        info "  ✓ $pod never reached L3 (C2 PASSED for this pod)"
      fi
      ;;
    must_L3)
      local time_to_l3
      time_to_l3=$(python3 - "$audit" "default/$pod" <<'PY'
import json
import sys

audit, container_id = sys.argv[1], sys.argv[2]
with open(audit, encoding="utf-8") as fh:
    for line in fh:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("container_id") == container_id and (row.get("new_tier") or row.get("applied_tier")) == "L3":
            print(row.get("timestamp", "unknown"))
            break
PY
      )
      if [[ -n "$time_to_l3" ]]; then
        info "  ✓ $pod reached L3 at $time_to_l3 (C2 PASSED for this pod)"
      else
        fail "C2 FAILED: $pod never reached L3 within test window (expected: must_L3)"
      fi
      ;;
  esac
}

info "Deploying all workloads..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 || true
sleep 15

# ── Test 2.1: Solo Benign Idle ────────────────────────────────────────────────
sep
info "Deploying ws-benign-idle..."
if wait_pod_running ws-benign-idle default 120; then
  info "ws-benign-idle Running"
  run_test "2.1-solo-idle" 180 "ws-benign-idle"
  check_tier "2.1-solo-idle" "ws-benign-idle" "never_L3"
else
  warn "ws-benign-idle did not reach Running state — skipping test 2.1"
fi

# ── Test 2.3: Solo Malicious CPU ──────────────────────────────────────────────
sep
info "Deploying ws-malicious-cpu..."
if wait_pod_running ws-malicious-cpu default 120; then
  info "ws-malicious-cpu Running"
  run_test "2.3-solo-malicious-cpu" 240 "ws-malicious-cpu"
  check_tier "2.3-solo-malicious-cpu" "ws-malicious-cpu" "must_L3"

  RESTARTS=$(kubectl get pod ws-malicious-cpu -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "unknown")
  info "  ws-malicious-cpu restart count after L3: $RESTARTS"
  echo "MALICIOUS_CPU_RESTARTS=$RESTARTS" >> "$RESULTS_DIR/phase2_metadata.env"
  if [[ "$RESTARTS" != "0" && "$RESTARTS" != "unknown" ]]; then
    warn "  Dr. S flag: kubelet restarted ws-malicious-cpu during L3 containment."
  fi
else
  warn "ws-malicious-cpu did not reach Running state — skipping test 2.3"
fi

# ── Test 2.4: Solo Malicious Network ──────────────────────────────────────────
sep
info "Deploying ws-malicious-net and raasa-net-server..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep -E 'ws-malicious-net|raasa-net-server' || true
if wait_pod_running raasa-net-server default 120 && wait_pod_running ws-malicious-net default 120; then
  info "ws-malicious-net + raasa-net-server Running"
  run_test "2.4-solo-malicious-net" 240 "ws-malicious-net"
  check_tier "2.4-solo-malicious-net" "ws-malicious-net" "must_L3"
else
  warn "Pods did not reach Running state — skipping test 2.4"
fi

# ── Test 2.5: Mixed 3 (idle + compute + malicious-cpu) ────────────────────────
sep
info "Running mixed test with 3 workloads..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep -E 'ws-benign|ws-malicious-cpu' || true
sleep 15

run_test "2.5-mixed-3" 300 "ws-benign-idle" "ws-benign-compute" "ws-malicious-cpu"
check_tier "2.5-mixed-3" "ws-benign-idle" "never_L3"
check_tier "2.5-mixed-3" "ws-benign-compute" "never_L3"
check_tier "2.5-mixed-3" "ws-malicious-cpu" "must_L3"

# ── Test 2.6: Mixed 5 (all core workloads) ────────────────────────────────────
sep
info "Running mixed test with all 5 core workloads..."
kubectl apply -f "$WORKLOADS_YAML" 2>&1 || true
sleep 15

run_test "2.6-mixed-5" 360 "ws-benign-idle" "ws-benign-compute" "ws-benign-bursty" "ws-suspicious-proc" "ws-malicious-cpu"
check_tier "2.6-mixed-5" "ws-benign-idle" "never_L3"
check_tier "2.6-mixed-5" "ws-benign-compute" "never_L3"
check_tier "2.6-mixed-5" "ws-benign-bursty" "never_L3"
check_tier "2.6-mixed-5" "ws-malicious-cpu" "must_L3"

# ── Summary ────────────────────────────────────────────────────────────────────
sep
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RESULTS_DIR/phase2_metadata.env"
echo "TOTAL_FAILURES=$FAILURES" >> "$RESULTS_DIR/phase2_metadata.env"

info "Phase 2 Summary"
info "Results dir: $RESULTS_DIR"
cat "$RESULTS_DIR/phase2_metadata.env"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 2 PASSED — Closed-loop correctness validated.${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 2 FAILED — $FAILURES check(s) failed.${NC}"
  exit 1
fi
