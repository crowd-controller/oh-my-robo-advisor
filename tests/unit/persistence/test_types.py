"""Lossless persistence type adapter tests."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.dialects import sqlite

from omra.core.errors import InvariantViolation
from omra.persistence.types import DecimalText, KSTDateTimeText

_DIALECT = sqlite.dialect()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1.2300"), "1.2300"),
        (Decimal("0"), "0"),
        (Decimal("0.00000001"), "0.00000001"),
    ],
)
def test_decimal_text_preserves_scale_without_exponent(value: Decimal, expected: str) -> None:
    adapter = DecimalText()
    stored = adapter.process_bind_param(value, _DIALECT)

    assert stored == expected
    assert adapter.process_result_value(stored, _DIALECT) == value


@pytest.mark.parametrize("value", [0.1, "1.0", 1])
def test_decimal_text_rejects_non_decimal_bind_values(value: object) -> None:
    with pytest.raises(TypeError, match="Decimal values only"):
        DecimalText().process_bind_param(value, _DIALECT)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_decimal_text_rejects_non_finite_values(value: Decimal) -> None:
    with pytest.raises(InvariantViolation, match="finite"):
        DecimalText().process_bind_param(value, _DIALECT)


def test_kst_datetime_text_normalizes_an_aware_instant() -> None:
    adapter = KSTDateTimeText()
    source = datetime(2026, 8, 19, 1, 2, 3, tzinfo=UTC)

    stored = adapter.process_bind_param(source, _DIALECT)
    restored = adapter.process_result_value(stored, _DIALECT)

    assert stored == "2026-08-19T10:02:03+09:00"
    assert restored is not None
    assert restored.isoformat() == stored
    assert restored.astimezone(UTC) == source


def test_kst_datetime_text_rejects_naive_datetime() -> None:
    with pytest.raises(InvariantViolation, match="timezone-aware"):
        KSTDateTimeText().process_bind_param(datetime(2026, 8, 19, 10, 2, 3), _DIALECT)


def test_persistence_types_pass_through_null() -> None:
    decimal_adapter = DecimalText()
    datetime_adapter = KSTDateTimeText()

    assert decimal_adapter.process_bind_param(None, _DIALECT) is None
    assert decimal_adapter.process_result_value(None, _DIALECT) is None
    assert datetime_adapter.process_bind_param(None, _DIALECT) is None
    assert datetime_adapter.process_result_value(None, _DIALECT) is None
