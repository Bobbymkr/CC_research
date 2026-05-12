from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a declared dependency
    psutil = None  # type: ignore[assignment]


def _run_command(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
        }

    return {
        "ok": completed.returncode == 0,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def _docker_info() -> dict[str, Any]:
    docker_path = shutil.which("docker")
    if not docker_path:
        return {"available": False}

    client = _run_command(["docker", "version", "--format", "{{.Client.Version}}"])
    server = _run_command(["docker", "version", "--format", "{{.Server.Version}}"])
    fallback = _run_command(["docker", "--version"])
    return {
        "available": True,
        "path": docker_path,
        "client_version": client["stdout"] if client["ok"] else None,
        "server_version": server["stdout"] if server["ok"] else None,
        "docker_version_output": fallback["stdout"] if fallback["ok"] else None,
        "errors": [entry for entry in (client, server, fallback) if not entry["ok"]],
    }


def _kubectl_info() -> dict[str, Any]:
    kubectl_path = shutil.which("kubectl")
    if not kubectl_path:
        return {"available": False}

    version = _run_command(["kubectl", "version", "--client", "--output=json"])
    payload: dict[str, Any] = {
        "available": True,
        "path": kubectl_path,
    }
    if version["ok"] and version["stdout"]:
        try:
            payload["client_version"] = json.loads(version["stdout"])
        except json.JSONDecodeError:
            payload["client_version_raw"] = version["stdout"]
    else:
        payload["errors"] = [version]
    return payload


def _git_info() -> dict[str, Any]:
    commit = _run_command(["git", "rev-parse", "HEAD"])
    branch = _run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    status = _run_command(["git", "status", "--short"])
    return {
        "commit": commit["stdout"] if commit["ok"] else None,
        "branch": branch["stdout"] if branch["ok"] else None,
        "dirty": bool(status["stdout"]) if status["ok"] else None,
    }


def build_snapshot(workspace_root: Path) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace_root.resolve()),
        "host": {
            "hostname": platform.node(),
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "python": {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "git": _git_info(),
        "docker": _docker_info(),
        "kubectl": _kubectl_info(),
    }

    if psutil is not None:
        snapshot["hardware"] = {
            "logical_cpu_count": psutil.cpu_count(logical=True),
            "physical_cpu_count": psutil.cpu_count(logical=False),
            "memory_total_bytes": psutil.virtual_memory().total,
        }
    else:
        snapshot["hardware"] = {
            "logical_cpu_count": None,
            "physical_cpu_count": None,
            "memory_total_bytes": None,
        }

    return snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture the current local RAASA execution environment.")
    parser.add_argument(
        "--output",
        default="docs/local_environment_snapshot.json",
        help="Path to the JSON file that should receive the snapshot.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parents[2]
    output_path = (workspace_root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot = build_snapshot(workspace_root)
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Wrote environment snapshot to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
