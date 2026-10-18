"""Optional KittenTTS 2 (emb4-compatible) synthesis boundary."""

from collections.abc import Callable
import io
import wave

from .config import KittenTTSConfig
from .errors import AdapterUnavailableError, ProviderCancelledError, ProviderRequestError
from .protocols import Cancellation


class KittenTTS:
    """Synthesize PCM WAV bytes without importing or downloading a model at import time.

    ``loader`` and ``synthesizer`` are injectable so tests and deployments can choose
    the installed KittenTTS 2 runtime. The default loader is intentionally lazy.
    """

    def __init__(self, config: KittenTTSConfig = KittenTTSConfig(), loader: Callable | None = None) -> None:
        self.config = config
        self._loader = loader or self._load_model
        self._model = None

    @staticmethod
    def _load_model(model_name: str, weights: str):
        try:
            from kittenml import KittenTTS as KittenModel  # optional dependency
        except ImportError as exc:
            raise AdapterUnavailableError("KittenTTS is not installed") from exc
        try:
            return KittenModel(model_name, weights=weights)
        except Exception as exc:
            raise ProviderRequestError("KittenTTS model could not be loaded") from exc

    def synthesize(self, text: str, cancellation: Cancellation) -> bytes:
        if cancellation.is_set():
            raise ProviderCancelledError("KittenTTS request cancelled")
        if not text.strip():
            raise ProviderRequestError("KittenTTS requires non-empty text")
        try:
            if self._model is None:
                self._model = self._loader(self.config.model, self.config.weights)
            if cancellation.is_set():
                raise ProviderCancelledError("KittenTTS request cancelled")
            samples = self._model.generate(text, voice=self.config.voice)
            return self._wav(samples)
        except ProviderCancelledError:
            raise
        except (AdapterUnavailableError, ProviderRequestError):
            raise
        except Exception as exc:
            raise ProviderRequestError("KittenTTS synthesis failed") from exc

    def _wav(self, samples) -> bytes:
        # numpy is optional too; accepting any iterable keeps the adapter testable.
        values = [max(-1.0, min(1.0, float(value))) for value in samples]
        pcm = b"".join(int(value * 32767).to_bytes(2, "little", signed=True) for value in values)
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.config.sample_rate)
            wav.writeframes(pcm)
        return output.getvalue()
