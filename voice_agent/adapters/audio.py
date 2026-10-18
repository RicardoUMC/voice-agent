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
            while not cancellation.is_set():
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
            if cancellation.is_set():
                process.terminate()
                raise ProviderCancelledError("audio capture cancelled")
            if process.wait() != 0:
                raise ProviderRequestError("audio capture failed")
        finally:
            if process.poll() is None:
                process.terminate()


class SoxAudioOutput:
    def __init__(self, config: AudioConfig = AudioConfig(), popen: Callable = subprocess.Popen) -> None:
        self.config, self._popen = config, popen

    def play(self, chunks: Iterable[bytes], cancellation: Cancellation) -> None:
        if cancellation.is_set():
            raise ProviderCancelledError("audio playback cancelled")
        command = (*self.config.playback_command, "-q", "-t", "raw", "-b", "16", "-e", "signed-integer", "-c", str(self.config.channels), "-r", str(self.config.sample_rate), "-")
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
