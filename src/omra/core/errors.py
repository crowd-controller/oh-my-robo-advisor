"""예외 계층 — 전 레이어 공통 기저와 분류 규약.

**왜 타입으로 분류하는가**: 재시도 가능/불가와 버그/외부 장애의 구분이 타입에
없으면 tenacity 술어가 문자열 매칭으로 전락한다. 그리고 감사로그(계획 01 §6.3)가
요구하는 "왜 그 결정이었는가"의 재구성은 예외에 안정 식별자(`code`)가 있어야
가능하다.

## 사용 규칙 (전 레이어 규약 — 설계 02 §10.2)

1. **예상된 거부는 모듈 경계 밖으로 예외가 되어 나가지 않는다.** pre-trade 거부,
   가드 `DEFER/SHRINK/ABORT`, 감시 `SV2` 차단, 밴드 미달 스킵의 공개 API 반환값은
   **판정 객체**다. 거부는 감사로그의 1급 데이터(계획 00 §5 원칙 4 — 미집행 주문
   기록)인데 예외로 던지면 호출부마다 catch-후-기록이 중복된다.
   - 경계 **안**의 예외 사용은 허용한다([DD-02-20]): 단계가 10개 넘게 직렬로
     이어지는 pre-trade 체인에서는 각 단계 헬퍼가 `PretradeRejection`을 던지고
     **체인 러너가 자기 경계에서 전부 잡아 판정 객체 1개로 변환**한다. 러너 밖으로
     전파되면 그것이 버그다.
2. **`InvariantViolation`은 절대 재시도·절대 삼킴 금지.** 잡은 즉시 실패 처리 +
   warning. 반복 관측되면 브레이커(P9 계열)가 잡는다 — 예외 자체가 상태를 바꾸지
   않는다.
3. **`AmbiguousOrderState`는 성공으로도 실패로도 처리 금지.** 유일한 합법 처리는
   계획 01 §3.2 프로토콜(재조회 확정 → 실패 시 `EXPIRED_UNKNOWN` + 화이트리스트
   `kind=orphan_order`)이다.
4. **예외로 상태 전이를 일으키지 않는다.** `BotState`/`SleeveState` 전이는 09의
   명시 경로만 가능하다. 예외 핸들러의 최대치는 "잡 실패 기록 + 알림"이다.
5. **레이어별 확장은 자기 기저 아래로만.** 새 최상위 분기는 설계 02의 개정 사항이다.

정본: 설계 02 §10 [DD-02-12] · [DD-02-20]
"""

from __future__ import annotations

from typing import ClassVar

__all__ = [
    "AmbiguousOrderState",
    "BrokerAuthError",
    "BrokerError",
    "BrokerRateLimited",
    "BrokerUnavailable",
    "CalendarError",
    "ConfigError",
    "DataError",
    "DomainError",
    "EngineError",
    "IdentifierError",
    "InvariantViolation",
    "LotStepError",
    "OmraError",
    "OrderRejectedError",
    "PersistenceError",
    "PretradeRejection",
    "ProviderError",
    "StaleDataError",
    "TaxSellBlockedError",
    "TickRuleError",
    "TransitionError",
]

# 감사 봉투는 JSON이므로 `context`의 최종 표현은 문자열이다. 다만 **입력은
# 무엇이든 받아 생성 시점에 정규화**한다 — 호출부에 `str()` 반복을 강요하면
# 예외를 던지는 코드가 장황해지고, 그러면 문맥을 안 담는 쪽으로 기운다.
# 실계좌번호·API 키는 애초에 core 타입 어디에도 필드가 없다([DD-02-3]).
_CONTEXT_VALUE = object


