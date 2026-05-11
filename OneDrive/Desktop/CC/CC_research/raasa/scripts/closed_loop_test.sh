#!/usr/bin/env bash
# raasa/scripts/closed_loop_test.sh
#
# Closed-loop RAASA Detection Validation Test
# ============================================
# Tests the full detection cycle (escalation → hold → de-escalation) by
# injecting load into test pods via kubectl exec and polling the RAASA
# audit JSONL log for tier decisions.
#
# Usage:
#   bash raasa/scripts/closed_loop_test.sh
#
# Requirements (on the EC2 instance):
#   - K3s running, RAASA DaemonSet deployed in raasa-system
#   - labeled phase0 test pods present in the default namespace

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
KUBECTL="sudo k3s kubectl"
NAMESPACE="default"
RAASA_NS="raasa-system"
BENIGN_SELECTOR='app=raasa-test,raasa.class=benign,raasa.expected_tier=L2'
MALICIOUS_SELECTOR='app=raasa-test,raasa.class=malicious,raasa.expected_tier=L3'
POLL_INTERVAL=5        # seconds between RAASA iterations
ESCALATION_TIMEOUT=45  # seconds max to wait for escalation (9 cycles)
DEESCALATION_TIMEOUT=120  # seconds max to wait for de-escalation (cooldown + streak)

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS="${GREEN}[PASS]${NC}"; FAIL="${RED}[FAIL]${NC}"; SKIP="${YELLOW}[SKIP]${NC}"

RESULTS=()

log() { echo -e "  $*"; }
pass() { RESULTS+=("PASS: $1"); log "${PASS} $1"; }
fail() { RESULTS+=("FAIL: $1"); log "${FAIL} $1"; }

# ── Helpers ───────────────────────────────────────────────────────────────────

# Get the latest tier for a pod from the RAASA audit log
get_tier() {
    local pod_ref="$NAMESPACE/$1"
    local agent_pod
    agent_pod=$(get_agent_pod)
    [[ -z "$agent_pod" ]] && echo "UNKNOWN" && return

    local log_file
    log_file=$($KUBECTL exec -n "$RAASA_NS" "$agent_pod" -c raasa-agent -- \
        sh -c 'ls /app/raasa/logs/*.jsonl 2>/dev/null | tail -1' 2>/dev/null)
    [[ -z "$log_file" ]] && echo "UNKNOWN" && return

    # JSONL: one JSON object per line — grep the last matching line, parse with python
    $KUBECTL exec -n "$RAASA_NS" "$agent_pod" -c raasa-agent -- \
        sh -c "grep '\"${pod_ref}\"' ${log_file} | tail -1" 2>/dev/null \
        | python3 -c "
import sys, json
line = sys.stdin.readline().strip()
if line:
    d = json.loads(line)
    print(d.get('new_tier', 'UNKNOWN'))
else:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN"
}

