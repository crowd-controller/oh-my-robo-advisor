"""`core.errors` — 예외 계층·retryable 규약·감사 payload.

검증 항목: 설계 02 §10.4
"""

from __future__ import annotations

import inspect
import re

import pytest

from omra.core import errors
from omra.core.errors import (
    AmbiguousOrderState,
    BrokerAuthError,
    BrokerError,
    BrokerRateLimited,
    BrokerUnavailable,
    CalendarError,
    ConfigError,
    DataError,
    DomainError,
    EngineError,
    IdentifierError,
    InvariantViolation,
    LotStepError,
    OmraError,
    OrderRejectedError,
    PersistenceError,
    PretradeRejection,
    ProviderError,
    StaleDataError,
    TaxSellBlockedError,
    TickRuleError,
    TransitionError,
)


def _all_error_classes() -> list[type[OmraError]]:
    return [
        obj
        for _, obj in inspect.getmembers(errors, inspect.isclass)
        if issubclass(obj, OmraError) and obj.__module__ == errors.__name__
    ]


# ══════════════════════════════════════════════════════════════════════
# 트리 구조 (설계 02 §10.1)
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("child", "parent"),
    [
        (DomainError, OmraError),
        (InvariantViolation, DomainError),
        (IdentifierError, DomainError),
        (TickRuleError, DomainError),
        (LotStepError, DomainError),
        (TransitionError, InvariantViolation),
        (PretradeRejection, OmraError),
        (TaxSellBlockedError, PretradeRejection),
        (EngineError, OmraError),
        (ConfigError, OmraError),
        (BrokerError, OmraError),
        (BrokerAuthError, BrokerError),
        (BrokerRateLimited, BrokerError),
        (BrokerUnavailable, BrokerError),
        (OrderRejectedError, BrokerError),
        (AmbiguousOrderState, BrokerError),
        (DataError, OmraError),
        (ProviderError, DataError),
        (StaleDataError, DataError),
        (CalendarError, OmraError),
        (PersistenceError, OmraError),
    ],
)
def test_hierarchy(child: type[OmraError], parent: type[OmraError]) -> None:
    """설계 02 §10.1 트리 그대로다."""
    assert issubclass(child, parent)


def test_transition_error_is_an_invariant_violation() -> None:
    """전이표 위반은 **버그 신호**다 — 재시도 대상이 아니다.

    `TransitionError`가 `DomainError` 직속이면 "재시도해 볼 만한 오류"로
    오해될 수 있다. `InvariantViolation` 하위에 두는 것이 그 오해를 막는다.
    """
    assert issubclass(TransitionError, InvariantViolation)
    assert TransitionError().is_retryable is False


def test_no_class_inherits_exception_directly_except_the_base() -> None:
    """§10.2 규칙 5의 기계 검사 — 새 최상위 분기는 설계 02의 개정 사항이다."""
    for cls in _all_error_classes():
        if cls is OmraError:
            assert cls.__bases__ == (Exception,)
        else:
            assert all(issubclass(b, OmraError) for b in cls.__bases__), (
                f"{cls.__name__} 이 OmraError 밖을 직접 상속한다"
            )


# ══════════════════════════════════════════════════════════════════════
# code 규약
# ══════════════════════════════════════════════════════════════════════
def test_every_class_declares_a_code() -> None:
    for cls in _all_error_classes():
        assert cls.code, f"{cls.__name__} 에 code 가 없다"


def test_codes_are_unique() -> None:
    """`code` 중복은 감사·알림 집계를 오염시킨다."""
    codes = [cls.code for cls in _all_error_classes()]
    duplicates = {c for c in codes if codes.count(c) > 1}
    assert not duplicates, f"중복 code: {sorted(duplicates)}"


def test_codes_use_dotted_lowercase_form() -> None:
    """`"tick.rule_unknown"` 형태 — 집계 키로 쓰이므로 표기가 안정해야 한다."""
    pattern = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
    for cls in _all_error_classes():
        assert pattern.match(cls.code), f"{cls.__name__}: {cls.code!r}"


def test_instance_can_override_code() -> None:
    err = TickRuleError("x", code="tick.rule_unknown")
    assert err.effective_code == "tick.rule_unknown"
    assert TickRuleError("x").effective_code == "domain.tick_rule"


# ══════════════════════════════════════════════════════════════════════
# retryable 규약 — tenacity 술어의 입력 (설계 02 §10.4)
# ══════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    ("cls", "expected"),
    [
        (BrokerUnavailable, True),
        (BrokerRateLimited, True),
        (BrokerAuthError, False),
        (OrderRejectedError, False),
        (AmbiguousOrderState, False),
        (InvariantViolation, False),
        (TransitionError, False),
        (StaleDataError, False),
        (PretradeRejection, False),
        (TaxSellBlockedError, False),
        (OmraError, False),
    ],
)
def test_retryable_defaults(cls: type[OmraError], expected: bool) -> None:
    assert cls().is_retryable is expected


