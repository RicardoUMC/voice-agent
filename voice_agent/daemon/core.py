from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from .types import Cancellation, SessionRegistry, TurnCoordinator


@dataclass
class CancellationState:
    cancelled: bool = False


class DaemonCore:
    """Transport-neutral request dispatcher for one or more persistent sessions."""

    def __init__(self, registry: SessionRegistry, coordinator: TurnCoordinator):
        self._registry = registry
        self._coordinator = coordinator
        self._state_lock = RLock()
        self._cancellations: dict[str, CancellationState] = {}

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = request.get("op")
        if operation == "turn":
            session_id = self._required(request, "session_id")
            text = self._required(request, "text")
            self._registry.ensure(session_id)
            cancellation = CancellationState()
            with self._state_lock:
                if session_id in self._cancellations:
                    raise RuntimeError(f"session already has an active turn: {session_id}")
                self._cancellations[session_id] = cancellation
            try:
                result = self._coordinator.submit(session_id, text, cancellation)
                self._registry.append_turn(session_id, text, result.text)
                return {"ok": True, "session_id": result.session_id, "text": result.text}
            finally:
                with self._state_lock:
                    if self._cancellations.get(session_id) is cancellation:
                        self._cancellations.pop(session_id, None)
        if operation == "interrupt":
            session_id = self._required(request, "session_id")
            with self._state_lock:
                state = self._cancellations.get(session_id)
                if state is not None:
                    state.cancelled = True
            # Do not hold the map lock while the provider observes the interrupt.
            self._coordinator.interrupt(session_id)
            return {"ok": True}
        if operation == "sessions":
            return {"ok": True, "sessions": self._registry.list_ids()}
        raise ValueError(f"unsupported operation: {operation!r}")

    @staticmethod
    def _required(request: dict[str, Any], key: str) -> str:
        value = request.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{key} must be a non-empty string")
        return value


class NoopUnixSocketServer:
    """Lifecycle seam for a future Unix-socket transport implementation."""

    def __init__(self, handler: DaemonCore):
        self.handler = handler
        self.closed = False

    def serve_forever(self) -> None:
        if self.closed:
            raise RuntimeError("server is closed")

    def close(self) -> None:
        self.closed = True