class OmraError(Exception):
    """모든 옴라 예외의 기저.

    Attributes:
        code: 안정 식별자. 감사·알림 집계의 키다(예: `"tick.rule_unknown"`).
            메시지는 바뀌어도 `code`는 바뀌지 않는다 — 바뀌면 과거 감사로그의
            집계가 어긋난다.
        retryable: tenacity 술어의 입력. 기본 False.
        context: 구조화 문맥. 마스킹 규칙을 준수한다(실계좌번호·키 금지).
    """

    #: 하위 클래스가 재정의한다. 미정의면 클래스명 기반 폴백을 쓴다.
    code: ClassVar[str] = "omra.error"
    #: 재시도 가능 여부의 클래스 기본값. 인스턴스 인자로 덮을 수 있다.
    retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str = "",
        *,
        code: str | None = None,
        retryable: bool | None = None,
        **context: _CONTEXT_VALUE,
    ) -> None:
        super().__init__(message or type(self).__name__)
        self.message = message or type(self).__name__
        self._code = code
        self._retryable = retryable
        self.context: dict[str, str] = {k: str(v) for k, v in context.items()}

    @property
    def effective_code(self) -> str:
        """인스턴스 오버라이드를 반영한 최종 `code`."""
        return self._code or type(self).code

    @property
    def is_retryable(self) -> bool:
        """인스턴스 오버라이드를 반영한 최종 재시도 가능 여부."""
        return type(self).retryable if self._retryable is None else self._retryable

    def to_audit_payload(self) -> dict[str, object]:
        """감사 봉투의 `payload`로 그대로 들어간다 (계획 01 §6.3).

        마스킹은 감사 라이터가 직렬화 직전에 한 번 더 적용한다 — 여기서
        마스킹하지 않는 이유는 마스킹 코드를 두 벌 두지 않기 위함이다
        (정본: 설계 03 §7.3).
        """
        return {
            "error_type": type(self).__name__,
            "code": self.effective_code,
            "retryable": self.is_retryable,
            "message": self.message,
            "context": dict(self.context),
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.effective_code!r}, message={self.message!r})"


# ══════════════════════════════════════════════════════════════════════
# 도메인·불변식
# ══════════════════════════════════════════════════════════════════════
class DomainError(OmraError):
    """도메인 규약 위반의 기저."""

    code: ClassVar[str] = "domain.error"


class InvariantViolation(DomainError):
    """버그 신호. 재시도·삼킴이 **절대** 금지된다 (§10.2 규칙 2).

    같은 입력으로 다시 시도해도 같은 결과이므로 재시도는 시간 낭비이고,
    삼키면 잘못된 상태로 계속 운용된다.
    """

    code: ClassVar[str] = "domain.invariant_violation"
    retryable: ClassVar[bool] = False


class IdentifierError(DomainError):
    """`instrument_key`·`sleeve`·`account_id` 해석 실패.

    종목 판정은 exact match로만 한다(정본: 설계 06 §9.1). 해석 실패가
    조용히 `None`을 반환하면 이름 매칭 폴백이 생기고, 그것이 곧 오주문이다.
    """

    code: ClassVar[str] = "domain.identifier"


class TickRuleError(DomainError):
    """호가단위 규칙 위반 — 미지 규칙·비격자 가격·범위 밖 가격."""

    code: ClassVar[str] = "domain.tick_rule"


class LotStepError(DomainError):
    """수량 격자(`lot_step`) 위반 — 음수·0 이하 step·격자 밖 수량."""

    code: ClassVar[str] = "domain.lot_step"


class TransitionError(InvariantViolation):
    """`assert_transition` 위반 — 합법 전이표 밖의 상태 전이 시도."""

    code: ClassVar[str] = "domain.transition"


# ══════════════════════════════════════════════════════════════════════
# 집행 전 판정 (pre-trade) — 체인 소유는 09, 단계 정의는 계획 03 §1.6
# ══════════════════════════════════════════════════════════════════════
class PretradeRejection(OmraError):
    """pre-trade 체인 **내부** 신호. 체인 경계 밖으로 새지 않는다.

    러너 밖으로 전파되면 그것이 버그다(§10.2 규칙 1 — 아키텍처 테스트로 검출).

    Attributes:
        step: 거부가 발생한 체인 단계 식별자.
        order_id: 대상 주문의 내부 ULID (없을 수 있다 — draft 단계 거부).
        reason: 사람이 읽는 사유. 감사로그의 `blocked_by`와는 별개다.
        retry_today: 당일 재시도 가능 여부. False면 그날은 그 레그를 버린다.
    """

    code: ClassVar[str] = "pretrade.rejected"
    retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str = "",
        *,
        step: str = "",
        order_id: str | None = None,
        reason: str = "",
        retry_today: bool = False,
        code: str | None = None,
        **context: _CONTEXT_VALUE,
    ) -> None:
        super().__init__(message, code=code, retryable=False, **context)
        self.step = step
        self.order_id = order_id
        self.reason = reason or message
        self.retry_today = retry_today

    def to_audit_payload(self) -> dict[str, object]:
        payload = super().to_audit_payload()
        payload.update(
            {
                "step": self.step,
                "order_id": self.order_id,
                "reason": self.reason,
                "retry_today": self.retry_today,
            }
        )
        return payload


