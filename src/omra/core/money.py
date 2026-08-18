"""Decimal-only persistence, rounding, and budget primitives."""

from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Annotated

from pydantic import BeforeValidator

from omra.core.errors import InvariantViolation, LotStepError

_ONE = Decimal(1)


def _reject_float(value: object) -> object:
    if isinstance(value, float):
        msg = "float input is forbidden for Decimal domain values"
        raise ValueError(msg)
    return value


Dec = Annotated[Decimal, BeforeValidator(_reject_float)]


def _require_finite(value: Decimal, *, field: str) -> None:
    if not value.is_finite():
        raise InvariantViolation(
            f"{field} must be finite",
            context={"field": field, "value": str(value)},
        )


def to_text(value: Decimal) -> str:
    """Serialize a finite Decimal without exponent notation, preserving scale."""
    _require_finite(value, field="decimal")
    if value.is_zero() and value.is_signed():
        raise InvariantViolation(
            "signed zero is not a canonical Decimal representation",
            context={"value": str(value)},
        )
    return format(value, "f")


def from_text(value: str) -> Decimal:
    """Deserialize persisted Decimal text and enforce value invariants."""
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise InvariantViolation(
            "invalid persisted Decimal text",
            context={"value": value},
        ) from error
    _require_finite(parsed, field="decimal")
    if parsed.is_zero() and parsed.is_signed():
        raise InvariantViolation(
            "signed zero is not a canonical Decimal representation",
            context={"value": value},
        )
    return parsed


def krw_floor(value: Decimal) -> Decimal:
    """Truncate a KRW amount toward zero at the one-won boundary."""
    _require_finite(value, field="krw")
    return value.to_integral_value(rounding=ROUND_DOWN)


def qty_floor(qty: Decimal, lot_step: Decimal) -> Decimal:
    """Floor a non-negative quantity to its positive lot-step grid."""
    _require_finite(qty, field="qty")
    _require_finite(lot_step, field="lot_step")
    if lot_step <= 0:
        raise LotStepError(
            "lot_step must be positive",
            context={"lot_step": str(lot_step)},
        )
    if qty < 0:
        raise LotStepError(
            "quantity must be non-negative",
            context={"qty": str(qty)},
        )
    units = (qty / lot_step).to_integral_value(rounding=ROUND_DOWN)
    return units * lot_step


def usd_budget(krw: Decimal, fx_rate: Decimal, buffer: Decimal) -> Decimal:
    """Convert KRW conservatively using V / (fx * (1 + buffer))."""
    _require_finite(krw, field="krw")
    _require_finite(fx_rate, field="fx_rate")
    _require_finite(buffer, field="buffer")
    if fx_rate <= 0:
        raise InvariantViolation(
            "fx_rate must be positive",
            context={"fx_rate": str(fx_rate)},
        )
    multiplier = _ONE + buffer
    if multiplier <= 0:
        raise InvariantViolation(
            "buffer must be greater than -1",
            context={"buffer": str(buffer)},
        )
    return krw / (fx_rate * multiplier)
