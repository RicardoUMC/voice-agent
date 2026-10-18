"""Persistent, provider-independent adapter for Pi 1.3 RPC."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import itertools
import os
import json
import re
import queue
import subprocess
import threading
import time
from typing import Any, Protocol

from voice_agent.adapters.errors import (
    AdapterUnavailableError,
    ProviderCancelledError,
    ProviderRequestError,
)


class _Process(Protocol):
    stdin: Any
    stdout: Any
    stderr: Any
    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...


@dataclass(frozen=True)
class PiRpcConfig:
    command: tuple[str, ...] = ("pi", "--mode", "rpc")
    session_id: str = "voice-agent"
    session_dir: str | None = None
    startup_timeout: float = 10.0
    command_timeout: float = 60.0

    def __post_init__(self) -> None:
        if not self.command or self.startup_timeout <= 0 or self.command_timeout <= 0:
            raise ValueError("Pi RPC command and timeouts are required")
        if not isinstance(self.session_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.session_id) is None:
            raise ValueError("Pi RPC session_id must use letters, numbers, '.', '_' or '-'")
        if self.session_dir is not None and (not isinstance(self.session_dir, str) or not self.session_dir.strip() or "\x00" in self.session_dir):
            raise ValueError("Pi RPC session_dir must be a non-empty path")

    @property
    def child_command(self) -> tuple[str, ...]:
        command = (*self.command, "--session-id", self.session_id)
        if self.session_dir is not None:
            command += ("--session-dir", os.fspath(self.session_dir))
        return command


class PiRpcConversationBackend:
    """One persistent Pi RPC child process, intended to be owned by one session.

    Process streams are injected so protocol behavior can be tested without Pi,
    credentials, or a live terminal. Mutating commands are serialized by the
    command lock; a stdout reader continuously receives events independently.
    """

    def __init__(
        self,
        config: PiRpcConfig | None = None,
        *,
        process_factory: Callable[[tuple[str, ...]], _Process] | None = None,
        startup_timeout: float | None = None,
    ) -> None:
        self.config = config or PiRpcConfig()
        self._timeout = self.config.startup_timeout if startup_timeout is None else startup_timeout
        if self._timeout <= 0:
            raise ValueError("startup timeout must be positive")
        self._factory = process_factory or self._spawn
        try:
            self._process = self._factory(self.config.child_command)
        except (OSError, FileNotFoundError) as exc:
            raise AdapterUnavailableError("Pi executable is unavailable") from exc
        self._events: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._ids = itertools.count(1)
        self._write_lock = threading.Lock()
        self._closed = threading.Event()
        self._stderr: list[str] = []
        self._active_cancellation: Any | None = None
        self._active_lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_stdout, name="pi-rpc-stdout", daemon=True)
        self._stderr_reader = threading.Thread(target=self._read_stderr, name="pi-rpc-stderr", daemon=True)
        self._reader.start()
        self._stderr_reader.start()
        try:
            self._request("get_state", timeout=self._timeout)
        except Exception:
            self.close()
            raise

    @staticmethod
    def _spawn(command: tuple[str, ...]) -> _Process:
        return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def submit(self, session_id: str, text: str, cancellation: Any) -> str:
        """TurnCoordinator-compatible entry point for one dedicated session."""
        if not isinstance(session_id, str) or not session_id:
            raise ProviderRequestError("Pi conversation session is required")
        with self._active_lock:
            self._active_cancellation = cancellation
        try:
            return self.complete(text, cancellation)
        finally:
            with self._active_lock:
                self._active_cancellation = None

    def interrupt(self, session_id: str) -> None:
        if not isinstance(session_id, str) or not session_id:
            return
        with self._active_lock:
            token = self._active_cancellation
        if token is None:
            return
        setter = getattr(token, "set", None)
        if callable(setter):
            setter()
        elif hasattr(token, "cancelled"):
            try:
                token.cancelled = True
            except AttributeError:
                pass

    def complete(self, text: str, cancellation: Any) -> str:
        if not isinstance(text, str) or not text.strip():
            raise ProviderRequestError("Pi prompt requires non-empty text")
        with self._write_lock:
            if self._cancelled(cancellation):
                self._cancel_remote_locked()
                raise ProviderCancelledError("Pi prompt cancelled")
            command_id = self._write({"type": "prompt", "message": text})
            deltas: list[str] = []
            deadline = time.monotonic() + self.config.command_timeout
            while True:
                try:
                    event = self._events.get(timeout=self._remaining(deadline))
                except queue.Empty as exc:
                    raise ProviderRequestError("Pi RPC prompt timed out") from exc
                if isinstance(event, BaseException):
                    raise ProviderRequestError("Pi RPC stdout closed") from event
                if self._cancelled(cancellation):
                    self._cancel_remote_locked()
                    raise ProviderCancelledError("Pi prompt cancelled")
                if event.get("type") == "message_update":
                    delta = self._text_delta(event)
                    if delta:
                        deltas.append(delta)
                elif event.get("type") == "response" and event.get("id") == command_id:
                    self._check_response(event, "prompt")
                elif event.get("type") == "agent_settled":
                    return "".join(deltas)

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._process.terminate()
        except (OSError, AttributeError):
            pass
        for stream in (getattr(self._process, "stdin", None), getattr(self._process, "stdout", None), getattr(self._process, "stderr", None)):
            try:
                stream.close()
            except (OSError, AttributeError):
                pass

    def _request(self, command: str, *, timeout: float) -> dict[str, Any]:
        with self._write_lock:
            command_id = self._write({"type": command})
            deadline = time.monotonic() + timeout
            while True:
                try:
                    event = self._events.get(timeout=self._remaining(deadline))
                except queue.Empty as exc:
                    raise ProviderRequestError(f"Pi RPC {command} timed out") from exc
                if isinstance(event, BaseException):
                    raise ProviderRequestError("Pi RPC stdout closed") from event
                if event.get("type") != "response":
                    continue
                if event.get("id") != command_id and event.get("command") != command:
                    continue
                self._check_response(event, command)
                return event

    def _write(self, payload: dict[str, Any]) -> int:
        command_id = next(self._ids)
        payload = {**payload, "id": str(command_id)}
        try:
            encoded = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            self._process.stdin.write(encoded)
            self._process.stdin.flush()
        except Exception as exc:
            raise ProviderRequestError("Pi RPC stdin failed") from exc
        return command_id

    def _cancel_remote_locked(self) -> None:
        # Called while the mutating-command lock is held. These are deliberately
        # ordered and bounded; abort alone can leave queued work.
        deadline = time.monotonic() + min(self.config.command_timeout, 2.0)
        for command in ("clear_queue", "abort"):
            try:
                command_id = self._write({"type": command})
                while True:
                    event = self._events.get(timeout=self._remaining(deadline))
                    if isinstance(event, BaseException):
                        raise ProviderRequestError("Pi RPC stdout closed") from event
                    if event.get("type") == "response" and (event.get("id") == command_id or event.get("command") == command):
                        self._check_response(event, command)
                        break
            except (ProviderRequestError, queue.Empty):
                pass

    def _read_stdout(self) -> None:
        try:
            while not self._closed.is_set():
                line = self._process.stdout.readline()
                if not line:
                    break
                if not line.endswith(b"\n"):
                    raise ValueError("Pi RPC emitted a non-LF-framed line")
                value = json.loads(line[:-1].decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("Pi RPC frame is not an object")
                self._events.put(value)
        except BaseException as exc:
            if not self._closed.is_set():
                self._events.put(exc)

    def _read_stderr(self) -> None:
        try:
            while not self._closed.is_set():
                line = self._process.stderr.readline()
                if not line:
                    return
                self._stderr.append(line.decode("utf-8", errors="replace").rstrip("\r\n"))
                del self._stderr[:-100]
        except (OSError, AttributeError):
            return

    @staticmethod
    def _remaining(deadline: float) -> float:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise queue.Empty
        return remaining

    @staticmethod
    def _text_delta(event: Mapping[str, Any]) -> str:
        nested = event.get("assistantMessageEvent")
        if isinstance(nested, Mapping) and nested.get("type") == "text_delta":
            return str(nested.get("delta", ""))
        if event.get("delta") is not None:
            return str(event["delta"])
        return ""

    @staticmethod
    def _check_response(event: Mapping[str, Any], command: str) -> None:
        if event.get("success") is not True:
            detail = event.get("error") or f"Pi RPC {command} failed"
            raise ProviderRequestError(str(detail))

    @staticmethod
    def _cancelled(token: Any) -> bool:
        method = getattr(token, "is_set", None)
        return bool(method()) if callable(method) else bool(getattr(token, "cancelled", False))
