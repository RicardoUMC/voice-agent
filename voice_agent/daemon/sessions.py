from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .types import Session, Turn


class SessionStateError(ValueError):
    """The persisted registry is unreadable or violates its bounded schema."""


class JsonSessionRegistry:
    """Small atomic JSON registry; state is retained independently of daemon uptime."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = RLock()
        self._sessions: dict[str, Session] = {}
        self._load()

    def ensure(self, session_id: str) -> Session:
        self._validate_id(session_id)
        with self._lock:
            session = self._sessions.setdefault(session_id, Session(session_id))
            self._save()
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._sessions)

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        self._validate_id(session_id)
        with self._lock:
            self.ensure(session_id).turns.append(Turn(user_text, assistant_text))
            self._save()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open(encoding="utf-8") as stream:
                raw = json.load(stream)
            self._sessions = self._decode(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise SessionStateError(f"invalid session state in {self._path}") from error

    @classmethod
    def _decode(cls, raw: object) -> dict[str, Session]:
        if not isinstance(raw, dict):
            raise ValueError("state root must be an object")
        sessions: dict[str, Session] = {}
        for session_id, turns in raw.items():
            if not isinstance(session_id, str):
                raise ValueError("session identifiers must be strings")
            cls._validate_id(session_id)
            if not isinstance(turns, list):
                raise ValueError("session turns must be a list")
            decoded_turns: list[Turn] = []
            for item in turns:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"user_text", "assistant_text"}
                    or not isinstance(item["user_text"], str)
                    or not isinstance(item["assistant_text"], str)
                ):
                    raise ValueError("turn records must contain two text fields")
                decoded_turns.append(Turn(item["user_text"], item["assistant_text"]))
            sessions[session_id] = Session(session_id, decoded_turns)
        return sessions

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            session_id: [turn.__dict__ for turn in session.turns]
            for session_id, session in self._sessions.items()
        }
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(raw, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
        temporary.replace(self._path)

    @staticmethod
    def _validate_id(session_id: str) -> None:
        if not session_id or "/" in session_id or "\\" in session_id:
            raise ValueError("session_id must be a non-empty local identifier")
