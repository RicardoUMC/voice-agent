"""Small local CLI client for the voice-agent Unix-socket protocol."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
from typing import Any, Callable

from .daemon.app import settings_from_environment


SocketFactory = Callable[[int, int], socket.socket]


def request(
    socket_path: Path,
    payload: dict[str, Any],
    *,
    timeout: float = 120.0,
    socket_factory: SocketFactory = socket.socket,
) -> dict[str, Any]:
    """Send one JSONL request to the local daemon and return its response."""
    if timeout <= 0:
        raise ValueError("timeout must be positive")
    with socket_factory(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(socket_path))
        client.sendall((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        raw = client.makefile("rb").readline()
    if not raw:
        raise RuntimeError("voice-agent closed the connection without a response")
    response = json.loads(raw.decode("utf-8"))
    if not isinstance(response, dict):
        raise RuntimeError("voice-agent returned a non-object response")
    return response


def _parser() -> argparse.ArgumentParser:
    defaults = settings_from_environment()
    parser = argparse.ArgumentParser(description="Control the local voice-agent daemon")
    parser.add_argument("--socket", type=Path, default=defaults.socket_path)
    parser.add_argument("--timeout", type=float, default=120.0)
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("sessions", "status"):
        commands.add_parser(name, help="list persistent sessions")

    for name, help_text in (("turn", "send a text turn"), ("voice", "run one microphone voice turn")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("session_id")
        if name == "turn":
            command.add_argument("text")

    for name, operation, help_text in (
        ("stop", "stop_recording", "finish microphone capture without cancelling the turn"),
        ("interrupt", "interrupt", "cancel the active turn"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("session_id")
        command.set_defaults(operation=operation)
    return parser


def _payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.command in {"sessions", "status"}:
        return {"op": "sessions"}
    if args.command == "turn":
        return {"op": "turn", "session_id": args.session_id, "text": args.text}
    if args.command == "voice":
        return {"op": "voice_turn", "session_id": args.session_id}
    return {"op": args.operation, "session_id": args.session_id}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    payload = _payload(args)
    try:
        response = request(args.socket, payload, timeout=args.timeout)
    except (socket.timeout, TimeoutError) as error:
        if payload.get("op") in {"turn", "voice_turn"}:
            session_id = payload.get("session_id")
            if isinstance(session_id, str):
                try:
                    request(args.socket, {"op": "interrupt", "session_id": session_id}, timeout=5.0)
                except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
                    pass
        print(f"voice-agent client: request timed out; active turn was interrupted when possible", file=sys.stderr)
        return 2
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"voice-agent client: {error}", file=sys.stderr)
        return 2
    print(json.dumps(response, ensure_ascii=False, separators=(",", ":")))
    return 0 if response.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
