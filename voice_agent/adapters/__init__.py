"""Provider-neutral adapters for the voice agent."""

from .config import AdapterConfig, AudioConfig, DeepgramConfig, KittenTTSConfig
from .errors import (
    AdapterError,
    AdapterUnavailableError,
    ConfigurationError,
    ProviderError,
    ProviderRequestError,
    ProviderCancelledError,
)

__all__ = [
    "AdapterConfig",
    "AudioConfig",
    "DeepgramConfig",
    "KittenTTSConfig",
    "AdapterError",
    "AdapterUnavailableError",
    "ConfigurationError",
    "ProviderError",
    "ProviderRequestError",
    "ProviderCancelledError",
]
