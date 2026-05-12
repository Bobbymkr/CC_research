from __future__ import annotations

import json
import shutil
import socket
import tempfile
import time
import unittest
from pathlib import Path

from raasa.core.ipc import UnixSocketClient, UnixSocketServer


class UnixSocketClientTests(unittest.TestCase):
    def test_client_rejects_non_dict_payload(self) -> None:
        client = UnixSocketClient(socket_path="/tmp/nonexistent.sock")
        self.assertFalse(client.send_command(["not", "a", "dict"]))  # type: ignore[arg-type]

    def test_wait_until_available_returns_false_for_missing_socket(self) -> None:
        client = UnixSocketClient(socket_path="/tmp/nonexistent.sock")
        self.assertFalse(client.wait_until_available(timeout_seconds=0.01, poll_interval_seconds=0.01))


class UnixSocketServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="raasa-ipc-"))
        self.socket_path = self.temp_dir / "enforcer.sock"

    def tearDown(self) -> None:
        if hasattr(self, "server"):
            self.server.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _roundtrip(self, raw_payload: str) -> str:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(str(self.socket_path))
            client.sendall(raw_payload.encode("utf-8"))
            return client.recv(1024).decode("utf-8").strip()

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix domain sockets are unavailable on this platform")
    def test_server_rejects_non_object_json(self) -> None:
        self.server = UnixSocketServer(handler=lambda payload: True, socket_path=str(self.socket_path))
        self.server.start()
        time.sleep(0.05)

        response = self._roundtrip(json.dumps(["bad", "payload"]) + "\n")
        self.assertEqual(response, "ERR_INVALID_PAYLOAD")

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix domain sockets are unavailable on this platform")
    def test_server_accepts_valid_object_payload(self) -> None:
        calls: list[dict[str, str]] = []

        def handler(payload):
            calls.append(payload)
            return True

        self.server = UnixSocketServer(handler=handler, socket_path=str(self.socket_path))
        self.server.start()
        time.sleep(0.05)

        response = self._roundtrip(json.dumps({"container_id": "default/raasa-test-benign", "tier": "L2"}) + "\n")
        self.assertEqual(response, "OK")
        self.assertEqual(calls[0]["tier"], "L2")

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix domain sockets are unavailable on this platform")
    def test_client_wait_until_available_succeeds_when_server_listens(self) -> None:
        self.server = UnixSocketServer(handler=lambda payload: True, socket_path=str(self.socket_path))
        self.server.start()

        client = UnixSocketClient(socket_path=str(self.socket_path))
        self.assertTrue(client.wait_until_available(timeout_seconds=0.2, poll_interval_seconds=0.01))


if __name__ == "__main__":
    unittest.main()
