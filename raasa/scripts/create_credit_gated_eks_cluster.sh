#!/usr/bin/env bash
# Create a tightly bounded EKS smoke cluster under AWS-issued credits only.
#
# Required environment:
#   export RAASA_CONFIRM_EKS_SMOKE=1
#   export RAASA_SSH_CIDR="<your-public-ip>/32"
#   export RAASA_AGENT_IMAGE_URI="<account>.dkr.ecr.<region>.amazonaws.com/raasa-agent:<tag>"
#   export RAASA_PROBE_IMAGE_URI="<account>.dkr.ecr.<region>.amazonaws.com/raasa-ebpf-probe:<tag>"
#
# Optional environment:
#   export AWS_REGION=us-east-1
#   export RAASA_CLUSTER_NAME=raasa-eks-smoke
#   export RAASA_NODE_TYPE=m7i-flex.large
#   export RAASA_VOLUME_SIZE_GB=30
#   export RAASA_MIN_REMAINING_CREDITS=50
#   export RAASA_ALLOW_FREE_PLAN_EKS=1

set -euo pipefail

PROJECT_TAG="RAASA-EKS-Smoke"
MANAGED_TAG="raasa-cloudshell"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
CLUSTER_NAME="${RAASA_CLUSTER_NAME:-raasa-eks-smoke-$(date -u +%Y%m%d%H%M%S)}"
NODE_TYPE="${RAASA_NODE_TYPE:-m7i-flex.large}"
VOLUME_SIZE_GB="${RAASA_VOLUME_SIZE_GB:-30}"
MIN_REMAINING_CREDITS="${RAASA_MIN_REMAINING_CREDITS:-50}"
SSH_CIDR="${RAASA_SSH_CIDR:-}"
AGENT_IMAGE_URI="${RAASA_AGENT_IMAGE_URI:-}"
PROBE_IMAGE_URI="${RAASA_PROBE_IMAGE_URI:-}"
OUTPUT_DIR="${HOME}/raasa-eks-smoke-$(date -u +%Y%m%dT%H%M%SZ)"

