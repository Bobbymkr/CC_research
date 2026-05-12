#!/usr/bin/env python3
"""
Test: Can the Python kubernetes client reach the Metrics API
using explicit K3s kubeconfig path?
"""
import os
import json

os.environ['KUBECONFIG'] = '/etc/rancher/k3s/k3s.yaml'

from kubernetes import client, config

config.load_kube_config(config_file='/etc/rancher/k3s/k3s.yaml')
ca = client.CustomObjectsApi()

try:
    result = ca.get_namespaced_custom_object(
        'metrics.k8s.io', 'v1beta1', 'default', 'pods', 'raasa-test-malicious-cpu'
    )
    containers = result.get('containers', [])
    print("SUCCESS — containers:", json.dumps(containers))
    for c in containers:
        usage = c.get('usage', {})
        print(f"  cpu={usage.get('cpu')}  memory={usage.get('memory')}")
except Exception as e:
    print(f"FAILED: {e}")
