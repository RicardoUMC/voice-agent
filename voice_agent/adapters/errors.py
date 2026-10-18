"""Stable errors exposed by adapter boundaries."""


class AdapterError(Exception):
    """Base class for expected adapter failures."""


class ConfigurationError(AdapterError, ValueError):
    """Configuration is missing or invalid."""


class ProviderError(AdapterError):
    """A provider rejected a request or returned an unusable result."""


class ProviderRequestError(ProviderError):
    """A provider request failed after it was sent."""


class AdapterUnavailableError(ProviderError):
    """An optional executable or Python provider is not available."""


class ProviderCancelledError(ProviderError):
    """The caller cancelled an in-flight adapter operation."""
