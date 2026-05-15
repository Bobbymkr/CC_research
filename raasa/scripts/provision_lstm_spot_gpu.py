from __future__ import annotations

import argparse
import shlex
import textwrap
from dataclasses import dataclass
from typing import Any

import boto3


DEFAULT_DLAMI_SSM_PARAMETER = (
    "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-22.04/latest/ami-id"
)


@dataclass(slots=True)
class SpotGpuConfig:
    region: str
    profile: str | None
    instance_type: str
    market_type: str
    max_hours: float
    max_budget_usd: float
    ami_id: str
    key_name: str | None
    subnet_id: str | None
    security_group_ids: list[str]
    instance_profile_name: str | None
    repo_url: str
    branch: str
    source_archive_s3_uri: str | None
    log_dir: str
    output_path: str
    epochs: int
    sequence_length: int
    s3_output_uri: str | None
    max_hourly_price: float | None
    dry_run: bool


def latest_spot_price(ec2: Any, instance_type: str, region: str) -> float:
    response = ec2.describe_spot_price_history(
        InstanceTypes=[instance_type],
        ProductDescriptions=["Linux/UNIX"],
        MaxResults=1,
    )
    history = response.get("SpotPriceHistory", [])
    if not history:
        response = ec2.describe_spot_price_history(
            InstanceTypes=[instance_type],
            ProductDescriptions=["Linux/UNIX"],
            MaxResults=1,
        )
        history = response.get("SpotPriceHistory", [])
    if not history:
        raise RuntimeError(f"No Spot price history returned for {instance_type}")
    return float(history[0]["SpotPrice"])


def resolve_ami_id(session: boto3.Session, configured_ami_id: str, ssm_parameter: str) -> str:
    if configured_ami_id:
        return configured_ami_id
    ssm = session.client("ssm")
    response = ssm.get_parameter(Name=ssm_parameter)
    return str(response["Parameter"]["Value"])


def build_user_data(config: SpotGpuConfig, shutdown_minutes: int) -> str:
    if config.source_archive_s3_uri:
        source_ref = shlex.quote(config.source_archive_s3_uri)
        fetch_command = (
            f"aws s3 cp {source_ref} /opt/raasa/source.zip"
            if config.source_archive_s3_uri.startswith("s3://")
            else f"curl -fsSL {source_ref} -o /opt/raasa/source.zip"
        )
        source_commands = textwrap.dedent(
            f"""
            mkdir -p /opt/raasa/repo
            {fetch_command}
            unzip -q /opt/raasa/source.zip -d /opt/raasa/repo
            cd /opt/raasa/repo
            """
        ).strip()
    else:
        source_commands = textwrap.dedent(
            f"""
            git clone {config.repo_url} repo
            cd repo
            git checkout {config.branch}
            """
        ).strip()

    upload_commands = ""
    log_upload_command = "true"
    if config.s3_output_uri:
        metadata_path = f"{config.output_path}.metadata.json"
        s3_output = config.s3_output_uri.rstrip("/")
        upload_commands = textwrap.dedent(
            f"""
            aws s3 cp {config.output_path} {s3_output}/temporal_lstm.keras || true
            aws s3 cp {metadata_path} {s3_output}/temporal_lstm.keras.metadata.json || true
            """
        ).strip()
        log_upload_command = (
            f"aws s3 cp /var/log/raasa-lstm-user-data.log {s3_output}/runs/${{INSTANCE_ID}}-user-data.log || true; "
            f"aws s3 cp /var/log/raasa-lstm-user-data.log {s3_output}/latest-user-data.log || true"
        )

    progress_checkpoint = f"checkpoint() {{ echo \"RAASA_CHECKPOINT: $1\"; {log_upload_command}; }}"
    return textwrap.dedent(
        f"""\
        #!/bin/bash
        set -euxo pipefail
        exec > >(tee -a /var/log/raasa-lstm-user-data.log) 2>&1
        TOKEN="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 21600' || true)"
        INSTANCE_ID="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id || hostname)"
        {progress_checkpoint}
        trap '{log_upload_command}' EXIT
        shutdown -h +{shutdown_minutes}
        checkpoint bootstrapped
        export DEBIAN_FRONTEND=noninteractive
        if command -v apt-get >/dev/null 2>&1; then
          checkpoint apt-get-detected
          apt-get update
          timeout 600 apt-get install -y git python3-pip python3-venv unzip awscli curl
        elif command -v dnf >/dev/null 2>&1; then
          checkpoint dnf-detected
          timeout 600 dnf install -y git python3-pip unzip awscli curl
        elif command -v yum >/dev/null 2>&1; then
          checkpoint yum-detected
          timeout 600 yum install -y git python3-pip unzip awscli curl
        else
          echo "No supported package manager found: need apt-get, dnf, or yum" >&2
          exit 1
        fi
        checkpoint packages-installed
        mkdir -p /opt/raasa
        cd /opt/raasa
        {source_commands}
        checkpoint source-ready
        python3 -m venv .venv
        . .venv/bin/activate
        python -m pip install --upgrade pip
        timeout 1800 python -m pip install --progress-bar off --only-binary=:all: numpy==2.2.6 scikit-learn==1.6.1 joblib==1.4.2 tensorflow==2.20.0
        checkpoint python-deps-installed
        python -m raasa.ml.temporal_lstm \\
          --log-dir {config.log_dir} \\
          --output-path {config.output_path} \\
          --sequence-length {config.sequence_length} \\
          --epochs {config.epochs}
        checkpoint training-complete
        {upload_commands}
        checkpoint artifacts-uploaded
        shutdown -h now
        """
    ).lstrip()


