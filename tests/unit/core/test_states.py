"""`core.states` — 상태 enum과 제약 벡터 타입.

검증 항목: 설계 02 §9 [DD-02-13], 계획 01 §3.4, 진행표 S03-1.
"""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import get_type_hints

import pytest
from pydantic import ValidationError

from omra.core import states
from omra.core.money import Dec
from omra.core.states import (
    BotState,
    BuyAxis,
    ConstraintVector,
    NetBuyCap,
    PresenceState,
    SellAxis,
    SleeveState,
)


def test_public_exports_are_exact_s03_1_surface() -> None:
    assert states.__all__ == [
        "BotState",
        "BuyAxis",
        "ConstraintVector",
        "NetBuyCap",
        "PresenceState",
        "SellAxis",
        "SleeveState",
    ]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (
            BotState,
            [
                ("RUNNING", "RUNNING"),
                ("SAFE_MODE", "SAFE_MODE"),
                ("PAUSED", "PAUSED"),
                ("STOPPED", "STOPPED"),
                ("HALTED", "HALTED"),
                ("RELOAD_CONFIG", "RELOAD_CONFIG"),
            ],
        ),
        (
            SleeveState,
            [
                ("ACTIVE", "ACTIVE"),
                ("PAUSED", "PAUSED"),
                ("PAUSED_ALL", "PAUSED_ALL"),
            ],
        ),
        (
            PresenceState,
            [
                ("NORMAL", "NORMAL"),
                ("AWAY_SOFT", "AWAY_SOFT"),
                ("AWAY", "AWAY"),
                ("AWAY_LONG", "AWAY_LONG"),
            ],
        ),
    ],
)
def test_state_planes_are_exact_str_enum_snapshots(
    enum_type: type[StrEnum],
    expected: list[tuple[str, str]],
) -> None:
    assert issubclass(enum_type, StrEnum)
    assert enum_type.__module__ == "omra.core.states"
    assert [(member.name, member.value) for member in enum_type] == expected
    assert list(enum_type.__members__) == [name for name, _ in expected]


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    [
        (
            BuyAxis,
            [
                ("BUY_BLOCKED", 0),
                ("BUY_ALLOWED", 1),
            ],
        ),
        (
            SellAxis,
            [
                ("SELL_BLOCKED", 0),
                ("SELL_DOWNWARD_BLOCKED", 1),
                ("SELL_ALLOWED", 2),
            ],
        ),
    ],
)
def test_restriction_axes_are_exact_int_enum_snapshots(
    enum_type: type[IntEnum],
    expected: list[tuple[str, int]],
) -> None:
    assert issubclass(enum_type, IntEnum)
    assert enum_type.__module__ == "omra.core.states"
    assert [(member.name, member.value) for member in enum_type] == expected
    assert len(enum_type.__members__) == len(enum_type)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (BuyAxis.BUY_BLOCKED, BuyAxis.BUY_BLOCKED, BuyAxis.BUY_BLOCKED),
        (BuyAxis.BUY_BLOCKED, BuyAxis.BUY_ALLOWED, BuyAxis.BUY_BLOCKED),
        (BuyAxis.BUY_ALLOWED, BuyAxis.BUY_ALLOWED, BuyAxis.BUY_ALLOWED),
    ],
)
def test_buy_axis_lattice_ordering(
    left: BuyAxis,
    right: BuyAxis,
    expected: BuyAxis,
) -> None:
    assert min(left, right) is expected


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (SellAxis.SELL_BLOCKED, SellAxis.SELL_BLOCKED, SellAxis.SELL_BLOCKED),
        (
            SellAxis.SELL_BLOCKED,
            SellAxis.SELL_DOWNWARD_BLOCKED,
            SellAxis.SELL_BLOCKED,
        ),
        (SellAxis.SELL_BLOCKED, SellAxis.SELL_ALLOWED, SellAxis.SELL_BLOCKED),
        (
            SellAxis.SELL_DOWNWARD_BLOCKED,
            SellAxis.SELL_DOWNWARD_BLOCKED,
            SellAxis.SELL_DOWNWARD_BLOCKED,
        ),
        (
            SellAxis.SELL_DOWNWARD_BLOCKED,
            SellAxis.SELL_ALLOWED,
            SellAxis.SELL_DOWNWARD_BLOCKED,
        ),
        (SellAxis.SELL_ALLOWED, SellAxis.SELL_ALLOWED, SellAxis.SELL_ALLOWED),
    ],
)
def test_sell_axis_lattice_ordering(
    left: SellAxis,
    right: SellAxis,
    expected: SellAxis,
) -> None:
    assert min(left, right) is expected


