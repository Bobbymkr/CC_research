#!/bin/bash
# ==============================================================================
# RAASA v2 AWS Bootstrap — K3s + Tetragon eBPF
# ==============================================================================
# Target OS : Ubuntu 24.04 LTS (Kernel 6.8+, BTF enabled by default)
# Instance  : m7i-flex.large (2 vCPU, 8 GiB RAM) or equivalent
#
# Installs:
#   1. K3s  — lightweight, CNCF-certified Kubernetes (single binary, ~75MB)
#   2. Helm — Kubernetes package manager (required for Tetragon chart)
#   3. Tetragon — Cilium eBPF sensor (DaemonSet; hooks into Linux BTF kernel)
#   4. kubectl Metrics Server — provides CPU/RAM data to observer_k8s.py
#   5. Python venv + all RAASA requirements
#
# Usage:
#   chmod +x bootstrap_k8s_ebpf.sh && ./bootstrap_k8s_ebpf.sh
# ==============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Colour

info()    { echo -e "${GREEN}[RAASA-v2]${NC} $*"; }
warning() { echo -e "${YELLOW}[RAASA-v2 WARNING]${NC} $*"; }
error()   { echo -e "${RED}[RAASA-v2 ERROR]${NC} $*"; exit 1; }

# ── Pre-flight checks ──────────────────────────────────────────────────────────
info "Checking kernel version for eBPF/BTF support..."
KERNEL_VERSION=$(uname -r | cut -d. -f1)
[ "$KERNEL_VERSION" -ge 5 ] || error "Kernel $(uname -r) is too old. Need 5.8+. Abort."
if [ -f /sys/kernel/btf/vmlinux ]; then
    info "BTF support CONFIRMED at /sys/kernel/btf/vmlinux ✓"
else
    warning "BTF file not found — Tetragon will still work on Ubuntu 24.04 via CO-RE."
fi

# ── 1. System packages ─────────────────────────────────────────────────────────
info "Updating APT and installing base dependencies..."
sudo apt-get update -y -qq
sudo apt-get install -y -qq \
    python3 python3-pip python3-venv \
    curl wget git iproute2 jq \
    ca-certificates gnupg lsb-release

# Verify iproute2 provides 'tc' (traffic control — required for EnforcerK8s)
command -v tc >/dev/null 2>&1 || error "'tc' (iproute2) not found. Cannot enforce network limits."
info "Traffic control (tc) binary confirmed ✓"

# ── 2. K3s (Kubernetes) ────────────────────────────────────────────────────────
if command -v k3s >/dev/null 2>&1; then
    info "K3s is already installed — skipping."
else
    info "Installing K3s (lightweight Kubernetes)..."
    curl -sfL https://get.k3s.io | sh -s - \
        --write-kubeconfig-mode 644 \
        --disable traefik \
        --disable servicelb
fi

# Export KUBECONFIG for this session and permanently
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
grep -qxF 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' ~/.bashrc \
    || echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc

info "Waiting for K3s node to become Ready (up to 60s)..."
for i in $(seq 1 12); do
    if kubectl get nodes 2>/dev/null | grep -q "Ready"; then
        info "K3s node is Ready ✓"
        break
    fi
    sleep 5
    [ "$i" -eq 12 ] && error "K3s node did not become Ready in 60 seconds. Check 'journalctl -u k3s'."
done

# ── 3. Helm ────────────────────────────────────────────────────────────────────
if command -v helm >/dev/null 2>&1; then
    info "Helm is already installed — skipping."
else
    info "Installing Helm v3..."
    curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# ── 4. Tetragon (eBPF Sensor) ─────────────────────────────────────────────────
info "Adding Cilium Helm repo and deploying Tetragon..."
helm repo add cilium https://helm.cilium.io --force-update > /dev/null
helm repo update > /dev/null

# Check if already installed to make this script idempotent
if helm status tetragon -n kube-system >/dev/null 2>&1; then
    info "Tetragon is already deployed — skipping."
else
    helm install tetragon cilium/tetragon \
        --namespace kube-system \
        --set tetragon.enableProcessCred=true \
        --set tetragon.enableProcessNs=true \
        --wait
fi

info "Verifying Tetragon DaemonSet rollout..."
kubectl rollout status ds/tetragon -n kube-system --timeout=120s
info "Tetragon eBPF sensor is LIVE ✓"

# ── 5. Kubernetes Metrics Server ──────────────────────────────────────────────
# Required by observer_k8s.py to read CPU/memory usage via the Metrics API.
info "Installing Kubernetes Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# Patch for single-node K3s: disable TLS verification for kubelet metrics
kubectl patch deployment metrics-server \
    -n kube-system \
    --type=json \
    -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' \
    2>/dev/null || warning "Metrics Server TLS patch failed — metrics API may be slow to start."

info "Waiting for Metrics Server to be available (up to 60s)..."
sleep 30
kubectl top nodes 2>/dev/null && info "Metrics Server is READY ✓" \
    || warning "Metrics Server not yet serving — observer_k8s.py has graceful fallback."

# ── 6. RAASA eBPF Syscall Probe Directory ────────────────────────────────────
# This is the shared directory where Tetragon sidecar will write per-pod rates.
# observer_k8s.py reads from /var/run/raasa/<pod-uid>/syscall_rate
info "Creating RAASA syscall probe directory..."
sudo mkdir -p /var/run/raasa
sudo chmod 777 /var/run/raasa

# ── 7. Python Environment ─────────────────────────────────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

info "Installing Python dependencies (including kubernetes client)..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

info "Verifying kubernetes Python client installation..."
python3 -c "import kubernetes; print(f'  kubernetes client v{kubernetes.__version__} ✓')"

# ── Final Summary ──────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  RAASA v2 AWS Environment is READY"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "  Docker backend (v1 — local, no root needed):"
echo "    source venv/bin/activate && export PYTHONPATH=."
echo "    python raasa/experiments/run_experiment.py \\"
echo "      --mode raasa --scenario small_tuned --run-id docker_baseline"
echo ""
echo "  K8s/eBPF backend (v2 — AWS cloud, requires root):"
echo "    source venv/bin/activate && export PYTHONPATH=."
echo "    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml"
echo "    sudo -E env PYTHONPATH=. python raasa/experiments/run_experiment.py \\"
echo "      --mode raasa --scenario small_tuned --backend k8s --run-id aws_k8s_ebpf_r1"
echo ""
echo "══════════════════════════════════════════════════════════════════"
