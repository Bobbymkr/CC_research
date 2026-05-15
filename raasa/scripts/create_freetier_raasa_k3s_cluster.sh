#!/usr/bin/env bash
# Create a three-node RAASA Free Tier / credit-backed K3s cluster from AWS CloudShell.
#
# Required environment:
#   export RAASA_CONFIRM_MULTINODE=1
#   export RAASA_SSH_CIDR="<your-public-ip>/32"
#
# Optional environment:
#   export AWS_REGION=us-east-1
#   export RAASA_KEY_NAME=raasa-k3s-key
#   export RAASA_INSTANCE_TYPE=m7i-flex.large
#   export RAASA_VOLUME_SIZE_GB=30
#   export RAASA_ALLOW_EXISTING_CLUSTER=1

set -euo pipefail

PROJECT_TAG="RAASA-FreeTier-K3s"
MANAGED_TAG="raasa-cloudshell"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
INSTANCE_TYPE="${RAASA_INSTANCE_TYPE:-m7i-flex.large}"
VOLUME_SIZE_GB="${RAASA_VOLUME_SIZE_GB:-30}"
KEY_NAME="${RAASA_KEY_NAME:-raasa-k3s-key-$(date -u +%Y%m%d%H%M%S)}"
SSH_CIDR="${RAASA_SSH_CIDR:-}"
OUTPUT_DIR="${HOME}/raasa-k3s-cluster-launch-$(date -u +%Y%m%dT%H%M%SZ)"
KEY_PATH="${OUTPUT_DIR}/${KEY_NAME}.pem"
SG_NAME="raasa-free-tier-k3s-sg"
ROLE_NAMES=("control-plane" "worker-a" "worker-b")

fail() {
  echo "[RAASA k3s create] ERROR: $*" >&2
  exit 1
}

info() {
  echo "[RAASA k3s create] $*"
}

command -v aws >/dev/null 2>&1 || fail "aws CLI is required. Run this from AWS CloudShell or an AWS CLI host."

