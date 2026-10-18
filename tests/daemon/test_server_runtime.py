import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from voice_agent.daemon.core import DaemonCore
from voice_agent.daemon.app import settings_from_environment
from voice_agent.daemon.runtime import PiSessionCoordinator
from voice_agent.daemon.server import JsonLineUnixServer
from voice_agent.daemon.sessions import JsonSessionRegistry
from voice_agent.daemon.types import TurnResult
from voice_agent.voice.pipeline import VoiceTurnCancelled


class FakeBackend:
    def __init__(self, session_id):
        self.session_id = session_id
        self.interrupts = 0
        self.closed = False

    def submit(self, session_id, text, cancellation):
        return f"reply:{session_id}:{text}"

    def interrupt(self, session_id):
        self.interrupts += 1

    def close(self):
        self.closed = True


class ServerRuntimeTests(unittest.TestCase):
    def test_environment_settings_are_explicit_and_split(self):
        settings = settings_from_environment({
            "VOICE_AGENT_HOME": "/tmp/voice-agent",
            "VOICE_AGENT_PI_COMMAND": "pi --mode rpc",
            "VOICE_AGENT_PI_SESSION_DIR": "/tmp/pi-sessions",
        })
        self.assertEqual(settings.socket_path, Path("/tmp/voice-agent/voice-agent.sock"))
        self.assertEqual(settings.state_path, Path("/tmp/voice-agent/sessions.json"))
        self.assertEqual(settings.pi_command, ("pi", "--mode", "rpc"))
        self.assertEqual(settings.pi_session_dir, Path("/tmp/pi-sessions"))

    def test_coordinator_reuses_one_backend_per_session_and_closes_it(self):
        created = []

        def factory(session_id):
            backend = FakeBackend(session_id)
            created.append(backend)
            return backend

        coordinator = PiSessionCoordinator(factory)
        result = coordinator.submit("s1", "hello", threading.Event())
        self.assertEqual(result, TurnResult("s1", "reply:s1:hello"))
        coordinator.submit("s1", "again", threading.Event())
        coordinator.submit("s2", "other", threading.Event())
        self.assertEqual([backend.session_id for backend in created], ["s1", "s2"])
        coordinator.interrupt("s1")
        self.assertEqual(created[0].interrupts, 1)
        coordinator.close()
        self.assertTrue(all(backend.closed for backend in created))

    def test_unix_socket_server_returns_cancelled_voice_turn_error(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "voice-agent.sock"
            core = DaemonCore(
                JsonSessionRegistry(Path(directory) / "sessions.json"),
                _UnusedCoordinator(),
                voice_coordinator=_CancelledVoiceCoordinator(),
            )
            server = JsonLineUnixServer(socket_path, core)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.assertTrue(server.ready.wait(timeout=2))
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                client.sendall(b'{"op":"voice_turn","session_id":"voice-main"}\n')
                response = json.loads(client.makefile("rb").readline())
            self.assertEqual(response, {"ok": False, "error": "voice turn cancelled during audio_input"})
            server.close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_unix_socket_server_round_trips_json_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            socket_path = Path(directory) / "voice-agent.sock"
            core = DaemonCore(JsonSessionRegistry(Path(directory) / "sessions.json"), _UnusedCoordinator())
            server = JsonLineUnixServer(socket_path, core)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.assertTrue(server.ready.wait(timeout=2))
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                client.sendall(b'{"op":"sessions"}\n')
                response = json.loads(client.makefile("rb").readline())
            self.assertEqual(response, {"ok": True, "sessions": []})
            server.close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())


class _CancelledVoiceCoordinator:
    def run(self, session_id, cancellation):
        raise VoiceTurnCancelled("audio_input")


class _UnusedCoordinator:
    def submit(self, session_id, text, cancellation):
        return TurnResult(session_id, text)

    def interrupt(self, session_id):
        pass


if __name__ == "__main__":
    unittest.main()
