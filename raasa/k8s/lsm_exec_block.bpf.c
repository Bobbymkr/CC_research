// RAASA eBPF LSM progressive exec blocking.
//
// This BPF LSM program enforces a narrow L3 containment rule: when the
// enforcer sidecar marks a host TGID in raasa_lsm_blocked_tgids, any future
// execve transition from that process is denied at bprm_check_security.

#define SEC(NAME) __attribute__((section(NAME), used))
#define BPF_MAP_TYPE_HASH 1
#define BPF_ANY 0
#define EACCES 13

#define __uint(name, val) int (*name)[val]
#define __type(name, val) val *name

typedef unsigned int __u32;
typedef unsigned long long __u64;

struct linux_binprm;

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 65536);
    __type(key, __u32);
    __type(value, __u32);
} raasa_lsm_blocked_tgids SEC(".maps");

static void *(*bpf_map_lookup_elem)(void *map, const void *key) = (void *)1;
static __u64 (*bpf_get_current_pid_tgid)(void) = (void *)14;

SEC("lsm/bprm_check_security")
int raasa_bprm_check_security(struct linux_binprm *bprm, int ret)
{
    (void)bprm;
    if (ret != 0) {
        return ret;
    }

    __u64 pid_tgid = bpf_get_current_pid_tgid();
    __u32 tgid = (__u32)(pid_tgid >> 32);
    __u32 *blocked = bpf_map_lookup_elem(&raasa_lsm_blocked_tgids, &tgid);
    if (blocked && *blocked != 0) {
        return -EACCES;
    }
    return 0;
}

char _license[] SEC("license") = "GPL";
