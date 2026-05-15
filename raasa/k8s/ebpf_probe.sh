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
BPF_SOURCE=${BPF_SOURCE:-/app/raasa/k8s/sock_ops_probe.bpf.c}
LSM_SOURCE=${LSM_SOURCE:-/app/raasa/k8s/lsm_exec_block.bpf.c}
BPF_CGROUP_PATH=${BPF_CGROUP_PATH:-/sys/fs/cgroup}
BPF_PIN_DIR=${BPF_PIN_DIR:-/sys/fs/bpf/raasa}
BPF_MAP_PIN_DIR=${BPF_MAP_PIN_DIR:-${BPF_PIN_DIR}/maps}
BPF_EDGE_MAP_PIN=${BPF_EDGE_MAP_PIN:-${BPF_PIN_DIR}/raasa_pod_edges}
BPF_LSM_MAP_PIN=${BPF_LSM_MAP_PIN:-${BPF_MAP_PIN_DIR}/raasa_lsm_blocked_tgids}
BPF_LSM_PROG_PIN_DIR=${BPF_LSM_PROG_PIN_DIR:-${BPF_PIN_DIR}/lsm_exec_block}
BPF_OBJ="${PROBE_DIR}/raasa_sock_ops.bpf.o"
BPF_LSM_OBJ="${PROBE_DIR}/raasa_lsm_exec_block.bpf.o"
POD_EDGES_FILE="${PROBE_DIR}/pod_edges.jsonl"
SOCK_OPS_STATUS_FILE="${PROBE_DIR}/sock_ops_status"
LSM_STATUS_FILE="${PROBE_DIR}/lsm_exec_block_status"
DNS_QUERIES_FILE="${PROBE_DIR}/dns_queries.jsonl"
mkdir -p "$PROBE_DIR"

echo "[probe] Starting RAASA syscall rate probe (interval: ${POLL_INTERVAL}s)"
echo "[probe] Mode: cgroup-based /proc estimation"

start_sock_ops_probe() {
    if [[ "${ENABLE_SOCK_OPS_PROBE:-1}" != "1" ]]; then
        echo "disabled" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops communication graph disabled"
        return 0
    fi
    if [[ ! -f "$BPF_SOURCE" ]]; then
        echo "missing_source:${BPF_SOURCE}" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops source missing: $BPF_SOURCE"
        return 0
    fi
    if ! command -v clang >/dev/null 2>&1 || ! command -v bpftool >/dev/null 2>&1; then
        echo "unavailable:clang_or_bpftool_missing" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops probe unavailable: clang or bpftool missing"
        return 0
    fi

    mkdir -p "$BPF_PIN_DIR"
    if ! clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -c "$BPF_SOURCE" -o "$BPF_OBJ" 2>"${PROBE_DIR}/sock_ops_compile.err"; then
        echo "compile_failed" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops compile failed; see ${PROBE_DIR}/sock_ops_compile.err"
        return 0
    fi

    bpftool prog detach "$BPF_CGROUP_PATH" sock_ops pinned "${BPF_PIN_DIR}/raasa_sock_ops" >/dev/null 2>&1 || true
    rm -f "${BPF_PIN_DIR}/raasa_sock_ops" "${BPF_PIN_DIR}/maps/raasa_pod_edges" "$BPF_EDGE_MAP_PIN" 2>/dev/null || true
    if ! bpftool prog loadall "$BPF_OBJ" "$BPF_PIN_DIR" type sockops 2>"${PROBE_DIR}/sock_ops_load.err"; then
        echo "load_failed" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops load failed; see ${PROBE_DIR}/sock_ops_load.err"
        return 0
    fi

    if [[ -e "${BPF_PIN_DIR}/maps/raasa_pod_edges" ]]; then
        BPF_EDGE_MAP_PIN="${BPF_PIN_DIR}/maps/raasa_pod_edges"
    fi
    if ! bpftool cgroup attach "$BPF_CGROUP_PATH" sock_ops pinned "${BPF_PIN_DIR}/raasa_sock_ops" 2>"${PROBE_DIR}/sock_ops_attach.err"; then
        echo "attach_failed" > "$SOCK_OPS_STATUS_FILE"
        echo "[probe] sock_ops attach failed; see ${PROBE_DIR}/sock_ops_attach.err"
        return 0
    fi

    echo "attached:${BPF_EDGE_MAP_PIN}" > "$SOCK_OPS_STATUS_FILE"
    echo "[probe] sock_ops communication graph attached; map=${BPF_EDGE_MAP_PIN}"
}

