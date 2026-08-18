"""Core immutable instrument domain model."""

from decimal import Decimal
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from omra.core.errors import InvariantViolation
from omra.core.ids import Market, instrument_key
from omra.core.money import Dec
from omra.core.tick import TickRuleId

__all__ = ["EQUITY_CLASSES", "Instrument", "Market"]

EQUITY_CLASSES: Final[frozenset[str]] = frozenset({"kr_etf_equity", "us_etf_equity", "us_stock"})

_WHOLE_SHARE = Decimal(1)
_UPBIT_LOT = Decimal("1e-8")


class Instrument(BaseModel):
    """One tradable instrument with a venue-consistent execution contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    market: Market
    currency: Literal["KRW", "USD"]
    asset_class: str
    lot_step: Dec
    tick_rule: TickRuleId

    @model_validator(mode="after")
    def _validate_venue_contract(self) -> Self:
        _ = self.key
        if self.market is Market.KRX:
            valid = (
                self.currency == "KRW"
                and self.tick_rule in {TickRuleId.KRX_ETF_5, TickRuleId.KRX7}
                and self.lot_step == _WHOLE_SHARE
            )
        elif self.market is Market.UPBIT:
            valid = (
                self.currency == "KRW"
                and self.tick_rule is TickRuleId.UPBIT
                and self.lot_step == _UPBIT_LOT
            )
        else:
            valid = (
                self.currency == "USD"
                and self.tick_rule is TickRuleId.USD_PENNY
                and self.lot_step == _WHOLE_SHARE
            )

        if not valid:
            raise InvariantViolation(
                "instrument market, currency, tick rule, and lot step are inconsistent",
                context={
                    "market": self.market.value,
                    "currency": self.currency,
                    "tick_rule": self.tick_rule.value,
                    "lot_step": str(self.lot_step),
                },
            )
        return self

    @property
    def key(self) -> str:
        """Return the canonical exact-match instrument key."""
        return instrument_key(self.market, self.symbol)
