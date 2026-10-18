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
    vad_enabled: bool = True
    silence_threshold: int = 500
    silence_duration: float = 0.8
    max_capture_duration: float = 30.0

    def __post_init__(self) -> None:
        if self.sample_rate <= 0 or self.channels <= 0 or self.sample_width <= 0:
            raise ConfigurationError("audio dimensions must be positive")
        if self.playback_format not in {"wav", "raw"}:
            raise ConfigurationError("playback_format must be 'wav' or 'raw'")
        if self.silence_threshold < 0 or self.silence_duration <= 0 or self.max_capture_duration <= 0:
            raise ConfigurationError("audio endpoint values must be non-negative threshold and positive durations")

    @classmethod
    def from_environment(cls, environ: dict[str, str] | None = None) -> "AudioConfig":
        env = os.environ if environ is None else environ
        return cls(
            vad_enabled=env.get("VOICE_AGENT_VAD_ENABLED", "1").lower() not in {"0", "false", "no"},
            silence_threshold=int(env.get("VOICE_AGENT_SILENCE_THRESHOLD", "500")),
            silence_duration=float(env.get("VOICE_AGENT_SILENCE_DURATION", "0.8")),
            max_capture_duration=float(env.get("VOICE_AGENT_MAX_CAPTURE_DURATION", "30")),
        )


@dataclass(frozen=True)
class DeepgramConfig:
    api_key: str = field(repr=False)
    model: str = "nova-3"
    language: str = "es-419"
    sample_rate: int = 16_000
    channels: int = 1
    realtime_pacing: bool = True

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
