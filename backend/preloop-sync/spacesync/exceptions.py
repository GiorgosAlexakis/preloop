"""
Custom exceptions for SpaceSync.
"""


class SpaceSyncError(Exception):
    """Base exception for all SpaceSync errors."""

    pass


class ConfigurationError(SpaceSyncError):
    """Raised when there's an issue with the configuration."""

    pass


class DatabaseError(SpaceSyncError):
    """Raised when there's an issue with the database operations."""

    pass


class TrackerError(SpaceSyncError):
    """Base exception for all tracker-related errors."""

    pass


class TrackerAuthenticationError(TrackerError):
    """Raised when there's an authentication issue with a tracker."""

    pass


class TrackerConnectionError(TrackerError):
    """Raised when there's a connection issue with a tracker."""

    pass


class TrackerRateLimitError(TrackerError):
    """Raised when a tracker API rate limit is hit."""

    pass


class TrackerResponseError(TrackerError):
    """Raised when a tracker API returns an error response."""

    pass


class EmbeddingError(SpaceSyncError):
    """Raised when there's an issue with generating embeddings."""

    pass
