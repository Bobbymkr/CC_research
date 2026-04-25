#!/bin/bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
sudo k3s kubectl patch -n kube-system deployment metrics-server --type=json -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
sudo k3s kubectl apply -f ~/CC_research/raasa/k8s/daemonset.yaml
