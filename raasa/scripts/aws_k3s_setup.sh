#!/bin/bash
# RAASA Zero-Touch AWS EC2 Setup Script
# Run this script on a fresh Ubuntu 24.04/22.04 EC2 instance to fully deploy the RAASA Kubernetes environment.

set -e

echo "========================================================="
echo "   RAASA Zero-Touch Infrastructure Setup (AWS EC2)       "
echo "========================================================="

# 1. Update and install dependencies
echo "[1/5] Installing base dependencies (Docker, build tools)..."
sudo apt-get update
sudo apt-get install -y docker.io containerd bc jq build-essential

# 2. Install K3s (Lightweight Kubernetes)
# We disable traefik to save memory, as RAASA doesn't need external ingress yet.
echo "[2/5] Installing K3s..."
curl -sfL https://get.k3s.io | sh -s - --disable traefik
# Wait for node to be ready
echo "Waiting for K3s node to become ready..."
sleep 15
sudo k3s kubectl wait --for=condition=Ready node --all --timeout=60s

# Ensure local user can run kubectl
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG="$HOME/.kube/config"

# 3. Build Docker Images Locally (avoiding Docker Hub)
# K3s uses containerd, but we can build with docker and import to containerd
echo "[3/5] Building RAASA Docker images..."
sudo docker build -t raasa/agent:1.0.0 -f raasa/k8s/Dockerfile .
sudo docker build -t raasa/ebpf-probe:1.0.0 -f raasa/k8s/Dockerfile.ebpf .

echo "Importing images into K3s..."
sudo docker save raasa/agent:1.0.0 | sudo k3s ctr images import -
sudo docker save raasa/ebpf-probe:1.0.0 | sudo k3s ctr images import -

# 4. Install Metrics Server (required by RAASA ObserverK8s)
echo "[4/5] Installing K8s Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# Patch metrics server to allow insecure TLS (standard practice for local/K3s setups)
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

echo "Waiting for Metrics Server..."
sleep 20

# 5. Deploy RAASA
echo "[5/5] Deploying RAASA Controller..."
kubectl apply -f raasa/k8s/daemonset.yaml

echo "========================================================="
echo "Setup Complete! RAASA is now running."
echo "View logs with:"
echo "  kubectl logs -n raasa-system -l app=raasa-agent --follow"
echo "========================================================="
