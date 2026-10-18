import json
import unittest
from pathlib import Path

from voice_agent.client import _payload, main, request


class FakeSocket:
    def __init__(self, response):
        self.response = response
        self.sent = b""
        self.connected = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, path):
        self.connected = path

    def sendall(self, payload):
        self.sent += payload

    def makefile(self, _mode):
        class Reader:
            def __init__(self, response):
                self.response = response

            def readline(self):
                return self.response

        return Reader(self.response)


class ClientTests(unittest.TestCase):
    def test_request_sends_one_json_line_and_reads_object(self):
        fake = FakeSocket(b'{"ok":true,"sessions":[]}\n')
        response = request(
            Path("/tmp/voice-agent.sock"),
            {"op": "sessions"},
            socket_factory=lambda *_args: fake,
        )
        self.assertEqual(response, {"ok": True, "sessions": []})
        self.assertEqual(json.loads(fake.sent), {"op": "sessions"})
        self.assertEqual(fake.connected, "/tmp/voice-agent.sock")

    def test_payloads_cover_text_voice_stop_and_interrupt(self):
        self.assertEqual(_payload(type("Args", (), {"command": "turn", "session_id": "s1", "text": "hola"})()), {
            "op": "turn", "session_id": "s1", "text": "hola",
        })
        self.assertEqual(_payload(type("Args", (), {"command": "voice", "session_id": "s1"})()), {
            "op": "voice_turn", "session_id": "s1",
        })
        self.assertEqual(_payload(type("Args", (), {"command": "stop", "session_id": "s1", "operation": "stop_recording"})()), {
            "op": "stop_recording", "session_id": "s1",
        })
        self.assertEqual(_payload(type("Args", (), {"command": "interrupt", "session_id": "s1", "operation": "interrupt"})()), {
            "op": "interrupt", "session_id": "s1",
        })

    def test_main_interrupts_remote_turn_when_request_times_out(self):
        import voice_agent.client as client

        calls = []
        original = client.request

        def timed_request(_path, payload, **_kwargs):
            calls.append(payload)
            if payload["op"] == "voice_turn":
                raise TimeoutError("timed out")
            return {"ok": True}

        try:
            client.request = timed_request
            self.assertEqual(main(["voice", "s1"]), 2)
            self.assertEqual(calls, [
                {"op": "voice_turn", "session_id": "s1"},
                {"op": "interrupt", "session_id": "s1"},
            ])
        finally:
            client.request = original

    def test_main_returns_nonzero_for_daemon_error(self):
        fake = FakeSocket(b'{"ok":false,"error":"not running"}\n')
        original = __import__("voice_agent.client", fromlist=["request"]).request
        try:
            import voice_agent.client as client
            client.request = lambda *_args, **_kwargs: {"ok": False, "error": "not running"}
            self.assertEqual(main(["sessions"]), 1)
        finally:
            client.request = original


if __name__ == "__main__":
    unittest.main()
