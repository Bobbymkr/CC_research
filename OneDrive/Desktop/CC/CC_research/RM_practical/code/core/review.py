from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from raasa.core.approval import clear_approval, set_approval
from raasa.core.override import clear_override, set_override


def _load_records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _resolve_log_path(path: str | None, log_directory: str = "raasa/logs") -> Path:
    if path:
        return Path(path)
    candidates = sorted(Path(log_directory).glob("run_*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError("No RAASA audit logs were found.")
    return candidates[0]


def _iter_latest_records(records: Iterable[dict]) -> list[dict]:
    latest_by_container: dict[str, dict] = {}
    for record in records:
        latest_by_container[str(record.get("container_id", ""))] = record
    return [latest_by_container[key] for key in sorted(latest_by_container)]


def show_status(log_path: Path) -> None:
    records = _load_records(log_path)
    latest_records = _iter_latest_records(records)
    print(f"Log: {log_path}")
    for record in latest_records:
        print(
            " | ".join(
                [
                    f"container={record.get('container_id', '')}",
                    f"tier={record.get('new_tier', '')}",
                    f"risk={float(record.get('risk', 0.0) or 0.0):.3f}",
                    f"confidence={float(record.get('confidence', 0.0) or 0.0):.3f}",
                    f"variant={record.get('controller_variant', '')}",
                    f"approval={record.get('approval_state', 'not_needed')}",
                    f"reason={record.get('reason', '')}",
                ]
            )
        )


def show_audit(log_path: Path, limit: int) -> None:
    records = _load_records(log_path)
    print(f"Log: {log_path}")
    for record in records[-max(limit, 1) :]:
        print(
            " | ".join(
                [
                    str(record.get("timestamp", "")),
                    f"container={record.get('container_id', '')}",
                    f"prev={record.get('prev_tier', '')}",
                    f"new={record.get('new_tier', '')}",
                    f"risk={float(record.get('risk', 0.0) or 0.0):.3f}",
                    f"approval={record.get('approval_state', 'not_needed')}",
                    f"reason={record.get('reason', '')}",
                ]
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="RAASA CLI review and operator actions")
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
        
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Show the latest record per container")
    status_parser.add_argument("--log", default=None, help="Optional path to a JSONL audit log")

    audit_parser = subparsers.add_parser("audit", help="Show recent audit records")
    audit_parser.add_argument("--log", default=None, help="Optional path to a JSONL audit log")
    audit_parser.add_argument("--limit", type=int, default=10, help="Number of records to print")

    approval_parser = subparsers.add_parser("approval", help="Manage approval decisions")
    approval_subparsers = approval_parser.add_subparsers(dest="approval_command", required=True)
    approval_set = approval_subparsers.add_parser("set", help="Approve or reject an L3 escalation")
    approval_set.add_argument("container_id")
    approval_set.add_argument("decision", choices=["approve", "reject"])
    approval_set.add_argument("--tier", default="L3", choices=["L3"])
    approval_clear = approval_subparsers.add_parser("clear", help="Clear a saved approval decision")
    approval_clear.add_argument("container_id")

    override_parser = subparsers.add_parser("override", help="Manage forced tier overrides")
    override_subparsers = override_parser.add_subparsers(dest="override_command", required=True)
    override_set = override_subparsers.add_parser("set", help="Force a tier")
    override_set.add_argument("container_id")
    override_set.add_argument("tier", choices=["L1", "L2", "L3"])
    override_clear = override_subparsers.add_parser("clear", help="Clear a forced tier")
    override_clear.add_argument("container_id")

    args = parser.parse_args()

    if args.command == "status":
        show_status(_resolve_log_path(args.log))
    elif args.command == "audit":
        show_audit(_resolve_log_path(args.log), args.limit)
    elif args.command == "approval":
        if args.approval_command == "set":
            set_approval(args.container_id, args.decision, target_tier=args.tier)
        elif args.approval_command == "clear":
            clear_approval(args.container_id)
    elif args.command == "override":
        if args.override_command == "set":
            set_override(args.container_id, args.tier)
        elif args.override_command == "clear":
            clear_override(args.container_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
