"""
Unix Domain Socket IPC for RAASA.

Provides a structured, signed way for the unprivileged RAASA controller
to send containment commands to the privileged Enforcer sidecar.
"""
from __future__ import annotations

import base64
import binascii
from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import logging
import os
import secrets
import socket
import threading
import time
from typing import Any, Callable, Dict, Optional

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - dependency is declared for runtime builds
    InvalidSignature = None
    serialization = None
    Ed25519PrivateKey = None
    Ed25519PublicKey = None

logger = logging.getLogger(__name__)

DEFAULT_IPC_DIR = os.environ.get("RAASA_IPC_DIR", "/var/run/raasa/ipc")
DEFAULT_SOCKET_PATH = os.environ.get("RAASA_IPC_SOCKET_PATH", os.path.join(DEFAULT_IPC_DIR, "enforcer.sock"))
DEFAULT_PRIVATE_KEY_PATH = os.environ.get(
    "RAASA_IPC_SIGNING_PRIVATE_KEY",
    os.path.join(DEFAULT_IPC_DIR, "command_signing_key.pem"),
)
DEFAULT_PUBLIC_KEY_PATH = os.environ.get(
    "RAASA_IPC_SIGNING_PUBLIC_KEY",
    os.path.join(DEFAULT_IPC_DIR, "command_signing_key.pub"),
)
DEFAULT_IPC_DIR_MODE = 0o770
DEFAULT_SOCKET_MODE = 0o660
DEFAULT_PRIVATE_KEY_MODE = 0o640
DEFAULT_PUBLIC_KEY_MODE = 0o640


