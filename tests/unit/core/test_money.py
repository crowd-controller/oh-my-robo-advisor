"""Unit contracts for Decimal-only domain boundaries."""

from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from omra.core import (
    Dec,
    InvariantViolation,
    LotStepError,
    from_text,
    krw_floor,
    qty_floor,
    to_text,
    usd_budget,
)


class _DecimalBoundary(BaseModel):
    amount: Dec


@pytest.mark.parametrize("value", [Decimal("0.1"), "0.1", 1])
def test_dec_accepts_exact_decimal_inputs(value: object) -> None:
    parsed = _DecimalBoundary.model_validate({"amount": value})

    assert parsed.amount == Decimal(str(value))


def test_dec_rejects_float_input() -> None:
    with pytest.raises(ValidationError, match="float input is forbidden"):
        _DecimalBoundary.model_validate({"amount": 0.1})


def test_decimal_text_round_trip_preserves_fractional_scale() -> None:
    value = Decimal("1.50")

    rendered = to_text(value)

    assert rendered == "1.50"
    assert from_text(rendered).as_tuple() == value.as_tuple()


def test_decimal_text_normalizes_exponent_notation() -> None:
    assert to_text(Decimal("1E+2")) == "100"
    assert from_text("1E+2") == Decimal("100")


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_decimal_text_rejects_non_finite_values(value: Decimal) -> None:
    with pytest.raises(InvariantViolation, match="finite"):
        to_text(value)


@pytest.mark.parametrize("value", [Decimal("-0"), Decimal("-0.00")])
def test_decimal_text_rejects_signed_zero(value: Decimal) -> None:
    with pytest.raises(InvariantViolation, match="signed zero"):
        to_text(value)

    with pytest.raises(InvariantViolation, match="signed zero"):
        from_text(str(value))


def test_krw_floor_truncates_toward_zero_for_both_signs() -> None:
    assert krw_floor(Decimal("1234.9")) == Decimal("1234")
    assert krw_floor(Decimal("-1234.9")) == Decimal("-1234")


@pytest.mark.parametrize(
    ("qty", "step", "expected"),
    [
        ("12.9", "1", "12"),
        ("0.123456789", "0.00000001", "0.12345678"),
        ("0", "0.00000001", "0E-8"),
    ],
)
def test_qty_floor_snaps_down_to_lot_grid(qty: str, step: str, expected: str) -> None:
    assert qty_floor(Decimal(qty), Decimal(step)) == Decimal(expected)


@pytest.mark.parametrize(
    ("qty", "step"),
    [("1", "0"), ("1", "-1"), ("-1", "1")],
)
def test_qty_floor_rejects_invalid_domain(qty: str, step: str) -> None:
    with pytest.raises(LotStepError):
        qty_floor(Decimal(qty), Decimal(step))


def test_usd_budget_matches_the_canonical_buffer_formula() -> None:
    result = usd_budget(Decimal("1000000"), Decimal("1350"), Decimal("0.005"))

    assert result == Decimal("1000000") / (Decimal("1350") * Decimal("1.005"))


@pytest.mark.parametrize(
    ("fx_rate", "buffer"),
    [("0", "0.005"), ("-1", "0.005"), ("1350", "-1")],
)
def test_usd_budget_rejects_non_positive_denominator(fx_rate: str, buffer: str) -> None:
    with pytest.raises(InvariantViolation):
        usd_budget(Decimal("1000000"), Decimal(fx_rate), Decimal(buffer))
