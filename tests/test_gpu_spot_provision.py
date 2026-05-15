from __future__ import annotations

import unittest
from unittest.mock import patch

from raasa.scripts.provision_lstm_spot_gpu import (
    SpotGpuConfig,
    build_run_instances_request,
    run,
)


def _config(**overrides) -> SpotGpuConfig:
    values = {
        "region": "us-east-1",
        "profile": None,
        "instance_type": "g5.xlarge",
        "market_type": "spot",
        "max_hours": 4.0,
        "max_budget_usd": 40.0,
        "ami_id": "ami-123",
        "key_name": None,
        "subnet_id": "subnet-123",
        "security_group_ids": ["sg-123"],
        "instance_profile_name": "raasa-gpu-trainer",
        "repo_url": "https://github.com/example/raasa.git",
        "branch": "codex/test",
        "source_archive_s3_uri": None,
        "log_dir": "raasa/logs",
        "output_path": "raasa/models/temporal_lstm.keras",
        "epochs": 2,
        "sequence_length": 5,
        "s3_output_uri": "s3://raasa-artifacts/lstm",
        "max_hourly_price": 1.0,
        "dry_run": True,
    }
    values.update(overrides)
    return SpotGpuConfig(**values)


class SpotGpuProvisionTests(unittest.TestCase):
    def test_builds_guarded_spot_run_instances_request(self) -> None:
        request = build_run_instances_request(_config())

        self.assertTrue(request["UserData"].startswith("#!/bin/bash\n"))
        self.assertEqual(request["InstanceType"], "g5.xlarge")
        self.assertTrue(request["DryRun"])
        self.assertEqual(request["InstanceMarketOptions"]["MarketType"], "spot")
        self.assertEqual(request["InstanceMarketOptions"]["SpotOptions"]["MaxPrice"], "1.0000")
        self.assertEqual(request["InstanceMarketOptions"]["SpotOptions"]["InstanceInterruptionBehavior"], "terminate")
        self.assertEqual(request["InstanceInitiatedShutdownBehavior"], "terminate")
        self.assertIn("shutdown -h +240", request["UserData"])
        self.assertIn("exec > >(tee -a /var/log/raasa-lstm-user-data.log) 2>&1", request["UserData"])
        self.assertIn("X-aws-ec2-metadata-token-ttl-seconds", request["UserData"])
        self.assertIn('INSTANCE_ID="$(curl -fsS -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id || hostname)"', request["UserData"])
        self.assertIn("runs/${INSTANCE_ID}-user-data.log", request["UserData"])
        self.assertIn("latest-user-data.log", request["UserData"])
        self.assertIn("checkpoint bootstrapped", request["UserData"])
        self.assertIn("checkpoint packages-installed", request["UserData"])
        self.assertIn("checkpoint python-deps-installed", request["UserData"])
        self.assertIn("checkpoint artifacts-uploaded", request["UserData"])
        self.assertIn("command -v apt-get", request["UserData"])
        self.assertIn("command -v dnf", request["UserData"])
        self.assertIn("command -v yum", request["UserData"])
        self.assertIn(
            "python -m pip install --progress-bar off --only-binary=:all: numpy==2.2.6 scikit-learn==1.6.1 joblib==1.4.2 tensorflow==2.20.0",
            request["UserData"],
        )
        self.assertIn("python -m raasa.ml.temporal_lstm", request["UserData"])
        self.assertEqual(request["IamInstanceProfile"], {"Name": "raasa-gpu-trainer"})

    def test_source_archive_skips_git_clone(self) -> None:
        request = build_run_instances_request(
            _config(repo_url="", source_archive_s3_uri="s3://raasa-artifacts/lstm/source.zip")
        )

        self.assertIn("aws s3 cp s3://raasa-artifacts/lstm/source.zip /opt/raasa/source.zip", request["UserData"])
        self.assertIn("unzip -q /opt/raasa/source.zip -d /opt/raasa/repo", request["UserData"])
        self.assertNotIn("git clone", request["UserData"])

    def test_source_archive_url_uses_curl(self) -> None:
        request = build_run_instances_request(
            _config(repo_url="", source_archive_s3_uri="https://example.com/source.zip?X-Amz-Signature=abc&x=1")
        )

        self.assertIn(
            "curl -fsSL 'https://example.com/source.zip?X-Amz-Signature=abc&x=1' -o /opt/raasa/source.zip",
            request["UserData"],
        )
        self.assertIn("curl", request["UserData"])

    def test_on_demand_request_omits_spot_market_options(self) -> None:
        request = build_run_instances_request(_config(market_type="on-demand"))

        self.assertNotIn("InstanceMarketOptions", request)
        self.assertEqual(request["InstanceInitiatedShutdownBehavior"], "terminate")

    def test_refuses_launch_when_price_ceiling_exceeds_budget(self) -> None:
        config = _config(max_hourly_price=20.0, max_hours=4.0, max_budget_usd=40.0)

        with self.assertRaisesRegex(RuntimeError, "Refusing launch"):
            run(config)

    def test_run_uses_boto3_when_budget_allows(self) -> None:
        class FakeEc2:
            def __init__(self) -> None:
                self.request = None

            def run_instances(self, **request):
                self.request = request
                return {"Instances": [{"InstanceId": "i-123"}]}

        class FakeSession:
            def __init__(self, profile_name, region_name):
                self.profile_name = profile_name
                self.region_name = region_name
                self.ec2 = FakeEc2()

            def client(self, name):
                if name != "ec2":
                    raise AssertionError(name)
                return self.ec2

        fake_session = FakeSession(None, "us-east-1")

        with patch("raasa.scripts.provision_lstm_spot_gpu.boto3.Session", return_value=fake_session):
            response = run(_config(max_hourly_price=1.0))

        self.assertEqual(response["Instances"][0]["InstanceId"], "i-123")
        self.assertEqual(fake_session.ec2.request["SubnetId"], "subnet-123")


if __name__ == "__main__":
    unittest.main()
