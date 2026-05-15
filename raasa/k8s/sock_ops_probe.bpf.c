// RAASA pod communication graph probe.
//
// Tracks IPv4 socket establishment edges as (src_ip, dst_ip) pairs. The
// sidecar exports this map for ObserverK8s, which converts first-ever pod
// edges into a lateral_movement_signal.

#define SEC(NAME) __attribute__((section(NAME), used))
#define BPF_MAP_TYPE_LRU_HASH 9
#define BPF_ANY 0
#define AF_INET 2
#define BPF_SOCK_OPS_ACTIVE_ESTABLISHED_CB 4
#define BPF_SOCK_OPS_PASSIVE_ESTABLISHED_CB 5

#define __uint(name, val) int (*name)[val]
#define __type(name, val) val *name

typedef unsigned int __u32;
typedef unsigned long long __u64;

struct bpf_sock_ops {
    __u32 op;
    __u32 family;
    __u32 remote_ip4;
    __u32 local_ip4;
};

struct raasa_conn_key {
    __u32 src_ip;
    __u32 dst_ip;
};

struct raasa_conn_value {
    __u64 count;
    __u64 last_seen_ns;
};

struct {
    __uint(type, BPF_MAP_TYPE_LRU_HASH);
    __uint(max_entries, 16384);
    __type(key, struct raasa_conn_key);
    __type(value, struct raasa_conn_value);
} raasa_pod_edges SEC(".maps");

static void *(*bpf_map_lookup_elem)(void *map, const void *key) = (void *)1;
static long (*bpf_map_update_elem)(void *map, const void *key, const void *value, __u64 flags) = (void *)2;
static __u64 (*bpf_ktime_get_ns)(void) = (void *)5;

SEC("sockops")
int raasa_sock_ops(struct bpf_sock_ops *skops)
{
    if (skops->family != AF_INET) {
        return 0;
    }
    if (skops->op != BPF_SOCK_OPS_ACTIVE_ESTABLISHED_CB &&
        skops->op != BPF_SOCK_OPS_PASSIVE_ESTABLISHED_CB) {
        return 0;
    }

    struct raasa_conn_key key = {
        .src_ip = skops->local_ip4,
        .dst_ip = skops->remote_ip4,
    };
    struct raasa_conn_value *existing = bpf_map_lookup_elem(&raasa_pod_edges, &key);
    if (existing) {
        struct raasa_conn_value next = {
            .count = existing->count + 1,
            .last_seen_ns = bpf_ktime_get_ns(),
        };
        bpf_map_update_elem(&raasa_pod_edges, &key, &next, BPF_ANY);
        return 0;
    }

    struct raasa_conn_value first = {
        .count = 1,
        .last_seen_ns = bpf_ktime_get_ns(),
    };
    bpf_map_update_elem(&raasa_pod_edges, &key, &first, BPF_ANY);
    return 0;
}

char _license[] SEC("license") = "GPL";
