import json
import tempfile
import threading
import unittest
from pathlib import Path

from voice_agent.daemon.config import DaemonConfig
from voice_agent.daemon.core import DaemonCore
from voice_agent.daemon.sessions import JsonSessionRegistry, SessionStateError
from voice_agent.daemon.types import TurnResult
from voice_agent.voice.pipeline import VoiceTurnResult


class FakeCoordinator:
    def __init__(self):
        self.calls = []
        self.interrupts = []

    def submit(self, session_id, text, cancellation):
        self.calls.append((session_id, text, cancellation))
        return TurnResult(session_id=session_id, text="reply")

    def interrupt(self, session_id):
        self.interrupts.append(session_id)


class FailingCoordinator(FakeCoordinator):
    def submit(self, session_id, text, cancellation):
        raise RuntimeError("provider failed")


class BlockingCoordinator(FakeCoordinator):
    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def submit(self, session_id, text, cancellation):
        self.calls.append((session_id, text, cancellation))
        if session_id == "s1":
            self.started.set()
            self.release.wait(timeout=2)
        return TurnResult(session_id=session_id, text="reply-" + session_id)


class FailingRegistry(JsonSessionRegistry):
    def append_turn(self, session_id, user_text, assistant_text):
        raise RuntimeError("state write failed")


class FakeVoiceCoordinator:
    def __init__(self):
        self.calls = []

    def run(self, session_id, cancellation):
        self.calls.append((session_id, cancellation))
        return VoiceTurnResult(session_id, "hola", "respuesta")


class DaemonCoreTests(unittest.TestCase):
    def test_voice_turn_persists_transcript_and_response(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = JsonSessionRegistry(Path(directory) / "sessions.json")
            voice = FakeVoiceCoordinator()
            core = DaemonCore(registry, FakeCoordinator(), voice_coordinator=voice)
            response = core.handle({"op": "voice_turn", "session_id": "voice-main"})
            self.assertEqual(response, {
                "ok": True,
                "session_id": "voice-main",
                "transcript": "hola",
                "text": "respuesta",
            })
            self.assertEqual([(turn.user_text, turn.assistant_text) for turn in registry.get("voice-main").turns], [("hola", "respuesta")])

    def test_config_requires_absolute_local_paths(self):
        with self.assertRaises(ValueError):
            DaemonConfig(socket_path=Path("relative.sock"), state_path=Path("/tmp/state.json"))

    def test_sessions_survive_registry_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.json"
            first = JsonSessionRegistry(path)
            first.ensure("session-1")
            first.append_turn("session-1", "hello", "hola")

            second = JsonSessionRegistry(path)
            self.assertEqual(second.get("session-1").turns[0].user_text, "hello")
            self.assertEqual(second.list_ids(), ["session-1"])

    def test_core_routes_turns_and_interrupts_by_session(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = JsonSessionRegistry(Path(directory) / "sessions.json")
            coordinator = FakeCoordinator()
            core = DaemonCore(registry=registry, coordinator=coordinator)

            response = core.handle({"op": "turn", "session_id": "s1", "text": "hello"})
            self.assertEqual(response, {"ok": True, "session_id": "s1", "text": "reply"})
            self.assertEqual(coordinator.calls[0][0:2], ("s1", "hello"))

            self.assertEqual(core.handle({"op": "interrupt", "session_id": "s1"}), {"ok": True})
            self.assertEqual(coordinator.interrupts, ["s1"])

    def test_coordinator_failure_cleans_up_active_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            core = DaemonCore(JsonSessionRegistry(Path(directory) / "sessions.json"), FailingCoordinator())
            with self.assertRaisesRegex(RuntimeError, "provider failed"):
                core.handle({"op": "turn", "session_id": "s1", "text": "hello"})
            self.assertNotIn("s1", core._cancellations)

    def test_persistence_failure_cleans_up_active_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = FailingRegistry(Path(directory) / "sessions.json")
            core = DaemonCore(registry, FakeCoordinator())
            with self.assertRaisesRegex(RuntimeError, "state write failed"):
                core.handle({"op": "turn", "session_id": "s1", "text": "hello"})
            self.assertNotIn("s1", core._cancellations)

    def test_active_turns_are_isolated_and_interruptible(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = BlockingCoordinator()
            core = DaemonCore(JsonSessionRegistry(Path(directory) / "sessions.json"), coordinator)
            first = threading.Thread(target=core.handle, args=({"op": "turn", "session_id": "s1", "text": "one"},))
            first.start()
            self.assertTrue(coordinator.started.wait(timeout=2))

            second = core.handle({"op": "turn", "session_id": "s2", "text": "two"})
            self.assertEqual(second["session_id"], "s2")
            self.assertEqual(core.handle({"op": "interrupt", "session_id": "s1"}), {"ok": True})
            self.assertTrue(coordinator.calls[0][2].cancelled)
            self.assertEqual(coordinator.interrupts, ["s1"])
            coordinator.release.set()
            first.join(timeout=2)
            self.assertFalse(first.is_alive())

    def test_malformed_session_state_is_explicit(self):
        for content in ("not json", '{"s1": [{"user_text": "missing assistant"}]}'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "sessions.json"
                path.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(SessionStateError, "invalid session state"):
                    JsonSessionRegistry(path)

    def test_core_rejects_unknown_operations(self):
        core = DaemonCore(registry=JsonSessionRegistry(Path(tempfile.gettempdir()) / "unused-sessions.json"), coordinator=FakeCoordinator())
        with self.assertRaises(ValueError):
            core.handle({"op": "shutdown"})


if __name__ == "__main__":
    unittest.main()
