import json
import threading
import unittest

from voice_agent.adapters.errors import ProviderCancelledError, ProviderRequestError
from voice_agent.conversation.pi_rpc import PiRpcConfig, PiRpcConversationBackend


class FakeStream:
    def __init__(self):
        self.lines = []
        self.history = []
        self.condition = threading.Condition()
        self.closed = False

    def write(self, data):
        message = json.loads(data.decode())
        with self.condition:
            self.history.append(message)
            self.lines.append(message)
            self.condition.notify_all()
        return len(data)

    def flush(self):
        pass

    def readline(self):
        with self.condition:
            while not self.lines and not self.closed:
                self.condition.wait(1)
            if self.lines:
                message = self.lines.pop(0)
                return (json.dumps(message) + "\n").encode()
            return b""

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()


class FakeProcess:
    def __init__(self):
        self.stdin = FakeStream()
        self.stdout = FakeStream()
        self.stderr = FakeStream()
        self.returncode = None
        self._thread = threading.Thread(target=self._respond, daemon=True)
        self._thread.start()

    def _respond(self):
        while not self.stdin.closed:
            with self.stdin.condition:
                while not self.stdin.lines and not self.stdin.closed:
                    self.stdin.condition.wait(1)
                if self.stdin.closed:
                    return
                command = self.stdin.lines.pop(0)
            response = self._response(command)
            if response is not None:
                self.stdout.write((json.dumps(response) + "\n").encode())

    def _response(self, command):
        if command["type"] == "get_state":
            return {"type": "response", "command": "get_state", "id": command["id"], "success": True}
        if command["type"] == "prompt":
            self.stdout.write((json.dumps({"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "hola"}}) + "\n").encode())
            self.stdout.write((json.dumps({"type": "agent_settled"}) + "\n").encode())
        return {"type": "response", "command": command["type"], "id": command["id"], "success": True}

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0
        self.stdin.close()
        self.stdout.close()
        self.stderr.close()


class PiRpcTests(unittest.TestCase):
    def test_session_id_matches_pi_persistence_identifier_rules(self):
        with self.assertRaises(ValueError):
            PiRpcConfig(session_id="../unsafe")

    def test_session_flags_are_appended_to_injected_base_command(self):
        process = FakeProcess()
        seen = []
        backend = PiRpcConversationBackend(
            PiRpcConfig(command=("fake-pi", "--mode", "rpc"), session_id="conversation-7", session_dir="/tmp/pi-sessions"),
            process_factory=lambda command: (seen.append(command) or process),
            startup_timeout=1,
        )
        self.assertEqual(seen, [("fake-pi", "--mode", "rpc", "--session-id", "conversation-7", "--session-dir", "/tmp/pi-sessions")])
        backend.close()

    def test_pi_rpc_streams_deltas_and_confirms_readiness(self):
        process = FakeProcess()
        backend = PiRpcConversationBackend(process_factory=lambda _: process, startup_timeout=1)
        self.assertEqual(backend.complete("hola", threading.Event()), "hola")
        backend.close()

    def test_pi_rpc_maps_bad_response(self):
        class BadProcess(FakeProcess):
            def _response(self, command):
                return {"type": "response", "command": command["type"], "id": command["id"], "success": False, "error": "no"}

        with self.assertRaises(ProviderRequestError):
            PiRpcConversationBackend(process_factory=lambda _: BadProcess(), startup_timeout=1)

    def test_pi_rpc_cancellation_clears_queue_then_aborts(self):
        process = FakeProcess()
        token = threading.Event()
        backend = PiRpcConversationBackend(process_factory=lambda _: process, startup_timeout=1)
        token.set()
        with self.assertRaises(ProviderCancelledError):
            backend.complete("hola", token)
        types = [item["type"] for item in process.stdin.history]
        self.assertEqual(types[-2:], ["clear_queue", "abort"])
        backend.close()


if __name__ == "__main__":
    unittest.main()
