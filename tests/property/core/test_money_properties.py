"""Property contracts for Decimal persistence and quantity rounding."""

from decimal import Decimal

from hypothesis import assume, given
from hypothesis import strategies as st

from omra.core import from_text, qty_floor, to_text

_FINITE_DECIMALS = st.decimals(
    allow_nan=False,
    allow_infinity=False,
    places=12,
)
_POSITIVE_STEPS = st.decimals(
    min_value=Decimal("0.00000001"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=8,
)


@given(value=_FINITE_DECIMALS)
def test_decimal_text_round_trip_has_no_exponent_notation(value: Decimal) -> None:
    assume(not (value.is_zero() and value.is_signed()))

    rendered = to_text(value)

    assert "e" not in rendered.lower()
    assert from_text(rendered) == value
    assert from_text(rendered).as_tuple().exponent == value.as_tuple().exponent


@given(
    qty=st.decimals(
        min_value=Decimal("0"),
        max_value=Decimal("1000000000"),
        allow_nan=False,
        allow_infinity=False,
        places=8,
    ),
    step=_POSITIVE_STEPS,
)
def test_qty_floor_is_aligned_bounded_and_idempotent(qty: Decimal, step: Decimal) -> None:
    result = qty_floor(qty, step)

    assert Decimal(0) <= result <= qty
    assert result % step == 0
    assert qty - result < step
    assert qty_floor(result, step) == result
