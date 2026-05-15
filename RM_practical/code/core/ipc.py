"""
Unix Domain Socket IPC for RAASA.

Provides a structured, group-restricted way for the unprivileged RAASA controller
to send containment commands to the privileged Enforcer sidecar.
"""
import json
import logging
import socket
import os
import threading
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_SOCKET_PATH = "/var/run/raasa/ipc/enforcer.sock"
DEFAULT_SOCKET_MODE = 0o660


def _ipc_gid():
    raw = os.environ.get("RAASA_IPC_GID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("[IPC] Ignoring invalid RAASA_IPC_GID=%r", raw)
        return None

class UnixSocketClient:
    """Client used by the unprivileged controller to send enforcement decisions."""
    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path

    def send_command(self, payload: Dict[str, Any]) -> bool:
        """Send a JSON payload to the privileged sidecar."""
        if not os.path.exists(self.socket_path):
            logger.error(f"[IPC Client] Socket {self.socket_path} does not exist. Is the sidecar running?")
            return False

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2.0)
                client.connect(self.socket_path)
                data = json.dumps(payload) + "\n"
                client.sendall(data.encode('utf-8'))
                
                # Wait for ACK
                response = client.recv(1024).decode('utf-8').strip()
                if response == "OK":
                    return True
                logger.warning(f"[IPC Client] Sidecar returned error: {response}")
                return False
        except Exception as e:
            logger.error(f"[IPC Client] Failed to send IPC command: {e}")
            return False


class UnixSocketServer:
    """Server used by the privileged sidecar to receive commands."""
    def __init__(self, handler: Callable[[Dict[str, Any]], bool], socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path
        self.handler = handler
        self.running = False
        self.server_socket = None

    def start(self):
        """Start the socket listener in a background thread."""
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.socket_path), exist_ok=True)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        
        gid = _ipc_gid()
        if gid is not None and hasattr(os, "chown"):
            try:
                os.chown(self.socket_path, -1, gid)
            except OSError as exc:
                logger.warning("[IPC] Could not chown socket to gid %s: %s", gid, exc)
        os.chmod(self.socket_path, DEFAULT_SOCKET_MODE)

        self.server_socket.listen(5)
        self.running = True
        
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        logger.info(f"[IPC Server] Listening on {self.socket_path}")

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _accept_loop(self):
        while self.running:
            try:
                conn, _ = self.server_socket.accept()
                with conn:
                    data = conn.recv(4096).decode('utf-8').strip()
                    if not data:
                        continue
                    
                    try:
                        payload = json.loads(data)
                        success = self.handler(payload)
                        response = "OK\n" if success else "ERR\n"
                        conn.sendall(response.encode('utf-8'))
                    except json.JSONDecodeError:
                        logger.error("[IPC Server] Received malformed JSON")
                        conn.sendall(b"ERR_INVALID_JSON\n")
            except Exception as e:
                if self.running:
                    logger.error(f"[IPC Server] Connection error: {e}")
