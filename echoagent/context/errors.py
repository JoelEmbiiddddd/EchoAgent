class ContextError(Exception):
    """Base error for context operations."""


class SnapshotError(ContextError):
    """Raised when snapshot serialization fails."""
