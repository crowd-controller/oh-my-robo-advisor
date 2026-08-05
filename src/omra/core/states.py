"""상태 enum과 5축 제약 벡터 타입.

`core.states`는 전역·슬리브·부재 상태의 공유 어휘와 제약 축의 타입만
소유한다. 상태별 벡터 표, 결합, 전이는 `protections` 계층의 책임이다.

정본: 설계 02 §9 [DD-02-13], 계획 01 §3.4
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import BaseModel

from omra.core.money import Dec  # noqa: TC001 - Pydantic needs the runtime validator.

__all__ = [
    "BotState",
    "BuyAxis",
    "ConstraintVector",
    "NetBuyCap",
    "PresenceState",
    "SellAxis",
    "SleeveState",
]


class BotState(StrEnum):
    """전역 봇 상태."""

    RUNNING = "RUNNING"
    SAFE_MODE = "SAFE_MODE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    HALTED = "HALTED"
    RELOAD_CONFIG = "RELOAD_CONFIG"


class SleeveState(StrEnum):
    """브로커·시장 슬리브별 오버레이 상태."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    PAUSED_ALL = "PAUSED_ALL"


class PresenceState(StrEnum):
    """사용자 부재 평면 상태."""

    NORMAL = "NORMAL"
    AWAY_SOFT = "AWAY_SOFT"
    AWAY = "AWAY"
    AWAY_LONG = "AWAY_LONG"


class BuyAxis(IntEnum):
    """신규 매수 제약 축. 작은 값일수록 더 제한적이다."""

    BUY_BLOCKED = 0
    BUY_ALLOWED = 1


class SellAxis(IntEnum):
    """매도 제약 축. 작은 값일수록 더 제한적이다."""

    SELL_BLOCKED = 0
    SELL_DOWNWARD_BLOCKED = 1
    SELL_ALLOWED = 2


class NetBuyCap(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """순매수 상한 비율."""

    daily_nav_pct: Dec
    rolling_30d_nav_pct: Dec


class ConstraintVector(BaseModel, frozen=True):  # type: ignore[explicit-any]
    """03 §2.1 5축 표의 한 행."""

    buy: BuyAxis
    sell: SellAxis
    targets_update: bool
    band_multiplier: Dec
    net_buy_cap: NetBuyCap | None
