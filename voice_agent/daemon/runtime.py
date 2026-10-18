from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any

from voice_agent.conversation.pi_rpc import PiRpcConversationBackend

from .types import Cancellation, TurnResult


class PiSessionCoordinator:
    """Own one persistent Pi RPC backend per logical voice session."""

    def __init__(self, backend_factory: Callable[[str], PiRpcConversationBackend]):
        self._backend_factory = backend_factory
        self._backends: dict[str, Any] = {}
        self._lock = RLock()

    def _backend(self, session_id: str) -> Any:
        with self._lock:
            backend = self._backends.get(session_id)
            if backend is None:
                backend = self._backend_factory(session_id)
                self._backends[session_id] = backend
            return backend

    def submit(self, session_id: str, text: str, cancellation: Cancellation) -> TurnResult:
        backend = self._backend(session_id)
        answer = backend.submit(session_id, text, cancellation)
        return TurnResult(session_id=session_id, text=answer)

    def interrupt(self, session_id: str) -> None:
        with self._lock:
            backend = self._backends.get(session_id)
        if backend is not None:
            backend.interrupt(session_id)

    def submit_text(self, session_id: str, text: str, cancellation: Cancellation) -> str:
        return self.submit(session_id, text, cancellation).text

    def close(self) -> None:
        with self._lock:
            backends = list(self._backends.values())
            self._backends.clear()
        for backend in backends:
            backend.close()


class TextConversationAdapter:
    """Expose the text-only shape consumed by the voice pipeline."""

    def __init__(self, coordinator: PiSessionCoordinator):
        self._coordinator = coordinator

    def submit(self, session_id: str, text: str, cancellation: Cancellation) -> str:
        return self._coordinator.submit_text(session_id, text, cancellation)
