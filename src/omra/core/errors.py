"""Application-wide exception foundation."""

from collections.abc import Mapping
from typing import ClassVar


class OmraError(Exception):
    """Base class for errors handled at an OMRA process boundary."""

    default_code: ClassVar[str] = "omra.error"
    default_retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        retryable: bool | None = None,
        context: Mapping[str, str] | None = None,
    ) -> None:
        rendered = self.__class__.__name__ if message is None else message
        super().__init__(rendered)
        self.code = self.default_code if code is None else code
        self.retryable = self.default_retryable if retryable is None else retryable
        self.context = dict(context or {})

    def to_audit_payload(self) -> dict[str, object]:
        """Return the stable, structured representation used by audit boundaries."""
        return {
            "code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "context": dict(self.context),
        }


class DomainError(OmraError):
    """Base class for invalid domain values or relationships."""

    default_code = "domain.error"


class InvariantViolation(DomainError):  # noqa: N818 - canonical design name
    """A non-retryable invariant was violated."""

    default_code = "domain.invariant_violation"


class IdentifierError(DomainError):
    """A domain identifier is malformed or cannot be mapped."""

    default_code = "domain.identifier_invalid"


class LotStepError(DomainError):
    """A quantity or lot-step relationship is invalid."""

    default_code = "domain.lot_step_invalid"


class PersistenceError(OmraError):
    """Base class for durable storage and audit failures."""

    default_code = "persistence.error"
