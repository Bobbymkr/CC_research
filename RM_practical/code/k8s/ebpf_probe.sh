#!/bin/bash
# RAASA eBPF Syscall Rate Probe (Sidecar)
#
# Uses bpftrace to count syscalls per cgroup-inode, maps to pod UID,
# writes per-second rate to /var/run/raasa/<pod-uid>/syscall_rate.
#
# Requirements: bpftrace >= 0.20, bc, SYS_ADMIN capability, host /sys mount

POLL_INTERVAL=${POLL_INTERVAL:-5}
PROBE_DIR="/var/run/raasa"
mkdir -p "$PROBE_DIR"

echo "Starting RAASA eBPF syscall probe (interval: ${POLL_INTERVAL}s)..."

declare -gA CGROUP_MAP

build_cgroup_map() {
    CGROUP_MAP=()
    # K3s creates cgroup v2 slices in three QoS class formats:
    #   Guaranteed:  kubepods-pod<uid>.slice
    #   Burstable:   kubepods-burstable-pod<uid>.slice
    #   BestEffort:  kubepods-besteffort-pod<uid>.slice
    # The inode number of this directory IS the cgroup ID reported by bpftrace.
    local cg inode uid base
    while IFS= read -r cg; do
        inode=$(stat -c %i "$cg" 2>/dev/null) || continue
        [[ -z "$inode" ]] && continue

        base=$(basename "$cg")
        # Strip any of the three prefixes and the trailing .slice
        uid=$(echo "$base" | sed -E 's/^kubepods(-burstable|-besteffort)?-pod([0-9a-f_-]+)\.slice$/\2/')
        # K3s uses underscores in slice names for dashes in UIDs — normalise them
        uid="${uid//_/-}"

        # Validate: must be a 36-char UUID (8-4-4-4-12)
        if [[ "$uid" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
            CGROUP_MAP[$inode]=$uid
        fi
    done < <(find /sys/fs/cgroup/kubepods.slice/ -maxdepth 3 -type d -name "*.slice" 2>/dev/null)

    echo "[probe] cgroup map: ${#CGROUP_MAP[@]} pod(s) discovered"
}

# Write bpftrace program to a temp file to avoid shell quoting issues
BPFTRACE_PROG=$(mktemp /tmp/raasa_probe_XXXXXX.bt)
cat > "$BPFTRACE_PROG" <<'BTEOF'
tracepoint:raw_syscalls:sys_enter {
    @counts[cgroup] = count();
}
interval:s:INTERVAL_PLACEHOLDER {
    print(@counts);
    clear(@counts);
}
BTEOF

# Substitute the interval
sed -i "s/INTERVAL_PLACEHOLDER/${POLL_INTERVAL}/" "$BPFTRACE_PROG"

# Start bpftrace in background
bpftrace "$BPFTRACE_PROG" > /tmp/bpftrace_output 2>&1 &
BPF_PID=$!
echo "bpftrace started (PID=$BPF_PID)"

cleanup() {
    echo "Stopping eBPF probe..."
    kill $BPF_PID 2>/dev/null
    rm -f "$BPFTRACE_PROG"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Give bpftrace time to attach
sleep 3

while kill -0 $BPF_PID 2>/dev/null; do
    sleep "$POLL_INTERVAL"
    build_cgroup_map

    # Snapshot current output
    cp /tmp/bpftrace_output /tmp/bpftrace_current 2>/dev/null
    # Clear bpftrace output file (bpftrace keeps appending)
    truncate -s 0 /tmp/bpftrace_output

    # Parse: @counts[<cgroup_id>]: <count>
    while IFS= read -r line; do
        if [[ "$line" =~ @counts\[([0-9]+)\]:\ +([0-9]+) ]]; then
            cg_id="${BASH_REMATCH[1]}"
            count="${BASH_REMATCH[2]}"
            uid="${CGROUP_MAP[$cg_id]:-}"
            if [[ -n "$uid" ]]; then
                rate=$(awk "BEGIN{printf \"%.2f\", $count / $POLL_INTERVAL}")
                mkdir -p "${PROBE_DIR}/${uid}"
                echo "$rate" > "${PROBE_DIR}/${uid}/syscall_rate"
                echo "[probe] pod=$uid cgroup=$cg_id syscall_rate=$rate/s"
            fi
        fi
    done < /tmp/bpftrace_current
done

echo "bpftrace exited unexpectedly. Last output:"
cat /tmp/bpftrace_output
exit 1