[[ "${RAASA_CONFIRM_MULTINODE:-}" == "1" ]] || fail "Set RAASA_CONFIRM_MULTINODE=1 after confirming the three-node credit-backed campaign is intended."
[[ -n "$SSH_CIDR" ]] || fail "Set RAASA_SSH_CIDR to your workstation public IP CIDR, for example 203.0.113.10/32."
[[ "$SSH_CIDR" != "0.0.0.0/0" ]] || fail "Refusing to open SSH to the world. Use your public IP as /32."
[[ "$SSH_CIDR" == */* ]] || fail "RAASA_SSH_CIDR must include a CIDR suffix, usually /32."
[[ "$INSTANCE_TYPE" == "m7i-flex.large" ]] || fail "This credits-only script is locked to m7i-flex.large."
[[ "$VOLUME_SIZE_GB" =~ ^[0-9]+$ ]] || fail "RAASA_VOLUME_SIZE_GB must be an integer."
(( VOLUME_SIZE_GB <= 30 )) || fail "Refusing EBS volume larger than 30 GiB."

mkdir -p "$OUTPUT_DIR"

info "Using region: $REGION"
aws sts get-caller-identity --output json > "${OUTPUT_DIR}/caller_identity.json"

if aws freetier get-account-plan-state --region "$REGION" --output json > "${OUTPUT_DIR}/free_tier_plan_state.json" 2>"${OUTPUT_DIR}/free_tier_plan_state.err"; then
  info "Captured Free Tier plan state."
else
  fail "Free Tier plan API was unavailable for this account. Resolve account state before launching the multi-node cluster."
fi

ACTIVE_COUNT="$(
  aws ec2 describe-instances \
    --region "$REGION" \
    --filters "Name=tag:Project,Values=${PROJECT_TAG}" "Name=tag:ManagedBy,Values=${MANAGED_TAG}" "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'length(Reservations[].Instances[])' \
    --output text
)"
if [[ "$ACTIVE_COUNT" != "0" && "${RAASA_ALLOW_EXISTING_CLUSTER:-}" != "1" ]]; then
  fail "Found ${ACTIVE_COUNT} existing tagged multi-node instance(s). Set RAASA_ALLOW_EXISTING_CLUSTER=1 only if you intentionally want another cluster."
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

mapfile -t SUBNET_ROWS < <(
  aws ec2 describe-subnets \
    --region "$REGION" \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=default-for-az,Values=true" \
    --query 'Subnets[].[SubnetId,AvailabilityZone]' \
    --output text | sort -k2,2
)
(( ${#SUBNET_ROWS[@]} >= 1 )) || fail "No default subnet found in ${REGION}/${VPC_ID}."

SUBNET_IDS=()
for row in "${SUBNET_ROWS[@]}"; do
  IFS=$'\t' read -r subnet_id availability_zone <<<"$row"
  if [[ -n "$subnet_id" && "$subnet_id" == subnet-* ]]; then
    SUBNET_IDS+=("$subnet_id")
  else
    fail "Could not parse subnet row from AWS CLI output: ${row}"
  fi
done

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
      --description "RAASA Free Tier multi-node K3s SSH-only security group" \
      --vpc-id "$VPC_ID" \
      --query GroupId \
      --output text
  )"
  aws ec2 create-tags --region "$REGION" --resources "$SG_ID" --tags "Key=Project,Value=${PROJECT_TAG}" "Key=ManagedBy,Value=${MANAGED_TAG}"
fi

aws ec2 revoke-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0 >/dev/null 2>&1 || true
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol tcp --port 22 --cidr "$SSH_CIDR" >/dev/null 2>&1 || true
# K3s nodes must be able to talk to each other across the shared security group.
aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID" --protocol -1 --source-group "$SG_ID" >/dev/null 2>&1 || true

aws ec2 create-key-pair \
  --region "$REGION" \
  --key-name "$KEY_NAME" \
  --key-type rsa \
  --key-format pem \
  --tag-specifications "ResourceType=key-pair,Tags=[{Key=Project,Value=${PROJECT_TAG}},{Key=ManagedBy,Value=${MANAGED_TAG}}]" \
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
Purpose=multi-node-k3s-validation
MARKER
EOF

INSTANCE_ROWS=()
for i in "${!ROLE_NAMES[@]}"; do
  role="${ROLE_NAMES[$i]}"
  subnet="${SUBNET_IDS[$(( i % ${#SUBNET_IDS[@]} ))]}"
  instance_id="$(
    aws ec2 run-instances \
      --region "$REGION" \
      --image-id "$AMI_ID" \
      --instance-type "$INSTANCE_TYPE" \
      --key-name "$KEY_NAME" \
      --security-group-ids "$SG_ID" \
      --subnet-id "$subnet" \
      --associate-public-ip-address \
      --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=${VOLUME_SIZE_GB},VolumeType=gp3,DeleteOnTermination=true}" \
      --metadata-options 'HttpTokens=required,HttpEndpoint=enabled' \
      --user-data "file://${OUTPUT_DIR}/user-data.sh" \
      --tag-specifications \
        "ResourceType=instance,Tags=[{Key=Name,Value=raasa-k3s-${role}},{Key=Project,Value=${PROJECT_TAG}},{Key=ManagedBy,Value=${MANAGED_TAG}},{Key=ClusterRole,Value=${role}}]" \
        "ResourceType=volume,Tags=[{Key=Name,Value=raasa-k3s-${role}-root},{Key=Project,Value=${PROJECT_TAG}},{Key=ManagedBy,Value=${MANAGED_TAG}},{Key=ClusterRole,Value=${role}}]" \
      --query 'Instances[0].InstanceId' \
      --output text
  )"
  INSTANCE_ROWS+=("${role} ${instance_id} ${subnet}")
done

INSTANCE_IDS=()
for row in "${INSTANCE_ROWS[@]}"; do
  INSTANCE_IDS+=("$(awk '{print $2}' <<<"$row")")
done

aws ec2 wait instance-running --region "$REGION" --instance-ids "${INSTANCE_IDS[@]}"

{
  echo -e "Role\tInstanceId\tSubnetId\tPrivateIp\tPublicIp\tAvailabilityZone"
  for row in "${INSTANCE_ROWS[@]}"; do
    role="$(awk '{print $1}' <<<"$row")"
    instance_id="$(awk '{print $2}' <<<"$row")"
    subnet_id="$(awk '{print $3}' <<<"$row")"
    details="$(
      aws ec2 describe-instances \
        --region "$REGION" \
        --instance-ids "$instance_id" \
        --query 'Reservations[0].Instances[0].[PrivateIpAddress,PublicIpAddress,Placement.AvailabilityZone]' \
        --output text
    )"
    private_ip="$(awk '{print $1}' <<<"$details")"
    public_ip="$(awk '{print $2}' <<<"$details")"
    az="$(awk '{print $3}' <<<"$details")"
    echo -e "${role}\t${instance_id}\t${subnet_id}\t${private_ip}\t${public_ip}\t${az}"
  done
} > "${OUTPUT_DIR}/cluster_instances.tsv"

cat > "${OUTPUT_DIR}/summary.md" <<EOF
# RAASA Free Tier Multi-Node K3s Launch

- Region: \`${REGION}\`
- Instance type: \`${INSTANCE_TYPE}\`
- Key name: \`${KEY_NAME}\`
- Local CloudShell key path: \`${KEY_PATH}\`
- SSH CIDR allowed: \`${SSH_CIDR}\`
- Security group: \`${SG_ID}\`
- Root EBS per node: \`${VOLUME_SIZE_GB} GiB gp3\`, delete on termination

## Nodes

\`\`\`text
$(cat "${OUTPUT_DIR}/cluster_instances.tsv")
\`\`\`

## Next Windows Step

Download \`${KEY_PATH}\` from CloudShell to:

\`\`\`powershell
C:\\Users\\Admin\\.ssh\\${KEY_NAME}.pem
\`\`\`

Then use the control-plane public IP from \`cluster_instances.tsv\` with:

\`\`\`powershell
\$env:RAASA_AWS_KEY_PATH = "C:\\Users\\Admin\\.ssh\\${KEY_NAME}.pem"
\$ControlPlaneHost = "<control-plane-public-ip>"
\$WorkerHosts = @("<worker-a-public-ip>", "<worker-b-public-ip>")
\`\`\`

## Cleanup

From CloudShell:

\`\`\`bash
export RAASA_CONFIRM_DESTROY=1
export RAASA_KEY_NAME=${KEY_NAME}
bash raasa/scripts/destroy_freetier_raasa_k3s_cluster.sh
\`\`\`
EOF

aws ec2 describe-instances --region "$REGION" --instance-ids "${INSTANCE_IDS[@]}" --output json > "${OUTPUT_DIR}/instances.json"

info "Launch complete."
info "Cluster inventory: ${OUTPUT_DIR}/cluster_instances.tsv"
info "Private key saved in CloudShell: ${KEY_PATH}"
info "Summary: ${OUTPUT_DIR}/summary.md"
