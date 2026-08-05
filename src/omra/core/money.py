"""Decimal·화폐·수량 규약.

**Money 클래스를 만들지 않는다**([DD-02-9]). 계획 01 §3.1의 시그니처 초안이
`qty: Decimal; limit_price: Decimal | None`으로 확정되어 있어 통화를 실은
클래스는 정본 시그니처와 충돌한다. 대신 세 가지로 통화 혼동을 방어한다:
① 모델 필드는 순수 `Decimal` ② 통화 문맥은 필드명(`*_krw`·`*_usd`)과
`Instrument.currency` ③ 반올림·환산은 이 모듈의 순수 함수로 통일.

**float은 생성 경계에서 거부한다**. `0.1 + 0.2 != 0.3`이 주문 수량에 닿으면
그것이 곧 돈이다. `Dec` 타입이 pydantic 검증 시점에 막는다.

**전역 Decimal 컨텍스트를 변경하지 않는다.** skfolio 등 외부 라이브러리와
간섭하기 때문이다 — 모든 반올림은 `quantize`/명시적 `ROUND_*` 인자로 국소
수행한다.

정본: 설계 02 §5 [DD-02-9] · [DD-02-10] · [DD-02-15]
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from typing import Annotated, Final

from pydantic import BeforeValidator

from omra.core.clock import KST
from omra.core.errors import InvariantViolation, LotStepError

__all__ = [
    "KST",
    "Dec",
    "from_kst_text",
    "from_text",
    "krw_floor",
    "qty_floor",
    "to_kst_text",
    "to_text",
    "usd_budget",
    "utc_to_text",
]

_ZERO: Final = Decimal(0)


# ══════════════════════════════════════════════════════════════════════
# Dec — float 차단 타입 (설계 02 §5.1)
# ══════════════════════════════════════════════════════════════════════
def _reject_float(v: object) -> object:
    """float이 들어오면 거부한다.

    `Decimal(str(x))` 우회도 금지 대상이다 — 우회를 허용하면 "어디서
    float이 들어왔는가"를 추적할 수 없고, 그 추적 불가가 곧 금액 오차의
    원인 규명 실패다. 허용 입력은 `Decimal | int | str` 이다.

    `bool`도 거부한다. 파이썬에서 `bool`은 `int`의 하위 타입이라
    `Decimal(True) == Decimal(1)`이 조용히 성립하는데, 그것이 의도인
    경우는 없다.
    """
    if isinstance(v, bool):
        raise ValueError("bool은 수량·금액이 될 수 없다 (설계 02 §5.1)")
    if isinstance(v, float):
        raise ValueError(
            "float 금지 — Decimal·int·str 로 넘겨라. "
            "float은 금액 경로에서 조용한 오차를 만든다 (설계 02 §5.1)"
        )
    return v


#: 모든 pydantic 모델의 Decimal 필드는 이 타입을 쓴다.
Dec = Annotated[Decimal, BeforeValidator(_reject_float)]


# ══════════════════════════════════════════════════════════════════════
# TEXT 직렬화 정규형 (설계 02 §5.2 [DD-02-10])
# ══════════════════════════════════════════════════════════════════════
def _assert_finite(d: Decimal, *, where: str) -> None:
    if d.is_nan() or d.is_infinite():
        raise InvariantViolation(
            f"{where}: NaN·Infinity 는 저장할 수 없다",
            code="money.non_finite",
            value=str(d),
        )


def to_text(d: Decimal) -> str:
    """Decimal → TEXT 정규형.

    규약 넷 ([DD-02-10]):
      ① `format(d, "f")` — **지수 표기 절대 금지**(`1E+2` 가 아니라 `100`)
      ② **스케일 보존** — `Decimal("1.50")` → `"1.50"`. 크립토 수량의 유효
         자리는 감사 증거다
      ③ `NaN`·`Infinity` 거부
      ④ 부호 있는 0(`-0`)은 `0`으로 정규화

    정규형이 없으면 `UNIQUE` 제약과 exact-match 비교가 **표기 차이로**
    깨진다 — 같은 값이 두 벌로 저장되기 때문이다.
    """
    _assert_finite(d, where="to_text")
    if d == _ZERO and d.is_signed():
        d = -d  # "-0" → "0"
    return format(d, "f")


def from_text(s: str) -> Decimal:
    """TEXT 정규형 → Decimal. `to_text` 의 역함수이며 왕복이 항등이다."""
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvariantViolation(
            "Decimal 로 해석할 수 없는 문자열",
            code="money.parse_failed",
            raw=s,
        ) from exc
    _assert_finite(d, where="from_text")
    return d


# ══════════════════════════════════════════════════════════════════════
# 반올림 규약 (설계 02 §5.3 — 전부 계획 정본의 이관)
# ══════════════════════════════════════════════════════════════════════
def krw_floor(x: Decimal) -> Decimal:
    """KRW 환산 금액을 **원 단위로 절사**한다 (계획 02 §4.7-(d)).

    방향은 `ROUND_DOWN`(0 방향 절사)으로 고정한다 — 수학적 floor(음의 무한대 방향)가
    아니다. 양수에서는 둘이 같고, **음수(유출·차감)에서는 절대값을 키우지
    않는 `ROUND_DOWN`이 보수적**이다. 즉 어떤 부호에서도 `abs(결과) <= abs(입력)`이다.
    """
    _assert_finite(x, where="krw_floor")
    return x.quantize(Decimal(1), rounding=ROUND_DOWN)


def qty_floor(qty: Decimal, lot_step: Decimal) -> Decimal:
    """수량을 `lot_step` 격자로 **내림**한다 (계획 02 §4.7-(d)·§3.3 1단계).

    수량 산정은 언제나 floor다 — 올림하면 가용 현금을 초과하는 주문이 나가고,
    그 초과는 브로커 거부로 이어져 P9 연속 오류를 유발한다.

    Raises:
        LotStepError: `lot_step <= 0` 이거나 결과가 음수일 때.
    """
    _assert_finite(qty, where="qty_floor")
    _assert_finite(lot_step, where="qty_floor")
    if lot_step <= _ZERO:
        raise LotStepError("lot_step 은 양수여야 한다", lot_step=to_text(lot_step))
    if qty < _ZERO:
        raise LotStepError("음수 수량은 격자 정렬 대상이 아니다", qty=to_text(qty))
    steps = (qty / lot_step).to_integral_value(rounding=ROUND_DOWN)
    result = steps * lot_step
    # 격자 스케일을 보존한다 — `1e-8` 격자에서 `Decimal("0.1")` 이
    # `Decimal("0.10000000")` 로 남아야 감사 표기가 일관된다.
    return result.quantize(lot_step, rounding=ROUND_DOWN)


def usd_budget(krw: Decimal, fx_rate: Decimal, buffer: Decimal) -> Decimal:
    """원화 예산을 달러 예산으로 **보수적으로** 환산한다.

    `krw / (fx_rate * (1 + buffer))` — 계획 02 §3.3의 예산식 그대로다.
    buffer(기본 0.005)를 분모에 곱하는 이유는 통합증거금 자동환전 시점의
    환율이 판정 시점과 다르기 때문이며, 분모를 키우면 산출 예산이 줄어
    **증거금 부족 방향의 오차가 나지 않는다**.

    이 함수는 예산만 낸다. 수량 격자 정렬은 호출부가 `qty_floor`로 따로 한다.

    Raises:
        InvariantViolation: `fx_rate <= 0` 이거나 `1 + buffer <= 0` 일 때.
    """
    for name, value in (("krw", krw), ("fx_rate", fx_rate), ("buffer", buffer)):
        _assert_finite(value, where=f"usd_budget({name})")
    if fx_rate <= _ZERO:
        raise InvariantViolation(
            "환율은 양수여야 한다", code="money.fx_rate", fx_rate=to_text(fx_rate)
        )
    denominator = fx_rate * (Decimal(1) + buffer)
    if denominator <= _ZERO:
        raise InvariantViolation(
            "환율 버퍼가 분모를 0 이하로 만든다",
            code="money.fx_buffer",
            buffer=to_text(buffer),
        )
    return krw / denominator


# ══════════════════════════════════════════════════════════════════════
# 시각 직렬화 규약 (설계 02 §5.4 [DD-02-15])
# ══════════════════════════════════════════════════════════════════════
def to_kst_text(dt: datetime) -> str:
    """aware datetime → KST ISO8601 (`"2026-08-02T10:03:11+09:00"`).

    naive datetime은 거부한다. 오프셋 없는 시각은 "언제인가"를 답하지 못하고,
    그 모호함이 결제일·귀속 연도 판정으로 전파되면 세금 사고가 된다.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise InvariantViolation(
            "naive datetime 은 직렬화할 수 없다 (설계 02 §5.4)",
            code="money.naive_datetime",
            value=dt.isoformat(),
        )
    return dt.astimezone(KST).isoformat()


def from_kst_text(s: str) -> datetime:
    """KST ISO8601 → aware datetime. `to_kst_text` 의 역함수다."""
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise InvariantViolation(
            "ISO8601 로 해석할 수 없는 시각",
            code="money.timestamp_parse_failed",
            raw=s,
        ) from exc
    if dt.tzinfo is None:
        raise InvariantViolation(
            "오프셋 없는 시각 문자열은 거부한다 (설계 02 §5.4)",
            code="money.naive_datetime",
            raw=s,
        )
    return dt.astimezone(KST)


def utc_to_text(dt: datetime) -> str:
    """접미사 없는 **시각** 컬럼용 UTC ISO8601 (설계 03 §3.1).

    날짜 컬럼(`run_date`·`settle_date` 등)은 시각이 아니라 venue 현지 거래일
    `YYYY-MM-DD` 이며 이 함수의 대상이 아니다 — 그 산출은 캘린더(06)가 한다.
    """
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise InvariantViolation(
            "naive datetime 은 직렬화할 수 없다 (설계 03 §3.1)",
            code="money.naive_datetime",
            value=dt.isoformat(),
        )
    return dt.astimezone(UTC).isoformat()