fail() {
  echo "[RAASA eks create] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA eks create] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required."
command -v kubectl >/dev/null 2>&1 || fail "kubectl is required on PATH."
command -v eksctl >/dev/null 2>&1 || fail "eksctl is required on PATH."

[[ "${RAASA_CONFIRM_EKS_SMOKE:-}" == "1" ]] || fail "Set RAASA_CONFIRM_EKS_SMOKE=1 after confirming this bounded EKS phase is intended."
[[ -n "$SSH_CIDR" && "$SSH_CIDR" == */* && "$SSH_CIDR" != "0.0.0.0/0" ]] || fail "Set RAASA_SSH_CIDR to your public IP as /32."
[[ -n "$AGENT_IMAGE_URI" ]] || fail "Set RAASA_AGENT_IMAGE_URI to the pushed ECR URI for the RAASA agent image."
[[ -n "$PROBE_IMAGE_URI" ]] || fail "Set RAASA_PROBE_IMAGE_URI to the pushed ECR URI for the RAASA eBPF probe image."
[[ "$NODE_TYPE" == "m7i-flex.large" ]] || fail "This credits-only EKS smoke path is locked to m7i-flex.large."
[[ "$VOLUME_SIZE_GB" =~ ^[0-9]+$ ]] || fail "RAASA_VOLUME_SIZE_GB must be an integer."
(( VOLUME_SIZE_GB <= 30 )) || fail "Refusing EBS volume larger than 30 GiB."

mkdir -p "$OUTPUT_DIR"
aws sts get-caller-identity --output json > "${OUTPUT_DIR}/caller_identity.json"

PLAN_JSON="${OUTPUT_DIR}/free_tier_plan_state.json"
aws freetier get-account-plan-state --region "$REGION" --output json > "$PLAN_JSON" 2>"${OUTPUT_DIR}/free_tier_plan_state.err" || \
  fail "Could not retrieve Free Tier plan state for the EKS gate."

PLAN_TYPE="$(aws freetier get-account-plan-state --region "$REGION" --query 'accountPlanType' --output text)"
PLAN_STATUS="$(aws freetier get-account-plan-state --region "$REGION" --query 'accountPlanStatus' --output text)"
REMAINING_CREDITS="$(aws freetier get-account-plan-state --region "$REGION" --query 'accountPlanRemainingCredits.amount' --output text)"

python3 - "$REMAINING_CREDITS" "$MIN_REMAINING_CREDITS" <<'PY'
import sys
value = sys.argv[1]
minimum = float(sys.argv[2])
try:
    credits = float(value)
except Exception:
    raise SystemExit(2)
if credits < minimum:
    raise SystemExit(1)
PY
case "$?" in
  1) fail "Remaining credits (${REMAINING_CREDITS}) are below the minimum EKS gate (${MIN_REMAINING_CREDITS})." ;;
  2) fail "Remaining credits were ambiguous (${REMAINING_CREDITS}). Resolve account state before attempting EKS." ;;
esac

if [[ "$PLAN_TYPE" != "PAID" && "${RAASA_ALLOW_FREE_PLAN_EKS:-}" != "1" ]]; then
  fail "Current plan type is ${PLAN_TYPE}. Set RAASA_ALLOW_FREE_PLAN_EKS=1 only after confirming EKS access is available on this account plan or upgrade the account while staying inside AWS-issued credits."
fi
if [[ "$PLAN_STATUS" != "ACTIVE" ]]; then
  fail "Account plan status is ${PLAN_STATUS}, not ACTIVE."
fi

VPC_ID="$(
  aws ec2 describe-vpcs \
    --region "$REGION" \
    --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' \
    --output text
)"
[[ -n "$VPC_ID" && "$VPC_ID" != "None" ]] || fail "No default VPC found in ${REGION}."

mapfile -t SUBNET_ROWS < <(
  aws ec2 describe-subnets \
    --region "$REGION" \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
    --query 'Subnets[].{SubnetId:SubnetId,AvailabilityZone:AvailabilityZone,MapPublicIpOnLaunch:MapPublicIpOnLaunch}' \
    --output text | sort -k2,2
)

declare -A UNIQUE_AZ_SUBNETS=()
for row in "${SUBNET_ROWS[@]}"; do
  subnet_id="$(awk '{print $1}' <<<"$row")"
  az="$(awk '{print $2}' <<<"$row")"
  public_flag="$(awk '{print $3}' <<<"$row")"
  if [[ "$public_flag" == "True" && -n "$subnet_id" && -n "$az" && -z "${UNIQUE_AZ_SUBNETS[$az]:-}" ]]; then
    UNIQUE_AZ_SUBNETS[$az]="$subnet_id"
  fi
done

SUBNET_IDS=()
for az in "${!UNIQUE_AZ_SUBNETS[@]}"; do
  SUBNET_IDS+=("${UNIQUE_AZ_SUBNETS[$az]}")
done
IFS=$'\n' SUBNET_IDS=($(sort <<<"${SUBNET_IDS[*]}"))
unset IFS
(( ${#SUBNET_IDS[@]} >= 2 )) || fail "Need at least two public default subnets in distinct AZs for the EKS smoke cluster."

SUBNET_ARG="$(IFS=,; echo "${SUBNET_IDS[*]:0:2}")"

eksctl create cluster \
  --name "$CLUSTER_NAME" \
  --region "$REGION" \
  --managed \
  --nodes 2 \
  --nodes-min 2 \
  --nodes-max 2 \
  --node-type "$NODE_TYPE" \
  --node-volume-size "$VOLUME_SIZE_GB" \
  --vpc-public-subnets "$SUBNET_ARG" \
  --tags "Project=${PROJECT_TAG},ManagedBy=${MANAGED_TAG}" \
  > "${OUTPUT_DIR}/eksctl_create_cluster.txt" 2>&1

aws eks update-cluster-config \
  --region "$REGION" \
  --name "$CLUSTER_NAME" \
  --resources-vpc-config "endpointPublicAccess=true,endpointPrivateAccess=false,publicAccessCidrs=${SSH_CIDR}" \
  > "${OUTPUT_DIR}/eks_update_cluster_config.json"

aws eks wait cluster-active --region "$REGION" --name "$CLUSTER_NAME"
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME" --kubeconfig "${OUTPUT_DIR}/kubeconfig" --alias "$CLUSTER_NAME" > "${OUTPUT_DIR}/update_kubeconfig.txt"
export KUBECONFIG="${OUTPUT_DIR}/kubeconfig"

kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml > "${OUTPUT_DIR}/metrics_server_apply.txt" 2>&1
kubectl rollout status deployment/metrics-server -n kube-system --timeout=240s > "${OUTPUT_DIR}/metrics_server_rollout.txt" 2>&1

PATCHED_MANIFEST="${OUTPUT_DIR}/daemonset.eks.yaml"
sed \
  -e "s|image: raasa/agent:1.0.0|image: ${AGENT_IMAGE_URI}|g" \
  -e "s|image: raasa/ebpf-probe:1.0.0|image: ${PROBE_IMAGE_URI}|g" \
  raasa/k8s/daemonset.yaml > "$PATCHED_MANIFEST"

kubectl apply -f "$PATCHED_MANIFEST" > "${OUTPUT_DIR}/daemonset_apply.txt" 2>&1
kubectl rollout status daemonset/raasa-agent -n raasa-system --timeout=360s > "${OUTPUT_DIR}/daemonset_rollout.txt" 2>&1
kubectl apply -f raasa/k8s/phase0-test-pods.yaml > "${OUTPUT_DIR}/phase0_apply.txt" 2>&1
kubectl wait --for=condition=Ready pod -l app=raasa-test -n default --timeout=240s > "${OUTPUT_DIR}/phase0_wait.txt" 2>&1
kubectl get nodes -o wide > "${OUTPUT_DIR}/nodes_after_create.txt"
kubectl get pods -A -o wide > "${OUTPUT_DIR}/pods_after_create.txt"

cat > "${OUTPUT_DIR}/summary.md" <<EOF
# RAASA Credit-Gated EKS Smoke Cluster

- Region: \`${REGION}\`
- Cluster name: \`${CLUSTER_NAME}\`
- Plan type at create time: \`${PLAN_TYPE}\`
- Plan status at create time: \`${PLAN_STATUS}\`
- Remaining credits at create time: \`${REMAINING_CREDITS}\`
- Node type: \`${NODE_TYPE}\`
- Node count: \`2\`
- Public endpoint CIDR: \`${SSH_CIDR}\`
- Public subnets: \`${SUBNET_ARG}\`
- Patched DaemonSet manifest: \`${PATCHED_MANIFEST}\`
EOF

info "EKS smoke cluster created."
info "Kubeconfig: ${OUTPUT_DIR}/kubeconfig"
info "Summary: ${OUTPUT_DIR}/summary.md"
