from __future__ import annotations

import json
import os
from pathlib import Path
import socketserver
import stat
import threading
from typing import Any

from .core import DaemonCore

_MAX_REQUEST_BYTES = 1024 * 1024


class _ThreadingUnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


class _JsonLineHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        owner: JsonLineUnixServer = self.server.owner  # type: ignore[attr-defined]
        while True:
            raw = self.rfile.readline(_MAX_REQUEST_BYTES + 1)
            if not raw:
                return
            if len(raw) > _MAX_REQUEST_BYTES:
                self._send({"ok": False, "error": "request exceeds maximum size"})
                return
            try:
                request = json.loads(raw.decode("utf-8"))
                if not isinstance(request, dict):
                    raise ValueError("request must be a JSON object")
                response = owner.core.handle(request)
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, RuntimeError) as error:
                response = {"ok": False, "error": str(error)}
            self._send(response)

    def _send(self, response: dict[str, Any]) -> None:
        encoded = (json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.wfile.write(encoded)
        self.wfile.flush()


class JsonLineUnixServer:
    """Restricted local JSONL transport for the transport-neutral daemon core."""

    def __init__(self, socket_path: Path, core: DaemonCore, socket_mode: int = 0o600):
        self.socket_path = Path(socket_path)
        self.core = core
        self.socket_mode = socket_mode
        self.ready = threading.Event()
        self._closed = threading.Event()
        self._server: _ThreadingUnixServer | None = None

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._remove_stale_socket()
        server = _ThreadingUnixServer(str(self.socket_path), _JsonLineHandler)
        server.owner = self  # type: ignore[attr-defined]
        os.chmod(self.socket_path, self.socket_mode)
        self._server = server
        self.ready.set()
        try:
            server.serve_forever()
        finally:
            server.server_close()
            self._server = None
            self._unlink_owned_socket()

    def close(self) -> None:
        self._closed.set()
        server = self._server
        if server is not None:
            server.shutdown()
            server.server_close()
            self._unlink_owned_socket()

    def _remove_stale_socket(self) -> None:
        try:
            mode = self.socket_path.stat().st_mode
        except FileNotFoundError:
            return
        if not stat.S_ISSOCK(mode):
            raise RuntimeError(f"refusing to replace non-socket path: {self.socket_path}")
        self.socket_path.unlink()

    def _unlink_owned_socket(self) -> None:
        try:
            if stat.S_ISSOCK(self.socket_path.stat().st_mode):
                self.socket_path.unlink()
        except FileNotFoundError:
            pass
