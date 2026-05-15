from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

DEFAULT_APPROVAL_PATH_ENV = "RAASA_APPROVAL_PATH"


def get_approval_path(workspace_dir: str | Path = ".") -> Path:
    configured_path = os.getenv(DEFAULT_APPROVAL_PATH_ENV)
    if configured_path:
        return Path(configured_path)

    target_dir = Path(workspace_dir) / "raasa" / "runtime"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "approvals.json"


def load_approvals(path: Optional[Path] = None) -> Dict[str, Dict[str, str]]:
    target = path or get_approval_path()
    if not target.exists():
        return {}
    try:
        with open(target, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(container_id): {
            "decision": str(item.get("decision", "")),
            "target_tier": str(item.get("target_tier", "L3")),
            "updated_at": str(item.get("updated_at", "")),
        }
        for container_id, item in payload.items()
        if isinstance(item, dict)
    }


def save_approvals(
    approvals: Dict[str, Dict[str, str]],
    path: Optional[Path] = None,
) -> None:
    target = path or get_approval_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(approvals, f, indent=2)


def set_approval(
    container_id: str,
    decision: str,
    target_tier: str = "L3",
    path: Optional[Path] = None,
) -> None:
    approvals = load_approvals(path)
    approvals[container_id] = {
        "decision": decision.lower(),
        "target_tier": target_tier.upper(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_approvals(approvals, path)
    print(f"Set approval: {container_id} -> {decision.lower()} {target_tier.upper()}")


def clear_approval(container_id: str, path: Optional[Path] = None) -> None:
    approvals = load_approvals(path)
    if container_id in approvals:
        del approvals[container_id]
        save_approvals(approvals, path)
        print(f"Cleared approval for {container_id}")
    else:
        print(f"No active approval for {container_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage RAASA approval decisions")
    
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
        
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser("set", help="Approve or reject an escalation")
    set_parser.add_argument("container_id", help="Target container ID")
    set_parser.add_argument("decision", choices=["approve", "reject"], help="Decision to persist")
    set_parser.add_argument("--tier", default="L3", choices=["L3"], help="Tier under review")

    clear_parser = subparsers.add_parser("clear", help="Clear an approval decision")
    clear_parser.add_argument("container_id", help="Target container ID")

    args = parser.parse_args()

    if args.command == "set":
        set_approval(args.container_id, args.decision, target_tier=args.tier)
    elif args.command == "clear":
        clear_approval(args.container_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
