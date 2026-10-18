import threading
import unittest

from voice_agent.voice import VoiceTurnCancelled, VoiceTurnCoordinator, VoiceTurnError


class FakeInput:
    def __init__(self, calls, chunks=(b"pcm",)):
        self.calls, self.chunks = calls, chunks

    def capture(self, cancellation):
        self.calls.append(("input", cancellation))
        yield from self.chunks


class FakeSTT:
    def __init__(self, calls, text="hola"):
        self.calls, self.text = calls, text

    def transcribe(self, chunks, cancellation):
        self.calls.append(("stt", tuple(chunks), cancellation))
        return self.text


class FakeConversation:
    def __init__(self, calls, response="respuesta", cancel=False):
        self.calls, self.response, self.cancel = calls, response, cancel

    def submit(self, session_id, text, cancellation):
        self.calls.append(("conversation", session_id, text, cancellation))
        if self.cancel:
            cancellation.set()
        return self.response


class FakeTTS:
    def __init__(self, calls):
        self.calls = calls

    def synthesize(self, text, cancellation):
        self.calls.append(("tts", text, cancellation))
        return b"speech"


class FakeOutput:
    def __init__(self, calls):
        self.calls = calls

    def play(self, chunks, cancellation):
        self.calls.append(("output", tuple(chunks), cancellation))


class PipelineTests(unittest.TestCase):
    def make_coordinator(self, calls, events, conversation=None):
        return VoiceTurnCoordinator(
            FakeInput(calls),
            FakeSTT(calls),
            conversation or FakeConversation(calls),
            FakeTTS(calls),
            FakeOutput(calls),
            on_event=events.append,
        )

    def test_success_orders_stages_and_preserves_session_id(self):
        calls, events = [], []
        result = self.make_coordinator(calls, events).run("session-7")

        self.assertEqual(result.session_id, "session-7")
        self.assertEqual(result.transcript, "hola")
        self.assertEqual(result.response, "respuesta")
        self.assertEqual([item[0] for item in calls], ["input", "stt", "conversation", "tts", "output"])
        self.assertEqual([event.name for event in events], [
            "turn_started", "stage_started", "stage_completed",
            "stage_started", "stage_completed", "stage_started", "stage_completed",
            "stage_started", "stage_completed", "stage_started", "stage_completed",
            "turn_completed",
        ])
        self.assertTrue(all(event.session_id == "session-7" for event in events))
        self.assertIs(calls[2][3], calls[0][1])

    def test_cancellation_stops_following_stages_and_is_observable(self):
        calls, events = [], []
        token = threading.Event()
        coordinator = self.make_coordinator(calls, events, FakeConversation(calls, cancel=True))

        with self.assertRaises(VoiceTurnCancelled) as raised:
            coordinator.run("session-cancel", token)

        self.assertEqual(raised.exception.stage, "conversation")
        self.assertEqual([item[0] for item in calls], ["input", "stt", "conversation"])
        self.assertEqual(events[-1].name, "turn_cancelled")
        self.assertIs(calls[2][3], token)

    def test_provider_failure_is_redacted_and_ordered(self):
        calls, events = [], []

        class FailingSTT(FakeSTT):
            def transcribe(self, chunks, cancellation):
                self.calls.append(("stt", tuple(chunks), cancellation))
                raise RuntimeError("api-key=super-secret")

        coordinator = VoiceTurnCoordinator(
            FakeInput(calls), FailingSTT(calls), FakeConversation(calls), FakeTTS(calls), FakeOutput(calls),
            on_event=events.append,
        )
        with self.assertRaises(VoiceTurnError) as raised:
            coordinator.run("session-failure")

        self.assertEqual(str(raised.exception), "voice turn failed during stt")
        self.assertNotIn("super-secret", str(raised.exception))
        self.assertEqual([event.name for event in events], [
            "turn_started", "stage_started", "stage_completed",
            "stage_started", "turn_failed",
        ])
        self.assertEqual(events[-1].stage, "stt")


if __name__ == "__main__":
    unittest.main()
