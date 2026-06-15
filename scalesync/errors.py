"""Custom exceptions for ScaleSync."""


class ScaleSyncError(RuntimeError):
    """Base exception for all ScaleSync errors."""


class UnsupportedFormatError(ScaleSyncError):
    """Raised when the file extension has no registered handler."""


class ValidationError(ScaleSyncError):
    """Raised when an asset fails scale validation checks."""