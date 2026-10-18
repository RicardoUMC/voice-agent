"""Dependency-injection contracts for audio and speech providers."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol
import threading


class Cancellation(Protocol):
    def is_set(self) -> bool: ...


@dataclass(frozen=True)
class AudioFormat:
    sample_rate: int = 16_000
    channels: int = 1
    sample_width: int = 2


class AudioInput(Protocol):
    def capture(self, cancellation: Cancellation) -> Iterator[bytes]: ...


class AudioOutput(Protocol):
    def play(self, chunks: Iterable[bytes], cancellation: Cancellation) -> None: ...


class SpeechToText(Protocol):
    def transcribe(self, chunks: Iterable[bytes], cancellation: Cancellation) -> str: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str, cancellation: Cancellation) -> bytes: ...


def cancelled(cancellation: Cancellation) -> bool:
    return cancellation.is_set()


def new_cancellation() -> threading.Event:
    """Return the standard cancellation token used by the adapters."""
    return threading.Event()
