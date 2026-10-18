from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    text: str


@dataclass(frozen=True)
class Turn:
    user_text: str
    assistant_text: str


@dataclass
class Session:
    session_id: str
    turns: list[Turn] = field(default_factory=list)


class Cancellation(Protocol):
    @property
    def cancelled(self) -> bool: ...


class SessionRegistry(Protocol):
    def ensure(self, session_id: str) -> Session: ...
    def get(self, session_id: str) -> Session | None: ...
    def list_ids(self) -> list[str]: ...
    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None: ...


class TurnCoordinator(Protocol):
    def submit(self, session_id: str, text: str, cancellation: Cancellation) -> TurnResult: ...
    def interrupt(self, session_id: str) -> None: ...


class UnixSocketServer(Protocol):
    def serve_forever(self) -> None: ...
    def close(self) -> None: ...
