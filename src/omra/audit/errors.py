"""Audit persistence exception hierarchy."""

from omra.core import PersistenceError


class AuditError(PersistenceError):
    """Base class for audit validation, read, and write failures."""

    default_code = "audit.error"


class AuditValidationError(AuditError):
    """An event cannot satisfy the canonical audit schema."""

    default_code = "audit.validation_error"


class AuditWriteError(AuditError):
    """An audit event could not be durably appended."""

    default_code = "audit.write_error"


class AuditReadError(AuditError):
    """An audit line cannot be decoded under a supported schema."""

    default_code = "audit.read_error"
