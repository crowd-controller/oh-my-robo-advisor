"""도메인 종목·주문·체결 모델과 주문·계획 enum.

`Market`의 물리적 정의는 순환 import 방지를 위해 `core.ids`가 소유하며 이 모듈은
같은 타입을 재수출한다. `Instrument`는 시장·통화·호가단위·수량 격자의 잘못된
조합을 생성 경계에서 fail-fast로 차단한다. `Order` 상태는 `transition_to()`로만
전이하며 `Fill`은 브로커 체결 사실을 불변 값으로 보존한다.

정본: 설계 02 §4·§7.1~§7.3 [DD-02-4·5·6·17·18·19]
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime  # noqa: TC003 - Pydantic resolves model annotations.
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal, Self

if TYPE_CHECKING:
    from collections.abc import Mapping

from pydantic import BaseModel, model_validator

from omra.core.errors import InvariantViolation, LotStepError, TickRuleError, TransitionError
from omra.core.ids import Market, instrument_key
from omra.core.money import Dec, qty_floor
from omra.core.tick import TickRuleId, is_aligned

__all__ = [
    "EQUITY_CLASSES",
    "Fill",
    "Instrument",
    "Market",
    "Order",
    "OrderIntent",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PlanReason",
    "assert_transition",
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


_PRICE_ORDER_TYPES: Final = frozenset({OrderType.LIMIT, OrderType.LOO, OrderType.LOC})


class OrderStatus(StrEnum):
    SUBMITTING = "SUBMITTING"
    PENDING = "PENDING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXPIRED_UNKNOWN = "EXPIRED_UNKNOWN"


_TERMINAL: Final = frozenset(
    {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.EXPIRED,
    }
)
_ALLOWED_TRANSITIONS: Final = frozenset(
    {
        (OrderStatus.SUBMITTING, OrderStatus.PENDING),
        (OrderStatus.SUBMITTING, OrderStatus.REJECTED),
        (OrderStatus.SUBMITTING, OrderStatus.EXPIRED_UNKNOWN),
        (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED),
        (OrderStatus.PENDING, OrderStatus.FILLED),
        (OrderStatus.PENDING, OrderStatus.CANCELLED),
        (OrderStatus.PENDING, OrderStatus.EXPIRED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.EXPIRED),
        (OrderStatus.EXPIRED_UNKNOWN, OrderStatus.PENDING),
        (OrderStatus.EXPIRED_UNKNOWN, OrderStatus.CANCELLED),
    }
)


def assert_transition(current: OrderStatus, new: OrderStatus) -> None:
    """주문 상태 전이가 정본 전이표에 속하는지 검증한다.

    동일 상태 재적용은 멱등 갱신으로 허용한다. 그 밖의 표 외 전이는 주문 원장의
    불변식 위반이므로 재시도 불가 버그 신호인 ``TransitionError``를 발생시킨다.
    """
    if current == new or (current, new) in _ALLOWED_TRANSITIONS:
        return
    raise TransitionError(
        "합법 주문 상태 전이표 밖의 전이",
        current=current.value,
        new=new.value,
    )


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


class Order(BaseModel):  # type: ignore[explicit-any]
    id: str
    account_id: str
    broker_order_id: str | None = None
    broker_order_org_no: str | None = None
    orig_broker_order_id: str | None = None
    instrument: Instrument
    side: OrderSide
    order_type: OrderType
    intent: OrderIntent
    qty: Dec
    limit_price: Dec | None = None
    status: OrderStatus = OrderStatus.SUBMITTING
    plan_id: str | None = None
    reprice_count: int = 0
    submitted_at_kst: datetime | None = None
    dry_run: bool

    def __setattr__(self, name: str, value: object) -> None:
        if name == "status":
            raise InvariantViolation(
                "주문 상태는 transition_to()로만 변경할 수 있다",
                order_id=self.id,
            )
        if name in type(self).model_fields and name in self.__dict__:
            validated = self._validated_update({name: value})
            object.__setattr__(self, name, getattr(validated, name))
            self.__pydantic_fields_set__.add(name)
            return
        super().__setattr__(name, value)

    def transition_to(self, new: OrderStatus) -> None:
        if not isinstance(new, OrderStatus):
            raise InvariantViolation(
                "주문 상태는 OrderStatus여야 한다",
                order_id=self.id,
                status=repr(new),
            )
        assert_transition(self.status, new)
        object.__setattr__(self, "status", new)
        self.__pydantic_fields_set__.add("status")

    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        if update is None:
            return super().model_copy(deep=deep)
        if "status" in update and update["status"] != self.status:
            raise InvariantViolation(
                "model_copy로 주문 상태를 변경할 수 없다",
                order_id=self.id,
            )
        return self._validated_update(update, deep=deep)

    def _validated_update(
        self,
        update: Mapping[str, object],
        *,
        deep: bool = False,
    ) -> Self:
        fields = type(self).model_fields
        unknown = set(update).difference(fields)
        if unknown:
            raise InvariantViolation(
                "Order에 정의되지 않은 필드는 갱신할 수 없다",
                fields=",".join(sorted(unknown)),
            )
        values: dict[str, object] = {name: getattr(self, name) for name in fields}
        values.update(update)
        if deep:
            values = deepcopy(values)
        candidate = type(self).model_validate(values)
        candidate.__pydantic_fields_set__.clear()
        candidate.__pydantic_fields_set__.update(self.__pydantic_fields_set__)
        candidate.__pydantic_fields_set__.update(update)
        return candidate

    @model_validator(mode="after")
    def validate_quantity(self) -> Self:
        if self.qty <= 0:
            raise LotStepError("주문 수량은 양수여야 한다", qty=str(self.qty))
        if qty_floor(self.qty, self.instrument.lot_step) != self.qty:
            raise LotStepError(
                "주문 수량이 종목 lot_step 격자에 맞지 않는다",
                qty=str(self.qty),
                lot_step=str(self.instrument.lot_step),
            )
        return self

    @model_validator(mode="after")
    def validate_limit_price(self) -> Self:
        requires_price = self.order_type in _PRICE_ORDER_TYPES
        if requires_price and self.limit_price is None:
            raise TickRuleError(
                "지정 가격 주문 유형에는 limit_price가 필요하다",
                order_type=self.order_type.value,
            )
        if not requires_price and self.limit_price is not None:
            raise TickRuleError(
                "비가격 주문 유형에는 limit_price를 둘 수 없다",
                order_type=self.order_type.value,
            )
        if self.limit_price is not None and not is_aligned(
            self.limit_price, self.instrument.tick_rule
        ):
            raise TickRuleError(
                "limit_price가 종목 호가 격자에 맞지 않는다",
                limit_price=str(self.limit_price),
                tick_rule=self.instrument.tick_rule.value,
            )
        return self

    @model_validator(mode="after")
    def validate_submitted_timestamp(self) -> Self:
        submitted = self.submitted_at_kst
        if submitted is not None and (
            submitted.tzinfo is None or submitted.tzinfo.utcoffset(submitted) is None
        ):
            raise InvariantViolation(
                "submitted_at_kst는 aware datetime이어야 한다",
                order_id=self.id,
            )
        return self


class Fill(BaseModel, frozen=True):  # type: ignore[explicit-any]
    id: str
    order_id: str
    qty: Dec
    price: Dec
    fee: Dec | None = None
    tax: Dec | None = None
    filled_at_kst: datetime
    settle_date: date
    broker_exec_id: str | None = None

    def model_copy(
        self,
        *,
        update: Mapping[str, object] | None = None,
        deep: bool = False,
    ) -> Self:
        if update is None:
            return super().model_copy(deep=deep)
        fields = type(self).model_fields
        unknown = set(update).difference(fields)
        if unknown:
            raise InvariantViolation(
                "Fill에 정의되지 않은 필드는 갱신할 수 없다",
                fields=",".join(sorted(unknown)),
            )
        values: dict[str, object] = {name: getattr(self, name) for name in fields}
        values.update(update)
        if deep:
            values = deepcopy(values)
        candidate = type(self).model_validate(values)
        candidate.__pydantic_fields_set__.clear()
        candidate.__pydantic_fields_set__.update(self.__pydantic_fields_set__)
        candidate.__pydantic_fields_set__.update(update)
        return candidate

    @model_validator(mode="after")
    def validate_fill_facts(self) -> Self:
        if self.qty <= 0:
            raise InvariantViolation("체결 수량은 양수여야 한다", fill_id=self.id)
        if self.price <= 0:
            raise InvariantViolation("체결 가격은 양수여야 한다", fill_id=self.id)
        if (
            self.filled_at_kst.tzinfo is None
            or self.filled_at_kst.tzinfo.utcoffset(self.filled_at_kst) is None
        ):
            raise InvariantViolation(
                "filled_at_kst는 aware datetime이어야 한다",
                fill_id=self.id,
            )
        return self


class PlanReason(StrEnum):
    DRIFT_BAND = "drift_band"
    CASHFLOW = "cashflow"
    HARVEST = "harvest"
    MANUAL = "manual"
    E7_TRANSFER = "e7_transfer"
