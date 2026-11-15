class ServiceConfigurationError(RuntimeError):
    """Required production service configuration is missing."""


class ExternalServiceError(RuntimeError):
    """A real AWS service call failed or returned an invalid result."""
