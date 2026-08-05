"""호가단위 규칙과 가격 격자 산술.

정본: 설계 02 §6 [DD-02-7·8]
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    ROUND_CEILING,
    ROUND_FLOOR,
    Decimal,
    DecimalException,
    localcontext,
)
from enum import StrEnum
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator

from omra.core.errors import InvariantViolation, TickRuleError

__all__ = [
    "TickRuleId",
    "is_aligned",
    "next_down",
    "next_up",
    "snap_buy",
    "snap_sell",
    "tick_size",
    "ticks_between",
]

type _Ladder = tuple[tuple[Decimal, Decimal], ...]
type _Segment = tuple[Decimal, Decimal, Decimal | None]

_ZERO: Final = Decimal("0")
_USD_MIN_PRICE: Final = Decimal("1")
_PRECISION_GUARD_DIGITS: Final = 12


class TickRuleId(StrEnum):
    KRX_ETF_5 = "krx_etf_5"
    KRX7 = "krx7"
    USD_PENNY = "usd_penny"
    UPBIT = "upbit"


_UNIFORM_TICKS: Final[dict[TickRuleId, Decimal]] = {
    TickRuleId.KRX_ETF_5: Decimal("5"),
    TickRuleId.USD_PENNY: Decimal("0.01"),
}

# [확인 필요] KRX 유가·코스닥시장 공식 호가단위와 KIS 종목마스터 실측으로
# M2에서 확정한다. 거래소 규칙이므로 YAML 설정으로 분리하지 않는다([DD-02-8]).
_KRX7_LADDER: Final[_Ladder] = ()

# [확인 필요] Upbit 공식 KRW 마켓 호가단위와 M7 주문 거부 실측으로 확정한다.
# 활성화 전까지 런타임에서는 fail-closed로 주문 가격 산출을 차단한다.
_UPBIT_LADDER: Final[_Ladder] = ()

_LADDERS: Final[dict[TickRuleId, _Ladder]] = {
    TickRuleId.KRX7: _KRX7_LADDER,
    TickRuleId.UPBIT: _UPBIT_LADDER,
}


def tick_size(price: Decimal, rule: TickRuleId) -> Decimal:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        return uniform
    return _tick_size_from_ladder(p, _ladder_for(rule))


def snap_buy(price: Decimal, rule: TickRuleId) -> Decimal:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        return _ensure_output(_snap_floor(p, _ZERO, uniform), rule)
    return _ensure_output(_snap_buy_from_ladder(p, _ladder_for(rule)), rule)


def snap_sell(price: Decimal, rule: TickRuleId) -> Decimal:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        return _ensure_output(_snap_ceil(p, _ZERO, uniform), rule)
    return _ensure_output(_snap_sell_from_ladder(p, _ladder_for(rule)), rule)


def next_up(price: Decimal, rule: TickRuleId) -> Decimal:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        result = _ensure_output(_decimal_add(_snap_floor(p, _ZERO, uniform), uniform), rule)
    else:
        result = _ensure_output(_next_up_from_ladder(p, _ladder_for(rule)), rule)
    if result <= p:
        raise InvariantViolation(
            "next_up은 입력 가격보다 커야 한다", price=str(price), result=str(result)
        )
    return result


def next_down(price: Decimal, rule: TickRuleId) -> Decimal:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        base = _snap_floor(p, _ZERO, uniform)
        if base == p:
            base = _decimal_sub(base, uniform)
        result = _ensure_output(base, rule)
    else:
        result = _ensure_output(_next_down_from_ladder(p, _ladder_for(rule)), rule)
    if result >= p:
        raise InvariantViolation(
            "next_down은 입력 가격보다 작아야 한다", price=str(price), result=str(result)
        )
    return result


def ticks_between(lo: Decimal, hi: Decimal, rule: TickRuleId) -> int:
    lo_p = _validate_price(lo, rule)
    hi_p = _validate_price(hi, rule)
    if lo_p > hi_p:
        raise InvariantViolation("틱 거리 하한이 상한보다 클 수 없다", lo=str(lo), hi=str(hi))
    if lo_p == hi_p:
        if not is_aligned(lo_p, rule):
            raise TickRuleError("틱 거리 끝점은 모두 가격 격자 위에 있어야 한다", price=str(lo))
        return 0

    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        if not is_aligned(lo_p, rule) or not is_aligned(hi_p, rule):
            raise TickRuleError("틱 거리 끝점은 모두 가격 격자 위에 있어야 한다")
        return _ticks_between_uniform(lo_p, hi_p, uniform)

    return _ticks_between_from_ladder(lo_p, hi_p, _ladder_for(rule))


def is_aligned(price: Decimal, rule: TickRuleId) -> bool:
    p = _validate_price(price, rule)
    uniform = _UNIFORM_TICKS.get(rule)
    if uniform is not None:
        return _snap_floor(p, _ZERO, uniform) == p
    ladder = _ladder_for(rule)
    return _snap_buy_from_ladder(p, ladder) == p


def _validate_price(price: Decimal, rule: TickRuleId) -> Decimal:
    if not isinstance(rule, TickRuleId):
        raise TickRuleError("알 수 없는 호가단위 규칙", rule=str(rule))
    if type(price) is not Decimal:
        raise TickRuleError(
            "호가단위 가격은 Decimal 인스턴스여야 한다", price_type=type(price).__name__
        )
    if not price.is_finite():
        raise TickRuleError("호가단위 가격은 NaN·Infinity가 될 수 없다", price=str(price))
    if price <= _ZERO:
        raise TickRuleError("호가단위 가격은 양수여야 한다", price=str(price))
    if rule is TickRuleId.USD_PENNY and price < _USD_MIN_PRICE:
        raise TickRuleError("usd_penny 가격은 1 USD 미만을 지원하지 않는다", price=str(price))
    return price


def _ensure_output(price: Decimal, rule: TickRuleId) -> Decimal:
    if price <= _ZERO:
        raise TickRuleError("호가단위 산출 가격은 0 이하가 될 수 없다", price=str(price))
    if rule is TickRuleId.USD_PENNY and price < _USD_MIN_PRICE:
        raise TickRuleError("usd_penny 산출 가격은 1 USD 미만이 될 수 없다", price=str(price))
    return price


def _ladder_for(rule: TickRuleId) -> _Ladder:
    ladder = _LADDERS.get(rule)
    if ladder is None:
        raise TickRuleError("알 수 없는 호가단위 규칙", rule=str(rule))
    if not ladder:
        raise TickRuleError("호가단위 사다리 표 확인 필요", rule=rule.value)
    _validate_ladder(ladder)
    return ladder


def _validate_ladder(ladder: _Ladder) -> None:
    if not ladder:
        raise TickRuleError("호가단위 사다리 표 확인 필요")
    previous_lower: Decimal | None = None
    for lower, tick in ladder:
        if type(lower) is not Decimal or type(tick) is not Decimal:
            raise TickRuleError("호가단위 사다리 하한과 tick은 Decimal이어야 한다")
        if not lower.is_finite() or not tick.is_finite():
            raise TickRuleError("호가단위 사다리 하한과 tick은 NaN·Infinity가 될 수 없다")
        if lower < _ZERO:
            raise TickRuleError("호가단위 사다리 하한은 음수일 수 없다", lower=str(lower))
        if tick <= _ZERO:
            raise TickRuleError("호가단위 사다리 tick은 양수여야 한다", tick=str(tick))
        if previous_lower is not None and lower <= previous_lower:
            raise TickRuleError("호가단위 사다리 하한은 오름차순이어야 한다", lower=str(lower))
        previous_lower = lower
    if ladder[0][0] != _ZERO:
        raise TickRuleError("호가단위 사다리 첫 하한은 0이어야 한다", lower=str(ladder[0][0]))


def _segment_for(price: Decimal, ladder: _Ladder) -> _Segment:
    _validate_ladder(ladder)
    selected_lower = ladder[0][0]
    selected_tick = ladder[0][1]
    next_lower: Decimal | None = None
    for index, (lower, tick) in enumerate(ladder):
        if lower > price:
            break
        selected_lower = lower
        selected_tick = tick
        next_lower = ladder[index + 1][0] if index + 1 < len(ladder) else None
    return selected_lower, selected_tick, next_lower


def _previous_segment_for_boundary(
    boundary: Decimal, ladder: _Ladder
) -> tuple[Decimal, Decimal] | None:
    previous_segment: tuple[Decimal, Decimal] | None = None
    for lower, tick in ladder:
        if lower == boundary:
            return previous_segment
        previous_segment = (lower, tick)
    return None


def _tick_size_from_ladder(price: Decimal, ladder: _Ladder) -> Decimal:
    _, tick, _ = _segment_for(price, ladder)
    return tick


def _snap_buy_from_ladder(price: Decimal, ladder: _Ladder) -> Decimal:
    lower, tick, _ = _segment_for(price, ladder)
    return _snap_floor(price, lower, tick)


def _snap_sell_from_ladder(price: Decimal, ladder: _Ladder) -> Decimal:
    lower, tick, next_lower = _segment_for(price, ladder)
    candidate = _snap_ceil(price, lower, tick)
    if next_lower is not None and candidate > next_lower:
        return next_lower
    return candidate


def _next_up_from_ladder(price: Decimal, ladder: _Ladder) -> Decimal:
    base = _snap_buy_from_ladder(price, ladder)
    _, tick, next_lower = _segment_for(base, ladder)
    candidate = _decimal_add(base, tick)
    if next_lower is not None and candidate > next_lower:
        return next_lower
    return candidate


def _next_down_from_ladder(price: Decimal, ladder: _Ladder) -> Decimal:
    base = _snap_buy_from_ladder(price, ladder)
    previous_segment = _previous_segment_for_boundary(base, ladder)
    if base == price and previous_segment is not None:
        previous_lower, previous_tick = previous_segment
        steps = _ceil_positive_steps(_decimal_sub(base, previous_lower), previous_tick)
        return _quantized_grid_price(previous_lower, steps - 1, previous_tick)
    _, tick, _ = _segment_for(base, ladder)
    if base == price:
        return _decimal_sub(base, tick)
    return base


def _ticks_between_from_ladder(lo: Decimal, hi: Decimal, ladder: _Ladder) -> int:
    if _snap_buy_from_ladder(lo, ladder) != lo or _snap_buy_from_ladder(hi, ladder) != hi:
        raise TickRuleError("틱 거리 끝점은 모두 가격 격자 위에 있어야 한다")
    count = 0
    current = lo
    while current < hi:
        _, tick, next_lower = _segment_for(current, ladder)
        segment_hi = hi if next_lower is None or hi <= next_lower else next_lower
        step_count = _ceil_positive_steps(_decimal_sub(segment_hi, current), tick)
        if step_count <= 0:
            raise InvariantViolation("호가단위 사다리 next_up이 단조 증가하지 않는다")
        count += step_count
        current = segment_hi
    return count


def _snap_floor(price: Decimal, lower: Decimal, tick: Decimal) -> Decimal:
    try:
        with _exact_decimal_context(price, lower, tick):
            steps = ((price - lower) / tick).to_integral_value(rounding=ROUND_FLOOR)
            return (lower + steps * tick).quantize(tick)
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 내림 산술을 Decimal로 표현할 수 없다",
            price=str(price),
            lower=str(lower),
            tick=str(tick),
        ) from exc


def _snap_ceil(price: Decimal, lower: Decimal, tick: Decimal) -> Decimal:
    try:
        with _exact_decimal_context(price, lower, tick):
            steps = ((price - lower) / tick).to_integral_value(rounding=ROUND_CEILING)
            return (lower + steps * tick).quantize(tick)
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 올림 산술을 Decimal로 표현할 수 없다",
            price=str(price),
            lower=str(lower),
            tick=str(tick),
        ) from exc


def _ceil_positive_steps(distance: Decimal, tick: Decimal) -> int:
    try:
        with _exact_decimal_context(distance, tick):
            return int((distance / tick).to_integral_value(rounding=ROUND_CEILING))
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 틱 거리 산술을 Decimal로 표현할 수 없다",
            distance=str(distance),
            tick=str(tick),
        ) from exc


def _ticks_between_uniform(lo: Decimal, hi: Decimal, tick: Decimal) -> int:
    try:
        with _exact_decimal_context(lo, hi, tick):
            distance = (hi - lo) / tick
            return int(distance.to_integral_exact())
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 틱 거리 산술을 Decimal로 표현할 수 없다",
            lo=str(lo),
            hi=str(hi),
            tick=str(tick),
        ) from exc


def _quantized_grid_price(lower: Decimal, steps: int, tick: Decimal) -> Decimal:
    try:
        with _exact_decimal_context(lower, tick):
            return (lower + Decimal(steps) * tick).quantize(tick)
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 격자 가격을 Decimal로 표현할 수 없다",
            lower=str(lower),
            steps=str(steps),
            tick=str(tick),
        ) from exc


def _decimal_sub(left: Decimal, right: Decimal) -> Decimal:
    try:
        with _exact_decimal_context(left, right):
            return left - right
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 차감 산술을 Decimal로 표현할 수 없다",
            left=str(left),
            right=str(right),
        ) from exc


def _decimal_add(left: Decimal, right: Decimal) -> Decimal:
    try:
        with _exact_decimal_context(left, right):
            return left + right
    except DecimalException as exc:
        raise TickRuleError(
            "호가단위 가산 산술을 Decimal로 표현할 수 없다",
            left=str(left),
            right=str(right),
        ) from exc


@contextmanager
def _exact_decimal_context(*values: Decimal) -> Iterator[None]:
    try:
        with localcontext() as ctx:
            ctx.prec = _required_precision(*values)
            ctx.Emax = min(MAX_EMAX, max(ctx.Emax, _required_emax(*values)))
            ctx.Emin = max(MIN_EMIN, min(ctx.Emin, _required_emin(*values)))
            yield
    except (OverflowError, ValueError) as exc:
        raise TickRuleError("호가단위 Decimal 산술 컨텍스트를 구성할 수 없다") from exc


def _required_precision(*values: Decimal) -> int:
    integer_digits = 1
    fractional_digits = 0
    coefficient_digits = 1
    for value in values:
        digit_count = len(value.as_tuple().digits)
        coefficient_digits = max(coefficient_digits, digit_count)
        exponent = _finite_decimal_exponent(value)
        integer_digits = max(integer_digits, value.adjusted() + 1, 1)
        fractional_digits = max(fractional_digits, -exponent, 0)
    return integer_digits + fractional_digits + coefficient_digits + _PRECISION_GUARD_DIGITS


def _required_emax(*values: Decimal) -> int:
    return max((value.adjusted() + _PRECISION_GUARD_DIGITS for value in values), default=0)


def _required_emin(*values: Decimal) -> int:
    return min(
        (_finite_decimal_exponent(value) - _PRECISION_GUARD_DIGITS for value in values),
        default=0,
    )


def _finite_decimal_exponent(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise TickRuleError("호가단위 Decimal 값은 finite여야 한다", value=str(value))
    return exponent
