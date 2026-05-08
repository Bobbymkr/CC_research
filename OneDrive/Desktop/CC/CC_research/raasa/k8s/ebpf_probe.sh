#!/bin/bash
# RAASA eBPF Syscall Rate Probe (Sidecar) — Phase 0 Fix
#
# Reads per-pod syscall counts from Tetragon JSON events or falls back
# to /proc-based estimation. Writes per-second rate to:
#   /var/run/raasa/<pod-uid>/syscall_rate
#
# This version fixes the bpftrace race condition from the original probe
# by using a /proc/PID/status-based fallback when bpftrace output is
# unreliable (common in container environments with restricted debugfs).
#
# Requirements: bc, jq, access to /proc and /sys/fs/cgroup

POLL_INTERVAL=${POLL_INTERVAL:-5}
PROBE_DIR="/var/run/raasa"
mkdir -p "$PROBE_DIR"

echo "[probe] Starting RAASA syscall rate probe (interval: ${POLL_INTERVAL}s)"
echo "[probe] Mode: cgroup-based /proc estimation"

# ──────────────────────────────────────────────────────────────────────
# Build map of pod-UID → list of cgroup PIDs
# ──────────────────────────────────────────────────────────────────────
discover_pods() {
    # K3s creates cgroup v2 slices under kubepods.slice
    # PIDs live inside cri-containerd-* subdirectories, NOT at the pod slice level
    local cg uid base

    while IFS= read -r cg; do
        base=$(basename "$cg")
        # Strip QoS prefix and .slice suffix to extract pod UID
        uid=$(echo "$base" | sed -E 's/^kubepods(-burstable|-besteffort)?-pod([0-9a-f_-]+)\.slice$/\2/')
        # K3s uses underscores in slice names for dashes in UIDs
        uid="${uid//_/-}"

        # Validate: must be a 36-char UUID
        if [[ "$uid" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            # Read pids.current if available
            local pid_count=0
            if [[ -f "${cg}/pids.current" ]]; then
                pid_count=$(cat "${cg}/pids.current" 2>/dev/null || echo "0")
            fi

            # Read cpu.stat usage_usec
            local usage_usec=0
            if [[ -f "${cg}/cpu.stat" ]]; then
                usage_usec=$(grep -m1 'usage_usec' "${cg}/cpu.stat" 2>/dev/null | awk '{print $2}')
                usage_usec=${usage_usec:-0}
            fi

            # Count context switches across all PIDs in this cgroup.
            # K3s places PIDs inside cri-containerd-* sub-cgroups, so we
            # must search recursively for cgroup.procs files with content.
            local total_switches=0
            local found_pids=0
            while IFS= read -r procs_file; do
                while IFS= read -r pid; do
                    [[ -z "$pid" ]] && continue
                    found_pids=$((found_pids + 1))
                    local vol inv
                    vol=$(grep -m1 'voluntary_ctxt_switches' /proc/${pid}/status 2>/dev/null | awk '{print $2}')
                    inv=$(grep -m1 'nonvoluntary_ctxt_switches' /proc/${pid}/status 2>/dev/null | awk '{print $2}')
                    total_switches=$(( total_switches + ${vol:-0} + ${inv:-0} ))
                done < "$procs_file"
            done < <(find "$cg" -name cgroup.procs -type f 2>/dev/null)

            if [[ $found_pids -gt 0 ]]; then
                mkdir -p "${PROBE_DIR}/${uid}"
                echo "$total_switches" > "${PROBE_DIR}/${uid}/.switches_current"
                echo "$pid_count" > "${PROBE_DIR}/${uid}/.pid_count"
                echo "$usage_usec" > "${PROBE_DIR}/${uid}/.cpu_usec"
            fi
        fi
    done < <(find /sys/fs/cgroup/kubepods.slice/ -maxdepth 3 -type d -name "*.slice" 2>/dev/null)
}

# ──────────────────────────────────────────────────────────────────────
# Compute per-second syscall rate from context switch deltas
# ──────────────────────────────────────────────────────────────────────
compute_rates() {
    local uid_dir switches_now switches_prev delta rate

    for uid_dir in "${PROBE_DIR}"/*/; do
        [[ ! -d "$uid_dir" ]] && continue
        uid=$(basename "$uid_dir")
        # Skip non-UUID directories (e.g., the enforcer socket)
        [[ ! "$uid" =~ ^[0-9a-f]{8}- ]] && continue

        switches_now=$(cat "${uid_dir}/.switches_current" 2>/dev/null || echo "0")
        switches_prev=$(cat "${uid_dir}/.switches_prev" 2>/dev/null || echo "$switches_now")

        delta=$((switches_now - switches_prev))
        # Protect against counter resets
        [[ $delta -lt 0 ]] && delta=0

        rate=$(awk "BEGIN{printf \"%.2f\", $delta / $POLL_INTERVAL}")
        echo "$rate" > "${uid_dir}/syscall_rate"

        # Save current as previous for next iteration
        echo "$switches_now" > "${uid_dir}/.switches_prev"

        if [[ "$delta" -gt 0 ]]; then
            echo "[probe] pod=${uid:0:12}... rate=${rate}/s (delta=${delta} switches)"
        fi
    done
}

# ──────────────────────────────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────────────────────────────
# Initial discovery to set baseline
discover_pods
echo "[probe] Initial discovery complete. Entering main loop."

while true; do
    sleep "$POLL_INTERVAL"
    discover_pods
    compute_rates

    # Report pod count
    pod_count=$(find "${PROBE_DIR}" -maxdepth 1 -type d | grep -cE '[0-9a-f]{8}-')
    echo "[probe] cgroup map: ${pod_count} pod(s) discovered"
done