def build_run_instances_request(config: SpotGpuConfig) -> dict[str, Any]:
    shutdown_minutes = max(1, int(config.max_hours * 60))
    request: dict[str, Any] = {
        "ImageId": config.ami_id,
        "InstanceType": config.instance_type,
        "MinCount": 1,
        "MaxCount": 1,
        "UserData": build_user_data(config, shutdown_minutes),
        "InstanceInitiatedShutdownBehavior": "terminate",
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Project", "Value": "RAASA"},
                    {"Key": "Purpose", "Value": "temporal-lstm-training"},
                    {"Key": "CostCeilingUSD", "Value": f"{config.max_budget_usd:.2f}"},
                ],
            }
        ],
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": 80,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                },
            }
        ],
        "DryRun": config.dry_run,
    }
    if config.market_type == "spot":
        request["InstanceMarketOptions"] = {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        }
        if config.max_hourly_price is not None:
            request["InstanceMarketOptions"]["SpotOptions"]["MaxPrice"] = f"{config.max_hourly_price:.4f}"
    if config.key_name:
        request["KeyName"] = config.key_name
    if config.subnet_id:
        request["SubnetId"] = config.subnet_id
    if config.security_group_ids:
        request["SecurityGroupIds"] = config.security_group_ids
    if config.instance_profile_name:
        request["IamInstanceProfile"] = {"Name": config.instance_profile_name}
    return request


def run(config: SpotGpuConfig) -> dict[str, Any]:
    session = boto3.Session(profile_name=config.profile, region_name=config.region)
    ec2 = session.client("ec2")
    if config.market_type == "spot":
        observed_hourly_price = config.max_hourly_price or latest_spot_price(ec2, config.instance_type, config.region)
    else:
        if config.max_hourly_price is None:
            raise RuntimeError("Refusing on-demand launch without --max-hourly-price budget guard")
        observed_hourly_price = config.max_hourly_price
    estimated_ceiling = observed_hourly_price * config.max_hours
    if estimated_ceiling > config.max_budget_usd:
        raise RuntimeError(
            f"Refusing launch: estimated Spot ceiling ${estimated_ceiling:.2f} exceeds "
            f"budget ${config.max_budget_usd:.2f}"
        )
    request = build_run_instances_request(config)
    response = ec2.run_instances(**request)
    return response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provision a guarded EC2 Spot GPU trainer for RAASA LSTM.")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--instance-type", default="g5.xlarge")
    parser.add_argument("--market-type", choices=["spot", "on-demand"], default="spot")
    parser.add_argument("--max-hours", type=float, default=4.0)
    parser.add_argument("--max-budget-usd", type=float, default=40.0)
    parser.add_argument("--ami-id", default="")
    parser.add_argument("--dlami-ssm-parameter", default=DEFAULT_DLAMI_SSM_PARAMETER)
    parser.add_argument("--key-name", default=None)
    parser.add_argument("--subnet-id", default=None)
    parser.add_argument("--security-group-id", action="append", default=[])
    parser.add_argument("--instance-profile-name", default=None)
    parser.add_argument("--repo-url", default="")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--source-archive-s3-uri", default=None)
    parser.add_argument("--log-dir", default="raasa/logs")
    parser.add_argument("--output-path", default="raasa/models/temporal_lstm.keras")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--sequence-length", type=int, default=5)
    parser.add_argument("--s3-output-uri", default=None)
    parser.add_argument("--max-hourly-price", type=float, default=None)
    parser.add_argument("--max-spot-price", dest="max_hourly_price", type=float, default=None)
    parser.add_argument("--execute", action="store_true", help="Launch for real. Omit for EC2 DryRun.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    ami_id = resolve_ami_id(session, args.ami_id, args.dlami_ssm_parameter)
    config = SpotGpuConfig(
        region=args.region,
        profile=args.profile,
        instance_type=args.instance_type,
        market_type=args.market_type,
        max_hours=args.max_hours,
        max_budget_usd=args.max_budget_usd,
        ami_id=ami_id,
        key_name=args.key_name,
        subnet_id=args.subnet_id,
        security_group_ids=args.security_group_id,
        instance_profile_name=args.instance_profile_name,
        repo_url=args.repo_url,
        branch=args.branch,
        source_archive_s3_uri=args.source_archive_s3_uri,
        log_dir=args.log_dir,
        output_path=args.output_path,
        epochs=args.epochs,
        sequence_length=args.sequence_length,
        s3_output_uri=args.s3_output_uri,
        max_hourly_price=args.max_hourly_price,
        dry_run=not args.execute,
    )
    response = run(config)
    print(json_safe(response))


def json_safe(response: dict[str, Any]) -> str:
    import json

    def default(value: Any) -> str:
        return str(value)

    return json.dumps(response, indent=2, default=default)


if __name__ == "__main__":
    main()
