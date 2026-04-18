import argparse
import json
from pathlib import Path
from typing import Dict, Optional


def get_override_path(workspace_dir: str | Path = ".") -> Path:
    target_dir = Path(workspace_dir) / "raasa" / "configs"
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "overrides.json"


def load_overrides(path: Optional[Path] = None) -> Dict[str, str]:
    target = path or get_override_path()
    if not target.exists():
        return {}
    try:
        with open(target, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_overrides(overrides: Dict[str, str], path: Optional[Path] = None) -> None:
    target = path or get_override_path()
    with open(target, "w") as f:
        json.dump(overrides, f, indent=2)


def set_override(container_id: str, tier: str) -> None:
    overrides = load_overrides()
    overrides[container_id] = tier.upper()
    save_overrides(overrides)
    print(f"Set override: {container_id} -> {tier.upper()}")


def clear_override(container_id: str) -> None:
    overrides = load_overrides()
    if container_id in overrides:
        del overrides[container_id]
        save_overrides(overrides)
        print(f"Cleared override for {container_id}")
    else:
        print(f"No active override for {container_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage RAASA operator overrides")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    set_parser = subparsers.add_parser("set", help="Force a container to a specific tier")
    set_parser.add_argument("container_id", help="Target container ID")
    set_parser.add_argument("tier", choices=["L1", "L2", "L3"], help="Tier to force")
    
    clear_parser = subparsers.add_parser("clear", help="Clear an active override")
    clear_parser.add_argument("container_id", help="Target container ID")
    
    args = parser.parse_args()
    
    if args.command == "set":
        set_override(args.container_id, args.tier)
    elif args.command == "clear":
        clear_override(args.container_id)
        
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
