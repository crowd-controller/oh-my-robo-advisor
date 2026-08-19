"""Unit contracts for structured OMRA errors."""

from omra.audit import AuditError, AuditWriteError
from omra.core import InvariantViolation, OmraError, PersistenceError


def test_omra_error_exposes_stable_audit_payload_without_aliasing_context() -> None:
    context = {"field": "amount"}
    error = InvariantViolation("amount is invalid", context=context)
    context["field"] = "changed"

    assert error.code == "domain.invariant_violation"
    assert error.retryable is False
    assert error.to_audit_payload() == {
        "code": "domain.invariant_violation",
        "message": "amount is invalid",
        "retryable": False,
        "context": {"field": "amount"},
    }
    assert isinstance(error, OmraError)


def test_audit_write_error_belongs_to_the_persistence_error_hierarchy() -> None:
    error = AuditWriteError("disk unavailable")

    assert error.code == "audit.write_error"
    assert isinstance(error, AuditError)
    assert isinstance(error, PersistenceError)
    assert isinstance(error, OmraError)
