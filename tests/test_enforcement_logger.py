from datetime import datetime, timezone
import hashlib
import hmac
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from raasa.core.audit_integrity import KmsAuditSigner
from raasa.core.enforcement import ActionEnforcer
from raasa.core.logger import AuditLogger
from raasa.core.models import (
    Assessment,
    ContainerTelemetry,
    FeatureVector,
    PolicyDecision,
    Tier,
)


class FakeKmsClient:
    def __init__(self, secret: bytes = b"raasa-test-secret") -> None:
        self.secret = secret

    def generate_mac(self, KeyId, Message, MacAlgorithm):
        return {
            "KeyId": f"arn:aws:kms:us-east-1:123456789012:key/{KeyId}",
            "MacAlgorithm": MacAlgorithm,
            "Mac": hmac.new(self.secret, Message, hashlib.sha256).digest(),
        }

    def verify_mac(self, KeyId, Message, MacAlgorithm, Mac):
        expected = hmac.new(self.secret, Message, hashlib.sha256).digest()
        return {"MacValid": hmac.compare_digest(expected, Mac)}


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


class ActionEnforcerTests(unittest.TestCase):
    def test_applies_cpu_limit_once_per_tier(self) -> None:
        runner = RecordingRunner()
        enforcer = ActionEnforcer(runner=runner)
        decision = PolicyDecision(
            container_id="c1",
            timestamp=datetime.now(timezone.utc),
            previous_tier=Tier.L1,
            proposed_tier=Tier.L2,
            applied_tier=Tier.L2,
            reason="test escalation",
            action_required=True,
        )

        enforcer.apply([decision])
        enforcer.apply([decision])

        self.assertEqual(len(runner.commands), 1)
        self.assertEqual(runner.commands[0][:4], ["docker", "update", "--cpus", "0.5"])


class AuditLoggerTests(unittest.TestCase):
    def test_writes_jsonl_records(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir_name:
            tempdir = Path(temp_dir_name)
            logger = AuditLogger(tempdir, run_label="demo_run")
            now = datetime.now(timezone.utc)
            logger.log_tick(
                telemetry_batch=[
                    ContainerTelemetry(
                        container_id="c1",
                        timestamp=now,
                        cpu_percent=12.0,
                        memory_percent=15.0,
                        process_count=3,
                        metadata={"status": "running"},
                    )
                ],
                features=[
                    FeatureVector(
                        container_id="c1",
                        timestamp=now,
                        cpu_signal=0.12,
                        memory_signal=0.15,
                        process_signal=0.15,
                    )
                ],
                assessments=[
                    Assessment(
                        container_id="c1",
                        timestamp=now,
                        risk_score=0.13,
                        confidence_score=0.70,
                        reasons=["stable signals"],
                        attributions=[
                            {
                                "feature": "cpu",
                                "value": 0.12,
                                "weight": 0.40,
                                "shap_value": 0.048,
                            }
                        ],
                    )
                ],
                decisions=[
                    PolicyDecision(
                        container_id="c1",
                        timestamp=now,
                        previous_tier=Tier.L1,
                        proposed_tier=Tier.L1,
                        applied_tier=Tier.L1,
                        reason="hold",
                        action_required=False,
                    )
                ],
            )

            contents = Path(logger.output_path).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(contents), 1)
            self.assertEqual(Path(logger.output_path).name, "run_demo_run.jsonl")
            payload = json.loads(contents[0])
            self.assertEqual(payload["container_id"], "c1")
            self.assertEqual(payload["risk"], 0.13)
            self.assertEqual(payload["containment_profile"], "observe_only")
            self.assertEqual(payload["metadata"]["status"], "running")
            self.assertEqual(payload["risk_attributions"][0]["feature"], "cpu")
            self.assertAlmostEqual(payload["risk_attributions"][0]["shap_value"], 0.048)

    def test_writes_kms_signed_jsonl_records_when_enabled(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir_name:
            tempdir = Path(temp_dir_name)
            signer = KmsAuditSigner("alias/raasa-audit-hmac", client=FakeKmsClient())
            logger = AuditLogger(tempdir, run_label="signed_run", audit_signer=signer)
            now = datetime.now(timezone.utc)

            logger.log_tick(
                telemetry_batch=[],
                features=[],
                assessments=[],
                decisions=[
                    PolicyDecision(
                        container_id="c1",
                        timestamp=now,
                        previous_tier=Tier.L1,
                        proposed_tier=Tier.L1,
                        applied_tier=Tier.L1,
                        reason="hold",
                        action_required=False,
                    )
                ],
            )

            payload = json.loads(Path(logger.output_path).read_text(encoding="utf-8"))

        self.assertIn("audit_integrity", payload)
        self.assertTrue(signer.verify_record(payload, expected_key_id="alias/raasa-audit-hmac"))


if __name__ == "__main__":
    unittest.main()