class TaxSellBlockedError(PretradeRejection):
    """단계 2.5 `tax.assert_not_blocked` 위반 — 금소세 soft-stop·ISA 한도.

    **E7 유래 주문(`intent is OrderIntent.E7_TRANSFER`)은 면제된다**
    (계획 02 §5.6-(c) 불변식 5). 판정 로직의 정본은 설계 10 §13.2다.
    """

    code: ClassVar[str] = "pretrade.tax_sell_blocked"


# ══════════════════════════════════════════════════════════════════════
# 엔진 — 하위 9종의 정의는 설계 07 소유
# ══════════════════════════════════════════════════════════════════════
class EngineError(OmraError):
    """수치 엔진 실패의 기저.

    하위 9종(`InsufficientDataError`·`NotPositiveSemiDefiniteError`·
    `SingularMatrixError`·`InfeasibleError`·`UniverseMismatchError`·
    `UniverseSpecError`·`ViewLimitError`·`ViewSpecError`·`ParameterRangeError`)의
    정의는 설계 07 §2.2 [DD-07-1]-⑤가 소유한다. 기저와 `retryable` 규약만
    여기서 정한다.
    """

    code: ClassVar[str] = "engine.error"


# ══════════════════════════════════════════════════════════════════════
# 설정 — 하위 세분은 설계 04 소유
# ══════════════════════════════════════════════════════════════════════
class ConfigError(OmraError):
    """스키마·상호 제약 위반. 기동 phase A2에서 fail-fast 한다."""

    code: ClassVar[str] = "config.error"


# ══════════════════════════════════════════════════════════════════════
# 브로커 — 하위 확장은 설계 05 소유
# ══════════════════════════════════════════════════════════════════════
class BrokerError(OmraError):
    """브로커 어댑터 실패의 기저."""

    code: ClassVar[str] = "broker.error"


class BrokerAuthError(BrokerError):
    """토큰·키 무효. 재시도해도 같은 결과이므로 `retryable=False`."""

    code: ClassVar[str] = "broker.auth"
    retryable: ClassVar[bool] = False


class BrokerRateLimited(BrokerError):
    """레이트리밋 초과. `RateLimiter` 경유 재시도가 정상 경로다."""

    code: ClassVar[str] = "broker.rate_limited"
    retryable: ClassVar[bool] = True


class BrokerUnavailable(BrokerError):
    """5xx·타임아웃 — 일시적 장애."""

    code: ClassVar[str] = "broker.unavailable"
    retryable: ClassVar[bool] = True


class OrderRejectedError(BrokerError):
    """명시적 거부 응답 → `status=REJECTED`.

    VI·거래정지 유래 거부는 P9 연속 오류 카운트에서 **제외**된다
    (계획 04 §2 M4 추가①). 그 분류는 05가 사유코드로 판정한다.
    """

    code: ClassVar[str] = "broker.order_rejected"
    retryable: ClassVar[bool] = False


class AmbiguousOrderState(BrokerError):
    """응답 유실 — "성공도 실패도 확인 못 함".

    **성공으로도 실패로도 처리 금지**(§10.2 규칙 3). 유일한 합법 처리는
    계획 01 §3.2 프로토콜이다. 재시도하면 이중 주문이 되므로 `retryable=False`.
    """

    code: ClassVar[str] = "broker.ambiguous_order_state"
    retryable: ClassVar[bool] = False


# ══════════════════════════════════════════════════════════════════════
# 데이터·캘린더 — 하위 확장은 설계 06 소유
# ══════════════════════════════════════════════════════════════════════
class DataError(OmraError):
    """데이터 공급 실패의 기저."""

    code: ClassVar[str] = "data.error"


class ProviderError(DataError):
    """provider 호출 실패. 재시도 가능 여부는 원인별로 생성자 인자로 준다."""

    code: ClassVar[str] = "data.provider"


class StaleDataError(DataError):
    """`max_age` 초과. **기다려도 새로워지지 않으므로** `retryable=False`.

    재시도로 해결되는 문제가 아니라 폴백 경로(전일 스냅샷·`unknown` 판정)로
    가야 하는 상황이다.
    """

    code: ClassVar[str] = "data.stale"
    retryable: ClassVar[bool] = False


class CalendarError(OmraError):
    """휴장일 교차검증 불일치 등. fail-safe 소비는 06·12가 정한다."""

    code: ClassVar[str] = "calendar.error"


# ══════════════════════════════════════════════════════════════════════
# 영속성 — 하위 확장은 설계 03 소유
# ══════════════════════════════════════════════════════════════════════
class PersistenceError(OmraError):
    """DB 접근 실패의 기저. `SQLITE_BUSY` 재시도는 tenacity 3회(계획 01 §1.4)."""

    code: ClassVar[str] = "persistence.error"
