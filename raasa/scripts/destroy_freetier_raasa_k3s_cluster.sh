#!/usr/bin/env bash
# Destroy RAASA multi-node K3s Free Tier resources created by create_freetier_raasa_k3s_cluster.sh.
#
# Required:
#   export RAASA_CONFIRM_DESTROY=1
#
# Optional:
#   export AWS_REGION=us-east-1
#   export RAASA_DELETE_KEY_PAIR=1
#   export RAASA_KEY_NAME=raasa-k3s-key-...

set -euo pipefail

PROJECT_TAG="RAASA-FreeTier-K3s"
MANAGED_TAG="raasa-cloudshell"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
OUTPUT_DIR="${HOME}/raasa-k3s-cluster-destroy-$(date -u +%Y%m%dT%H%M%SZ)"

fail() {
  echo "[RAASA k3s destroy] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA k3s destroy] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required. Run this from AWS CloudShell or an AWS CLI host."
[[ "${RAASA_CONFIRM_DESTROY:-}" == "1" ]] || fail "Set RAASA_CONFIRM_DESTROY=1 before destroying resources."

mkdir -p "$OUTPUT_DIR"
aws sts get-caller-identity --output json > "${OUTPUT_DIR}/caller_identity.json"

mapfile -t INSTANCE_IDS < <(
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text | tr '\t' '\n' | sed '/^$/d'
)

if (( ${#INSTANCE_IDS[@]} > 0 )); then
  info "Terminating ${#INSTANCE_IDS[@]} tagged cluster instance(s)."
  aws ec2 terminate-instances --region "$REGION" --instance-ids "${INSTANCE_IDS[@]}" > "${OUTPUT_DIR}/terminate_instances.json"
  aws ec2 wait instance-terminated --region "$REGION" --instance-ids "${INSTANCE_IDS[@]}"
else
  info "No tagged cluster instances found."
fi

for _ in $(seq 1 30); do
  TAGGED_VOLUME_COUNT="$(
    aws ec2 describe-volumes \
      --region "$REGION" \
      --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
      --query 'length(Volumes[])' \
      --output text
  )"
  if [[ "$TAGGED_VOLUME_COUNT" == "0" ]]; then
    break
  fi
  sleep 10
done

mapfile -t SG_IDS < <(
  aws ec2 describe-security-groups \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
    --query 'SecurityGroups[].GroupId' \
    --output text | tr '\t' '\n' | sed '/^$/d'
)

for sg_id in "${SG_IDS[@]}"; do
  info "Deleting security group ${sg_id} if detached."
  aws ec2 delete-security-group --region "$REGION" --group-id "$sg_id" >/dev/null 2>&1 || \
    info "Security group ${sg_id} could not be deleted yet; it may still be detaching."
done

if [[ "${RAASA_DELETE_KEY_PAIR:-}" == "1" ]]; then
  KEY_NAME="${RAASA_KEY_NAME:-}"
  [[ -n "$KEY_NAME" ]] || fail "Set RAASA_KEY_NAME when RAASA_DELETE_KEY_PAIR=1."
  aws ec2 delete-key-pair --region "$REGION" --key-name "$KEY_NAME" >/dev/null
  info "Deleted EC2 key pair ${KEY_NAME}. Local PEM files are not removed by this script."
fi

INSTANCE_COUNT="$(
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'length(Reservations[].Instances[])' \
    --output text
)"
VOLUME_COUNT="$(
  aws ec2 describe-volumes \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
    --query 'length(Volumes[])' \
    --output text
)"
EIP_COUNT="$(
  aws ec2 describe-addresses \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
    --query 'length(Addresses[])' \
    --output text
)"
NAT_COUNT="$(
  aws ec2 describe-nat-gateways \
    --region "$REGION" \
    --filter "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
    --query 'length(NatGateways[])' \
    --output text 2>/dev/null || echo "0"
)"
LB_COUNT=0
mapfile -t LB_ARNS < <(
  aws elbv2 describe-load-balancers \
    --region "$REGION" \
    --query 'LoadBalancers[].LoadBalancerArn' \
    --output text 2>/dev/null | tr '\t' '\n' | sed '/^$/d'
)
for lb_arn in "${LB_ARNS[@]}"; do
  tag_rows="$(
    aws elbv2 describe-tags \
      --region "$REGION" \
      --resource-arns "$lb_arn" \
      --query 'TagDescriptions[0].Tags[].[Key,Value]' \
      --output text 2>/dev/null || true
  )"
  if grep -Fq "Project	${PROJECT_TAG}" <<<"$tag_rows" && grep -Fq "ManagedBy	${MANAGED_TAG}" <<<"$tag_rows"; then
    LB_COUNT=$((LB_COUNT + 1))
  fi
done

cat > "${OUTPUT_DIR}/summary.md" <<EOF
# RAASA Free Tier Multi-Node K3s Destroy

- Region: \`${REGION}\`
- Tagged active instances remaining: \`${INSTANCE_COUNT}\`
- Tagged volumes remaining: \`${VOLUME_COUNT}\`
- Tagged Elastic IPs remaining: \`${EIP_COUNT}\`
- Tagged NAT gateways remaining: \`${NAT_COUNT}\`
- Tagged load balancers remaining: \`${LB_COUNT}\`
EOF

info "Cleanup command completed."
info "Summary: ${OUTPUT_DIR}/summary.md"
