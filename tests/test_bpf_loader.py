from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from raasa.k8s.bpf_loader import BpfLoader, BpfPaths, EDGE_MAP_NAME, LSM_BLOCK_MAP_NAME


class BpfLoaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("tests/.tmp_bpf_loader")
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.sock_source = self.root / "sock_ops_probe.bpf.c"
        self.lsm_source = self.root / "lsm_exec_block.bpf.c"
        self.sock_source.write_text("int x;\n", encoding="utf-8")
        self.lsm_source.write_text("int y;\n", encoding="utf-8")
        self.paths = BpfPaths(
            sock_ops_source=self.sock_source,
            lsm_source=self.lsm_source,
            probe_dir=self.root / "run",
            pin_dir=self.root / "bpf",
            cgroup_path=self.root / "cgroup",
            map_pin_dir=self.root / "bpf" / "maps",
            edge_map_pin=self.root / "bpf" / "maps" / EDGE_MAP_NAME,
            lsm_block_map_pin=self.root / "bpf" / "maps" / LSM_BLOCK_MAP_NAME,
            lsm_prog_pin_dir=self.root / "bpf" / "lsm_exec_block",
        )
        self.paths.cgroup_path.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_load_sock_ops_compiles_loads_attaches_and_writes_status(self) -> None:
        calls: list[list[str]] = []

        def fake_run(args, capture_output=True, text=True):
            calls.append(list(args))
            if args[:3] == ["bpftool", "prog", "loadall"] and "sockops" in args:
                (self.paths.pin_dir / "maps").mkdir(parents=True, exist_ok=True)
                (self.paths.pin_dir / "maps" / EDGE_MAP_NAME).write_text("", encoding="utf-8")
                self.paths.sock_ops_program_pin.write_text("", encoding="utf-8")
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

        with patch("raasa.k8s.bpf_loader.shutil.which", return_value="tool"), \
             patch("raasa.k8s.bpf_loader.subprocess.run", side_effect=fake_run):
            result = BpfLoader(self.paths, enable_lsm=False).load_sock_ops()

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "attached")
        self.assertIn("attached:", (self.paths.probe_dir / "sock_ops_status").read_text(encoding="utf-8"))
        self.assertTrue(any(call[:3] == ["clang", "-O2", "-g"] for call in calls))
        self.assertTrue(any(call[:4] == ["bpftool", "cgroup", "attach", str(self.paths.cgroup_path)] for call in calls))

    def test_lsm_loader_reports_kernel_without_bpf_lsm(self) -> None:
        lsm_list = self.root / "lsm"
        lsm_list.write_text("lockdown,capability,yama\n", encoding="utf-8")

        with patch.dict("os.environ", {"RAASA_BPF_LSM_LIST_PATH": str(lsm_list)}), \
             patch("raasa.k8s.bpf_loader.shutil.which", return_value="tool"):
            result = BpfLoader(self.paths, enable_sock_ops=False).load_lsm_exec_block()

        self.assertFalse(result.ok)
        self.assertEqual(result.status_line, "unavailable:bpf_lsm_not_enabled")
        self.assertIn("bpf_lsm_not_enabled", (self.paths.probe_dir / "lsm_exec_block_status").read_text(encoding="utf-8"))

    def test_export_pod_edges_writes_observer_jsonl(self) -> None:
        self.paths.edge_map_pin.parent.mkdir(parents=True, exist_ok=True)
        self.paths.edge_map_pin.write_text("", encoding="utf-8")
        dump = [
            {
                "key": {"src_ip": 169090600, "dst_ip": 169090601},
                "value": {"count": 3, "last_seen_ns": 42},
            }
        ]

        def fake_run(args, capture_output=True, text=True):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps(dump), stderr="")

        with patch("raasa.k8s.bpf_loader.shutil.which", return_value="tool"), \
             patch("raasa.k8s.bpf_loader.subprocess.run", side_effect=fake_run):
            result = BpfLoader(self.paths).export_pod_edges()

        self.assertTrue(result.ok)
        records = [
            json.loads(line)
            for line in self.paths.pod_edges_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(records, [{"count": 3, "dst_ip": 169090601, "last_seen_ns": 42, "src_ip": 169090600}])

    def test_export_accepts_raw_byte_bpftool_records(self) -> None:
        self.paths.edge_map_pin.parent.mkdir(parents=True, exist_ok=True)
        self.paths.edge_map_pin.write_text("", encoding="utf-8")
        dump = [
            {
                "key": ["04", "03", "02", "01", "08", "07", "06", "05"],
                "value": ["02", "00", "00", "00", "00", "00", "00", "00", "2a", "00", "00", "00", "00", "00", "00", "00"],
            }
        ]

        def fake_run(args, capture_output=True, text=True):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout=json.dumps(dump), stderr="")

        with patch("raasa.k8s.bpf_loader.shutil.which", return_value="tool"), \
             patch("raasa.k8s.bpf_loader.subprocess.run", side_effect=fake_run):
            result = BpfLoader(self.paths).export_pod_edges()

        self.assertTrue(result.ok)
        record = json.loads(self.paths.pod_edges_file.read_text(encoding="utf-8").strip())
        self.assertEqual(record["src_ip"], 0x01020304)
        self.assertEqual(record["dst_ip"], 0x05060708)
        self.assertEqual(record["count"], 2)
        self.assertEqual(record["last_seen_ns"], 42)


if __name__ == "__main__":
    unittest.main()
