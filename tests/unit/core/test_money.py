"""`core.money` — Decimal 규약·직렬화 정규형·반올림·시각 표기.

검증 항목: 설계 02 §5.5
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import BaseModel, ValidationError

from omra.core.errors import InvariantViolation, LotStepError
from omra.core.money import (
    KST,
    Dec,
    from_kst_text,
    from_text,
    krw_floor,
    qty_floor,
    to_kst_text,
    to_text,
    usd_budget,
    utc_to_text,
)


class _Model(BaseModel):
    v: Dec


# ══════════════════════════════════════════════════════════════════════
# Dec — float 차단 (설계 02 §5.1)
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("bad", [0.1, 1.0, -3.5, 1e-8])
def test_dec_rejects_float(bad: float) -> None:
    """`0.1 + 0.2 != 0.3` 이 주문 수량에 닿으면 그것이 곧 돈이다."""
    with pytest.raises(ValidationError, match="float 금지"):
        _Model(v=bad)


def test_dec_rejects_bool() -> None:
    """`bool`은 `int` 하위 타입이라 `Decimal(True) == 1` 이 조용히 성립한다."""
    with pytest.raises(ValidationError, match="수량·금액이 될 수 없다"):
        _Model(v=True)


@pytest.mark.parametrize("good", [Decimal("0.1"), "0.1", 1, Decimal(0)])
def test_dec_accepts_decimal_str_int(good: Decimal | str | int) -> None:
    assert isinstance(_Model(v=good).v, Decimal)


def test_dec_preserves_exact_value_from_string() -> None:
    """문자열 경로는 정확하다 — float 경유였다면 오차가 생긴다."""
    assert _Model(v="0.1").v == Decimal("0.1")


# ══════════════════════════════════════════════════════════════════════
# TEXT 정규형 (설계 02 §5.2 [DD-02-10])
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.50", "1.50"),  # 스케일 보존 — 크립토 유효 자리는 감사 증거다
        ("1E+2", "100"),  # 지수 표기 금지
        ("1e-8", "0.00000001"),
        ("-0", "0"),  # 부호 있는 0 정규화
        ("0", "0"),
        ("-1234.5", "-1234.5"),
        ("100000000000000000000", "100000000000000000000"),
    ],
)
def test_to_text_normal_form(raw: str, expected: str) -> None:
    assert to_text(Decimal(raw)) == expected


@pytest.mark.parametrize(
    "raw", ["0", "1.50", "-1234.5", "1e-8", "0.00000001", "123456789.123456789"]
)
def test_text_roundtrip_is_identity(raw: str) -> None:
    """왕복이 항등이어야 `UNIQUE`·exact-match 비교가 표기 차이로 깨지지 않는다."""
    d = Decimal(raw)
    assert from_text(to_text(d)) == d


def test_text_roundtrip_preserves_scale() -> None:
    """값이 같아도 **스케일이 다르면 다른 표기**다 — 감사 증거로서 구별된다."""
    assert to_text(from_text("1.50")) == "1.50"
    assert to_text(from_text("1.5")) == "1.5"


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity", "sNaN"])
def test_to_text_rejects_non_finite(raw: str) -> None:
    with pytest.raises(InvariantViolation, match="NaN·Infinity"):
        to_text(Decimal(raw))


@pytest.mark.parametrize("raw", ["NaN", "Infinity"])
def test_from_text_rejects_non_finite(raw: str) -> None:
    with pytest.raises(InvariantViolation, match="NaN·Infinity"):
        from_text(raw)


@pytest.mark.parametrize("raw", ["", "abc", "1.2.3", "1,000", " 1 2 "])
def test_from_text_rejects_garbage(raw: str) -> None:
    with pytest.raises(InvariantViolation) as exc:
        from_text(raw)
    assert exc.value.effective_code == "money.parse_failed"


def test_from_text_accepts_unicode_digits_by_python_semantics() -> None:
    """전각 숫자는 `Decimal()` 이 그대로 받는다 — [DD-02-10]이 정한 동작이다.

    값은 정확하고, DB 경로는 언제나 `to_text` 를 거쳐 ASCII로 기록되므로
    저장 정규형이 오염되지는 않는다. 전각이 들어올 수 있는 유일한 경로는
    사람이 편집한 config이며 그쪽은 pydantic 검증이 먼저 본다.
    """
    fullwidth = "１２３"  # noqa: RUF001 — 전각 입력이 이 테스트의 대상이다
    assert from_text(fullwidth) == Decimal(123)
    assert to_text(from_text(fullwidth)) == "123"


def test_to_text_never_uses_exponent_notation() -> None:
    """지수 표기가 하나라도 새면 DB의 같은 값이 두 벌로 저장된다."""
    for exp in range(-12, 13):
        text = to_text(Decimal(1).scaleb(exp))
        assert "e" not in text.lower(), f"scaleb({exp}) → {text}"


# ══════════════════════════════════════════════════════════════════════
# krw_floor (계획 02 §4.7-(d))
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1234.9", "1234"),
        ("1234.0", "1234"),
        ("0.9", "0"),
        ("-1234.9", "-1234"),  # ROUND_DOWN — 수학적 floor(-1235)가 아니다
        ("-0.9", "0"),
    ],
)
def test_krw_floor(raw: str, expected: str) -> None:
    assert krw_floor(Decimal(raw)) == Decimal(expected)


def test_krw_floor_never_increases_magnitude() -> None:
    """어떤 부호에서도 `abs(결과) <= abs(입력)` 이다 — 음수 유출에서 보수적이다."""
    for raw in ("1234.9", "-1234.9", "0.5", "-0.5", "0"):
        x = Decimal(raw)
        assert abs(krw_floor(x)) <= abs(x)


# ══════════════════════════════════════════════════════════════════════
# qty_floor (계획 02 §4.7-(d)·§3.3)
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("qty", "step", "expected"),
    [
        ("3.7", "1", "3"),  # 정수 주식
        ("3.0", "1", "3"),
        ("0.9", "1", "0"),
        ("1.234567891", "1e-8", "1.23456789"),  # 크립토 8자리
        ("1.000000009", "1e-8", "1.00000000"),
        ("0", "1", "0"),
    ],
)
def test_qty_floor(qty: str, step: str, expected: str) -> None:
    assert qty_floor(Decimal(qty), Decimal(step)) == Decimal(expected)


def test_qty_floor_preserves_lot_step_scale() -> None:
    """`1e-8` 격자 결과는 8자리로 남는다 — 감사 표기가 일관된다."""
    assert to_text(qty_floor(Decimal("0.1"), Decimal("1e-8"))) == "0.10000000"


@pytest.mark.parametrize("step", ["0", "-1", "-1e-8"])
def test_qty_floor_rejects_non_positive_step(step: str) -> None:
    with pytest.raises(LotStepError, match="양수"):
        qty_floor(Decimal(1), Decimal(step))


def test_qty_floor_rejects_negative_qty() -> None:
    """음수 수량은 격자 정렬 대상이 아니다 — 매도는 side 로 표현한다."""
    with pytest.raises(LotStepError, match="음수 수량"):
        qty_floor(Decimal("-1"), Decimal(1))


def test_qty_floor_result_never_exceeds_input() -> None:
    """올림하면 가용 현금을 초과하는 주문이 나가고 P9 연속 오류로 이어진다."""
    for qty in ("3.7", "0.999999999", "1.00000001"):
        d = Decimal(qty)
        assert qty_floor(d, Decimal("1e-8")) <= d
        assert qty_floor(d, Decimal(1)) <= d


# ══════════════════════════════════════════════════════════════════════
# usd_budget (계획 02 §3.3)
# ══════════════════════════════════════════════════════════════════════
def test_usd_budget_matches_plan_formula() -> None:
    """`V / (rate × 1.005)` — 계획 02 §3.3의 예산식과 수치 일치 (고정 벡터)."""
    krw, rate, buf = Decimal(1_000_000), Decimal(1350), Decimal("0.005")
    assert usd_budget(krw, rate, buf) == krw / (rate * Decimal("1.005"))


def test_usd_budget_buffer_shrinks_the_budget() -> None:
    """버퍼는 분모를 키운다 — **증거금 부족 방향의 오차가 나지 않는다**."""
    krw, rate = Decimal(1_000_000), Decimal(1350)
    assert usd_budget(krw, rate, Decimal("0.005")) < usd_budget(krw, rate, Decimal(0))


@pytest.mark.parametrize("rate", ["0", "-1350"])
def test_usd_budget_rejects_non_positive_rate(rate: str) -> None:
    with pytest.raises(InvariantViolation) as exc:
        usd_budget(Decimal(1), Decimal(rate), Decimal("0.005"))
    assert exc.value.effective_code == "money.fx_rate"


def test_usd_budget_rejects_buffer_that_kills_denominator() -> None:
    with pytest.raises(InvariantViolation) as exc:
        usd_budget(Decimal(1), Decimal(1350), Decimal("-1"))
    assert exc.value.effective_code == "money.fx_buffer"


# ══════════════════════════════════════════════════════════════════════
# 시각 직렬화 (설계 02 §5.4 [DD-02-15])
# ══════════════════════════════════════════════════════════════════════
def test_to_kst_text_matches_audit_envelope_format() -> None:
    """계획 01 §6.3 감사 봉투 예시와 같은 형식이다."""
    dt = datetime(2026, 8, 2, 10, 3, 11, tzinfo=KST)
    assert to_kst_text(dt) == "2026-08-02T10:03:11+09:00"


def test_to_kst_text_converts_from_other_zones() -> None:
    """어느 타임존에서 오든 KST 오프셋으로 정규화된다."""
    dt = datetime(2026, 8, 2, 1, 3, 11, tzinfo=UTC)
    assert to_kst_text(dt) == "2026-08-02T10:03:11+09:00"


def test_kst_text_roundtrip() -> None:
    dt = datetime(2026, 12, 31, 23, 59, 59, tzinfo=KST)
    assert from_kst_text(to_kst_text(dt)) == dt


@pytest.mark.parametrize("fn", [to_kst_text, utc_to_text])
def test_naive_datetime_is_rejected(fn: object) -> None:
    """오프셋 없는 시각은 "언제인가"를 답하지 못한다 — 세금 귀속이 어긋난다."""
    assert callable(fn)
    with pytest.raises(InvariantViolation) as exc:
        fn(datetime(2026, 8, 2, 10, 3, 11))
    assert exc.value.effective_code == "money.naive_datetime"


def test_from_kst_text_rejects_offsetless_string() -> None:
    with pytest.raises(InvariantViolation) as exc:
        from_kst_text("2026-08-02T10:03:11")
    assert exc.value.effective_code == "money.naive_datetime"


def test_from_kst_text_rejects_garbage() -> None:
    with pytest.raises(InvariantViolation) as exc:
        from_kst_text("어제")
    assert exc.value.effective_code == "money.timestamp_parse_failed"


def test_utc_to_text_normalizes_to_utc() -> None:
    """접미사 없는 시각 컬럼은 UTC다 (설계 03 §3.1)."""
    dt = datetime(2026, 8, 2, 10, 3, 11, tzinfo=KST)
    assert utc_to_text(dt) == "2026-08-02T01:03:11+00:00"


def test_kst_offset_is_fixed_nine_hours() -> None:
    """한국은 서머타임이 없다 — 연중 +09:00 고정이다."""
    for month in (1, 4, 7, 10):
        dt = datetime(2026, month, 1, 12, 0, tzinfo=KST)
        assert dt.utcoffset() == timedelta(hours=9)


def test_kst_conversion_is_stable_across_dst_zones() -> None:
    """DST가 있는 타임존에서 변환해도 KST 표기는 흔들리지 않는다."""
    ny_summer = datetime(2026, 7, 1, 21, 0, tzinfo=timezone(timedelta(hours=-4)))
    assert to_kst_text(ny_summer) == "2026-07-02T10:00:00+09:00"