def test_constraint_model_field_types_are_exact_contract_snapshots() -> None:
    assert get_type_hints(NetBuyCap, include_extras=True) == {
        "daily_nav_pct": Dec,
        "rolling_30d_nav_pct": Dec,
    }
    assert get_type_hints(ConstraintVector, include_extras=True) == {
        "buy": BuyAxis,
        "sell": SellAxis,
        "targets_update": bool,
        "band_multiplier": Dec,
        "net_buy_cap": NetBuyCap | None,
    }


def test_constraint_models_accept_decimal_values() -> None:
    cap = NetBuyCap(
        daily_nav_pct=Decimal("0.03"),
        rolling_30d_nav_pct=Decimal("0.10"),
    )
    vector = ConstraintVector(
        buy=BuyAxis.BUY_ALLOWED,
        sell=SellAxis.SELL_DOWNWARD_BLOCKED,
        targets_update=False,
        band_multiplier=Decimal("2"),
        net_buy_cap=cap,
    )

    assert vector.net_buy_cap == cap
    assert vector.buy is BuyAxis.BUY_ALLOWED
    assert vector.sell is SellAxis.SELL_DOWNWARD_BLOCKED
    assert vector.band_multiplier == Decimal("2")


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("band_multiplier", 1.0),
        ("band_multiplier", True),
        ("daily_nav_pct", 0.03),
        ("daily_nav_pct", True),
        ("rolling_30d_nav_pct", 0.10),
        ("rolling_30d_nav_pct", False),
    ],
)
def test_constraint_models_reject_float_and_bool_decimals(
    field: str,
    bad: float | bool,
) -> None:
    cap_kwargs: dict[str, object] = {
        "daily_nav_pct": Decimal("0.03"),
        "rolling_30d_nav_pct": Decimal("0.10"),
    }
    vector_kwargs: dict[str, object] = {
        "buy": BuyAxis.BUY_ALLOWED,
        "sell": SellAxis.SELL_ALLOWED,
        "targets_update": True,
        "band_multiplier": Decimal("1"),
        "net_buy_cap": None,
    }
    if field in cap_kwargs:
        cap_kwargs[field] = bad
        with pytest.raises(ValidationError):
            NetBuyCap(**cap_kwargs)
        return

    vector_kwargs[field] = bad
    with pytest.raises(ValidationError):
        ConstraintVector(**vector_kwargs)


def test_constraint_models_are_frozen() -> None:
    cap = NetBuyCap(
        daily_nav_pct=Decimal("0.03"),
        rolling_30d_nav_pct=Decimal("0.10"),
    )
    vector = ConstraintVector(
        buy=BuyAxis.BUY_ALLOWED,
        sell=SellAxis.SELL_ALLOWED,
        targets_update=True,
        band_multiplier=Decimal("1"),
        net_buy_cap=cap,
    )

    with pytest.raises(ValidationError) as cap_exc:
        cap.daily_nav_pct = Decimal("0.04")  # type: ignore[misc]  # deliberate frozen violation
    with pytest.raises(ValidationError) as vector_exc:
        vector.targets_update = False  # type: ignore[misc]  # deliberate frozen violation

    assert cap_exc.value.errors()[0]["type"] == "frozen_instance"
    assert vector_exc.value.errors()[0]["type"] == "frozen_instance"


def test_identity_shaped_constraint_vector_serializes_and_round_trips() -> None:
    vector = ConstraintVector(
        buy=BuyAxis.BUY_ALLOWED,
        sell=SellAxis.SELL_ALLOWED,
        targets_update=True,
        band_multiplier=Decimal("1"),
        net_buy_cap=None,
    )

    assert vector.model_dump(mode="json") == {
        "buy": 1,
        "sell": 2,
        "targets_update": True,
        "band_multiplier": "1",
        "net_buy_cap": None,
    }
    assert ConstraintVector.model_validate_json(vector.model_dump_json()) == vector


def test_capped_constraint_vector_serializes_and_round_trips() -> None:
    vector = ConstraintVector(
        buy=BuyAxis.BUY_ALLOWED,
        sell=SellAxis.SELL_DOWNWARD_BLOCKED,
        targets_update=False,
        band_multiplier=Decimal("2.0"),
        net_buy_cap=NetBuyCap(
            daily_nav_pct=Decimal("0.030"),
            rolling_30d_nav_pct=Decimal("0.100"),
        ),
    )

    dumped = vector.model_dump(mode="json")
    assert dumped["net_buy_cap"] == {
        "daily_nav_pct": "0.030",
        "rolling_30d_nav_pct": "0.100",
    }
    assert ConstraintVector.model_validate_json(vector.model_dump_json()) == vector
