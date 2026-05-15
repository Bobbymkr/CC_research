from __future__ import annotations

import base64
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from raasa.core.audit_integrity import (
    AUDIT_INTEGRITY_FIELD,
    KmsAuditSigner,
    payload_digest_hex,
    verify_audit_log,
)


class FakeKmsClient:
    def __init__(self, secret: bytes = b"raasa-test-secret") -> None:
        self.secret = secret
        self.generated_messages: list[bytes] = []
        self.verified_messages: list[bytes] = []

    def generate_mac(self, KeyId, Message, MacAlgorithm):
        self.generated_messages.append(Message)
        return {
            "KeyId": f"arn:aws:kms:us-east-1:123456789012:key/{KeyId}",
            "MacAlgorithm": MacAlgorithm,
            "Mac": hmac.new(self.secret, Message, hashlib.sha256).digest(),
        }

    def verify_mac(self, KeyId, Message, MacAlgorithm, Mac):
        self.verified_messages.append(Message)
        expected = hmac.new(self.secret, Message, hashlib.sha256).digest()
        return {"MacValid": hmac.compare_digest(expected, Mac)}


class AuditIntegrityTests(unittest.TestCase):
    def test_signs_and_verifies_record_without_mutating_source(self) -> None:
        client = FakeKmsClient()
        signer = KmsAuditSigner("alias/raasa-audit-hmac", region_name="us-east-1", client=client)
        record = {"container_id": "c1", "risk": 0.42, "metadata": {"image": "nginx"}}

        signed = signer.sign_record(record)

        self.assertNotIn(AUDIT_INTEGRITY_FIELD, record)
        self.assertIn(AUDIT_INTEGRITY_FIELD, signed)
        integrity = signed[AUDIT_INTEGRITY_FIELD]
        self.assertEqual(integrity["version"], "kms-hmac-v1")
        self.assertEqual(integrity["kms_key_id"], "alias/raasa-audit-hmac")
        self.assertEqual(integrity["mac_algorithm"], "HMAC_SHA_256")
        self.assertEqual(integrity["payload_sha256"], payload_digest_hex(record))
        self.assertGreater(len(base64.b64decode(integrity["mac"])), 0)
        self.assertTrue(signer.verify_record(signed, expected_key_id="alias/raasa-audit-hmac"))

    def test_tampered_record_fails_verification(self) -> None:
        signer = KmsAuditSigner("alias/raasa-audit-hmac", client=FakeKmsClient())
        signed = signer.sign_record({"container_id": "c1", "risk": 0.42})

        tampered = json.loads(json.dumps(signed))
        tampered["risk"] = 0.01

        self.assertFalse(signer.verify_record(tampered, expected_key_id="alias/raasa-audit-hmac"))

    def test_unexpected_key_fails_verification(self) -> None:
        signer = KmsAuditSigner("alias/raasa-audit-hmac", client=FakeKmsClient())
        signed = signer.sign_record({"container_id": "c1", "risk": 0.42})

        self.assertFalse(signer.verify_record(signed, expected_key_id="alias/other-key"))

    def test_verify_audit_log_reports_line_results(self) -> None:
        signer = KmsAuditSigner("alias/raasa-audit-hmac", client=FakeKmsClient())
        good = signer.sign_record({"container_id": "c1", "risk": 0.42})
        bad = json.loads(json.dumps(good))
        bad["container_id"] = "c2"

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir_name:
            path = Path(temp_dir_name) / "audit.jsonl"
            path.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n", encoding="utf-8")

            results = verify_audit_log(path, signer, expected_key_id="alias/raasa-audit-hmac")

        self.assertEqual([result.ok for result in results], [True, False])
        self.assertEqual(results[0].container_id, "c1")
        self.assertEqual(results[1].container_id, "c2")


if __name__ == "__main__":
    unittest.main()
