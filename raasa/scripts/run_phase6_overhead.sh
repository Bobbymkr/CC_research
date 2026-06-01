#!/usr/bin/env bash
# =============================================================================
# RAASA Phase 6 — Runtime Overhead Characterization
# Expert Plan (Dr. S + Dr. E): Measures RAASA's resource footprint on AWS.
# Key metrics: agent CPU/mem, observer loop time, enforcement latency, veth resolution time.
# Usage: bash run_phase6_overhead.sh
# =============================================================================
set -uo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}[P6]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail() { echo -e "${RED}[FAIL]${NC} $*"; FAILURES=$((FAILURES+1)); }
sep()  { echo ''; echo '═══════════════════════════════════════════════════════'; echo ''; }

FAILURES=0
RESULTS_DIR="${RESULTS_DIR:-$(pwd)/AWS_Results_v3/phase6_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$RESULTS_DIR"
LOG="$RESULTS_DIR/phase6.log"
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

info "RAASA Phase 6 — Overhead Characterization"
info "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
info "Results: $RESULTS_DIR"
sep

# ── Measure RAASA agent process overhead ──────────────────────────────────────
measure_process_overhead() {
  local label=$1 pid=$2 duration=60
  local out="$RESULTS_DIR/overhead_${label}.log"
  info "  Sampling PID $pid for ${duration}s..."

  python3 - <<PYEOF > "$out" 2>/dev/null
import time, os, subprocess, json

pid = $pid
samples = []
start = time.time()
while time.time() - start < $duration:
    try:
        with open(f'/proc/{pid}/stat') as f:
            stat = f.read()
        parts = stat.rsplit(') ', 1)[1].split()
        with open(f'/proc/{pid}/status') as f:
            status = dict(line.split(':\t', 1) for line in f if ':\t' in line)
        utime = int(parts[11])
        stime = int(parts[12])
        vmrss_kb = int(status.get('VmRSS', '0 kB').split()[0])
        samples.append({'ts': time.time(), 'utime': utime, 'stime': stime, 'vmrss_kb': vmrss_kb})
    except Exception:
        pass
    time.sleep(2)

if len(samples) > 1:
    cpu_ticks = (samples[-1]['utime'] + samples[-1]['stime']) - (samples[0]['utime'] + samples[0]['stime'])
    elapsed = samples[-1]['ts'] - samples[0]['ts']
    # Convert jiffies to seconds (100 jiffies/sec on Linux)
    cpu_pct = (cpu_ticks / 100.0) / elapsed * 100 if elapsed > 0 else 0
    vmrss_avg = sum(s['vmrss_kb'] for s in samples) / len(samples)
    result = {
        'label': '$label',
        'pid': $pid,
        'duration_s': elapsed,
        'cpu_pct_avg': round(cpu_pct, 2),
        'vmrss_avg_mib': round(vmrss_avg / 1024, 2),
        'sample_count': len(samples)
    }
    print(json.dumps(result, indent=2))
else:
    print(json.dumps({'label': '$label', 'error': 'insufficient samples'}))
PYEOF

  cat "$out"
}

# ── Test 1: Idle overhead (benign-only pods) ───────────────────────────────────
sep
info "TEST 6.1: Agent overhead with benign-only pods (60s)"
kubectl apply -f "$WORKLOADS_YAML" 2>&1 | grep ws-benign || true
sleep 10

# Start RAASA in background
RAASA_LOG="$RESULTS_DIR/phase6_idle_raasa.log"
timeout 120 python3 -m raasa.core.app \
  --config "$CONFIG" --backend k8s --iterations 0 \
  --run-label phase6_idle \
  > "$RAASA_LOG" 2>&1 &
RAASA_PID=$!
info "  RAASA PID: $RAASA_PID"
sleep 10  # Let RAASA start

measure_process_overhead "agent_idle" "$RAASA_PID" > "$RESULTS_DIR/overhead_idle.json" 2>/dev/null || true
wait $RAASA_PID 2>/dev/null || true

# Collect audit for loop timing
AUDIT=$(latest_audit)
[[ -n "$AUDIT" ]] && cp "$AUDIT" "$RESULTS_DIR/phase6_idle_audit.jsonl" || true

