#!/usr/bin/env bash
# Create one RAASA AWS Free Tier / credit-backed EC2 test node from AWS CloudShell.
#
# Required environment:
#   export RAASA_CONFIRM_M7I_FREE_TIER=1
#   export RAASA_SSH_CIDR="<your-public-ip>/32"
#
# Optional environment:
#   export AWS_REGION=us-east-1
#   export RAASA_KEY_NAME=raasa-key-2
#   export RAASA_INSTANCE_TYPE=m7i-flex.large
#   export RAASA_VOLUME_SIZE_GB=30
#
# This script intentionally creates only EC2, security group, key pair, and EBS.
# It does not create EKS, NAT Gateway, Load Balancer, or Elastic IP resources.

set -euo pipefail

PROJECT_TAG="RAASA-FreeTier"
MANAGED_TAG="raasa-cloudshell"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
INSTANCE_TYPE="${RAASA_INSTANCE_TYPE:-m7i-flex.large}"
VOLUME_SIZE_GB="${RAASA_VOLUME_SIZE_GB:-30}"
KEY_NAME="${RAASA_KEY_NAME:-raasa-key-$(date -u +%Y%m%d%H%M%S)}"
SSH_CIDR="${RAASA_SSH_CIDR:-}"
OUTPUT_DIR="${HOME}/raasa-free-tier-launch-$(date -u +%Y%m%dT%H%M%SZ)"
KEY_PATH="${OUTPUT_DIR}/${KEY_NAME}.pem"