start_lsm_exec_block_probe() {
    if [[ "${ENABLE_LSM_EXEC_BLOCKING:-1}" != "1" ]]; then
        echo "disabled" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM exec blocking disabled"
        return 0
    fi
    if [[ ! -f "$LSM_SOURCE" ]]; then
        echo "missing_source:${LSM_SOURCE}" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM source missing: $LSM_SOURCE"
        return 0
    fi
    if ! command -v clang >/dev/null 2>&1 || ! command -v bpftool >/dev/null 2>&1; then
        echo "unavailable:clang_or_bpftool_missing" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM unavailable: clang or bpftool missing"
        return 0
    fi
    if [[ -r /sys/kernel/security/lsm ]] && ! grep -qw bpf /sys/kernel/security/lsm; then
        echo "unavailable:bpf_lsm_not_enabled" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM unavailable: kernel LSM list does not include bpf"
        return 0
    fi

    if ! mkdir -p "$BPF_PIN_DIR" "$BPF_MAP_PIN_DIR" "$BPF_LSM_PROG_PIN_DIR" 2>"${PROBE_DIR}/lsm_exec_block_pin.err"; then
        echo "pin_dir_failed" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM pin directory setup failed; see ${PROBE_DIR}/lsm_exec_block_pin.err"
        return 0
    fi
    if ! clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -c "$LSM_SOURCE" -o "$BPF_LSM_OBJ" 2>"${PROBE_DIR}/lsm_exec_block_compile.err"; then
        echo "compile_failed" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM compile failed; see ${PROBE_DIR}/lsm_exec_block_compile.err"
        return 0
    fi

    rm -rf "$BPF_LSM_PROG_PIN_DIR" "$BPF_LSM_MAP_PIN" 2>/dev/null || true
    mkdir -p "$BPF_LSM_PROG_PIN_DIR" "$BPF_MAP_PIN_DIR"
    if ! bpftool prog loadall "$BPF_LSM_OBJ" "$BPF_LSM_PROG_PIN_DIR" type lsm pinmaps "$BPF_MAP_PIN_DIR" autoattach 2>"${PROBE_DIR}/lsm_exec_block_load.err"; then
        echo "load_failed" > "$LSM_STATUS_FILE"
        echo "[probe] eBPF LSM load/attach failed; see ${PROBE_DIR}/lsm_exec_block_load.err"
        return 0
    fi

    if [[ -e "${BPF_MAP_PIN_DIR}/raasa_lsm_blocked_tgids" ]]; then
        BPF_LSM_MAP_PIN="${BPF_MAP_PIN_DIR}/raasa_lsm_blocked_tgids"
    fi
    echo "attached:${BPF_LSM_MAP_PIN}" > "$LSM_STATUS_FILE"
    echo "[probe] eBPF LSM exec blocking attached; map=${BPF_LSM_MAP_PIN}"
}

