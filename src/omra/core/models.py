"""도메인 종목 모델과 주문·계획 enum.

`Market`의 물리적 정의는 순환 import 방지를 위해 `core.ids`가 소유하며 이 모듈은
같은 타입을 재수출한다. `Instrument`는 시장·통화·호가단위·수량 격자의 잘못된
조합을 생성 경계에서 fail-fast로 차단한다.

정본: 설계 02 §4·§7.1~§7.2 [DD-02-4·5·6·17·19]
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import BaseModel, model_validator

from omra.core.errors import InvariantViolation
from omra.core.ids import Market, instrument_key
from omra.core.money import Dec  # noqa: TC001 - Pydantic needs the runtime validator.
from omra.core.tick import TickRuleId

__all__ = [
    "EQUITY_CLASSES",
    "Instrument",
    "Market",
    "OrderIntent",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PlanReason",
]

EQUITY_CLASSES: Final = frozenset({"kr_etf_equity", "us_etf_equity", "us_stock"})
_US_MARKETS: Final = frozenset({Market.NASD, Market.NYSE, Market.AMEX})


class Instrument(BaseModel, frozen=True):  # type: ignore[explicit-any]
    symbol: str
    market: Market
    currency: Literal["KRW", "USD"]
    asset_class: str
    lot_step: Dec
    tick_rule: TickRuleId

    @model_validator(mode="after")
    def validate_market_contract(self) -> Self:
        valid = (
            (
                self.market is Market.KRX
                and self.currency == "KRW"
                and self.tick_rule in {TickRuleId.KRX_ETF_5, TickRuleId.KRX7}
                and self.lot_step == 1
            )
            or (
                self.market in _US_MARKETS
                and self.currency == "USD"
                and self.tick_rule is TickRuleId.USD_PENNY
                and self.lot_step == 1
            )
            or (
                self.market is Market.UPBIT
                and self.currency == "KRW"
                and self.tick_rule is TickRuleId.UPBIT
                and self.lot_step == Decimal("1e-8")
            )
        )
        if not valid:
            raise InvariantViolation(
                "시장·통화·호가단위·수량 격자 조합이 Instrument 계약과 다르다",
                code="instrument.market_contract",
                market=self.market.value,
                currency=self.currency,
                tick_rule=self.tick_rule.value,
                lot_step=str(self.lot_step),
            )
        return self

    @property
    def key(self) -> str:
        return instrument_key(self.market, self.symbol)


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    LOO = "LOO"
    MOO = "MOO"
    LOC = "LOC"
    MOC = "MOC"


class OrderStatus(StrEnum):
    SUBMITTING = "SUBMITTING"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXPIRED_UNKNOWN = "EXPIRED_UNKNOWN"


class OrderIntent(StrEnum):
    BAND_RESTORE = "band_restore"
    CLASS_BAND = "class_band"
    CASHFLOW = "cashflow"
    HARVEST = "harvest"
    E7_TRANSFER = "e7_transfer"
    CONSTRAINT_CURE = "constraint_cure"
    CRYPTO_SLEEVE = "crypto_sleeve"
    SATELLITE_DD = "satellite_dd"
    TARGET_SHIFT = "target_shift"
    WITHDRAWAL = "withdrawal"
    MANUAL = "manual"


class PlanReason(StrEnum):
    DRIFT_BAND = "drift_band"
    CASHFLOW = "cashflow"
    HARVEST = "harvest"
    MANUAL = "manual"
    E7_TRANSFER = "e7_transfer"
