"""Unit contracts for structured OMRA errors."""

from omra.core import InvariantViolation, OmraError


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
