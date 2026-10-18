"""Deepgram Nova-3 adapter with injectable HTTP and WebSocket transports."""

from collections.abc import Iterable, Callable
import json
import urllib.error
import urllib.parse
import urllib.request

from .config import DeepgramConfig
from .errors import ProviderCancelledError, ProviderRequestError, AdapterUnavailableError
from .protocols import Cancellation


class DeepgramHttpTransport:
    """Buffered fallback transport for environments without WebSocket support."""

    def __call__(self, payload: bytes, config: DeepgramConfig, cancellation: Cancellation) -> str:
        if cancellation.is_set():
            raise ProviderCancelledError("Deepgram request cancelled")
        request = urllib.request.Request(
            self._url(config, "https"),
            data=payload,
            headers={"Authorization": f"Token {config.api_key}", "Content-Type": "audio/raw;encoding=linear16;sample_rate=16000;channels=1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read())
            return _transcript_from_response(body)
        except urllib.error.URLError as exc:
            raise ProviderRequestError("Deepgram request failed") from exc
        except (KeyError, IndexError, json.JSONDecodeError, TypeError) as exc:
            raise ProviderRequestError("Deepgram returned an invalid response") from exc

    @staticmethod
    def _url(config: DeepgramConfig, scheme: str) -> str:
        params = urllib.parse.urlencode(
            {
                "model": config.model,
                "language": config.language,
                "smart_format": "true",
                "punctuate": "true",
                "endpointing": "300",
                "encoding": "linear16",
                "sample_rate": str(config.sample_rate),
                "channels": str(config.channels),
            }
        )
        return f"{scheme}://api.deepgram.com/v1/listen?{params}"


class DeepgramWebSocketTransport:
    """Streaming transport compatible with the existing Pi dictation flow."""

    def __init__(self, websocket_factory: Callable | None = None):
        self._factory = websocket_factory or self._load_factory()

    @staticmethod
    def _load_factory() -> Callable:
        try:
            import websocket
        except ImportError as exc:
            raise AdapterUnavailableError("websocket-client is required for streaming Deepgram STT") from exc
        return websocket.create_connection

    def __call__(self, chunks: Iterable[bytes], config: DeepgramConfig, cancellation: Cancellation) -> str:
        if cancellation.is_set():
            raise ProviderCancelledError("Deepgram request cancelled")
        ws = None
        try:
            url = DeepgramHttpTransport._url(config, "wss")
            ws = self._factory(url, header=[f"Authorization: Token {config.api_key}"], timeout=1)
            for chunk in chunks:
                if cancellation.is_set():
                    raise ProviderCancelledError("Deepgram request cancelled")
                ws.send(chunk, opcode=2)
            ws.send(json.dumps({"type": "CloseStream"}))
            transcripts: list[str] = []
            while True:
                if cancellation.is_set():
                    raise ProviderCancelledError("Deepgram request cancelled")
                try:
                    message = ws.recv()
                except Exception as exc:
                    if _is_timeout(exc):
                        break
                    raise ProviderRequestError("Deepgram WebSocket receive failed") from exc
                if not message:
                    break
                try:
                    value = json.loads(message)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ProviderRequestError("Deepgram returned invalid WebSocket JSON") from exc
                transcript = _transcript_from_response(value, allow_empty=True)
                if transcript:
                    transcripts.append(transcript)
                if value.get("type") == "Metadata":
                    break
            return " ".join(transcripts)
        except ProviderCancelledError:
            raise
        except (AdapterUnavailableError, ProviderRequestError):
            raise
        except Exception as exc:
            raise ProviderRequestError("Deepgram WebSocket request failed") from exc
        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass


def _transcript_from_response(value: object, allow_empty: bool = False) -> str:
    if not isinstance(value, dict):
        raise TypeError("response must be an object")
    try:
        transcript = value["results"]["channels"][0]["alternatives"][0]["transcript"]
    except (KeyError, IndexError, TypeError) as exc:
        if allow_empty and value.get("type") in {"Results", "Metadata"}:
            return ""
        raise KeyError("transcript") from exc
    if not isinstance(transcript, str):
        raise TypeError("transcript must be text")
    return transcript


def _is_timeout(error: Exception) -> bool:
    return error.__class__.__name__ in {"WebSocketTimeoutException", "TimeoutError"}


class DeepgramSTT:
    def __init__(
        self,
        config: DeepgramConfig,
        transport: Callable | None = None,
        streaming_transport: Callable | None = None,
    ) -> None:
        self.config = config
        self._transport = transport or DeepgramHttpTransport()
        self._streaming_transport = streaming_transport

    def transcribe(self, chunks: Iterable[bytes], cancellation: Cancellation) -> str:
        if cancellation.is_set():
            raise ProviderCancelledError("Deepgram request cancelled")
        try:
            if self._streaming_transport is not None:
                return self._streaming_transport(chunks, self.config, cancellation)
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
