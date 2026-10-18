"""Deepgram Nova-3 adapter with an injectable network transport.

The bundled HTTP transport is intentionally non-streaming for now: it buffers
PCM and sends one request. Pi's streaming WebSocket baseline can be supplied as
an injected transport without changing the STT adapter contract.
"""

from collections.abc import Iterable, Callable
import json
import urllib.error
import urllib.request

from .config import DeepgramConfig
from .errors import ProviderCancelledError, ProviderRequestError, AdapterUnavailableError
from .protocols import Cancellation


class DeepgramHttpTransport:
    def __call__(self, payload: bytes, config: DeepgramConfig, cancellation: Cancellation) -> str:
        if cancellation.is_set():
            raise ProviderCancelledError("Deepgram request cancelled")
        request = urllib.request.Request(
            "https://api.deepgram.com/v1/listen?model=" + config.model + "&language=" + config.language,
            data=payload,
            headers={"Authorization": f"Token {config.api_key}", "Content-Type": "audio/raw;encoding=linear16;sample_rate=16000;channels=1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
            return body["results"]["channels"][0]["alternatives"][0]["transcript"]
        except urllib.error.URLError as exc:
            raise ProviderRequestError("Deepgram request failed") from exc
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise ProviderRequestError("Deepgram returned an invalid response") from exc


class DeepgramSTT:
    def __init__(self, config: DeepgramConfig, transport: Callable | None = None) -> None:
        self.config = config
        # The default transport imports only stdlib; an SDK can be supplied by callers.
        self._transport = transport or DeepgramHttpTransport()

    def transcribe(self, chunks: Iterable[bytes], cancellation: Cancellation) -> str:
        if cancellation.is_set():
            raise ProviderCancelledError("Deepgram request cancelled")
        try:
            payload = b"".join(chunks)
            if cancellation.is_set():
                raise ProviderCancelledError("Deepgram request cancelled")
            return self._transport(payload, self.config, cancellation)
        except ProviderCancelledError:
            raise
        except (ProviderRequestError, AdapterUnavailableError):
            raise
        except Exception as exc:
            raise ProviderRequestError("Deepgram provider failed") from exc
