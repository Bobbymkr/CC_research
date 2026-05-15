# AWS Validation Playbook

This playbook is the paper-first AWS path. It assumes a single-node EC2/K3s
host unless a multi-node cluster is explicitly named in the evidence bundle.

## Key Handling

Keep SSH keys outside the repository.

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-paper-key.pem"
python -m raasa.scripts.secret_scan --root .
```

All AWS PowerShell scripts accept `-KeyPath`; if it is omitted, they read
`RAASA_AWS_KEY_PATH`. Do not copy PEM files into the project tree.

## Required Paper Evidence

1. Local hygiene and tests:

```powershell
python -m raasa.scripts.secret_scan --root .
python -m pytest tests -q
```

2. Live AWS sanity capture:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/collect_aws_live_validation.ps1 `
    -TargetHost <AWS_IPV4>
```

3. Free-tier closed-loop soak:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_closed_loop_soak_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -Cycles 5
```

4. Five-run adversarial matrix:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_repeated_adversarial_matrix_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -Runs 5 `
    -DurationSeconds 60 `
    -QuiesceBackgroundWorkloads
```

This matrix includes benign control, syscall storm, process fanout, network
burst, and agent dependency/exfiltration workloads. A passing bundle must retain
all per-run summaries, audit rows, pod snapshots, and capacity snapshots.

5. Failure and stress evidence:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_failure_injection_aws.ps1 `
    -TargetHost <AWS_IPV4> `
    -TelemetryWindowSeconds 30 `
    -RecoverySeconds 15

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_metrics_api_stress_probe.ps1 `
    -TargetHost <AWS_IPV4> `
    -DurationSeconds 45 `
    -WorkerCount 8
```

6. L3 pod-specific containment:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_phase1d_resolution_validation.ps1 `
    -TargetHost <AWS_IPV4>
```

## Reviewer Acceptance Bar

- Every major claim maps to one row in
  [docs/evidence_index.md](/C:/Users/Admin/OneDrive/Desktop/CC/CC_research/docs/evidence_index.md).
- Failed runs are preserved with diagnosis instead of deleted.
- SSH timeouts, ambiguous host identity, or unknown AWS resources stop the
  campaign until the operator re-establishes host health and billing state.
- `L3` is described as hard containment for tested pod/network paths, not a
  general container sandbox.
- The final paper states the current scope: single-node K3s unless new
  multi-node evidence is collected.

## Fresh Free-Tier Instance Recovery Path

Use this path when the old EC2 private key is lost and `m7i-flex.large` is
confirmed as covered by the account's Free Tier credits.

From AWS CloudShell, first upload or clone this repository so
`raasa/scripts/create_freetier_raasa_ec2.sh` is present, then run:

```bash
export AWS_REGION=us-east-1
export RAASA_CONFIRM_M7I_FREE_TIER=1
export RAASA_SSH_CIDR="<your-workstation-public-ip>/32"
export RAASA_KEY_NAME="raasa-key-2"
bash raasa/scripts/create_freetier_raasa_ec2.sh
```

Download the generated PEM from the CloudShell output directory to:

```powershell
C:\Users\Admin\.ssh\raasa-key-2.pem
```

Then from this Windows workspace:

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-key-2.pem"
$TargetHost = "<new-public-ip>"

powershell -ExecutionPolicy Bypass -File raasa/scripts/bootstrap_freetier_raasa_instance.ps1 `
    -TargetHost $TargetHost
```

Cleanup from CloudShell:

```bash
export RAASA_CONFIRM_DESTROY=1
export RAASA_INSTANCE_ID="<instance-id>"
bash raasa/scripts/destroy_freetier_raasa_ec2.sh
```

This recovery path must still obey the zero-overage guardrails: one EC2 node,
no EKS, no NAT Gateway, no Load Balancer, no Elastic IP, and root EBS no larger
than 30 GiB.

## Fresh-Account Credits-Only Expansion Path

Use this path when a new AWS Free-plan account is available and the goal is to
advance from a clean single-node replay to a bounded 3-node K3s validation
without spending beyond AWS-issued credits.

### CloudShell preflight

Keep the account standalone, verify the current plan and remaining credits, and
stop immediately if inventory is not clean:

```bash
export AWS_REGION=us-east-1
export AWS_PAGER=""

aws freetier get-account-plan-state --region "$AWS_REGION" --output table
aws ec2 describe-instances --region "$AWS_REGION" --output table
aws ec2 describe-volumes --region "$AWS_REGION" --output table
aws ec2 describe-addresses --region "$AWS_REGION" --output table
aws ec2 describe-nat-gateways --region "$AWS_REGION" --output table
aws elbv2 describe-load-balancers --region "$AWS_REGION" --output table
aws eks list-clusters --region "$AWS_REGION" --output table
```

