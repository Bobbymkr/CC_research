#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 0 — K8s Foundation Validation
# Expert Plan: Validates that the K8s environment is ready for experiments.
# Must pass before running any Phase 1-7 scripts.
#
# Usage: bash raasa/scripts/run_phase0_foundation.sh
# =============================================================================
set -uo pipefail

RASA_BASE="${RAASA_BASE:-/home/ubuntu/CC_research}"
export KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"
export PYTHONPATH="${PYTHONPATH:-$RASA_BASE}"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${GREEN}[P0]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
check() { echo -e "${BLUE}[CHECK]${NC} $*"; }
sep()   { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase0_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"

LOG="$RESULTS_DIR/phase0_validation.log"
exec > >(tee -a "$LOG") 2>&1

info "RAASA Phase 0 — Foundation Validation"
info "Timestamp:    $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Results dir:  $RESULTS_DIR"
info "RAASA_BASE:   $RASA_BASE"
info "KUBECONFIG:   $KUBECONFIG"

# ── C0.1 / C0.2: Pod labels ───────────────────────────────────────────────────
sep
check "C0.1/C0.2 — Verifying all test pods have raasa.class and raasa.expected_tier labels"

MISSING_LABELS=0
while IFS= read -r pod; do
  [[ -z "$pod" ]] && continue
  NS=$(echo "$pod" | awk '{print $1}')
  NAME=$(echo "$pod" | awk '{print $2}')
  CLASS=$(kubectl get pod -n "$NS" "$NAME" -o jsonpath='{.metadata.labels.raasa\.class}' 2>/dev/null || echo "")
  TIER=$(kubectl get pod -n "$NS" "$NAME" -o jsonpath='{.metadata.labels.raasa\.expected_tier}' 2>/dev/null || echo "")
  if [[ -z "$CLASS" || -z "$TIER" ]]; then
    warn "Pod $NS/$NAME missing labels: class='$CLASS' tier='$TIER'"
    MISSING_LABELS=$((MISSING_LABELS+1))
  else
    info "  ✓ $NS/$NAME  class=$CLASS  expected_tier=$TIER"
  fi
done < <(kubectl get pods -A --no-headers --field-selector=status.phase=Running 2>/dev/null \
         | grep -v 'raasa-system\|kube-system\|kube-flannel' \
         | awk '{print $1, $2}' || true)

if [[ $MISSING_LABELS -gt 0 ]]; then
  fail "C0.1/C0.2 FAILED: $MISSING_LABELS pod(s) are missing raasa labels."
else
  info "C0.1/C0.2 PASSED: All running test pods have required RAASA labels."
fi

# ── C0.3: Metrics Server ──────────────────────────────────────────────────────
sep
check "C0.3 — Verifying Metrics Server stability (3 consecutive calls)"

METRICS_OK=0
for attempt in 1 2 3; do
  if kubectl top pods -A --no-headers 2>/dev/null | grep -qE '[0-9]+m[[:space:]]+[0-9]+Mi'; then
    info "  Attempt $attempt/3: kubectl top pods — OK"
    METRICS_OK=$((METRICS_OK+1))
  else
    warn "  Attempt $attempt/3: kubectl top pods — FAILED or empty"
  fi
  sleep 5
done

kubectl top pods -A > "$RESULTS_DIR/kubectl_top_pods.txt" 2>&1 || true
kubectl top nodes > "$RESULTS_DIR/kubectl_top_nodes.txt" 2>&1 || true

if [[ $METRICS_OK -lt 2 ]]; then
  fail "C0.3 FAILED: Metrics Server not stable ($METRICS_OK/3 calls succeeded)."
  echo "METRICS_SERVER_STABLE=false" >> "$RESULTS_DIR/phase0_flags.env"
else
  info "C0.3 PASSED: Metrics Server stable ($METRICS_OK/3)."
  echo "METRICS_SERVER_STABLE=true" >> "$RESULTS_DIR/phase0_flags.env"
fi

# ── C0.4: Network signal (pre-check, not a hard gate) ─────────────────────────
sep
check "C0.4 — Checking RAASA audit log for network telemetry (pre-check only)"

LATEST_LOG=$(find "$RASA_BASE/raasa/logs" -maxdepth 1 -name '*.jsonl' 2>/dev/null | sort -r | head -1 || echo "")

if [[ -z "$LATEST_LOG" ]]; then
  warn "C0.4 SKIPPED: No audit log yet — RAASA has not run. This is expected before Phase 2."
  echo "NETWORK_TELEMETRY_OK=unknown" >> "$RESULTS_DIR/phase0_flags.env"
else
  NET_OK=$(grep -c '"network_status":"metrics_ok"' "$LATEST_LOG" 2>/dev/null || echo 0)
  NET_FAIL=$(grep -c '"network_status":"metrics_unavailable"' "$LATEST_LOG" 2>/dev/null || echo 0)
  info "  Audit: $LATEST_LOG"
  info "  network_status=metrics_ok: $NET_OK | network_status=metrics_unavailable: $NET_FAIL"
  if [[ "$NET_OK" -gt 0 ]]; then
    info "C0.4 PASSED: At least one pod showing network_status=metrics_ok."
    echo "NETWORK_TELEMETRY_OK=true" >> "$RESULTS_DIR/phase0_flags.env"
  else
    warn "C0.4 WARN: No network_ok signal in recent audit log. Will retry in later phases."
    echo "NETWORK_TELEMETRY_OK=false" >> "$RESULTS_DIR/phase0_flags.env"
  fi
fi

# ── C0.5: Syscall probe files ─────────────────────────────────────────────────
sep
check "C0.5 — Checking for syscall probe files at /var/run/raasa/"

PROBE_COUNT=$(find /var/run/raasa -name syscall_rate 2>/dev/null | wc -l || echo 0)
ls -la /var/run/raasa/ > "$RESULTS_DIR/probe_volume_listing.txt" 2>&1 || echo "(probe dir not found)" > "$RESULTS_DIR/probe_volume_listing.txt"

if [[ "$PROBE_COUNT" -gt 0 ]]; then
  info "C0.5 PASSED: Found $PROBE_COUNT syscall_rate probe file(s)."
  find /var/run/raasa -name syscall_rate 2>/dev/null | head -5 | while read -r f; do
    info "  → $f ($(cat "$f" 2>/dev/null || echo empty))"
  done
  echo "SYSCALL_PROBE_OK=true" >> "$RESULTS_DIR/phase0_flags.env"
else
  fail "C0.5 FAILED: No syscall probe files found at /var/run/raasa/*/syscall_rate"
  warn "  → Verify ebpf_probe.sh is running and the DaemonSet probe volume is mounted."
  echo "SYSCALL_PROBE_OK=false" >> "$RESULTS_DIR/phase0_flags.env"
fi

# ── C0.6: Enforcer IPC readiness ──────────────────────────────────────────────
sep
check "C0.6 — Sending test IPC command to enforcer sidecar"

ENFORCER_POD=$(kubectl get pod -n raasa-system -l app=raasa-agent --no-headers 2>/dev/null | head -1 | awk '{print $1}' || echo "")
if [[ -n "$ENFORCER_POD" ]]; then
  IPC_RESULT=$(kubectl exec -n raasa-system "$ENFORCER_POD" -c enforcer -- sh -c \
    "python3 -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(\"/var/run/raasa/raasa.sock\"); s.sendall(b\"{\\\"container_id\\\": \\\"default/raasa-test\\\", \\\"tier\\\": \\\"L1\\\"}\"); s.settimeout(3); print(s.recv(1024).decode())' 2>&1" \
    2>/dev/null || echo "IPC_FAILED")
  if echo "$IPC_RESULT" | grep -qi 'ok\|accept\|applied'; then
    info "C0.6 PASSED: Enforcer responded to IPC test command."
    echo "ENFORCER_IPC_OK=true" >> "$RESULTS_DIR/phase0_flags.env"
  else
    warn "C0.6 PARTIAL: Enforcer pod found but IPC response ambiguous: $IPC_RESULT"
    echo "ENFORCER_IPC_OK=partial" >> "$RESULTS_DIR/phase0_flags.env"
  fi
else
  fail "C0.6 FAILED: No RAASA agent pod found in raasa-system namespace."
  warn "  → Deploy with: kubectl apply -f raasa/k8s/daemonset.yaml"
  echo "ENFORCER_IPC_OK=false" >> "$RESULTS_DIR/phase0_flags.env"
fi

# ── C0.7: Config hash ─────────────────────────────────────────────────────────
sep
check "C0.7 — Computing and recording active config SHA256 hash"

ACTIVE_CONFIG=$(kubectl get configmap raasa-config -n raasa-system -o jsonpath='{.data.config\.yaml}' 2>/dev/null || echo "")
if [[ -n "$ACTIVE_CONFIG" ]]; then
  CONFIG_HASH=$(echo "$ACTIVE_CONFIG" | sha256sum | awk '{print $1}')
  info "C0.7: Active K8s ConfigMap config hash: $CONFIG_HASH"
  echo "CONFIG_HASH=$CONFIG_HASH" >> "$RESULTS_DIR/phase0_flags.env"
  echo "$ACTIVE_CONFIG" > "$RESULTS_DIR/active_config_snapshot.yaml"
else
  LOCAL_CONFIG="$RASA_BASE/raasa/configs/config_tuned_small_linear_probe.yaml"
  if [[ -f "$LOCAL_CONFIG" ]]; then
    CONFIG_HASH=$(sha256sum "$LOCAL_CONFIG" | awk '{print $1}')
    info "C0.7: Local config hash (no K8s ConfigMap): $CONFIG_HASH"
    echo "CONFIG_HASH=$CONFIG_HASH" >> "$RESULTS_DIR/phase0_flags.env"
    cp "$LOCAL_CONFIG" "$RESULTS_DIR/active_config_snapshot.yaml"
  else
    fail "C0.7 FAILED: Cannot find active config — K8s ConfigMap missing and local file not found."
    echo "CONFIG_HASH=unknown" >> "$RESULTS_DIR/phase0_flags.env"
  fi
fi

# ── Summary ────────────────────────────────────────────────────────────────────
sep
info "Phase 0 Summary"
info "Results dir: $RESULTS_DIR"
cat "$RESULTS_DIR/phase0_flags.env" 2>/dev/null || true

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 0 PASSED — Environment is ready for Phases 1-7.${NC}"
  echo "PHASE0_RESULT=PASS" >> "$RESULTS_DIR/phase0_flags.env"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 0 FAILED — $FAILURES check(s) failed. Fix before proceeding.${NC}"
  echo "PHASE0_RESULT=FAIL" >> "$RESULTS_DIR/phase0_flags.env"
  exit 1
fi