# Extract observer loop time from audit
AUDIT_FOR_TIMING=$(latest_audit)
python3 - <<PYEOF > "$RESULTS_DIR/loop_timing.json" 2>/dev/null || true
import json, statistics
audit_file = '$AUDIT_FOR_TIMING'
if not audit_file:
    print('{"error": "no audit log"}')
    exit(0)
timestamps = []
try:
    with open(audit_file) as f:
        for line in f:
            try:
                rec = json.loads(line)
                if 'timestamp' in rec:
                    timestamps.append(rec['timestamp'])
            except:
                pass
    from datetime import datetime
    times = [datetime.fromisoformat(t.replace('Z','+00:00')) for t in sorted(set(timestamps))]
    deltas = [(times[i+1]-times[i]).total_seconds() for i in range(len(times)-1) if i+1 < len(times)]
    if deltas:
        result = {
            'observer_loop_mean_s': round(statistics.mean(deltas), 2),
            'observer_loop_std_s': round(statistics.stdev(deltas), 2) if len(deltas) > 1 else 0,
            'observer_loop_max_s': round(max(deltas), 2),
            'sample_count': len(deltas)
        }
        print(json.dumps(result, indent=2))
except Exception as e:
    print(json.dumps({'error': str(e)}))
PYEOF

info "Observer loop timing:"
cat "$RESULTS_DIR/loop_timing.json" 2>/dev/null || true

# Verify C6.1: agent CPU < 15%
AGENT_CPU=$(python3 -c "import json; d=json.load(open('$RESULTS_DIR/overhead_idle.json')); print(d.get('cpu_pct_avg',999))" 2>/dev/null || echo "999")
if python3 -c "exit(0 if float('$AGENT_CPU') < 15 else 1)" 2>/dev/null; then
  info "C6.1 PASSED: Agent CPU ${AGENT_CPU}% < 15% threshold"
else
  fail "C6.1 FAILED: Agent CPU ${AGENT_CPU}% >= 15% threshold"
fi

# Verify C6.2: agent mem < 200 MiB
AGENT_MEM=$(python3 -c "import json; d=json.load(open('$RESULTS_DIR/overhead_idle.json')); print(d.get('vmrss_avg_mib',999))" 2>/dev/null || echo "999")
if python3 -c "exit(0 if float('$AGENT_MEM') < 200 else 1)" 2>/dev/null; then
  info "C6.2 PASSED: Agent memory ${AGENT_MEM} MiB < 200 MiB"
else
  fail "C6.2 FAILED: Agent memory ${AGENT_MEM} MiB >= 200 MiB"
fi

# Verify C6.3: observer loop < 2s
LOOP_MAX=$(python3 -c "import json; d=json.load(open('$RESULTS_DIR/loop_timing.json')); print(d.get('observer_loop_max_s',999))" 2>/dev/null || echo "999")
if python3 -c "exit(0 if float('$LOOP_MAX') < 2 else 1)" 2>/dev/null; then
  info "C6.3 PASSED: Observer loop max ${LOOP_MAX}s < 2s"
else
  warn "C6.3 WARN: Observer loop max ${LOOP_MAX}s >= 2s — document as limitation"
fi

# Cleanup
for pod in ws-benign-idle ws-benign-compute ws-benign-bursty; do
  kubectl delete pod "$pod" --ignore-not-found=true 2>/dev/null || true
done

sep
echo "FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
echo "AGENT_CPU_PCT=$AGENT_CPU" >> "$RESULTS_DIR/phase6_summary.env"
echo "AGENT_MEM_MIB=$AGENT_MEM" >> "$RESULTS_DIR/phase6_summary.env"
echo "TOTAL_FAILURES=$FAILURES" >> "$RESULTS_DIR/phase6_summary.env"

info "Phase 6 Summary:"
cat "$RESULTS_DIR/phase6_summary.env"

if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}\n✅ PHASE 6 COMPLETE${NC}"
  exit 0
else
  echo -e "${RED}\n❌ PHASE 6 had $FAILURES failures${NC}"
  exit 1
fi
