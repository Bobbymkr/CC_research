"""
Runtime loader for RAASA eBPF enforcement and communication graph programs.

The loader intentionally uses the kernel/libbpf path exposed by clang and
bpftool instead of requiring a heavyweight Python eBPF dependency in the RAASA
agent image. It compiles the checked-in C programs, pins their maps under
/sys/fs/bpf/raasa, attaches the sock_ops and LSM programs, and exports the
pod communication edge map as JSONL for ObserverK8s.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

EDGE_MAP_NAME = "raasa_pod_edges"
LSM_BLOCK_MAP_NAME = "raasa_lsm_blocked_tgids"
SOCK_OPS_STATUS_FILE = "sock_ops_status"
LSM_STATUS_FILE = "lsm_exec_block_status"
POD_EDGES_FILE = "pod_edges.jsonl"
_TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass
class BpfLoadResult:
    component: str
    ok: bool
    status: str
    detail: str = ""

    @property
    def status_line(self) -> str:
        return f"{self.status}:{self.detail}" if self.detail else self.status


@dataclass
class BpfPaths:
    sock_ops_source: Path
    lsm_source: Path
    probe_dir: Path = Path("/var/run/raasa")
    pin_dir: Path = Path("/sys/fs/bpf/raasa")
    cgroup_path: Path = Path("/sys/fs/cgroup")
    map_pin_dir: Path = Path("/sys/fs/bpf/raasa/maps")
    edge_map_pin: Path = Path("/sys/fs/bpf/raasa/maps/raasa_pod_edges")
    lsm_block_map_pin: Path = Path("/sys/fs/bpf/raasa/maps/raasa_lsm_blocked_tgids")
    lsm_prog_pin_dir: Path = Path("/sys/fs/bpf/raasa/lsm_exec_block")

    @property
    def sock_ops_object(self) -> Path:
        return self.probe_dir / "raasa_sock_ops.bpf.o"

    @property
    def lsm_object(self) -> Path:
        return self.probe_dir / "raasa_lsm_exec_block.bpf.o"

    @property
    def sock_ops_program_pin(self) -> Path:
        return self.pin_dir / "raasa_sock_ops"

    @property
    def pod_edges_file(self) -> Path:
        return self.probe_dir / POD_EDGES_FILE


class BpfLoader:
    """Compile, attach, and export the RAASA eBPF programs."""

    def __init__(
        self,
        paths: Optional[BpfPaths] = None,
        *,
        target_arch: str = "x86",
        enable_sock_ops: bool = True,
        enable_lsm: bool = True,
    ) -> None:
        self.paths = paths or self.default_paths()
        self.target_arch = target_arch
        self.enable_sock_ops = enable_sock_ops
        self.enable_lsm = enable_lsm

    @classmethod
    def default_paths(cls) -> BpfPaths:
        source_dir = Path(__file__).resolve().parent
        pin_dir = Path(os.environ.get("RAASA_BPF_PIN_DIR", "/sys/fs/bpf/raasa"))
        map_pin_dir = Path(os.environ.get("RAASA_BPF_MAP_PIN_DIR", str(pin_dir / "maps")))
        return BpfPaths(
            sock_ops_source=Path(os.environ.get("RAASA_BPF_SOCK_OPS_SOURCE", str(source_dir / "sock_ops_probe.bpf.c"))),
            lsm_source=Path(os.environ.get("RAASA_BPF_LSM_SOURCE", str(source_dir / "lsm_exec_block.bpf.c"))),
            probe_dir=Path(os.environ.get("RAASA_BPF_PROBE_DIR", "/var/run/raasa")),
            pin_dir=pin_dir,
            cgroup_path=Path(os.environ.get("RAASA_BPF_CGROUP_PATH", "/sys/fs/cgroup")),
            map_pin_dir=map_pin_dir,
            edge_map_pin=Path(os.environ.get("RAASA_BPF_EDGE_MAP_PIN", str(map_pin_dir / EDGE_MAP_NAME))),
            lsm_block_map_pin=Path(os.environ.get("RAASA_BPF_LSM_MAP_PIN", str(map_pin_dir / LSM_BLOCK_MAP_NAME))),
            lsm_prog_pin_dir=Path(os.environ.get("RAASA_BPF_LSM_PROG_PIN_DIR", str(pin_dir / "lsm_exec_block"))),
        )

    @classmethod
    def from_env(cls) -> "BpfLoader":
        return cls(
            target_arch=os.environ.get("RAASA_BPF_TARGET_ARCH", "x86"),
            enable_sock_ops=_env_truthy("RAASA_ENABLE_SOCK_OPS_PROBE", default=True),
            enable_lsm=_env_truthy("RAASA_ENABLE_LSM_EXEC_BLOCKING", default=True),
        )

    def load_all(self) -> dict[str, BpfLoadResult]:
        return {
            "sock_ops": self.load_sock_ops(),
            "lsm_exec_block": self.load_lsm_exec_block(),
        }

    def load_sock_ops(self) -> BpfLoadResult:
        component = "sock_ops"
        if not self.enable_sock_ops:
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "disabled")
        if not self.paths.sock_ops_source.exists():
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "missing_source", str(self.paths.sock_ops_source))
        if not self._required_tools_available("clang", "bpftool"):
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "unavailable", "clang_or_bpftool_missing")

        self.paths.probe_dir.mkdir(parents=True, exist_ok=True)
        self.paths.pin_dir.mkdir(parents=True, exist_ok=True)
        compile_result = self._compile(
            self.paths.sock_ops_source,
            self.paths.sock_ops_object,
            self.paths.probe_dir / "sock_ops_compile.err",
        )
        if compile_result.returncode != 0:
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "compile_failed")

        self._run(
            [
                "bpftool",
                "cgroup",
                "detach",
                str(self.paths.cgroup_path),
                "sock_ops",
                "pinned",
                str(self.paths.sock_ops_program_pin),
            ],
            allow_failure=True,
        )
        self._remove_pin(self.paths.sock_ops_program_pin, self.paths.pin_dir)
        self._remove_pin(self.paths.pin_dir / "maps" / EDGE_MAP_NAME, self.paths.pin_dir)
        self._remove_pin(self.paths.edge_map_pin, self.paths.pin_dir)

        load_result = self._run(
            [
                "bpftool",
                "prog",
                "loadall",
                str(self.paths.sock_ops_object),
                str(self.paths.pin_dir),
                "type",
                "sockops",
            ],
            stderr_path=self.paths.probe_dir / "sock_ops_load.err",
        )
        if load_result.returncode != 0:
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "load_failed")

        self.paths.edge_map_pin = self._discover_edge_map_pin()
        attach_result = self._run(
            [
                "bpftool",
                "cgroup",
                "attach",
                str(self.paths.cgroup_path),
                "sock_ops",
                "pinned",
                str(self.paths.sock_ops_program_pin),
            ],
            stderr_path=self.paths.probe_dir / "sock_ops_attach.err",
        )
        if attach_result.returncode != 0:
            return self._status(component, SOCK_OPS_STATUS_FILE, False, "attach_failed")

        return self._status(component, SOCK_OPS_STATUS_FILE, True, "attached", str(self.paths.edge_map_pin))

    def load_lsm_exec_block(self) -> BpfLoadResult:
        component = "lsm_exec_block"
        if not self.enable_lsm:
            return self._status(component, LSM_STATUS_FILE, False, "disabled")
        if not self.paths.lsm_source.exists():
            return self._status(component, LSM_STATUS_FILE, False, "missing_source", str(self.paths.lsm_source))
        if not self._required_tools_available("clang", "bpftool"):
            return self._status(component, LSM_STATUS_FILE, False, "unavailable", "clang_or_bpftool_missing")
        if not self._bpf_lsm_enabled():
            return self._status(component, LSM_STATUS_FILE, False, "unavailable", "bpf_lsm_not_enabled")

        self.paths.probe_dir.mkdir(parents=True, exist_ok=True)
        self.paths.pin_dir.mkdir(parents=True, exist_ok=True)
        self.paths.map_pin_dir.mkdir(parents=True, exist_ok=True)
        compile_result = self._compile(
            self.paths.lsm_source,
            self.paths.lsm_object,
            self.paths.probe_dir / "lsm_exec_block_compile.err",
        )
        if compile_result.returncode != 0:
            return self._status(component, LSM_STATUS_FILE, False, "compile_failed")

        self._remove_pin(self.paths.lsm_prog_pin_dir, self.paths.pin_dir)
        self._remove_pin(self.paths.lsm_block_map_pin, self.paths.pin_dir)
        self.paths.lsm_prog_pin_dir.mkdir(parents=True, exist_ok=True)
        self.paths.map_pin_dir.mkdir(parents=True, exist_ok=True)
        load_result = self._run(
            [
                "bpftool",
                "prog",
                "loadall",
                str(self.paths.lsm_object),
                str(self.paths.lsm_prog_pin_dir),
                "type",
                "lsm",
                "pinmaps",
                str(self.paths.map_pin_dir),
                "autoattach",
            ],
            stderr_path=self.paths.probe_dir / "lsm_exec_block_load.err",
        )
        if load_result.returncode != 0:
            return self._status(component, LSM_STATUS_FILE, False, "load_failed")

        candidate = self.paths.map_pin_dir / LSM_BLOCK_MAP_NAME
        if candidate.exists():
            self.paths.lsm_block_map_pin = candidate
        return self._status(component, LSM_STATUS_FILE, True, "attached", str(self.paths.lsm_block_map_pin))

    def export_pod_edges(self) -> BpfLoadResult:
        records, status = self.read_pod_edges()
        if status != "edge_map_ok":
            return BpfLoadResult("pod_edges_export", False, status)

        self.paths.probe_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.paths.pod_edges_file.with_suffix(".jsonl.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            tmp_path.replace(self.paths.pod_edges_file)
        except OSError as exc:
            logger.warning("Failed to export RAASA pod edge map: %s", exc)
            return BpfLoadResult("pod_edges_export", False, "edge_map_export_failed", str(exc))
        return BpfLoadResult("pod_edges_export", True, "edge_map_exported", str(self.paths.pod_edges_file))

    def read_pod_edges(self) -> tuple[list[dict[str, int]], str]:
        edge_map_pin = self._discover_edge_map_pin()
        if not edge_map_pin.exists():
            return [], "edge_map_missing"
        if not self._required_tools_available("bpftool"):
            return [], "edge_map_tool_missing"

        result = self._run(["bpftool", "-j", "map", "dump", "pinned", str(edge_map_pin)])
        if result.returncode != 0:
            return [], "edge_map_dump_failed"
        try:
            parsed = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return [], "edge_map_invalid"
        if not isinstance(parsed, list):
            return [], "edge_map_invalid"

        records: list[dict[str, int]] = []
        for entry in parsed:
            record = _parse_edge_record(entry)
            if record is not None:
                records.append(record)
        if not records:
            return [], "edge_map_empty"
        return records, "edge_map_ok"

    def _compile(self, source: Path, obj: Path, stderr_path: Path) -> subprocess.CompletedProcess[str]:
        obj.parent.mkdir(parents=True, exist_ok=True)
        return self._run(
            [
                "clang",
                "-O2",
                "-g",
                "-target",
                "bpf",
                f"-D__TARGET_ARCH_{self.target_arch}",
                "-c",
                str(source),
                "-o",
                str(obj),
            ],
            stderr_path=stderr_path,
        )

    def _discover_edge_map_pin(self) -> Path:
        candidates = [
            self.paths.edge_map_pin,
            self.paths.map_pin_dir / EDGE_MAP_NAME,
            self.paths.pin_dir / "maps" / EDGE_MAP_NAME,
            self.paths.pin_dir / EDGE_MAP_NAME,
        ]
        for candidate in candidates:
            if candidate.exists():
                self.paths.edge_map_pin = candidate
                return candidate
        return self.paths.edge_map_pin

    def _required_tools_available(self, *tools: str) -> bool:
        return all(shutil.which(tool) is not None for tool in tools)

    def _bpf_lsm_enabled(self) -> bool:
        lsm_path = Path(os.environ.get("RAASA_BPF_LSM_LIST_PATH", "/sys/kernel/security/lsm"))
        if not lsm_path.exists():
            return True
        try:
            return any(item.strip() == "bpf" for item in lsm_path.read_text(encoding="utf-8").split(","))
        except OSError:
            return True

    def _run(
        self,
        args: list[str],
        *,
        stderr_path: Optional[Path] = None,
        allow_failure: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(args, capture_output=True, text=True)
        except FileNotFoundError as exc:
            result = subprocess.CompletedProcess(args=args, returncode=127, stdout="", stderr=str(exc))

        if stderr_path is not None and result.returncode != 0:
            try:
                stderr_path.parent.mkdir(parents=True, exist_ok=True)
                stderr_path.write_text(result.stderr or result.stdout or "", encoding="utf-8")
            except OSError:
                logger.debug("Could not write BPF command error file %s", stderr_path)
        if result.returncode != 0 and not allow_failure:
            logger.debug("BPF command failed rc=%s: %s", result.returncode, " ".join(args))
        return result

    def _status(
        self,
        component: str,
        filename: str,
        ok: bool,
        status: str,
        detail: str = "",
    ) -> BpfLoadResult:
        result = BpfLoadResult(component, ok, status, detail)
        try:
            self.paths.probe_dir.mkdir(parents=True, exist_ok=True)
            (self.paths.probe_dir / filename).write_text(result.status_line + "\n", encoding="utf-8")
        except OSError:
            logger.debug("Could not write BPF status file %s", filename)
        return result

    def _remove_pin(self, path: Path, allowed_root: Path) -> None:
        try:
            resolved_path = path.resolve(strict=False)
            resolved_root = allowed_root.resolve(strict=False)
            if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
                logger.warning("Refusing to remove BPF pin outside %s: %s", resolved_root, resolved_path)
                return
            if path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError as exc:
            logger.debug("Could not remove BPF pin %s: %s", path, exc)


def _env_truthy(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY_ENV_VALUES


def _parse_edge_record(entry: Any) -> Optional[dict[str, int]]:
    if not isinstance(entry, dict):
        return None
    key = entry.get("key")
    value = entry.get("value", {})
    src_ip = _extract_u32(key, "src_ip", 0)
    dst_ip = _extract_u32(key, "dst_ip", 4)
    if src_ip is None or dst_ip is None or src_ip == dst_ip:
        return None
    return {
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "count": max(1, _extract_u64(value, "count", 0) or 1),
        "last_seen_ns": max(0, _extract_u64(value, "last_seen_ns", 8) or 0),
    }


def _extract_u32(container: Any, field: str, offset: int) -> Optional[int]:
    value = _extract_named_int(container, field)
    if value is not None:
        return value & 0xFFFFFFFF
    raw_bytes = _extract_byte_list(container)
    if raw_bytes is None or len(raw_bytes) < offset + 4:
        return None
    return int.from_bytes(raw_bytes[offset : offset + 4], "little", signed=False)


def _extract_u64(container: Any, field: str, offset: int) -> Optional[int]:
    value = _extract_named_int(container, field)
    if value is not None:
        return value
    raw_bytes = _extract_byte_list(container)
    if raw_bytes is None or len(raw_bytes) < offset + 8:
        return None
    return int.from_bytes(raw_bytes[offset : offset + 8], "little", signed=False)


def _extract_named_int(container: Any, field: str) -> Optional[int]:
    if not isinstance(container, dict) or field not in container:
        return None
    raw = container[field]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _extract_byte_list(container: Any) -> Optional[list[int]]:
    if not isinstance(container, list):
        return None
    values: list[int] = []
    for item in container:
        try:
            if isinstance(item, str):
                values.append(int(item, 16) & 0xFF)
            else:
                values.append(int(item) & 0xFF)
        except (TypeError, ValueError):
            return None
    return values


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load and export RAASA eBPF programs")
    parser.add_argument("command", choices=["load", "export", "loop"], nargs="?", default="load")
    parser.add_argument("--interval", type=float, default=float(os.environ.get("RAASA_BPF_EXPORT_INTERVAL_SECONDS", "5")))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    loader = BpfLoader.from_env()
    if args.command == "load":
        results = loader.load_all()
        for result in results.values():
            logger.info("%s: %s", result.component, result.status_line)
        return 0 if any(result.ok for result in results.values()) else 1
    if args.command == "export":
        result = loader.export_pod_edges()
        logger.info("%s: %s", result.component, result.status_line)
        return 0 if result.ok else 1

    loader.load_all()
    interval = max(args.interval, 1.0)
    while True:
        loader.export_pod_edges()
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