def _canonical_json(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _require_crypto() -> None:
    if Ed25519PrivateKey is None or Ed25519PublicKey is None or serialization is None:
        raise RuntimeError("cryptography is required for RAASA signed IPC commands")


def _chmod(path: str, mode: int) -> None:
    try:
        os.chmod(path, mode)
    except OSError as exc:
        logger.warning("[IPC] Could not chmod %s to %s: %s", path, oct(mode), exc)


def _chown_group(path: str, gid: Optional[int]) -> None:
    if gid is None or not hasattr(os, "chown"):
        return
    try:
        os.chown(path, -1, gid)
    except OSError as exc:
        logger.warning("[IPC] Could not chown %s to gid %s: %s", path, gid, exc)


def ipc_gid_from_env(default: Optional[int] = None) -> Optional[int]:
    raw = os.environ.get("RAASA_IPC_GID", "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("[IPC] Ignoring invalid RAASA_IPC_GID=%r", raw)
        return default


def _write_private_key(path: str, data: bytes, mode: int, gid: Optional[int]) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    finally:
        _chown_group(path, gid)
        _chmod(path, mode)


def _write_public_key(path: str, data: bytes, mode: int, gid: Optional[int]) -> None:
    with open(path, "wb") as handle:
        handle.write(data)
    _chown_group(path, gid)
    _chmod(path, mode)


def ensure_ipc_keypair(
    private_key_path: str = DEFAULT_PRIVATE_KEY_PATH,
    public_key_path: str = DEFAULT_PUBLIC_KEY_PATH,
    *,
    gid: Optional[int] = None,
    directory_mode: int = DEFAULT_IPC_DIR_MODE,
    private_key_mode: int = DEFAULT_PRIVATE_KEY_MODE,
    public_key_mode: int = DEFAULT_PUBLIC_KEY_MODE,
) -> tuple[str, str]:
    """Create or refresh the ephemeral Ed25519 keypair used for IPC signing."""
    _require_crypto()
    key_dir = os.path.dirname(private_key_path)
    os.makedirs(key_dir, exist_ok=True)
    _chown_group(key_dir, gid)
    _chmod(key_dir, directory_mode)

    if os.path.exists(private_key_path):
        with open(private_key_path, "rb") as handle:
            private_key = serialization.load_pem_private_key(handle.read(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise RuntimeError(f"{private_key_path} does not contain an Ed25519 private key")
    else:
        private_key = Ed25519PrivateKey.generate()
        raw_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        _write_private_key(private_key_path, raw_private, private_key_mode, gid)

    raw_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    _write_public_key(public_key_path, raw_public, public_key_mode, gid)
    return private_key_path, public_key_path


def _key_id_for_public_key(public_key: Any) -> str:
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw_public).hexdigest()[:16]


@dataclass(slots=True)
class CommandSigner:
    private_key: Any
    key_id: str

    @classmethod
    def from_private_key_file(cls, private_key_path: str = DEFAULT_PRIVATE_KEY_PATH) -> "CommandSigner":
        _require_crypto()
        with open(private_key_path, "rb") as handle:
            private_key = serialization.load_pem_private_key(handle.read(), password=None)
        if not isinstance(private_key, Ed25519PrivateKey):
            raise RuntimeError(f"{private_key_path} does not contain an Ed25519 private key")
        return cls(private_key=private_key, key_id=_key_id_for_public_key(private_key.public_key()))

    def sign_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a JSON object")
        message = {
            "issued_at": time.time(),
            "key_id": self.key_id,
            "nonce": secrets.token_urlsafe(24),
            "payload": payload,
        }
        signature = self.private_key.sign(_canonical_json(message))
        signed = dict(message)
        signed["signature"] = base64.b64encode(signature).decode("ascii")
        return signed


@dataclass(slots=True)
class CommandVerifier:
    public_key: Any
    key_id: str
    max_age_seconds: float = 30.0
    nonce_cache_size: int = 4096
    _seen_nonces: set[str] = field(default_factory=set)
    _nonce_order: deque[str] = field(default_factory=deque)

    @classmethod
    def from_public_key_file(cls, public_key_path: str = DEFAULT_PUBLIC_KEY_PATH) -> "CommandVerifier":
        _require_crypto()
        with open(public_key_path, "rb") as handle:
            public_key = serialization.load_pem_public_key(handle.read())
        if not isinstance(public_key, Ed25519PublicKey):
            raise RuntimeError(f"{public_key_path} does not contain an Ed25519 public key")
        return cls(public_key=public_key, key_id=_key_id_for_public_key(public_key))

    def unwrap(self, message: Dict[str, Any]) -> tuple[bool, Optional[Dict[str, Any]], str]:
        if not isinstance(message, dict):
            return False, None, "signed command must be a JSON object"
        payload = message.get("payload")
        signature = message.get("signature")
        nonce = message.get("nonce")
        key_id = message.get("key_id")
        issued_at = message.get("issued_at")
        if not isinstance(payload, dict):
            return False, None, "signed command payload must be a JSON object"
        if not isinstance(signature, str) or not signature:
            return False, None, "missing signature"
        if not isinstance(nonce, str) or not nonce:
            return False, None, "missing nonce"
        if key_id != self.key_id:
            return False, None, "unexpected signing key"
        try:
            issued_at_float = float(issued_at)
        except (TypeError, ValueError):
            return False, None, "invalid issued_at"
        if abs(time.time() - issued_at_float) > self.max_age_seconds:
            return False, None, "stale signed command"
        if nonce in self._seen_nonces:
            return False, None, "replayed signed command"

        signed_part = {
            "issued_at": issued_at,
            "key_id": key_id,
            "nonce": nonce,
            "payload": payload,
        }
        try:
            decoded_signature = base64.b64decode(signature.encode("ascii"), validate=True)
            self.public_key.verify(decoded_signature, _canonical_json(signed_part))
        except (binascii.Error, InvalidSignature, ValueError) as exc:
            return False, None, f"invalid signature: {exc}"

        self._remember_nonce(nonce)
        return True, payload, ""

    def _remember_nonce(self, nonce: str) -> None:
        while len(self._nonce_order) >= self.nonce_cache_size:
            old_nonce = self._nonce_order.popleft()
            self._seen_nonces.discard(old_nonce)
        self._nonce_order.append(nonce)
        self._seen_nonces.add(nonce)


class UnixSocketClient:
    """Client used by the unprivileged controller to send enforcement decisions."""

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        *,
        signer: Optional[CommandSigner] = None,
        private_key_path: Optional[str] = DEFAULT_PRIVATE_KEY_PATH,
        signing_required: bool = False,
    ) -> None:
        self.socket_path = socket_path
        self.signer = signer
        self.private_key_path = private_key_path
        self.signing_required = signing_required

    def _load_signer(self) -> Optional[CommandSigner]:
        if self.signer is not None:
            return self.signer
        if not self.private_key_path or not os.path.exists(self.private_key_path):
            return None
        self.signer = CommandSigner.from_private_key_file(self.private_key_path)
        return self.signer

    def is_available(self) -> bool:
        """Return True when the sidecar socket exists and accepts connections."""
        if not hasattr(socket, "AF_UNIX") or not os.path.exists(self.socket_path):
            return False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(0.5)
                client.connect(self.socket_path)
            return True
        except OSError:
            return False

    def wait_until_available(
        self,
        timeout_seconds: float = 15.0,
        poll_interval_seconds: float = 0.25,
    ) -> bool:
        """Poll until the sidecar socket is reachable or the timeout expires."""
        deadline = time.time() + max(0.0, timeout_seconds)
        while time.time() < deadline:
            if self.is_available():
                return True
            time.sleep(max(0.01, poll_interval_seconds))
        return self.is_available()

    def send_command(self, payload: Dict[str, Any]) -> bool:
        """Send a JSON payload to the privileged sidecar."""
        if not isinstance(payload, dict):
            logger.error("[IPC Client] Payload must be a JSON object.")
            return False
        if not hasattr(socket, "AF_UNIX"):
            logger.error("[IPC Client] Unix domain sockets are not supported on this platform.")
            return False
        if not os.path.exists(self.socket_path):
            logger.error(f"[IPC Client] Socket {self.socket_path} does not exist. Is the sidecar running?")
            return False

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(2.0)
                client.connect(self.socket_path)
                message = payload
                signer = self._load_signer()
                if signer is not None:
                    message = signer.sign_payload(payload)
                elif self.signing_required:
                    logger.error("[IPC Client] Signed IPC is required, but no signing key is available.")
                    return False

                data = json.dumps(message) + "\n"
                client.sendall(data.encode("utf-8"))

                response = client.recv(1024).decode("utf-8").strip()
                if response == "OK":
                    return True
                logger.warning(f"[IPC Client] Sidecar returned error: {response}")
                return False
        except Exception as e:
            logger.error(f"[IPC Client] Failed to send IPC command: {e}")
            return False


class UnixSocketServer:
    """Server used by the privileged sidecar to receive commands."""

    def __init__(
        self,
        handler: Callable[[Dict[str, Any]], bool],
        socket_path: str = DEFAULT_SOCKET_PATH,
        *,
        verifier: Optional[CommandVerifier] = None,
        socket_mode: int = DEFAULT_SOCKET_MODE,
        socket_gid: Optional[int] = None,
        ipc_dir_mode: int = DEFAULT_IPC_DIR_MODE,
        ipc_dir_gid: Optional[int] = None,
    ) -> None:
        self.socket_path = socket_path
        self.handler = handler
        self.verifier = verifier
        self.socket_mode = socket_mode
        self.socket_gid = socket_gid
        self.ipc_dir_mode = ipc_dir_mode
        self.ipc_dir_gid = ipc_dir_gid
        self.running = False
        self.server_socket = None

    def start(self) -> None:
        """Start the socket listener in a background thread."""
        if not hasattr(socket, "AF_UNIX"):
            raise RuntimeError("Unix domain sockets are not supported on this platform.")
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        socket_dir = os.path.dirname(self.socket_path)
        os.makedirs(socket_dir, exist_ok=True)
        _chown_group(socket_dir, self.ipc_dir_gid)
        _chmod(socket_dir, self.ipc_dir_mode)

        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        _chown_group(self.socket_path, self.socket_gid)
        _chmod(self.socket_path, self.socket_mode)

        self.server_socket.listen(5)
        self.running = True

        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        logger.info(f"[IPC Server] Listening on {self.socket_path}")

    def stop(self) -> None:
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    def _accept_loop(self) -> None:
        while self.running:
            try:
                conn, _ = self.server_socket.accept()
                with conn:
                    data = conn.recv(4096).decode("utf-8").strip()
                    if not data:
                        continue

                    try:
                        payload = json.loads(data)
                        if not isinstance(payload, dict):
                            logger.error("[IPC Server] Received non-object JSON payload")
                            conn.sendall(b"ERR_INVALID_PAYLOAD\n")
                            continue
                        if self.verifier is not None:
                            verified, command_payload, error = self.verifier.unwrap(payload)
                            if not verified or command_payload is None:
                                logger.error("[IPC Server] Rejected unsigned/tampered command: %s", error)
                                conn.sendall(b"ERR_INVALID_SIGNATURE\n")
                                continue
                            payload = command_payload
                        success = self.handler(payload)
                        response = "OK\n" if success else "ERR\n"
                        conn.sendall(response.encode("utf-8"))
                    except json.JSONDecodeError:
                        logger.error("[IPC Server] Received malformed JSON")
                        conn.sendall(b"ERR_INVALID_JSON\n")
            except Exception as e:
                if self.running:
                    logger.error(f"[IPC Server] Connection error: {e}")