fail() {
  echo "[RAASA create] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA create] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required. Run this from AWS CloudShell or an AWS CLI host."

[[ "${RAASA_CONFIRM_M7I_FREE_TIER:-}" == "1" ]] || fail "Set RAASA_CONFIRM_M7I_FREE_TIER=1 after confirming m7i-flex.large is covered by your tier/credits."
[[ -n "$SSH_CIDR" ]] || fail "Set RAASA_SSH_CIDR to your workstation public IP CIDR, for example 203.0.113.10/32."
[[ "$SSH_CIDR" != "0.0.0.0/0" ]] || fail "Refusing to open SSH to the world. Use your public IP as /32."
[[ "$SSH_CIDR" == */* ]] || fail "RAASA_SSH_CIDR must include a CIDR suffix, usually /32."
[[ "$INSTANCE_TYPE" == "m7i-flex.large" ]] || fail "This zero-overage script is locked to m7i-flex.large. Set a different script/plan for other types."
[[ "$VOLUME_SIZE_GB" =~ ^[0-9]+$ ]] || fail "RAASA_VOLUME_SIZE_GB must be an integer."
(( VOLUME_SIZE_GB <= 30 )) || fail "Refusing EBS volume larger than 30 GiB."

mkdir -p "$OUTPUT_DIR"

info "Using region: $REGION"
aws sts get-caller-identity --output json > "${OUTPUT_DIR}/caller_identity.json"

if aws freetier get-account-plan-state --region "$REGION" --output json > "${OUTPUT_DIR}/free_tier_plan_state.json" 2>"${OUTPUT_DIR}/free_tier_plan_state.err"; then
  info "Captured Free Tier plan state."
else
  info "Free Tier plan API was unavailable for this account/region; continuing because explicit confirmation was provided."
fi

ACTIVE_COUNT="$(
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'length(Reservations[].Instances[])' \
    --output text
)"
if [[ "$ACTIVE_COUNT" != "0" && "${RAASA_ALLOW_SECOND_INSTANCE:-}" != "1" ]]; then
  fail "Found ${ACTIVE_COUNT} existing RAASA-FreeTier instance(s). Set RAASA_ALLOW_SECOND_INSTANCE=1 only if you intentionally want another."
fi

OFFERING_COUNT="$(
  aws ec2 describe-instance-type-offerings \
    --region "$REGION" \
    --location-type region \
    --filters "Name=instance-type,Values=${INSTANCE_TYPE}" \
    --query 'length(InstanceTypeOfferings[])' \
    --output text
)"
[[ "$OFFERING_COUNT" != "0" ]] || fail "${INSTANCE_TYPE} is not offered in ${REGION}."

VPC_ID="$(
  aws ec2 describe-vpcs \
    --region "$REGION" \
    --filters Name=is-default,Values=true \
    --query 'Vpcs[0].VpcId' \
    --output text
)"
[[ -n "$VPC_ID" && "$VPC_ID" != "None" ]] || fail "No default VPC found in ${REGION}."

SUBNET_ID="$(
  aws ec2 describe-subnets \
    --region "$REGION" \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
    --query 'Subnets[0].SubnetId' \
    --output text
)"
[[ -n "$SUBNET_ID" && "$SUBNET_ID" != "None" ]] || fail "No default subnet found in ${REGION}/${VPC_ID}."

AMI_ID="$(
  aws ssm get-parameter \
    --region "$REGION" \
    --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || true
)"
if [[ -z "$AMI_ID" || "$AMI_ID" == "None" ]]; then
  AMI_ID="$(
    aws ec2 describe-images \
      --region "$REGION" \
      --owners 099720109477 \
      --filters 'Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*' 'Name=state,Values=available' \
      --query 'sort_by(Images,&CreationDate)[-1].ImageId' \
      --output text
  )"
fi
[[ -n "$AMI_ID" && "$AMI_ID" != "None" ]] || fail "Could not resolve an Ubuntu 24.04 amd64 AMI."

SG_NAME="raasa-free-tier-sg"
SG_ID="$(
  aws ec2 describe-security-groups \
    --region "$REGION" \
    --filters "Name=group-name,Values=${SG_NAME}" "Name=vpc-id,Values=${VPC_ID}" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || true
)"
if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
  SG_ID="$(
    aws ec2 create-security-group \
      --region "$REGION" \
      --group-name "$SG_NAME" \
      --description "RAASA Free Tier SSH-only security group" \
      --vpc-id "$VPC_ID" \
      --query GroupId \
      --output text
  )"
  aws ec2 create-tags --region "$REGION" --resources "$SG_ID" --tags "Key=Project,Value=${PROJECT_TAG}" "Key=ManagedBy,Value=${MANAGED_TAG}"
fi

aws ec2 revoke-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$SSH_CIDR" >/dev/null 2>&1 || true

aws ec2 create-key-pair \
  --region "$REGION" \
  --key-name "$KEY_NAME" \
  --key-type rsa \
  --key-format pem \
  --query 'KeyMaterial' \
  --output text > "$KEY_PATH"
chmod 400 "$KEY_PATH"

cat > "${OUTPUT_DIR}/user-data.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
apt-get update -y
apt-get install -y ca-certificates curl jq tar gzip docker.io
systemctl enable --now docker
cat >/etc/raasa-free-tier-node <<'MARKER'
Project=RAASA-FreeTier
Purpose=single-node-k3s-validation
MARKER
EOF

INSTANCE_ID="$(
  aws ec2 run-instances \
    --region "$REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --subnet-id "$SUBNET_ID" \
    --associate-public-ip-address \
    --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${VOLUME_SIZE_GB},VolumeType=gp3,DeleteOnTermination=true}" \
    --user-data "file://${OUTPUT_DIR}/user-data.sh" \
    --tag-specifications \
      "ResourceType=instance,Tags=[{Key=Name,Value=raasa-free-tier-node},{Key=Project,Value=${PROJECT_TAG}},{Key=ManagedBy,Value=${MANAGED_TAG}}]" \
      "ResourceType=volume,Tags=[{Key=Name,Value=raasa-free-tier-node-root},{Key=Project,Value=${PROJECT_TAG}},{Key=ManagedBy,Value=${MANAGED_TAG}}]" \
    --query 'Instances[0].InstanceId' \
    --output text
)"

aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
PUBLIC_IP="$(
  aws ec2 describe-instances \
    --region "$REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
)"

cat > "${OUTPUT_DIR}/summary.md" <<EOF
# RAASA Free Tier EC2 Launch

- Region: \`${REGION}\`
- Instance ID: \`${INSTANCE_ID}\`
- Instance type: \`${INSTANCE_TYPE}\`
- Public IP: \`${PUBLIC_IP}\`
- SSH user: \`ubuntu\`
- Key name: \`${KEY_NAME}\`
- Local CloudShell key path: \`${KEY_PATH}\`
- SSH CIDR allowed: \`${SSH_CIDR}\`
- Security group: \`${SG_ID}\`
- Root EBS: \`${VOLUME_SIZE_GB} GiB gp3\`, delete on termination

## Next Windows Step

Download \`${KEY_PATH}\` from CloudShell to:

\`\`\`powershell
C:\\Users\\Admin\\.ssh\\${KEY_NAME}.pem
\`\`\`

Then set:

\`\`\`powershell
\$env:RAASA_AWS_KEY_PATH = "C:\\Users\\Admin\\.ssh\\${KEY_NAME}.pem"
\$TargetHost = "${PUBLIC_IP}"
\`\`\`

## Cleanup

From CloudShell:

\`\`\`bash
export RAASA_CONFIRM_DESTROY=1
export RAASA_INSTANCE_ID=${INSTANCE_ID}
bash raasa/scripts/destroy_freetier_raasa_ec2.sh
\`\`\`
EOF

aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID" --output json > "${OUTPUT_DIR}/instance.json"

info "Launch complete."
info "Public IP: ${PUBLIC_IP}"
info "Private key saved in CloudShell: ${KEY_PATH}"
info "Summary: ${OUTPUT_DIR}/summary.md"