export_lateral_edges() {
    [[ -e "$BPF_EDGE_MAP_PIN" ]] || return 0
    command -v bpftool >/dev/null 2>&1 || return 0
    command -v jq >/dev/null 2>&1 || return 0

    local tmp="${POD_EDGES_FILE}.tmp"
    if bpftool -j map dump pinned "$BPF_EDGE_MAP_PIN" 2>/dev/null \
        | jq -rc '.[] | select(.key.src_ip? and .key.dst_ip?) | {src_ip: .key.src_ip, dst_ip: .key.dst_ip, count: (.value.count // 1), last_seen_ns: (.value.last_seen_ns // 0)}' \
        > "$tmp"; then
        mv "$tmp" "$POD_EDGES_FILE"
    else
        rm -f "$tmp"
    fi
}

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
            local uid_dir="${PROBE_DIR}/${uid}"
            local syscall_samples_file="${uid_dir}/.syscall_samples_current"
            local file_samples_file="${uid_dir}/.file_samples_current"
            mkdir -p "$uid_dir"
            : > "$syscall_samples_file"
            : > "$file_samples_file"
            while IFS= read -r procs_file; do
                while IFS= read -r pid; do
                    [[ -z "$pid" ]] && continue
                    found_pids=$((found_pids + 1))
                    local vol inv syscall_id fd_seen fd_path fd_target
                    vol=$(grep -m1 'voluntary_ctxt_switches' /proc/${pid}/status 2>/dev/null | awk '{print $2}')
                    inv=$(grep -m1 'nonvoluntary_ctxt_switches' /proc/${pid}/status 2>/dev/null | awk '{print $2}')
                    total_switches=$(( total_switches + ${vol:-0} + ${inv:-0} ))
                    syscall_id=$(awk '{print $1}' /proc/${pid}/syscall 2>/dev/null || true)
                    if [[ "$syscall_id" =~ ^[0-9]+$ ]]; then
                        echo "$syscall_id" >> "$syscall_samples_file"
                    fi
                    fd_seen=0
                    for fd_path in /proc/${pid}/fd/*; do
                        fd_target=$(readlink "$fd_path" 2>/dev/null || true)
                        if [[ "$fd_target" == /* ]]; then
                            echo "$fd_target" >> "$file_samples_file"
                            fd_seen=$((fd_seen + 1))
                            [[ $fd_seen -ge 64 ]] && break
                        fi
                    done
                done < "$procs_file"
            done < <(find "$cg" -name cgroup.procs -type f 2>/dev/null)

            if [[ $found_pids -gt 0 ]]; then
                echo "$total_switches" > "${uid_dir}/.switches_current"
                echo "$pid_count" > "${uid_dir}/.pid_count"
                echo "$usage_usec" > "${uid_dir}/.cpu_usec"
                if [[ -s "$syscall_samples_file" ]]; then
                    awk 'BEGIN{printf "{"} {count[$1]++} END{sep=""; for (id in count) {printf "%s\"%s\":%d", sep, id, count[id]; sep=","} printf "}\n"}' \
                        "$syscall_samples_file" > "${uid_dir}/syscall_counts.json"
                else
                    echo "{}" > "${uid_dir}/syscall_counts.json"
                fi
                if [[ -s "$file_samples_file" ]]; then
                    awk 'BEGIN{printf "["} !seen[$0]++ {value=$0; gsub(/\\/,"\\\\",value); gsub(/"/,"\\\"",value); printf "%s\"%s\"", sep, value; sep=","} END{printf "]\n"}' \
                        "$file_samples_file" > "${uid_dir}/file_paths.json"
                else
                    echo "[]" > "${uid_dir}/file_paths.json"
                fi
                if [[ -f "$DNS_QUERIES_FILE" ]] && command -v jq >/dev/null 2>&1; then
                    jq -c --arg uid "$uid" '[select((.pod_uid // "") == $uid) | (.query_name // .query // empty) | select(type == "string")]' \
                        "$DNS_QUERIES_FILE" > "${uid_dir}/dns_queries.json" 2>/dev/null || echo "[]" > "${uid_dir}/dns_queries.json"
                else
                    echo "[]" > "${uid_dir}/dns_queries.json"
                fi
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
start_sock_ops_probe
start_lsm_exec_block_probe
discover_pods
echo "[probe] Initial discovery complete. Entering main loop."

while true; do
    sleep "$POLL_INTERVAL"
    discover_pods
    compute_rates
    export_lateral_edges

    # Report pod count
    pod_count=$(find "${PROBE_DIR}" -maxdepth 1 -type d | grep -cE '[0-9a-f]{8}-')
    echo "[probe] cgroup map: ${pod_count} pod(s) discovered"
done
