"""Custom exception types for consistent error handling across services."""


class ConflictError(ValueError):
    """Raised when an operation conflicts with existing state (e.g., duplicates)."""
    pass
