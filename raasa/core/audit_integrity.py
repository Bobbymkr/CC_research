from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


AUDIT_INTEGRITY_FIELD = "audit_integrity"
AUDIT_INTEGRITY_VERSION = "kms-hmac-v1"
MAC_MESSAGE_PREFIX = b"RAASA-AUDIT-V1\n"
DEFAULT_MAC_ALGORITHM = "HMAC_SHA_256"


@dataclass(slots=True)
class AuditVerificationResult:
    line_number: int
    ok: bool
    container_id: str
    reason: str = ""


class KmsAuditSigner:
    """KMS-backed HMAC signer/verifier for RAASA audit records."""

    def __init__(
        self,
        key_id: str,
        *,
        region_name: str | None = None,
        profile_name: str | None = None,
        mac_algorithm: str = DEFAULT_MAC_ALGORITHM,
        client: Any | None = None,
    ) -> None:
        if not key_id:
            raise ValueError("KMS audit signing requires a key id or alias")
        self.key_id = key_id
        self.region_name = region_name
        self.profile_name = profile_name
        self.mac_algorithm = mac_algorithm
        self.client = client or self._build_client()

    def sign_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        signed = copy.deepcopy(dict(record))
        signed.pop(AUDIT_INTEGRITY_FIELD, None)
        payload_sha256 = payload_digest_hex(signed)
        response = self.client.generate_mac(
            KeyId=self.key_id,
            Message=build_mac_message(payload_sha256),
            MacAlgorithm=self.mac_algorithm,
        )
        signed[AUDIT_INTEGRITY_FIELD] = {
            "version": AUDIT_INTEGRITY_VERSION,
            "payload_sha256": payload_sha256,
            "kms_key_id": self.key_id,
            "kms_resolved_key_id": str(response.get("KeyId", self.key_id)),
            "mac_algorithm": str(response.get("MacAlgorithm", self.mac_algorithm)),
            "mac": base64.b64encode(response["Mac"]).decode("ascii"),
        }
        return signed

    def verify_record(self, record: Mapping[str, Any], *, expected_key_id: str | None = None) -> bool:
        integrity = record.get(AUDIT_INTEGRITY_FIELD)
        if not isinstance(integrity, Mapping):
            return False
        if integrity.get("version") != AUDIT_INTEGRITY_VERSION:
            return False

        payload = copy.deepcopy(dict(record))
        payload.pop(AUDIT_INTEGRITY_FIELD, None)
        payload_sha256 = payload_digest_hex(payload)
        if integrity.get("payload_sha256") != payload_sha256:
            return False

        key_id = str(integrity.get("kms_key_id") or self.key_id)
        if expected_key_id is not None and key_id != expected_key_id:
            return False

        try:
            response = self.client.verify_mac(
                KeyId=key_id,
                Message=build_mac_message(payload_sha256),
                MacAlgorithm=str(integrity.get("mac_algorithm") or self.mac_algorithm),
                Mac=base64.b64decode(str(integrity.get("mac") or ""), validate=True),
            )
        except Exception:
            return False
        return bool(response.get("MacValid"))

    def _build_client(self) -> Any:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - exercised only without optional dependency.
            raise RuntimeError("boto3 is required when KMS audit signing is enabled") from exc
        session = boto3.Session(profile_name=self.profile_name, region_name=self.region_name)
        return session.client("kms")


def canonical_audit_bytes(record: Mapping[str, Any]) -> bytes:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def payload_digest_hex(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_audit_bytes(record)).hexdigest()


def build_mac_message(payload_sha256: str) -> bytes:
    return MAC_MESSAGE_PREFIX + payload_sha256.encode("ascii")


def verify_audit_log(
    path: str | Path,
    signer: KmsAuditSigner,
    *,
    expected_key_id: str | None = None,
) -> list[AuditVerificationResult]:
    results: list[AuditVerificationResult] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                results.append(
                    AuditVerificationResult(
                        line_number=line_number,
                        ok=False,
                        container_id="",
                        reason=f"invalid json: {exc.msg}",
                    )
                )
                continue

            container_id = str(record.get("container_id", ""))
            ok = signer.verify_record(record, expected_key_id=expected_key_id)
            results.append(
                AuditVerificationResult(
                    line_number=line_number,
                    ok=ok,
                    container_id=container_id,
                    reason="" if ok else "mac verification failed",
                )
            )
    return results


def _summarize_results(results: Iterable[AuditVerificationResult]) -> tuple[int, int]:
    total = 0
    failed = 0
    for result in results:
        total += 1
        if not result.ok:
            failed += 1
    return total, failed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify RAASA KMS-signed audit JSONL records.")
    parser.add_argument("log_path", help="Path to a RAASA audit JSONL log")
    parser.add_argument("--key-id", required=True, help="Expected KMS key id or alias")
    parser.add_argument("--region", default=None, help="AWS region for KMS")
    parser.add_argument("--profile", default=None, help="Optional AWS profile")
    parser.add_argument("--mac-algorithm", default=DEFAULT_MAC_ALGORITHM)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    signer = KmsAuditSigner(
        args.key_id,
        region_name=args.region,
        profile_name=args.profile,
        mac_algorithm=args.mac_algorithm,
    )
    results = verify_audit_log(args.log_path, signer, expected_key_id=args.key_id)
    total, failed = _summarize_results(results)
    for result in results:
        if not result.ok:
            print(f"line {result.line_number}: FAILED {result.reason}")
    print(f"verified={total - failed} failed={failed} total={total}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
