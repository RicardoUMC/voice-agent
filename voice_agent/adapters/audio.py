"""SoX/PipeWire-compatible audio boundaries."""

from collections.abc import Iterable, Iterator, Callable
import subprocess

from .config import AudioConfig
from .errors import AdapterUnavailableError, ProviderCancelledError, ProviderRequestError
from .protocols import Cancellation


class SoxAudioInput:
    def __init__(self, config: AudioConfig = AudioConfig(), popen: Callable = subprocess.Popen) -> None:
        self.config, self._popen = config, popen

    def capture(self, cancellation: Cancellation) -> Iterator[bytes]:
        if cancellation.is_set():
            raise ProviderCancelledError("audio capture cancelled")
        command = (*self.config.capture_command, "-q", "-t", "raw", "-b", "16", "-e", "signed-integer", "-c", str(self.config.channels), "-r", str(self.config.sample_rate), "-")
        try:
            process = self._popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise AdapterUnavailableError("audio capture executable is unavailable") from exc
        try:
            silent_seconds = 0.0
            speech_seen = False
            captured_seconds = 0.0
            while not cancellation.is_set():
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
                if self._stop_requested(cancellation):
                    break
                if self.config.vad_enabled:
                    duration = len(chunk) / (self.config.sample_rate * self.config.channels * self.config.sample_width)
                    captured_seconds += duration
                    if self._is_silent(chunk):
                        if speech_seen:
                            silent_seconds += duration
                            if silent_seconds >= self.config.silence_duration:
                                break
                    else:
                        speech_seen = True
                        silent_seconds = 0.0
                    if captured_seconds >= self.config.max_capture_duration:
                        break
            if cancellation.is_set():
                process.terminate()
                raise ProviderCancelledError("audio capture cancelled")
            if process.wait() != 0:
                raise ProviderRequestError("audio capture failed")
        finally:
            if process.poll() is None:
                process.terminate()

    def _is_silent(self, chunk: bytes) -> bool:
        width = self.config.sample_width
        if len(chunk) < width:
            return True
        return max(
            abs(int.from_bytes(chunk[offset : offset + width], "little", signed=True))
            for offset in range(0, len(chunk) - width + 1, width)
        ) <= self.config.silence_threshold

    @staticmethod
    def _stop_requested(cancellation: Cancellation) -> bool:
        stop_requested = getattr(cancellation, "stop_requested", None)
        return bool(stop_requested()) if callable(stop_requested) else False


class SoxAudioOutput:
    def __init__(self, config: AudioConfig = AudioConfig(), popen: Callable = subprocess.Popen) -> None:
        self.config, self._popen = config, popen

    def play(self, chunks: Iterable[bytes], cancellation: Cancellation) -> None:
        if cancellation.is_set():
            raise ProviderCancelledError("audio playback cancelled")
        if self.config.playback_format == "wav":
            command = (*self.config.playback_command, "-q", "-")
        else:
            command = (*self.config.playback_command, "-q", "-t", "raw", "-b", str(self.config.sample_width * 8), "-e", "signed-integer", "-c", str(self.config.channels), "-r", str(self.config.sample_rate), "-")
        try:
            process = self._popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as exc:
            raise AdapterUnavailableError("audio playback executable is unavailable") from exc
        try:
            for chunk in chunks:
                if cancellation.is_set():
                    raise ProviderCancelledError("audio playback cancelled")
                process.stdin.write(chunk)
            process.stdin.close()
            if process.wait() != 0:
                raise ProviderRequestError("audio playback failed")
        except BrokenPipeError as exc:
            raise ProviderRequestError("audio playback failed") from exc
        finally:
            if process.poll() is None:
                process.terminate()
