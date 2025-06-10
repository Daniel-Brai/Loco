"""Custom exceptions for the tunnel manager."""


class TunnelError(Exception):
    """Base exception for tunnel-related errors."""

    pass


class TunnelNotFoundError(TunnelError):
    """Raised when a tunnel is not found."""

    pass


class TunnelStartupError(TunnelError):
    """Raised when a tunnel fails to start."""

    pass


class TunnelConfigError(TunnelError):
    """Raised when tunnel configuration is invalid."""

    pass


class StorageError(TunnelError):
    """Raised when storage operations fail."""

    pass
