#!/usr/bin/env bash
# Destroy RAASA Free Tier resources created by create_freetier_raasa_ec2.sh.
#
# Required:
#   export RAASA_CONFIRM_DESTROY=1
#
# Optional:
#   export RAASA_INSTANCE_ID=i-...
#   export AWS_REGION=us-east-1
#   export RAASA_DELETE_KEY_PAIR=1
#   export RAASA_KEY_NAME=raasa-key-...

set -euo pipefail

PROJECT_TAG="RAASA-FreeTier"
MANAGED_TAG="raasa-cloudshell"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
INSTANCE_ID="${RAASA_INSTANCE_ID:-}"

fail() {
  echo "[RAASA destroy] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA destroy] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required. Run this from AWS CloudShell or an AWS CLI host."
[[ "${RAASA_CONFIRM_DESTROY:-}" == "1" ]] || fail "Set RAASA_CONFIRM_DESTROY=1 before destroying resources."

if [[ -z "$INSTANCE_ID" ]]; then
  mapfile -t IDS < <(
    aws ec2 describe-instances \
      --region "$REGION" \
      --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
      --query 'Reservations[].Instances[].InstanceId' \
      --output text | tr '\t' '\n' | sed '/^$/d'
  )
  if (( ${#IDS[@]} == 0 )); then
    info "No active RAASA-FreeTier instances found."
  elif (( ${#IDS[@]} == 1 )); then
    INSTANCE_ID="${IDS[0]}"
  else
    fail "Multiple RAASA-FreeTier instances found: ${IDS[*]}. Set RAASA_INSTANCE_ID explicitly."
  fi
fi

if [[ -n "$INSTANCE_ID" ]]; then
  info "Terminating ${INSTANCE_ID} in ${REGION}."
  aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
  aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"
  info "Instance terminated."
fi

mapfile -t SG_IDS < <(
  aws ec2 describe-security-groups \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" \
    --query 'SecurityGroups[].GroupId' \
    --output text | tr '\t' '\n' | sed '/^$/d'
)

for SG_ID in "${SG_IDS[@]}"; do
  info "Deleting security group ${SG_ID} if detached."
  aws ec2 delete-security-group --region "$REGION" --group-id "$SG_ID" >/dev/null 2>&1 || \
    info "Security group ${SG_ID} could not be deleted yet; it may still be detaching."
done

if [[ "${RAASA_DELETE_KEY_PAIR:-}" == "1" ]]; then
  KEY_NAME="${RAASA_KEY_NAME:-}"
  [[ -n "$KEY_NAME" ]] || fail "Set RAASA_KEY_NAME when RAASA_DELETE_KEY_PAIR=1."
  aws ec2 delete-key-pair --region "$REGION" --key-name "$KEY_NAME" >/dev/null
  info "Deleted EC2 key pair ${KEY_NAME}. Local PEM files are not removed by this script."
fi

info "Cleanup command completed."
