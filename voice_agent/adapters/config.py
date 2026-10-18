"""Validated, provider-specific adapter configuration."""

from dataclasses import dataclass, field
import os

from .errors import ConfigurationError


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16_000
    channels: int = 1
    sample_width: int = 2
    capture_command: tuple[str, ...] = ("rec",)
    playback_command: tuple[str, ...] = ("play",)
    playback_format: str = "wav"

    def __post_init__(self) -> None:
        if self.sample_rate <= 0 or self.channels <= 0 or self.sample_width <= 0:
            raise ConfigurationError("audio dimensions must be positive")
        if self.playback_format not in {"wav", "raw"}:
            raise ConfigurationError("playback_format must be 'wav' or 'raw'")


@dataclass(frozen=True)
class DeepgramConfig:
    api_key: str = field(repr=False)
    model: str = "nova-3"
    language: str = "es-419"
    sample_rate: int = 16_000
    channels: int = 1

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise ConfigurationError("Deepgram API key is required")
        if self.sample_rate <= 0 or self.channels != 1:
            raise ConfigurationError("Deepgram audio must be positive-rate mono PCM")

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "DeepgramConfig":
        env = os.environ if environ is None else environ
        key = env.get("DEEPGRAM_API_KEY", "")
        return cls(
            api_key=key,
            model=env.get("DEEPGRAM_MODEL", "nova-3"),
            language=env.get("DEEPGRAM_LANGUAGE", "es-419"),
        )


@dataclass(frozen=True)
class KittenTTSConfig:
    model: str = "KittenML/kitten-tts-2"
    weights: str = "emb4"
    voice: str = "Spanish"
    sample_rate: int = 24_000

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.weights.strip() or not self.voice.strip() or self.sample_rate <= 0:
            raise ConfigurationError("KittenTTS model, weights, voice, and sample rate are required")


@dataclass(frozen=True)
class AdapterConfig:
    audio: AudioConfig = AudioConfig()
    deepgram: DeepgramConfig | None = None
    kitten_tts: KittenTTSConfig = KittenTTSConfig()