### Single-node clean-account replay

Create one host from CloudShell:

```bash
export AWS_REGION=us-east-1
export RAASA_CONFIRM_M7I_FREE_TIER=1
export RAASA_SSH_CIDR="<your-workstation-public-ip>/32"
export RAASA_KEY_NAME="raasa-fresh-single"
bash raasa/scripts/create_freetier_raasa_ec2.sh
```

Then from this Windows workspace:

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-fresh-single.pem"
$TargetHost = "<new-public-ip>"

powershell -ExecutionPolicy Bypass -File raasa/scripts/bootstrap_freetier_raasa_instance.ps1 `
    -TargetHost $TargetHost

powershell -ExecutionPolicy Bypass -File raasa/scripts/collect_aws_live_validation.ps1 `
    -TargetHost $TargetHost

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_closed_loop_soak_aws.ps1 `
    -TargetHost $TargetHost `
    -Cycles 2
```

Destroy the replay host before multi-node work:

```bash
export RAASA_CONFIRM_DESTROY=1
export RAASA_INSTANCE_ID="<single-node-instance-id>"
bash raasa/scripts/destroy_freetier_raasa_ec2.sh
```

### Bounded 3-node K3s validation

Create the cluster from CloudShell:

```bash
export AWS_REGION=us-east-1
export RAASA_CONFIRM_MULTINODE=1
export RAASA_SSH_CIDR="<your-workstation-public-ip>/32"
export RAASA_KEY_NAME="raasa-fresh-k3s"
bash raasa/scripts/create_freetier_raasa_k3s_cluster.sh
```

Important AWS note: the shared security group must allow:

- `22/tcp` from the workstation `/32`
- self-referencing `All traffic` ingress so the K3s nodes can join each other

Bootstrap and validate from this Windows workspace:

```powershell
$env:RAASA_AWS_KEY_PATH = "C:\Users\Admin\.ssh\raasa-fresh-k3s.pem"
$TargetHost = "<control-plane-public-ip>"

powershell -ExecutionPolicy Bypass -File raasa/scripts/bootstrap_freetier_raasa_multinode.ps1 `
    -TargetHost $TargetHost

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_closed_loop_soak_aws.ps1 `
    -TargetHost $TargetHost `
    -Cycles 3

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_repeated_adversarial_matrix_aws.ps1 `
    -TargetHost $TargetHost `
    -Runs 2 `
    -DurationSeconds 45 `
    -QuiesceBackgroundWorkloads

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_failure_injection_aws.ps1 `
    -TargetHost $TargetHost `
    -TelemetryWindowSeconds 30 `
    -RecoverySeconds 15

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_metrics_api_stress_probe.ps1 `
    -TargetHost $TargetHost `
    -DurationSeconds 30 `
    -WorkerCount 6

powershell -ExecutionPolicy Bypass -File raasa/scripts/run_multinode_reschedule_validation_aws.ps1 `
    -TargetHost $TargetHost
```

Destroy the 3-node cluster from CloudShell after artifact capture:

```bash
export RAASA_CONFIRM_DESTROY=1
export RAASA_KEY_NAME="raasa-fresh-k3s"
# optionally: export RAASA_DELETE_KEY_PAIR=1
bash raasa/scripts/destroy_freetier_raasa_k3s_cluster.sh
```

### Optional EKS smoke gate

Only attempt EKS if:

- remaining AWS-issued credits are still comfortably healthy
- the account inventory is clean after K3s teardown
- the plan-access question is resolved without violating the zero-cash rule

If that gate passes, use:

```bash
bash raasa/scripts/create_credit_gated_eks_cluster.sh
```

then the Windows-side wrappers:

```powershell
powershell -ExecutionPolicy Bypass -File raasa/scripts/build_push_raasa_images_to_ecr.ps1
powershell -ExecutionPolicy Bypass -File raasa/scripts/collect_eks_live_validation.ps1
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_closed_loop_smoke_eks.ps1 -Cycles 2
powershell -ExecutionPolicy Bypass -File raasa/scripts/run_adversarial_smoke_eks.ps1 -Runs 1 -DurationSeconds 45
```

and finally:

```bash
bash raasa/scripts/destroy_credit_gated_eks_cluster.sh
```

Do not carry EKS forward if the credits gate weakens, if CloudShell inventory
is ambiguous, or if cleanup cannot be verified the same day.
