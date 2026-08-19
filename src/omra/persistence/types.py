"""Lossless SQLAlchemy adapters for canonical persistence representations."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import Text, TypeDecorator

from omra.core.clock import from_kst_text, to_kst_text
from omra.core.money import from_text, to_text


class DecimalText(TypeDecorator[Decimal]):
    """Persist finite :class:`Decimal` values as canonical TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, Decimal):
            msg = "DecimalText accepts Decimal values only"
            raise TypeError(msg)
        return to_text(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Decimal | None:
        del dialect
        if value is None:
            return None
        return from_text(value)


class KSTDateTimeText(TypeDecorator[datetime]):
    """Persist aware instants as canonical offset-bearing KST ISO 8601 TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, datetime):
            msg = "KSTDateTimeText accepts datetime values only"
            raise TypeError(msg)
        return to_kst_text(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        del dialect
        if value is None:
            return None
        return from_kst_text(value)


__all__ = ["DecimalText", "KSTDateTimeText"]