get_agent_pod() {
    $KUBECTL get pods -n "$RAASA_NS" -l app=raasa-agent \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

get_phase0_pod() {
    local selector="$1"
    $KUBECTL get pods -n "$NAMESPACE" -l "$selector" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null
}

install_stress() {
    local pod="$1"
    # Try to install stress-ng; skip silently if not possible (already installed or no apt)
    $KUBECTL exec -n "$NAMESPACE" "$pod" -- \
        sh -c "which stress-ng > /dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq stress-ng)" \
        >/dev/null 2>&1 || true
}

wait_for_tier() {
    local pod="$1" target_tier="$2" timeout_sec="$3"
    local elapsed=0
    while [[ $elapsed -lt $timeout_sec ]]; do
        local current
        current=$(get_tier "$pod")
        if [[ "$current" == "$target_tier" ]]; then
            echo "$current"
            return 0
        fi
        sleep 3
        elapsed=$((elapsed + 3))
    done
    local final_current
    final_current=$(get_tier "$pod")
    echo "$final_current"
    [[ "$final_current" == "$target_tier" ]]
}

# ── Pre-flight ────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  RAASA Closed-Loop Detection Validation"
echo "══════════════════════════════════════════════════════"
echo ""

AGENT_POD=$(get_agent_pod)
if [[ -z "$AGENT_POD" ]]; then
    echo -e "${FAIL} No RAASA agent pod found in ${RAASA_NS}. Aborting."
    exit 1
fi
log "Agent pod: $AGENT_POD"

BENIGN_POD=$(get_phase0_pod "$BENIGN_SELECTOR")
MALICIOUS_POD=$(get_phase0_pod "$MALICIOUS_SELECTOR")

if [[ -z "$BENIGN_POD" ]]; then
    echo -e "${FAIL} No benign L2 phase0 pod found with selector ${BENIGN_SELECTOR}."
    exit 1
fi
if [[ -z "$MALICIOUS_POD" ]]; then
    echo -e "${FAIL} No malicious L3 phase0 pod found with selector ${MALICIOUS_SELECTOR}."
    exit 1
fi

log "Benign test pod: $BENIGN_POD"
log "Malicious test pod: $MALICIOUS_POD"

# Install stress-ng in test pods (best-effort)
log "Installing stress-ng in test pods (may take 30s on first run)..."
install_stress "$BENIGN_POD"
install_stress "$MALICIOUS_POD"

# ── Test 1: Baseline — malicious pod should be at L3 ─────────────────────────
echo ""
echo "─── Test 1: Baseline — malicious pod holds L3 ───────────"
sleep $((POLL_INTERVAL * 2))
T1=$(get_tier "$MALICIOUS_POD")
log "malicious pod tier: $T1"
if [[ "$T1" == "L3" ]]; then
    pass "T1: malicious pod correctly held at L3 (risk=high, confidence=rising)"
else
    fail "T1: malicious pod at '${T1}', expected L3"
fi

# ── Test 2: Escalation — stress benign pod ───────────────────────────────────
echo ""
echo "─── Test 2: Escalation — inject stress into benign pod ──"
T2_BASELINE=$(get_tier "$BENIGN_POD")
log "Benign pod baseline tier: $T2_BASELINE"

# Launch a stronger, longer CPU burst so the heavy-stress path gets
# multiple observation windows instead of a single borderline sample.
$KUBECTL exec -n "$NAMESPACE" "$BENIGN_POD" -- \
    sh -c "nohup stress-ng --cpu 2 --cpu-load 95 --timeout 45s > /tmp/stress.log 2>&1 &" \
    2>/dev/null || {
    fail "T2: Failed to launch stress-ng in benign pod"
    RESULTS+=("SKIP: T3 (depends on T2)")
    goto_t4=true
}

if [[ -z "${goto_t4:-}" ]]; then
    log "stress-ng launched (2 workers, 95% CPU, 45s). Waiting for RAASA to detect..."
    if wait_for_tier "$BENIGN_POD" "L3" "$ESCALATION_TIMEOUT" > /dev/null 2>&1; then
        T2_RESULT=$(get_tier "$BENIGN_POD")
        pass "T2: Benign pod escalated from $T2_BASELINE → $T2_RESULT within ${ESCALATION_TIMEOUT}s"
    else
        T2_RESULT=$(get_tier "$BENIGN_POD")
        fail "T2: Benign pod at '${T2_RESULT}' after ${ESCALATION_TIMEOUT}s, expected L3"
    fi

# ── Test 3: De-escalation — wait for stress to end ───────────────────────────
    echo ""
    echo "─── Test 3: De-escalation — benign pod returns to L1 ────"
    log "Waiting for stress-ng to finish and RAASA to de-escalate (max ${DEESCALATION_TIMEOUT}s)..."
    if wait_for_tier "$BENIGN_POD" "L1" "$DEESCALATION_TIMEOUT" > /dev/null 2>&1; then
        pass "T3: Benign pod de-escalated back to L1 after stress ended"
    else
        T3_RESULT=$(get_tier "$BENIGN_POD")
        fail "T3: Benign pod at '${T3_RESULT}' after ${DEESCALATION_TIMEOUT}s, expected L1"
    fi
fi

# ── Test 4: False positive — moderate load should NOT trigger L3 ──────────────
echo ""
echo "─── Test 4: False positive — moderate load stays ≤ L2 ───"
$KUBECTL exec -n "$NAMESPACE" "$BENIGN_POD" -- \
    sh -c "nohup stress-ng --cpu 1 --cpu-load 30 --timeout 20s > /tmp/stress_fp.log 2>&1 &" \
    2>/dev/null || {
    fail "T4: Failed to launch moderate stress-ng"
}
sleep 25  # let RAASA see at least 3 cycles
T4=$(get_tier "$BENIGN_POD")
log "Benign pod tier at 30% CPU load: $T4"
if [[ "$T4" == "L1" || "$T4" == "L2" ]]; then
    pass "T4: Moderate 30% CPU load did NOT trigger L3 (tier=${T4})"
else
    fail "T4: False positive — benign pod escalated to '${T4}' on moderate load"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════"
echo "  RESULTS"
echo "══════════════════════════════════════════════════════"
PASS_COUNT=0; FAIL_COUNT=0
for r in "${RESULTS[@]}"; do
    if [[ "$r" == PASS* ]]; then
        echo -e "  ${GREEN}✓${NC} ${r#PASS: }"
        PASS_COUNT=$((PASS_COUNT + 1))
    elif [[ "$r" == SKIP* ]]; then
        echo -e "  ${YELLOW}-${NC} ${r#SKIP: }"
    else
        echo -e "  ${RED}✗${NC} ${r#FAIL: }"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
done
echo ""
echo "  ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
echo "══════════════════════════════════════════════════════"
echo ""

[[ $FAIL_COUNT -eq 0 ]] && exit 0 || exit 1
