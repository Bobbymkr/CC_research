from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from raasa.k8s.enforcement_k8s import EnforcerK8s


class EnforcerK8sSigningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="raasa-k8s-ipc-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initializes_agent_side_ipc_signing_keypair(self) -> None:
        private_key_path = self.temp_dir / "command_signing_key.pem"
        public_key_path = self.temp_dir / "command_signing_key.pub"
        socket_path = self.temp_dir / "enforcer.sock"

        with patch.dict(
            os.environ,
            {
                "RAASA_IPC_SIGNING_PRIVATE_KEY": str(private_key_path),
                "RAASA_IPC_SIGNING_PUBLIC_KEY": str(public_key_path),
                "RAASA_IPC_SOCKET_PATH": str(socket_path),
            },
        ):
            enforcer = EnforcerK8s()

        self.assertTrue(private_key_path.exists())
        self.assertTrue(public_key_path.exists())
        self.assertTrue(enforcer.ipc_client.signing_required)
        self.assertEqual(enforcer.ipc_client.private_key_path, str(private_key_path))
        self.assertEqual(enforcer.ipc_client.socket_path, str(socket_path))


if __name__ == "__main__":
    unittest.main()
