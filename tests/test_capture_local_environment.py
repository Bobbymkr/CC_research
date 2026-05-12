from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from raasa.scripts.capture_local_environment import build_snapshot


class CaptureLocalEnvironmentTests(unittest.TestCase):
    def test_build_snapshot_contains_expected_top_level_sections(self) -> None:
        workspace_root = Path.cwd()
        snapshot = build_snapshot(workspace_root)

        self.assertIn("captured_at_utc", snapshot)
        self.assertEqual(snapshot["workspace_root"], str(workspace_root.resolve()))
        self.assertIn("host", snapshot)
        self.assertIn("python", snapshot)
        self.assertIn("git", snapshot)
        self.assertIn("docker", snapshot)
        self.assertIn("kubectl", snapshot)
        self.assertIn("hardware", snapshot)

    def test_snapshot_can_be_serialized_to_json(self) -> None:
        snapshot = build_snapshot(Path.cwd())

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "snapshot.json"
            output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            reloaded = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(reloaded["workspace_root"], snapshot["workspace_root"])
        self.assertIn("version", reloaded["python"])