def test_ambiguous_order_state_is_never_retryable() -> None:
    """재시도하면 **이중 주문**이 된다 (§10.2 규칙 3).

    유일한 합법 처리는 계획 01 §3.2 프로토콜(재조회 확정 → 실패 시
    `EXPIRED_UNKNOWN`)이며, 재시도는 그 프로토콜이 아니다.
    """
    assert AmbiguousOrderState().is_retryable is False


def test_stale_data_is_not_retryable() -> None:
    """기다려도 새로워지지 않는다 — 재시도가 아니라 폴백이 정답이다."""
    assert StaleDataError().is_retryable is False


def test_provider_error_takes_retryable_per_cause() -> None:
    """provider 실패는 원인별로 갈린다 — 생성자 인자로 받는다."""
    assert ProviderError("timeout", retryable=True).is_retryable is True
    assert ProviderError("bad schema").is_retryable is False


def test_tenacity_predicate_contract() -> None:
    """ "재시도 대상인가"를 타입만으로 판정할 수 있다 — 문자열 매칭 불요."""

    def should_retry(exc: BaseException) -> bool:
        return isinstance(exc, OmraError) and exc.is_retryable

    assert should_retry(BrokerUnavailable("503"))
    assert not should_retry(BrokerAuthError("401"))
    assert not should_retry(InvariantViolation("bug"))


# ══════════════════════════════════════════════════════════════════════
# 감사 payload (계획 01 §6.3)
# ══════════════════════════════════════════════════════════════════════
def test_audit_payload_shape() -> None:
    err = LotStepError("격자 위반", instrument_key="KRX:069500", qty="1.5")
    payload = err.to_audit_payload()
    assert payload["error_type"] == "LotStepError"
    assert payload["code"] == "domain.lot_step"
    assert payload["retryable"] is False
    assert payload["message"] == "격자 위반"
    assert payload["context"] == {"instrument_key": "KRX:069500", "qty": "1.5"}


def test_audit_payload_context_is_a_copy() -> None:
    """반환된 payload를 수정해도 예외 객체가 오염되지 않는다."""
    err = LotStepError("x", a="1")
    payload = err.to_audit_payload()
    context = payload["context"]
    assert isinstance(context, dict)
    context["a"] = "2"
    assert err.context["a"] == "1"


def test_context_values_are_stringified() -> None:
    """감사 봉투는 JSON이다 — 비문자열이 섞이면 직렬화 시점에 터진다."""
    err = TickRuleError("x", price=1234, aligned=False)
    assert err.context == {"price": "1234", "aligned": "False"}


def test_pretrade_rejection_carries_step_and_retry_flag() -> None:
    """체인 러너가 판정 객체로 변환할 때 필요한 필드가 전부 있다."""
    err = PretradeRejection(
        "순매수 상한 초과",
        step="8.5",
        order_id="01J0000000000000000000000A",
        reason="net_buy_daily_cap",
        retry_today=False,
    )
    payload = err.to_audit_payload()
    assert payload["step"] == "8.5"
    assert payload["order_id"] == "01J0000000000000000000000A"
    assert payload["reason"] == "net_buy_daily_cap"
    assert payload["retry_today"] is False


def test_pretrade_reason_defaults_to_message() -> None:
    assert PretradeRejection("금소세 soft-stop").reason == "금소세 soft-stop"


def test_tax_sell_blocked_is_a_pretrade_signal() -> None:
    """단계 2.5 거부는 체인 **내부** 신호다 — 밖으로 새면 버그다."""
    err = TaxSellBlockedError("ISA 한도", step="2.5")
    assert isinstance(err, PretradeRejection)
    assert err.effective_code == "pretrade.tax_sell_blocked"
    assert err.step == "2.5"


# ══════════════════════════════════════════════════════════════════════
# 기타 규약
# ══════════════════════════════════════════════════════════════════════
def test_message_defaults_to_class_name() -> None:
    """빈 메시지로 던져도 로그에 무엇이 터졌는지 남는다."""
    assert str(InvariantViolation()) == "InvariantViolation"


def test_repr_shows_code_and_message() -> None:
    assert repr(IdentifierError("bad key")) == (
        "IdentifierError(code='domain.identifier', message='bad key')"
    )


def test_all_exports_match_module_contents() -> None:
    """`__all__` 이 실제 클래스 집합과 일치한다 — 누락된 export 는 우회 import 를 부른다."""
    exported = set(errors.__all__)
    defined = {cls.__name__ for cls in _all_error_classes()}
    assert exported == defined, (
        f"누락: {sorted(defined - exported)} / 초과: {sorted(exported - defined)}"
    )


def test_errors_module_has_no_internal_imports() -> None:
    """`core.errors` 는 core 안에서도 최하층(L0)이다 ([DD-02-1])."""
    source = inspect.getsource(errors)
    assert "from omra" not in source
    assert "import omra" not in source
