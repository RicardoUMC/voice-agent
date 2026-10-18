"""Provider-neutral orchestration for one cancellable voice turn."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
import threading
from typing import Any, Protocol

from voice_agent.adapters.errors import ProviderCancelledError
from voice_agent.adapters.protocols import AudioInput, AudioOutput, Cancellation, SpeechToText, TextToSpeech


class ConversationBackend(Protocol):
    def submit(self, session_id: str, text: str, cancellation: Cancellation) -> str: ...


@dataclass(frozen=True)
class LifecycleEvent:
    """Safe, structured observability data; it intentionally has no exception text."""

    name: str
    session_id: str
    stage: str


@dataclass(frozen=True)
class VoiceTurnResult:
    session_id: str
    transcript: str
    response: str


class VoiceTurnError(Exception):
    """Stable, deliberately redacted failure from the voice pipeline."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"voice turn failed during {stage}")


class VoiceTurnCancelled(VoiceTurnError):
    """The caller cancelled the turn."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.args = (f"voice turn cancelled during {stage}",)


EventCallback = Callable[[LifecycleEvent], Any]


class VoiceTurnCoordinator:
    """Compose audio input, STT, conversation, TTS, and audio output.

    All dependencies are injected and the coordinator has no transport or provider
    knowledge. One coordinator instance may be used for multiple session IDs, but
    callers should serialize turns for a given session.
    """

    def __init__(
        self,
        audio_input: AudioInput,
        stt: SpeechToText,
        conversation: ConversationBackend,
        tts: TextToSpeech,
        audio_output: AudioOutput,
        *,
        on_event: EventCallback | None = None,
    ) -> None:
        self.audio_input = audio_input
        self.stt = stt
        self.conversation = conversation
        self.tts = tts
        self.audio_output = audio_output
        self.on_event = on_event

    def run(self, session_id: str, cancellation: Cancellation | None = None) -> VoiceTurnResult:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id is required")
        token = cancellation or threading.Event()
        stage = "audio_input"
        self._emit("turn_started", session_id, stage)
        try:
            self._check_cancelled(token, stage)
            self._emit("stage_started", session_id, stage)
            chunks = self.audio_input.capture(token)
            # Materialize here so capture failures stay within the input stage and
            # the same captured audio can be handed to exactly one STT invocation.
            audio = tuple(chunks)
            self._check_cancelled(token, stage)
            self._emit("stage_completed", session_id, stage)

            stage = "stt"
            self._emit("stage_started", session_id, stage)
            transcript = self.stt.transcribe(audio, token)
            self._check_cancelled(token, stage)
            self._emit("stage_completed", session_id, stage)

            stage = "conversation"
            self._emit("stage_started", session_id, stage)
            response = self.conversation.submit(session_id, transcript, token)
            self._check_cancelled(token, stage)
            self._emit("stage_completed", session_id, stage)

            stage = "tts"
            self._emit("stage_started", session_id, stage)
            speech = self.tts.synthesize(response, token)
            self._check_cancelled(token, stage)
            self._emit("stage_completed", session_id, stage)

            stage = "audio_output"
            self._emit("stage_started", session_id, stage)
            self.audio_output.play((speech,), token)
            self._check_cancelled(token, stage)
            self._emit("stage_completed", session_id, stage)
            self._emit("turn_completed", session_id, stage)
            return VoiceTurnResult(session_id, transcript, response)
        except VoiceTurnCancelled:
            self._emit("turn_cancelled", session_id, stage)
            raise
        except Exception as exc:
            if self._is_cancelled(token) or isinstance(exc, ProviderCancelledError):
                self._emit("turn_cancelled", session_id, stage)
                raise VoiceTurnCancelled(stage) from exc
            self._emit("turn_failed", session_id, stage)
            raise VoiceTurnError(stage) from exc

    def _emit(self, name: str, session_id: str, stage: str) -> None:
        if self.on_event is not None:
            try:
                self.on_event(LifecycleEvent(name, session_id, stage))
            except Exception:
                # Observability must never change turn behavior.
                pass

    @staticmethod
    def _is_cancelled(token: Cancellation) -> bool:
        return bool(token.is_set())

    def _check_cancelled(self, token: Cancellation, stage: str) -> None:
        if self._is_cancelled(token):
            raise VoiceTurnCancelled(stage)
