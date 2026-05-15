#!/usr/bin/env bash
# Destroy the bounded RAASA EKS smoke resources.
#
# Required:
#   export RAASA_CONFIRM_DESTROY=1
#
# Optional:
#   export AWS_REGION=us-east-1
#   export RAASA_CLUSTER_NAME=raasa-eks-smoke-...
#   export RAASA_DELETE_ECR=1
#   export RAASA_AGENT_ECR_REPO=raasa-agent
#   export RAASA_PROBE_ECR_REPO=raasa-ebpf-probe

set -euo pipefail

PROJECT_TAG="RAASA-EKS-Smoke"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
CLUSTER_NAME="${RAASA_CLUSTER_NAME:-}"
OUTPUT_DIR="${HOME}/raasa-eks-smoke-destroy-$(date -u +%Y%m%dT%H%M%SZ)"

fail() {
  echo "[RAASA eks destroy] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA eks destroy] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required."
command -v eksctl >/dev/null 2>&1 || fail "eksctl is required on PATH."
[[ "${RAASA_CONFIRM_DESTROY:-}" == "1" ]] || fail "Set RAASA_CONFIRM_DESTROY=1 before destroying the EKS smoke resources."

mkdir -p "$OUTPUT_DIR"
aws sts get-caller-identity --output json > "${OUTPUT_DIR}/caller_identity.json"

if [[ -z "$CLUSTER_NAME" ]]; then
  mapfile -t CLUSTERS < <(
    aws eks list-clusters --region "$REGION" --query 'clusters[]' --output text | tr '\t' '\n' | sed '/^$/d'
  )
  if (( ${#CLUSTERS[@]} == 1 )); then
    CLUSTER_NAME="${CLUSTERS[0]}"
  else
    fail "Set RAASA_CLUSTER_NAME explicitly when more than one cluster may exist."
  fi
fi

eksctl delete cluster --name "$CLUSTER_NAME" --region "$REGION" > "${OUTPUT_DIR}/eksctl_delete_cluster.txt" 2>&1

if [[ "${RAASA_DELETE_ECR:-}" == "1" ]]; then
  AGENT_REPO="${RAASA_AGENT_ECR_REPO:-raasa-agent}"
  PROBE_REPO="${RAASA_PROBE_ECR_REPO:-raasa-ebpf-probe}"
  aws ecr delete-repository --region "$REGION" --repository-name "$AGENT_REPO" --force > "${OUTPUT_DIR}/delete_agent_repo.json" 2>&1 || true
  aws ecr delete-repository --region "$REGION" --repository-name "$PROBE_REPO" --force > "${OUTPUT_DIR}/delete_probe_repo.json" 2>&1 || true
fi

aws eks list-clusters --region "$REGION" --output json > "${OUTPUT_DIR}/eks_list_clusters_after.json"
aws ec2 describe-instances --region "$REGION" --output json > "${OUTPUT_DIR}/ec2_describe_instances_after.json"
aws ec2 describe-volumes --region "$REGION" --output json > "${OUTPUT_DIR}/ec2_describe_volumes_after.json"
aws ec2 describe-addresses --region "$REGION" --output json > "${OUTPUT_DIR}/ec2_describe_addresses_after.json"
aws elbv2 describe-load-balancers --region "$REGION" --output json > "${OUTPUT_DIR}/elbv2_describe_load_balancers_after.json" 2>/dev/null || true

cat > "${OUTPUT_DIR}/summary.md" <<EOF
# RAASA Credit-Gated EKS Smoke Destroy

- Region: \`${REGION}\`
- Cluster deleted: \`${CLUSTER_NAME}\`
- ECR repos deleted: \`${RAASA_DELETE_ECR:-0}\`
EOF

info "EKS cleanup command completed."
info "Summary: ${OUTPUT_DIR}/summary.md"
