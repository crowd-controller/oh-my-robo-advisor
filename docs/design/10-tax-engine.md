# 10. 세금 엔진 (Tax Engine)

> **범위**: `src/omra/tax/` 패키지 전체 — asset location(계좌 분해), 신규자금 배분 워터폴(정기분 자동이체 연계·비정기 목돈), 해외주식 연말 하베스팅, 금소세·건보 임계 추적(외부 금융소득 포함), ISA 비과세 한도 소진률(계약기간 누적·`unknown` 처리), 양도세 집계·판정·신고서 초안, T9 `waterfall_gap_check`, 과표기준가 처리, 매도 종목 우선순위·`tax_overlay`·pre-trade 세금 게이트, E7 상폐 사전 이전의 세금 측 절차, 12월 3중 충돌 조정, `tax.yaml` effective-date 소비.
> **계획 정본**: 02 §1.2·§1.3·§4.3.0·§5 전체 · 03 §1.6(단계 2.5)·§2.2(세금 행)·§2.5·§5.3.2·§6.1 · 00 §3.2 T1~T9·E4·E5·E7 · 05 §2.3·§9.3·§9.5 · 01 §2.2·§4.2·§6.1 · 06 §8.2·§8.4 · 04 §2 M6.
> **선행 문서**: [02-domain-model.md](02-domain-model.md)(Order·Instrument·Money·Clock·예외 계층), [03-data-and-persistence.md](03-data-and-persistence.md)(DDL), [04-configuration-and-secrets.md](04-configuration-and-secrets.md)(YAML 스키마), [06-market-data-and-calendar.md](06-market-data-and-calendar.md)(결제일 계산·환율).
> **이 문서가 소유하는 정의**: 브리프 §2.1 "세금 로직 전체". 인접 경계 — `pending_transfers`·세금 원장 등 **DDL은 03 소유**, pre-trade 체인 순서는 **09 소유**(tax는 단계 2.5의 구현만), E7 주문의 **집행 절차는 08 소유**(tax는 행 생성·슬라이스 산출까지), 잡 등록·시각은 **12 소유**(tax는 잡 본체 함수만), 밴드·리밸런서 알고리즘은 **07 소유**.

---

## 1. 개요 — 설계 대상과 책임

### 1.1 책임 요약과 자동화 등급 매핑

`tax/`는 한국 세제(일반위탁/ISA/연금저축/IRP/업비트)를 1급 시민으로 다루는 유일한 패키지다(정본: 00 §1). 이 시스템에서 세금 엔진이 만드는 화폐 가치는 리밸런싱 알파(연 5~21bp — 05 §4.5.1 차용치)보다 크다 — 연금 공제 미소진 1회가 79~99만원(05 §9.3)이므로, **세금 엔진의 실패는 "몇 bp"가 아니라 "몇십만 원" 단위**다. 그래서 이 패키지의 fail-safe 방향은 언제나 "과대추정·보수적 차단·사람 호출"이다.

| 등급(00 §3.2) | 책임 | 이 문서의 절 |
|---|---|---|
| **T1** (A0) | 손익·배당·분배금·원천징수 연중 집계, 금소세·건보 임계 추적 | §4, §8 |
| **T2** (A4+조건부 A3) | 외부 금융소득 등록·70% 도달 시 질의 | §8.3 |
| **T3** (1년차 A3 → 2년차+ A1) | 연말 하베스팅 | §11 |
| **T4** (A0) | 양도세 집계·250만 판정·신고서 초안 | §12 |
| **T5·T6** (A5) | 대행신고 신청·납부 — 알림·딥링크·산출물만 제공 | §12.1 |
| **T7** (A5) | 세법 개정 반영 — `tax.yaml` diff 초안 생성만 | §3.3 |
| **T9** (A0 감지 + A5 이체) | `waterfall_gap_check`(11/1) | §7 |
| **E4·E5** (A4 / A2+A3) | 워터폴 계산·이체 지시·`pending_transfer_reserve` | §6 |
| **E7** (A2) | 상폐 D−10 사전 이전의 세금 측 절차(`pending_transfers` 생성·슬라이스) | §14 |

### 1.2 설계 불변 원칙

1. **증권사 집계가 정본이다.** 자체 계산(이동평균·과표기준가·누적기)은 사전 시뮬레이션·경고 전용이며, 두 값이 어긋나면 증권사 값이 이긴다 (정본: 02 §5.2). 모든 사람용 산출물에는 "이 초안은 참고용이며 증권사 대행신고 산출액이 정본이다" 문구를 삽입한다 (정본: 00 §3.2 T4).
2. **로트 단위 TLH는 존재하지 않는다.** 해외주식 양도손익은 이동평균단가 체계이므로 통제 변수는 (종목 × 이동평균단가)뿐이다 (정본: 02 §5.1, 05 §9.5). 로트 원장은 분석·리포트 전용이다.
3. **귀속은 결제일, 환산은 결제일 고시환율, effective-date 선택은 주문 제출 시각의 KST 날짜.** (정본: 02 §5.1·§4.7-b, 01 §6.1)
4. **판정 불가 = 보수적.** 과표기준가 폴백은 실차익(과대추정), 외부 금융소득 미응답은 과대 가정 유지, ISA 소진률 `unknown`은 70% 행과 동일 처분(단 수치 가정 금지) (정본: 02 §5.2·§5.3, 00 §3.2 T2).
5. **세금 엔진은 주문을 "생성"하는 예외적 두 경로만 갖는다** — 하베스팅(자발적 매도, 승인 사다리 하)과 E7 슬라이스(`mandatory_orders`). 그 외에는 계획을 **차단·정렬·태깅**만 한다(`tax_overlay`·`blocked_for_sell`·`assert_not_blocked`). 밴드 복귀 매도의 종목·수량은 절대 바꾸지 않는다 (정본: 02 §5.4).
6. **세율·한도·임계의 하드코딩 금지** — 전부 `tax.yaml` effective-date 버전에서 온다 (정본: 00 §5 원칙 6, 02 §5.5).

### 1.3 이웃 문서와의 경계 (요약)

| 주제 | tax가 하는 것 | 이웃이 하는 것 |
|---|---|---|
| 계좌 분해 | `decompose_to_accounts` 알고리즘·산출물(§5) | 호출·재분해 트리거 판정·밴드 판정은 [07-portfolio-engine.md](07-portfolio-engine.md) |
| E7 | eligibility 판정, `pending_transfers` 행 생성, 슬라이스 수량 산출(§14) | **상태 전이 정의**·주문 제출·체결 추적·잔량은 [08-execution.md](08-execution.md) §14.2, DDL은 [03](03-data-and-persistence.md), KR-04 감지·`pending_tax_events` 기록은 [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md) |
| pre-trade | 단계 2.5 `assert_not_blocked` 구현(§13.2) | 체인 순서·소유는 [09-safety-protections.md](09-safety-protections.md) |
| 잡 | `waterfall_gap_check`·`tax_harvest`·연간 세무 잡의 **본체 함수**(§7·§11·§12) | 등록·시각·catch-up 분류는 [12-scheduling-and-operations.md](12-scheduling-and-operations.md) (정본: 01 §4.2·§4.2.1) |
| 결제일·D*·환율 | 소비자 | 계산기는 [06-market-data-and-calendar.md](06-market-data-and-calendar.md) (정본: 01 §4.1, 02 §4.7) |
| 승인 UX | 승인 필요 판정·대기 항목 생성(§13.1) | Telegram 상호작용·타임아웃 집행은 [13-web-and-telegram.md](13-web-and-telegram.md) (파라미터 정본: 03 §5.3.2) |
| YAML 스키마 | 소비 모델(pydantic) 정의 | 파일 스키마·키 정본은 [04-configuration-and-secrets.md](04-configuration-and-secrets.md) (키 이름 정본: 02 부록 A) |

---

## 2. 모듈 구조

### 2.1 파일 구성

계획 01 §2의 모듈 트리는 `tax/`를 단일 디렉토리로만 지정하므로 내부 분할은 이 문서가 확정한다.

> **[DD-10-1] `tax/` 내부 파일 분할과 파사드**
> - 결정: 아래 12개 모듈로 분할하고, 외부 소비자(rebalancer·execution·protections·web·rpc)는 `TaxEngine` 파사드 하나만 import한다.
> - 근거: 02 §4.3 의사코드가 호출하는 API가 4종(`blocked_for_sell`·`mandatory_orders`·`tax_overlay`·`assert_not_blocked`)으로 고정되어 있어 파사드가 자연 경계다. 내부 모듈은 기능별 단일 책임으로 나눠 M4(원장 스키마 선반영)→M6(엔진 본체)→M8(절세계좌) 순의 마일스톤 분할 구현이 가능하게 한다(04 §2).
> - 계획 문서와의 관계: 01 §2 트리의 여백을 채움. 충돌 없음.

```
src/omra/tax/
├── __init__.py          # TaxEngine 파사드 재수출
├── engine.py            # TaxEngine — 소비자 계약의 유일한 진입점 (§2.2)
├── params.py            # TaxParamStore — tax.yaml effective-date 소비 (§3)
├── cost_basis.py        # CostBasisCalculator ABC + MovingAverage 구현 (§4)
├── ledger.py            # TaxLedgerService — 결제일 귀속 원장 갱신·대사 (§4)
├── asset_location.py    # decompose_to_accounts + 표1/표2 소비 (§5)
├── waterfall.py         # 워터폴 계산·이체 지시·pending_transfer_reserve (§6)
├── gap_check.py         # waterfall_gap_check 잡 본체 (§7)
├── income.py            # FinancialIncomeTracker — 금소세·건보 (§8)
├── isa.py               # IsaUsageTracker — 계약기간 누적 소진률 (§9)
├── basis_price.py       # 과표기준가 소스 스위치 api|fallback (§10)
├── harvest.py           # HarvestPlanner — 연말 하베스팅 (§11)
├── capital_gains.py     # CapitalGainsReporter — 양도세 T4~T6 산출물 (§12)
├── overlay.py           # tax_overlay·blocked_for_sell·assert_not_blocked·매도 우선순위 (§13)
└── transfers.py         # TransferPlanner — E7 세금 측 절차 (§14)
```

import 규율(계약 원문: 01 §2.2): 01 §2.2의 금지줄은 관측 4레이어(`research`·`surveillance`·`realtime`·`labs`)에만 걸려 있고 `tax`는 default-allow다. 아래 **자기 제한은 계획에 없는 설계 규율이며 [DD-10-2]의 일부**다 — `tax`는 `core`·`persistence`(ro + 자기 repo)·`data`(과표기준가·환율 스냅샷 읽기)·`calendar`·`config`·`audit`만 import한다. `tax → execution·brokers·engine.optimizer`의 **런타임** import는 두지 않는다(주문 제출은 execution이 `mandatory_orders`/하베스팅 산출물을 **가져가는** 방향이다). 예외는 `OrderDraft` **타입 주석 한 건**이며 `if TYPE_CHECKING:` 하에서만 참조한다(반환 타입 정본이 08 §4.1이고 08 §4.2가 `list[OrderDraft]`로 소비하므로 타입을 재정의하면 두 벌이 된다). 이 예외를 import-linter 계약 파일에 어떻게 표기할지는 **01 문서 소유**다 — 런타임 간선이 아니므로 01 §2.2 금지줄과 충돌하지 않는다. `research`·`surveillance`·`realtime`은 `tax`를 import할 수 없다(01 §2.2 금지줄).

### 2.2 TaxEngine 파사드와 소비자 계약

```python
# src/omra/tax/engine.py
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from collections.abc import Iterable, Sequence
from omra.core.models import Order, OrderSide, OrderIntent   # 정의 정본: 02 §7.1·§7.2
if TYPE_CHECKING:                                            # ★ §2.1 자기 제한 참조
    from omra.execution.assembler import OrderDraft          # 정의 정본: 08 §4.1

class TaxEngine:
    """tax/ 파사드. 아래 4개 메서드가 02 §4.3 의사코드·03 §1.6 체인이 참조하는
    계약의 전부이며, 시그니처 변경은 07·08·09 문서와 동시 개정 사항이다."""

    def __init__(
        self,
        params: TaxParamStore,               # §3
        ledger: TaxLedgerService,            # §4
        income: FinancialIncomeTracker,      # §8
        isa: IsaUsageTracker,                # §9
        harvest: HarvestPlanner,             # §11
        transfers: TransferPlanner,          # §14
        waterfall: WaterfallEngine,          # §6
        approvals: TaxApprovalRegistry,      # §13.1
        clock: Clock,                        # 정의 정본: 02-domain-model.md
        audit: AuditLogger,                  # 정의 정본: 03-data-and-persistence.md
    ) -> None: ...

    # ── 02 §4.3 의사코드 (1)·(7) 소비 계약 ─────────────────────────────
    def blocked_for_sell(
        self, keys: Iterable[tuple[AccountId, InstrumentKey]]
    ) -> SellBlockMask:
        """§5.2 soft-stop·경고 티어 확인 대기·ISA 70%/unknown 확인 대기의
        '매도 방향 마스크'. 집합 분할이 아니다 (정본: 02 §5.4)."""

    def mandatory_orders(
        self, state: BotStateView, accounts: Sequence[AccountView]
    ) -> list[OrderDraft]:
        """breach와 무관하게 그날 반드시 나가야 하는 주문 — 현재는 E7 슬라이스뿐
        (정본: 02 §4.3 보조 정의 표). 반환 타입 정의 정본은 08 §4.1 `OrderDraft`이며
        08 §4.2 조립 3단계가 이 리스트를 그대로 병합한다."""

    def tax_overlay(
        self, orders: list[OrderDraft], ctx: PlanContext
    ) -> list[OrderDraft]:
        """현금 조달형 매도의 종목 우선순위 적용 + 연말 귀속 태그 + sell_blocked
        레그 제거. 밴드 복귀 매도의 종목·수량은 불변 (정본: 02 §5.4).
        08 §4.2 조립 2단계의 `ctx.tax.overlay(band_drafts)` 호출 지점과 동일 계약."""

    # ── 03 §1.6 pre-trade 단계 2.5 ────────────────────────────────────
    def assert_not_blocked(self, order: Order) -> None:
        """매도 방향에만 적용. E7 유래 주문(order.intent is OrderIntent.E7_TRANSFER)은
        면제 (정본: 03 §1.6, 02 §5.6-(c) 불변식 5). 위반 시 TaxSellBlockedError."""
```

**주문 출처 태그는 `OrderIntent` 하나뿐이다.** 타입·필드·값 집합의 단일 정본은 [02-domain-model.md](02-domain-model.md) §7.2 [DD-02-6]·[DD-02-17](11값)이고, 영속 필드는 `Order.intent`, draft 단계 필드는 같은 enum·같은 값을 담는 `OrderDraft.origin`(정의 정본: [08-execution.md](08-execution.md) §4.1)이다. 이 문서가 종전에 쓰던 타입명 `OrderOrigin`·필드명 `PlannedOrder.origin`과 8값 열거는 **폐지**하고 02 [DD-02-17]-④ 정규화표대로 아래와 같이 읽는다 — **매도/매수 세분은 enum 값이 아니라 `intent × side` 조합**이다([DD-02-17]-③).

| 종전 10 표기 | 현행 정본 표기 |
|---|---|
| `REBALANCE` | `BAND_RESTORE` \| `CLASS_BAND` \| `TARGET_SHIFT` — 밴드 복귀 매도 판별은 이 3값 집합 비교 |
| `CASHFLOW` · `CONSTRAINT_CURE` · `WITHDRAWAL` | 동명 `OrderIntent` 값 (항등) |
| `HARVEST_SELL` / `HARVEST_REBUY` | `HARVEST` × `side=SELL` / `× side=BUY` |
| `E7_TRANSFER_SELL` / `E7_TRANSFER_BUY` | `E7_TRANSFER` × `side=SELL` / `× side=BUY` |
| 타입명 `OrderOrigin` · 필드명 `order.origin` | `OrderIntent` · `Order.intent`(영속) / `OrderDraft.origin`(draft) |

E7 면제 판정 키는 08 §14.4 불변식 5·09 §6.1 단계 2.5와 **같은 타입·같은 필드·같은 값**(`order.intent is OrderIntent.E7_TRANSFER`)이다. `constraint_cure` 표시의 계획 근거는 02 §4.3.0-(g), E7 면제의 계획 근거는 03 §1.6이다.

### 2.3 영속화 의존 — 요구 스키마 명세 (DDL 정본: 03)

`tax/`가 읽고 쓰는 테이블. **DDL 원문은 [03-data-and-persistence.md](03-data-and-persistence.md) 소유**이며 아래는 tax가 요구하는 최소 필드 계약이다.

아래 표는 **03의 실제 테이블명·컬럼명**으로 쓴다(03 §3.3.8 대응표의 수용분 — 종전 이 표가 쓰던 `tax_ledger`·`avg_cost_basis`·`basis_price_snapshots`·`transfer_instructions`·`tax_approvals` 등의 가명은 폐지).

| 테이블 (03의 절) | R/W | tax가 쓰는 필드 | 계획 근거 |
|---|---|---|---|
| `tax_events` (§3.3.8) — 결제일 귀속 단일 원장 | W(krx_eod·us_reconcile 서브스텝)·R | `(id, account_id, instrument_key, kind[realized_pnl\|dividend\|distribution\|interest\|withholding\|redemption], amount_krw, qty, settle_date, fx_rate, source[broker_032\|period_rights\|computed\|manual], fill_id, created_at)`. 실현손익은 `kind='realized_pnl'` + `amount_krw` **부호**로 표현하고 별도 `taxable_krw` 컬럼을 두지 않는다(과세 차익 산출은 §10.2 함수) | 01 §1.3("세금 원장(결제일 기준)"), 02 §4.7-(b), 03 [DD-03-11] |
| `taxbase_snapshots` (§3.3.8) — 과표기준가 | R/W | `(instrument_key, as_of, taxbase_price, source, fetched_at)` — 매수·매도 시점 스냅샷. `source` 값 집합은 SP-C1 확정 전까지 **[확인 필요]**이며, 폴백 확정 시 적재 없이 스키마만 남는다(03 [DD-03-11]) | 02 §5.3 |
| `contribution_ledger` (§3.3.8, 신설 [DD-03-32]) | R/W | `(account_id, year, ytd_paid_krw, source[api\|csv\|manual], as_of, updated_at)` | 02 §1.3.2 |
| `harvest_ledger` (§3.3.8, 신설 [DD-03-32]) | R/W | `(year, order_amount_krw_cum, realized_target_krw_cum, updated_at)` — NAV 20% 게이트 입력 | 00 §3.2 T3 |
| `approval_requests` (§3.3.9) — 세금 A3 대기 + E5 이체 지시 | R/W (kind별 행) | `(id, kind, subject_key, account_id, payload_json, requested_at, grace_deadline, timeout_action, state, decided_at, decided_by)`. tax가 쓰는 `kind`: `harvest_y1`·`harvest_safemode`·`isa_sell_confirm`·`income_warn_sell`·`external_income_confirm`·`e7_demoted`·`e5_transfer`(§13.1) | 03 §5.3.2, 03 [DD-03-12] |
| `positions` (§3.2.1) — 이동평균단가 | R/W | `(account_id, instrument_key, qty, avg_cost, updated_at)`. **별도 원가 테이블을 두지 않는다** — 같은 사실의 이중 보관 금지(03 [DD-03-32]) | 02 §5.1 |
| `pending_transfers` (§3.2.4, E7) | R/W | 02 §5.6-(a) 스키마 그대로: `(account_id, instrument_key, abol_date, substitute_key, total_qty, slices_total, slices_done, state, created_at)` PK `(account_id, instrument_key)` | 02 §5.6 |
| `pending_tax_events` (§3.3.2) | **R only** (`persistence.ro`) | `(instrument_key, risk_type, abol_date, cross_checked, observed_at, state)` — 쓰기는 surveillance 전용 repo | 06 §8.4, 01 §2.2 |

**테이블을 만들지 않고 파생하는 것**(03 [DD-03-11]·[DD-03-36], 파생 질의 계약: 03 §3.5) — tax는 아래를 **누적기 테이블 없이** 매번 재계산한다. 계산 로직은 tax 소유, 조회 경로(인덱스)는 03 소유다.

| 파생값 | 원천 | 이 문서의 소비 지점 |
|---|---|---|
| YTD 실현손익 `G` | `tax_events(kind='realized_pnl')`, `ix_taxev_year` | §11.2 |
| 금소세·건보 YTD 누적 | `tax_events(kind IN ('dividend','distribution','interest','redemption'))` + 외부소득 config | §8.1 |
| ISA 계약기간 누적 소진률 | `tax_events` + `tax.isa_usage_opening_amount` | §9.1 |
| 로트 원장(분석·리포트 전용) | `fills` ⨝ `orders` | §4.3 |
| E7 기집행 **수량**(회차 아님) | `fills` ⨝ `orders(intent='e7_transfer', account_id, instrument_key)` | §14.3 |
| `pending_transfer_reserve[a]` | `approval_requests(kind='e5_transfer')` `payload_json.amount_krw` 합 | §6.4 |

> **[DD-10-2] tax 쓰기 리포지토리와 import 자기 제한** *(03 [DD-03-32]·§4 repos 표 수용으로 개정)*
> - 결정: 위 쓰기 테이블은 `persistence.repos.tax_events`(= `tax_events`·`taxbase_snapshots`·`contribution_ledger`·`harvest_ledger` 4테이블을 담는 단일 모듈, 03 §4 repos 표) + `persistence.repos.pending_transfers` + `persistence.repos.approvals`(protections·rpc와 공유, kind별 행)로 접근한다. 종전 이 DD가 요구한 `tax_*` repo **군**은 03이 단일 모듈로 수렴시켰으므로 그 판정을 따른다. 아울러 `tax`의 import 대상을 §2.1 목록으로 자기 제한한다.
> - 근거: 01 §2.2의 화이트리스트 방식(쓰기 = repo 모듈별 `TABLES` 선언)을 관측 레이어 밖에도 일관 적용. `pending_tax_events`는 surveillance 전용 repo이므로 tax는 `persistence.ro`로만 읽는다(06 §8.4와 일치).
> - 계획 문서와의 관계: 01 §2.2는 관측 4레이어만 금지줄로 봉인하고 나머지는 default-allow로 둔다 — 그 여백을 같은 패턴으로 채움. 계약 파일 등재 여부는 01 문서 소유. 충돌 없음.

---

## 3. 세법 파라미터 — `tax.yaml` effective-date 소비

### 3.1 TaxParams 모델

파일 스키마·키 이름 정본은 [04-configuration-and-secrets.md](04-configuration-and-secrets.md)(§5.8 `tax.yaml` · §4.2 `TaxCfg`/`WaterfallCfg`)이고, 소비 모델(`TaxParams`)의 필드 구성은 이 절이 소유한다.

> **[DD-10-16] 세법 파라미터 이중 정의 해소 — `tax.yaml` = 법령값 정본, `config.yaml` = 운영 스위치·사용자 입력 정본**
> - 결정: ① **세율·공제·한도(법령값)** 는 `tax.yaml`의 effective-date 버전 하나만 정본으로 두고, 소비 모델 `TaxParams`는 04 §5.8 `tax.yaml` `params:` 블록과 **필드 대 필드로 일치**시킨다(아래 코드). ② **운영 스위치·사용자 입력·알림 티어**(하베스팅 시즌 시작일·재매수 버퍼·자동 실행 승격·과표기준가 소스·금소세 티어 집합·ISA 사용자 입력·건보 자격·한계세율·gap check 일자/리마인더·이체 예약 만료일·`fill_pension_to_limit`)는 `config.yaml`의 `tax.*`·`waterfall.*` 하나만 정본으로 두고 그 스키마 소유는 04 §4.2(`TaxCfg`·`WaterfallCfg`)다 — tax는 재정의하지 않고 주입받는다. ③ 따라서 tax 엔진에 주입되는 것은 두 출처의 **결합 뷰** `TaxSettings`이며, 이 문서의 다른 절이 `params.X`로 쓰는 이름은 아래 소속표대로 `settings.law.X` 또는 `settings.cfg.X`/`settings.waterfall.X`로 읽는다.
> - 근거: 04 §14-15의 조율 요청("같은 법령값의 출처가 둘이면 개정 때 한쪽만 갱신된다")과 그 권고 방향(법령값은 `tax.yaml` 단일 정본)을 수용한다. 02 §5.5가 "세율·공제·한도는 `tax.yaml`에 effective-date 버전으로"를 명시하므로 법령값의 귀속은 계획이 이미 정했고, 반대로 사용자 입력(ISA 계약 개시일·건보 자격)은 effective-date 축이 없어 버전 파일에 둘 이유가 없다. 이 분리가 서면 04의 상호 제약 C-29(두 곳의 값 불일치 시 `ConfigConflictError`)는 **교집합이 사라져 무효 조건**이 되므로 04에 제거를 요청한다(§17 #17).
> - 계획 문서와의 관계: 02 §5.5의 귀속 규정을 그대로 따르고, 02 부록 A의 `tax.deduction`·`tax.isa_free_limit`·`waterfall.pension_deduct_cap_*` 행은 04 §14-15 권고대로 "`tax.yaml`의 같은 값을 가리키는 별칭"으로 재해석한다(`AppConfig` 필드에서 제거 — 04 소유 작업). 요청 출처: 04 §14-15. 충돌 없음.

```python
# src/omra/tax/params.py
from pydantic import BaseModel
from datetime import date
from decimal import Decimal

# ── (a) tax.yaml 유효 버전 = 법령값만 (04 §5.8 params: 블록과 1:1) ──────────
class TaxParams(BaseModel, frozen=True):
    effective_from: date

    # 해외주식 양도세 (정본: 05 §2.3)
    overseas_cg_rate: Decimal = Decimal("0.22")               # 20% + 지방세 2%
    overseas_cg_deduction_krw: Decimal = Decimal("2500000")   # 02 부록 A `tax.deduction`의 정본 값

    # 국내상장 해외 ETF / 배당 (정본: 05 §2.3)
    dividend_wht_rate: Decimal = Decimal("0.154")
    fin_income_aggregate_threshold_krw: Decimal = Decimal("20000000")  # 금소세 2,000만

    # ISA (정본: 05 §2.3, 02 §5.2)
    isa_free_limit_krw: Decimal = Decimal("2000000")     # 서민형 400만은 개정 버전으로 교체
    isa_excess_rate: Decimal = Decimal("0.099")
    isa_annual_contrib_cap_krw: Decimal = Decimal("20000000")   # 연 납입한도 (05 §2.3, 02 §1.3-3)

    # 연금 (정본: 02 §1.3·§1.3.2, 05 §2.3)
    pension_deduct_cap_savings_krw: Decimal = Decimal("6000000")
    pension_deduct_cap_total_krw: Decimal = Decimal("9000000")
    pension_contrib_cap_total_krw: Decimal = Decimal("18000000")

    # 하베스팅 게이트 (정본: 00 §3.2 T3)
    harvest_cost_gate_factor: Decimal = Decimal("0.5")   # 왕복비용 < 절세액 × 0.5
    harvest_annual_nav_cap: Decimal = Decimal("0.20")    # 연 주문금액 ≤ NAV 20%

    # 가상자산 과세 훅 — 시행 유예 추적, 활성 세율 없음 (정본: 02 §7)
    crypto_tax_enabled: bool = False

# ── (b) 결합 뷰 — 엔진에 주입되는 것은 이것이다 ─────────────────────────────
class TaxSettings(BaseModel, frozen=True):
    law: TaxParams          # 위 (a). 선택 규칙은 §3.2
    cfg: "TaxCfg"           # config.yaml `tax.*`       — 정의 정본: 04 §4.2
    waterfall: "WaterfallCfg"  # config.yaml `waterfall.*` — 정의 정본: 04 §4.2
```

**필드 소속표**(이 문서의 다른 절이 쓰는 이름 → 실제 출처. 값·기본값 정본은 각 열의 문서다):

| 이름 | 출처 | 비고 |
|---|---|---|
| `overseas_cg_rate` · `overseas_cg_deduction_krw` · `dividend_wht_rate` · `fin_income_aggregate_threshold_krw` · `isa_free_limit_krw` · `isa_excess_rate` · `isa_annual_contrib_cap_krw` · `pension_deduct_cap_*` · `pension_contrib_cap_total_krw` · `harvest_cost_gate_factor` · `harvest_annual_nav_cap` · `crypto_tax_enabled` | `settings.law.*` (`tax.yaml`) | 법령값 — effective-date 버전 축 |
| `income_alerts`(api/fallback 두 집합·mapping) · `basis_price_source` · `harvest_start` · `harvest_rebuy_buffer_pct` · `harvest_auto_enabled` · `isa_usage_alert` · `isa_contract_start_date` · `isa_usage_opening_amount` · `isa_usage_opening_as_of` · `health_insurance_status` · `user_marginal_credit_rate` · `deduction`·`isa_free_limit`(02 부록 A 별칭) | `settings.cfg.*` (04 §4.2 `TaxCfg`) | 운영 스위치·사용자 입력. `_krw` 접미를 붙이지 않는다(키 이름 규칙: 04 §4.1 규칙 1) |
| `fill_pension_to_limit` · `gap_check_date` · `reminders`(D-12/D-5/D-1) · `transfer_reserve_expiry_days` | `settings.waterfall.*` (04 §4.2 `WaterfallCfg`) | 워터폴 운영 파라미터 |

`income_alerts`는 스칼라 목록이 아니라 **mapping**이며 두 집합의 값(api = 1,000/1,200/1,600/1,800만, fallback = 1,000/1,400/1,800/1,900만)의 정본은 02 §5.3이다(스키마: 04 §4.2 `IncomeAlertSets`).

### 3.2 버전 선택 규칙

```python
class TaxParamStore:
    """tax.yaml의 versions: [...] 목록(effective_from 내림차순 정렬)을 보유.
    반환은 법령값 `TaxParams`이며, 운영 키(`TaxCfg`·`WaterfallCfg`)는 버전 축이 없으므로
    `TaxSettings`로 결합할 때 현행 config 값을 그대로 얹는다 ([DD-10-16])."""

    def at(self, kst_date: date) -> TaxParams:
        """effective_from <= kst_date 인 것 중 가장 최신 버전.
        기준 시각 = **주문 제출 시각의 KST 날짜** (정본: 01 §6.1 —
        체결일·결제일이 아니다. 03 §2.2의 기간 귀속 규칙과 동일)."""

    def for_settlement_year(self, year: int) -> TaxParams:
        """연 단위 집계(양도세 판정·gap check)는 해당 과세연도 1/1 기준 버전.
        연중 개정이 있으면 개정 effective_from 이후 발생분에 신 버전 적용."""
```

- **집행 경로**(soft-stop 판정·매도 확인·E7)는 `at(주문 제출 KST 날짜)`를 쓴다 — 01 §6.1 그대로.

> **[DD-10-13] 집계 경로의 effective-date 기준 = 이벤트 결제일**
> - 결정: **집행 경로**(주문 생성·pre-trade 판정)는 01 §6.1대로 `at(주문 제출 KST 날짜)`를 쓰고, **집계 경로**(YTD 누적·임계 비교·연말 양도세 판정)만 이벤트의 **결제일**이 속한 날짜의 버전을 쓴다.
> - 근거: 손익 귀속 자체가 결제일이므로(02 §5.1) 임계·공제액 비교가 다른 기준을 쓰면 연말 경계(12/30 체결·1/2 결제)에서 "귀속은 익년인데 적용 세율은 전년"이 된다. 집계에는 "주문 제출 시각"이 존재하지 않는 이벤트(배당·원천징수·해지상환)도 포함되어 01 §6.1의 문구를 그대로 적용할 수 없다.
> - 계획 문서와의 관계: 01 §6.1은 "`tax.yaml` 등 버전 파일은 주문 제출 시각의 KST 날짜로 고른다(체결일·결제일이 아니다)"라고 **주문 경로를 전제로** 규정한다. 이 DD는 그 규칙을 집행 경로에서 그대로 유지하고, 규정이 다루지 않은 집계 경로만 채운다. **01 §6.1을 "모든 경로"로 읽으면 충돌이므로 §17 #13에 이견으로 등재**한다.

### 3.3 T7 — 세법 개정 diff 초안 (A5)

세법 해석의 자동 반영은 **금지**다(00 §3.2 T7 — "자동화 불가가 아니라 자동화 금지"). tax가 제공하는 것은 diff 렌더링뿐이다.

```python
def render_tax_yaml_diff(current: TaxParams, proposed: TaxParams) -> str:
    """runbook '연 1회 세제 리뷰'(02 §5.5)에서 사람이 작성한 proposed 버전을
    현행과 필드 단위 비교해 마크다운 diff를 만든다. 적용은 A5(사람 승인 + 배포)."""
```

- 개정 후보의 **탐지**는 `research/` 다이제스트(키워드 게이트 ③ `세법`·`개정`·`시행령`·`ISA`·`연금저축`·`금융투자소득`·`건강보험료` — 07 §4.1)가 하고, **수치 결정과 승인은 사람**이다. LLM이 `tax.yaml` 값을 생성하는 경로는 존재하지 않는다(00 §6.2 "LLM의 직접 코드 수정" 금지, 04 부록 A.2 "LLM의 소스 코드·config 직접 수정" 영구 배제).
- 타임아웃 동작: 미승인 시 **직전 `tax.yaml` 유지 + 분기 1회 리마인드**(정본: 03 §5.3.2). 운용 정지가 아니다.
- 배당 분리과세 세율표·분기 키는 **만들지 않는다** — ETF·펀드·리츠 제외로 현 유니버스 적용분 0 (정본: 02 §5.5, 05 §2.3).

### 3.4 오류 경로

| 상황 | 동작 |
|---|---|
| 기동 시 유효 버전 0개 / 스키마 검증 실패 | 기동 셀프체크 실패 항목 → 자기복구 사다리(01 §6.4 (b)). 세금 파라미터 없이 집행을 시작하지 않는다 |
| 런타임 리로드(`RELOAD_CONFIG`) 실패 | **직전 인메모리 버전 유지 + warning** — T7 타임아웃 동작(직전 파라미터 유지)과 동일 방향 |
| `effective_from`이 미래뿐인 버전만 존재 | 유효 버전 0개와 동일 취급 |
| `isa_contract_start_date` 미입력인데 ISA 계좌 활성 | 소진률 `unknown` 경로(§9.2)로 강등 + 최초 브리핑·월간 리포트에 입력 요청 1건 (정본: 02 §5.2) |

### 3.5 검증 항목

- [ ] `at()`이 버전 경계일(당일 00:00 KST)에 신 버전을 선택한다 — 표 기반 test vector.
- [ ] 집계 경로가 결제일 기준 버전을 쓴다(12/30 체결·1/2 결제 케이스).
- [ ] 유효 버전 부재 시 기동이 실패한다(집행 개시 불가).
- [ ] `income_alerts` 두 자식 키가 mapping으로 파싱된다(값 정본 02 §5.3 / 스키마 04 §4.2 — 스칼라 목록이 아니다).
- [ ] [DD-10-16] 분리: `TaxParams` 필드 집합이 04 §5.8 `tax.yaml` `params:` 키 집합과 **정확히 일치**하고, 운영 키(`harvest_start`·`basis_price_source`·`isa_usage_alert` 등)가 `TaxParams`에 **없다**(있으면 이중 정의 재발) — 스키마 대조 테스트.

---

## 4. 원가 산정과 세금 원장 — `CostBasisCalculator`

### 4.1 인터페이스와 이동평균 구현

원가 산정기는 **인터페이스로 주입**한다 — KIS 실정산이 이동평균이 아닌 것으로 실증되면 구현체만 교체한다(정본: 02 §5.1).

```python
# src/omra/tax/cost_basis.py
from abc import ABC, abstractmethod

class CostBasisCalculator(ABC):
    @abstractmethod
    def on_buy(self, key: PositionKey, qty: Decimal, price: Decimal,
               settle_date: date) -> AvgCost: ...
    @abstractmethod
    def on_sell(self, key: PositionKey, qty: Decimal, price: Decimal,
                settle_date: date) -> RealizedResult: ...
    @abstractmethod
    def unrealized(self, key: PositionKey, mark_price: Decimal) -> Decimal: ...

class MovingAverageCalculator(CostBasisCalculator):
    """브로커와 동일한 이동평균 단일 경로 (정본: 02 §5.1).
    매수: avg' = (avg×qty + price×buy_qty) / (qty + buy_qty)  [통화 단위 유지]
    매도: 평단 불변, realized = (price − avg) × sell_qty
    ── 이동평균 체계에서 매도는 평단을 바꾸지 않는다는 성질이
       §11.3 수량식 q_i = floor(잔여목표 / |p_i − 평단_i|)의 정확성 근거다."""
```

- 계좌·과세유형별 복수 구현체를 **두지 않는다** — ISA는 계좌 내 통산이 증권사 산출이고 연금·IRP는 과세이연이라 원가 추적 불요(정본: 02 §5.2). 인스턴스는 (일반위탁 해외상장), (일반위탁·ISA 국내상장) 두 포지션 집합에 같은 클래스로 적용한다.
- 국내상장 ETF의 이동평균 가정은 **브로커 관행 가정(미확인)**이며 별도 폴백을 두지 않는다 — 오차는 §10 폴백의 과대추정 여유(~15%) 안에서 흡수(정본: 02 §5.2). M6 DoD 3에서 첫 매도 발생 시 증권사 명세와 1회 대사한다(04 §2 M6).

### 4.2 결제일 귀속·환율

```
실현손익(KRW) = (매도가 − 이동평균단가) × 수량 × FX(결제일 고시환율)
  귀속 연도  = 결제일이 속한 해 (정본: 02 §5.1 — 결제일(T+1) 기준)
  FX 스냅샷  = 02 §4.7-(b) "세금 원장 = 결제일 고시환율" 행. 소스 우선순위는
               KisFxFetcher → FdrFxFetcher (02 §4.7-(a), 구현: 06 문서)
  반올림     = KRW 원 단위 절사 (02 §4.7-(d))
```

갱신 지점(잡 정본: 01 §4.2): `krx_eod`(15:40) 서브스텝에서 국내 체결분, `us_reconcile`(US 마감+20분)에서 미국 체결분을 `TaxLedgerService.on_settlement(fill)`로 반영한다. **미결제(T+1/T+2 미도래) 체결분은 원장에 `pending` 상태로 두고 결제일 도래 시 확정**한다 — 연말 D\*−2 역산(§11.1)과 정합.

### 4.3 로트 원장 (분석 전용)

로트 원장은 **별도 테이블을 만들지 않는다** — `fills ⨝ orders`에서 파생한다(정본: 03 [DD-03-11], 파생 질의 계약 03 §3.5). 이는 "세액 계산 경로에 로트 개념을 두지 않는다"(02 §5.1)의 물리적 표현이다. 용도는 **분석·리포트 전용**(절세 리포트의 "로트별 손익 분해" 참고 표시)이며, 계획이 부여한 것 이상의 소비자를 만들지 않는다. 이동평균단가의 로컬 사본은 `positions.avg_cost` 한 곳뿐이다(03 §3.2.1, [DD-03-32] — 이중 보관 금지).

### 4.4 브로커 대사

```python
class TaxLedgerService:
    def reconcile_with_broker(self, year: int) -> LedgerReconcileResult:
        """`해외주식 기간손익`(032)의 연간 실현손익과 자체 이동평균 계산을 대사
        (정본: 00 §3.2 T1, 04 §2 M6 DoD 3). 불일치 시:
        ① 증권사 값을 정본으로 채택해 집계·판정에 사용 (02 §5.2)
        ② 자체 계산과의 차이를 warning + 월간 리포트 항목으로 기록
        ③ 차이 원인 미해명 상태가 2회 연속이면 하베스팅 자동 실행(A1)을
           A3로 강등한다 — 수량·손익 산식이 틀린 채 자동 매도할 수 없다."""
```

③은 계획에 없는 안전장치다 — 아래 DD로 선언한다.

> **[DD-10-3] 대사 불일치 2회 연속 시 하베스팅 A1 → A3 강등**
> - 결정: `reconcile_with_broker` 불일치(임계: 실현손익 차이 > max(1만원, 1%))가 2회 연속이면 T3의 2년차+ A1을 A3로 강등하고, 일치 복귀 시 원상 복구한다.
> - 근거: 하베스팅 자동 매도의 전제는 "자체 이동평균 계산이 브로커와 일치한다"는 M6 실증(02 §5.1 게이트)이다. 그 전제가 런타임에 깨졌는데 자동 매도를 계속하는 것은 게이트의 취지와 모순된다. fail-safe 방향(사람 호출) 일관.
> - 계획 문서와의 관계: 02 §5.1 M6 진입 게이트의 런타임 연장. 충돌 없음.

### 4.5 검증 항목

- [ ] 이동평균 매수/매도 시퀀스 표 기반 test vector(03 §4.1 "세금 계산 — 표 기반" 요구 항목).
- [ ] 결제일 연말 경계: 12/30 체결·1/2 결제 → 익년 귀속.
- [ ] FX 스냅샷이 감사로그에 기록된다(02 §4.7-(c), M6 DoD 5).
- [ ] `reconcile` 불일치 시 증권사 값이 판정 입력으로 채택된다.

---

## 5. Asset Location — 계좌 분해

### 5.1 입력 — 표1·표2의 소비

두 표의 값 정본은 02 §1.2다. `universe.yaml`의 종목별 컬럼(`tax_inefficiency_score`, `risk_asset` — 파일 스키마: 01 §6.1, 정의 정본: 04 문서)과, 자산군×계좌 선호 표(표2)를 소비한다.

> **[DD-10-4] 표2(계좌 선호 순서)의 config 승격 — `universe.yaml`의 `account_preference` 컬럼**
> - 결정: 02 §1.2 표2를 종목별 `account_preference: {pension: n, irp: n, isa: n, general: n}` 매핑으로 `universe.yaml`에 승격한다(표1의 `tax_inefficiency_score`가 이미 같은 방식으로 승격되어 있음 — 01 §6.1 예시).
> - 근거: 표2가 코드 하드코딩이면 "파라미터는 코드가 아닌 설정"(00 §5 원칙 6) 위반. 자산군 단위 표를 종목 단위 컬럼으로 전개하는 것은 유니버스 재평가 파이프라인(02 §2.3)의 산출 단계에서 기계적으로 가능하다.
> - 계획 문서와의 관계: 02 §1.2 표1의 승격 방식("universe.yaml의 자산별 컬럼으로 승격")을 표2에 동일 적용. 스키마 등재는 04 문서에 위임. 충돌 없음.

### 5.2 `decompose_to_accounts` — 시그니처·의사코드

알고리즘 정본은 02 §4.3.0-(b)다. 아래는 그 실행 가능한 구체화이며, **호출·트리거 판정·저장은 [07-portfolio-engine.md](07-portfolio-engine.md)의 리밸런서가 소유**한다(02 §4.3 의사코드 (2)).

```python
# src/omra/tax/asset_location.py
class Decomposition(BaseModel, frozen=True):
    sub_alloc: dict[AccountId, dict[InstrumentKey, Decimal]]   # KRW 금액 (02 §4.3.0-a)
    targets_capped: dict[InstrumentKey, Decimal]               # 실효 총자산 목표
    legacy: frozenset[tuple[AccountId, InstrumentKey]]
    v_total_at_save: Decimal
    v_a_at_save: dict[AccountId, Decimal]

def decompose_to_accounts(
    targets: Mapping[InstrumentKey, Decimal],      # 총자산 목표비중 T[i] = **원목표**(§5.2 확정 회신)
    accounts: Sequence[AccountView],               # V_a, 유형, allowed[a]
    holdings: PortfolioView,
    universe: UniverseView,                        # score·preference·risk_asset
    clock: Clock,
) -> Decomposition:
```

```
의사코드 (02 §4.3.0-b의 1:1 구현 — 단계 번호 동일)
1. 자산 정렬: tax_inefficiency_score 내림차순, 동점은 종목코드 오름차순 (결정론)
2. 각 자산 i: allowed 계좌를 account_preference[i][a] 오름차순 순회
     cap = min(V_a − alloc_account[a],  T[i]×V_total − alloc_instrument[i])
     배정 후 누적 갱신
3. IRP 사전 검사: Σ_{risk_asset} sub_alloc[IRP][i] + cap ≤ 0.70 × V_IRP
     초과분은 cap 축소 후 다음 선호 계좌로
4. 잔량은 일반위탁 흡수. 그마저 부족 → 해당 자산 목표를 실현 가능 값으로
     하향(축소 방향만) → targets_capped 반영
5. 유니버스 밖 보유 자산 → legacy, sub_alloc = 0
6. 산출: Decomposition(...). 불변식:
     Σ_a sub_alloc[a][i] == targets_capped[i] × V_total_at_save   (02 §4.3.0-b)
```

> **`targets` 인자 = 원목표 `T[i]` (확정)** — 계획 02 §4.3은 의사코드 (2)가 `targets_eff`를 넘기는 것처럼 읽히지만 같은 절 보조 정의 표는 "입력은 `targets`(원목표)이지 `targets_eff`가 아니다"라고 쓴다. 이 내부 모순의 확정 주체는 호출자를 소유하는 [07-portfolio-engine.md](07-portfolio-engine.md)이며, **07 §10.2가 "인자는 `targets`(원목표)다 — `targets_eff`를 넘기지 않는다"로 회신**해 확정했다(근거: 재정규화는 분해 이후 일별 판정 단계이고, 동결 상태를 분해에 각인하면 해제 후 되돌릴 계기가 없으며, 4단계 하향은 `targets_capped`로 별도 표현된다). tax는 넘겨받은 벡터를 그대로 분해하는 순수 함수이므로 구현 변경은 없고, 호출 지점은 07 §16.1이다.

구현 규율:

- **순수 함수**다. DB·시계·브로커에 닿지 않고 입력 스냅샷만 받는다 — 백테스트 `account_model: multi`(M8, 02 §8.1)가 같은 함수를 그대로 호출한다.
- 하향 총액이 `band.class_abs`를 넘으면 info 알림 + "계좌 간 자금 재배치 제안"(§6.4의 E5 경로)에 편입하고, 잔여 드리프트는 03 §4.6 TE ①(비용)에 계상한다(02 §4.3.0-b 6).
- 산출물 영속화(`sub_alloc` + `V_total_at_save`·`V_a_at_save` 동반 저장)와 재분해 트리거(3조건: 월 목표 갱신 / 신규 자금 누적 > V_total 1% / 1년 경과, 콜드스타트 무조건 — 02 §4.3 보조 정의)는 07 문서의 리밸런서 상태 관리가 소유한다.

### 5.3 IRP 70% — 1차 강제와 2차 방어선

- **1차 강제 지점은 위 3단계(선형 제약)**다 (정본: 02 §1.2). property-based 테스트: "어떤 입력에서도 `Σ risk_asset sub_alloc[IRP] ≤ 0.70 × V_IRP`" (04 §2 M8 DoD).
- 03 §1.6 단계 5의 pre-trade 검사와 02 §4.3.0-(g)의 사후 시정(`constraint_cure`, 72% 발동/68% 해소 히스테리시스)은 **2차 방어선**이며 각각 09·07 문서 소유다. tax는 `risk_asset` 분류값 제공자다.

### 5.4 검증 항목

- [ ] 결정론: 같은 입력 → 같은 출력(동점 타이브레이크 포함).
- [ ] 불변식 `Σ_a sub_alloc[a][i] = targets_capped[i] × V_total_at_save`.
- [ ] IRP 70% property-based.
- [ ] 4단계 하향이 상향을 만들지 않는다(축소 방향만).
- [ ] legacy 자산에 sub_alloc 0이 부여되고 breach 목록에 오르지 않는다(07과의 계약).

---

## 6. 신규자금 배분 워터폴

### 6.1 3층 구조 (정본: 02 §1.3.1)

| 층 | 구현 위치 | 자동화 |
|---|---|---|
| A. 정기분 — 월정액 자동이체 사전 등록 | `external_schedules.yaml`(스키마: 01 §6.1, 04 소유) + §6.5 설계 제안 헬퍼 | A4 — 등록은 사람, 이후 무인 (00 §3.2 E4) |
| B. 비정기분 — 목돈 유입 감지 → 워터폴 계산 → 이체 지시 | `waterfall.py` (§6.2~6.4) | 감지·계산 A0, 일반위탁 내 배분 A2, 절세계좌 이체 지시 A3 (00 §3.2 E5) |
| C. 한도 감시 — `waterfall_gap_check` | `gap_check.py` (§7) | A0 감지 + A5 이체 (00 §3.2 T9) |

**워터폴을 자동이체로 완전 대체하지 않는다**(02 §1.3.1 기각 판정) — 계산은 런타임에서 계속 수행한다.

### 6.2 유입 감지·분류

감지 시점은 `daily_planner` 07:00 서브스텝(잔고 폴링 — 정본: 02 §4.2, 잡 소유: 12 문서). tax는 분류·계산 함수를 제공한다.

```python
class InflowClass(StrEnum):
    SCHEDULED   = "scheduled"    # external_schedules 기대값과 매칭 — 목적지 확정, 워터폴 불요
    LUMP_SUM    = "lump_sum"     # 매칭 실패 입금 — 워터폴 대상 (00 §3.2 E5)

def classify_inflow(
    inflow: CashInflow,                          # (account_id, amount_krw, observed_date)
    expectations: Sequence[ReconcileExpectation],# 03 §1.3.1 화이트리스트 행 (ro)
) -> InflowClass:
    """금액 허용폭(`amount_tolerance`, 컬럼명 정본: 03 §1.3.1 DDL)·날짜 창
    (`expected_date_from`/`expected_date_to`) 내 매칭이면 SCHEDULED.
    kind = cash_in · source = external_schedule 행만 본다(03 §1.3.1 매칭 규칙 1·3).
    매칭 판정 자체는 P8 대사(09 문서)와 같은 행을 읽되 **소비하지 않는다**
    (`consumed_at` 기록은 대사 소유자인 09만 한다 — 03 §1.3.1 규칙 4)."""
```

### 6.3 `compute_waterfall` 의사코드

```python
class WaterfallLeg(BaseModel, frozen=True):
    to_account: AccountId
    amount_krw: Decimal
    reason: str            # "연금저축 공제 잔여" 등 — 감사로그·지시서 문구

def compute_waterfall(
    amount_krw: Decimal,
    asof: date,
    contrib: ContributionLedgerView,   # 계좌별 YTD 납입액
    settings: TaxSettings,             # 법령값 = settings.law, 운영 키 = settings.waterfall ([DD-10-16])
    *,
    horizon_lt_3y: bool = False,       # 시평 <3년 자금 예외 (02 §1.3)
) -> list[WaterfallLeg]:
```

```
1. horizon_lt_3y 이면 → 전액 일반위탁 (1~3단계 스킵 — 중도해지 페널티 회피, 02 §1.3)
2. 공제인정_연금저축 = min(YTD_연금저축, 600만)                    # 02 §1.3.2와 동일 캡
   잔여_연금저축_공제 = max(0, 600만 − 공제인정_연금저축)
   leg₁ = min(amount, 잔여_연금저축_공제) → 연금저축
3. 잔여_총공제 = max(0, 900만 − (공제인정_연금저축′ + YTD_IRP))     # ′ = leg₁ 반영 후
   leg₂ = min(잔액, 잔여_총공제) → IRP                              # IRP 단독 한도 없음 — 결합제약
4. [옵션] settings.waterfall.fill_pension_to_limit: true 이면
   leg₂b = min(잔액, 1,800만 − (YTD_연금계좌합산 + leg₁ + leg₂)) → 연금저축
                                                # 공제 초과분도 과세이연 목적 유효 (02 §1.3)
5. leg₃ = min(잔액, 2,000만 − YTD_ISA) → ISA
6. leg₄ = 잔액 → 일반위탁
불변식 W1: Σ leg = amount, 모든 leg ≥ 0
불변식 W2: leg₁+leg₂+leg₂b 반영 후 **연금계좌(연금저축+IRP) 합산 납입 ≤ 1,800만**
           (납입한도 — 05 §2.3, 02 §1.3. IRP 납입분 leg₂도 이 한도를 소비한다)
불변식 W3: 재실행 멱등 — 같은 asof·contrib에서 같은 결과
```

> **[DD-10-5] `horizon_lt_3y` 플래그의 표현**
> - 결정: 비정기 유입 감지 알림(A2 브리핑)에 "이 자금의 사용 시평이 3년 미만입니까?" 선택지를 포함하고, 응답 없으면 `false`(워터폴 정상 적용)로 둔다. 응답은 해당 유입 건에만 적용한다.
> - 근거: 02 §1.3의 예외("시평 <3년 자금은 1~3 건너뜀")는 자금의 성격 정보라 시스템이 감지할 수 없다. 미응답 기본값을 `false`로 두는 이유는 절세계좌 **이체 지시가 어차피 A3**(사람 승인)라 잘못된 기본값이 실제 이체로 이어지지 않기 때문이다.
> - 계획 문서와의 관계: 02 §1.3 예외의 입력 수단 여백을 채움. 충돌 없음.

### 6.4 이체 지시·`pending_transfer_reserve`

이체 지시는 **전용 테이블이 아니라 `approval_requests(kind='e5_transfer')` 행**이다(정본: 03 §3.3.9 [DD-03-12]). 지시 본문(금액·출발/목적 계좌·근거 문구)은 `payload_json`에 담는다.

```
LUMP_SUM 유입 (daily_planner 07:00 서브스텝 — 07:30 의사코드 (6.5)보다 선행, 02 §4.2):
1. legs = compute_waterfall(...)
2. 일반위탁 leg → 이체 불요. 당일 07:30 cash-flow first가 소진 (A2 — 00 §3.2 E5)
3. 절세계좌 leg → approval_requests(kind='e5_transfer', state=PENDING,
     account_id=<목적 계좌>, payload_json={from_account, to_account, amount_krw, reason})
     행 생성 + A3 승인 요청
     → 승인 대기(PENDING) + 승인·미이행(APPROVED ∧ payload_json.fulfilled_at IS NULL)
        금액의 합이 pending_transfer_reserve[a]
        (02 §4.2 — cash-flow first가 이체 예정 현금을 소진하지 못하게 하는 장치)
4. 승인(state=APPROVED) 후 waterfall.transfer_reserve_expiry_days(기본 7일) 내 이행
     (입금 감지로 확인) 없으면 state=EXPIRED, 예약 자동 해제
     → 다음 사이클 cash-flow first가 회수 (02 §4.2)
5. 이행 확인(절세계좌 입금 매칭) → payload_json.fulfilled_at 기록(state는 APPROVED 유지)
     → 예약 해제 + contribution_ledger 갱신
```

```python
class WaterfallEngine:
    def on_inflow(self, inflow: CashInflow, ctx: PlanContext) -> InflowDisposition: ...
    def pending_transfer_reserve(self, account_id: AccountId, asof: datetime) -> Decimal:
        """02 §4.2 정의 그대로 — 승인 대기 또는 승인·미이행 상태 지시 금액 합(KRW, 계좌별).
        실현 현금 예약이므로 cash.buffer 판정에 포함된다(frozen_reserve와 다름).
        물리 원천은 approval_requests(kind='e5_transfer') — 03 §3.5 파생 질의 계약."""
    def expire_stale(self, asof: date) -> list[ApprovalRequest]: ...
```

- 이체 실행 자동화 경로는 **없다**(KIS 이체 TR 부재·오픈뱅킹 개인 이용 불가 — 정본: 02 §1.3.2, 05 §3.2). 산출물은 지시(금액·목적지·근거)와 알림이다.
- 계좌 간 현금 불균형의 "재배치 제안"(02 §4.3.0-f — 누적 부족액 > 총자산 1% 시 월간 리포트)도 같은 `kind='e5_transfer'` 경로(A3)로 표현한다. 부족액 산출은 07의 리밸런서가, 지시 생성은 tax가 담당.
- **[조율] 파생 질의의 상태 범위**: 03 §3.5·07 §9·09가 `pending_transfer_reserve`를 `state='PENDING'` 행만으로 파생하는데, 02 §4.2의 정의는 "승인 대기 **또는 승인·미이행**"이다. 승인 직후~입금 확인 전 구간이 누락되면 그 기간 동안 cash-flow first가 이체 예정 현금을 소진할 수 있다. 값 산출의 소유는 10이므로 이 문서는 위 5단계 정의(PENDING + APPROVED∧미이행)를 정본으로 두고, 03·07·09에 파생 조건 확장을 요청한다(§17 #18).

### 6.5 정기분 자동이체 설계 제안 (A4 연계)

```python
def propose_annual_transfer_plan(
    expected_monthly_inflow_krw: Decimal, params: TaxParams,
) -> list[WaterfallLeg]:
    """연 1회(00 §3.2 E4 '연 1회 설계') 사람이 자동이체 4건을 갱신할 때 쓰는
    제안치: 월 50만(연금저축 600만/12) / 월 25만(IRP 300만/12) /
    ISA·일반위탁 배분. 합계 월 100만 초과 시 '영업점 1회 등록 필요' 문구 포함
    (00 §3.2 E4). 제안일 뿐 등록·변경은 전부 사람이다."""
```

> **[DD-10-6] 정기분 설계 제안 헬퍼**
> - 결정: 위 헬퍼를 연간 캘린더(1월, 03 §6.1 세제 리뷰와 동일 창)의 리포트 항목으로 제공한다.
> - 근거: 02 §1.3.1 층 A의 "연 1회 설계"는 사람 행위인데 계산 근거(한도÷12)는 기계적이다. 제안 생성은 개입을 늘리지 않고 오류(한도 착오)를 줄인다.
> - 계획 문서와의 관계: 층 A의 여백을 채움. 자동 등록이 아니므로 E4의 A4 등급과 충돌 없음.

### 6.6 검증 항목

- [ ] 워터폴 산술 표 기반 test vector — 특히 `fill_pension_to_limit` on/off × 연금저축 기납입 600만 초과 케이스(공제인정 캡).
- [ ] 불변식 W1~W3 property-based.
- [ ] `pending_transfer_reserve`가 `allocatable_cash` 차감에 반영된다(07과의 통합 테스트 — 02 §4.2 최종형).
- [ ] 7일 만료 자동 해제 후 cash-flow first 회수(시계 주입 시뮬).
- [ ] SCHEDULED 유입이 워터폴을 타지 않는다(이중 배분 금지).

---

## 7. `waterfall_gap_check` (T9)

### 7.1 잡 스펙

| 항목 | 값 | 정본 |
|---|---|---|
| 시각 | 11/1 09:00 + 12/8·12/15·12/19 09:00 (D-12/D-5/D-1) | 01 §4.2 |
| catch-up | `until 12/19` — 창 안이면 재실행 | 01 §4.2.1 |
| 등급 | 잔여 발생 시 **critical**(Telegram+SMTP 양쪽) | 03 §7.2 critical ⑧ |
| ISA 잔여 | 같은 잡에서 산출, 등급 **info**(이월 가능 — 긴급성 낮음) | 02 §1.3.2-5 |
| 이체 | A5 — 알림이 최종 산출물 | 00 §3.2 T9 |

### 7.2 산술 — 합산 900만 결합제약 (02 §1.3.2 그대로)

```python
class GapCheckResult(BaseModel, frozen=True):
    year: int
    paid_pension: Decimal          # YTD 납입_연금저축
    paid_irp: Decimal
    paid_isa: Decimal
    remaining_total: Decimal       # 잔여_총
    remaining_pension: Decimal
    remaining_irp: Decimal
    est_credit_krw: Decimal        # 예상 세액공제 = 잔여_총 × 한계세율
    isa_remaining: Decimal         # 2,000만 − YTD_ISA
    deadline: date                 # 12/20 (02 §1.3.2-3 문구 기준)

def run_waterfall_gap_check(asof: date, contrib, params, rate: Decimal) -> GapCheckResult:
    인정_연금 = min(paid_pension, params.pension_deduct_cap_savings_krw)   # 600만 캡
    잔여_총   = max(0, params.pension_deduct_cap_total_krw - (인정_연금 + paid_irp))
    잔여_연금 = min(잔여_총, max(0, params.pension_deduct_cap_savings_krw - 인정_연금))
    잔여_irp  = 잔여_총 - 잔여_연금
    # ★ 계좌별 단순 차감 금지 — IRP 단독 한도 없음, fill_pension_to_limit로
    #   600만 초과 납입이 능동적으로 생기므로 공제인정액으로 캡 (02 §1.3.2 ★)
```

**YTD 납입액 집계 소스** — 3단 폴백:

1. `contribution_ledger`(§6.4의 이행 확인 + `SCHEDULED` 유입 누적) — 기본.
2. KIS 잔고·입금 내역 API 재집계(02 §1.3.2-1). SP-C4로 절세계좌 잔고 조회가 확정되어야 하며, 조회용 TR·입금 내역 필드는 **[확인 필요]** — SP-C4 실증 및 공식 문서로 확인.
3. 실패 시 월 1회 CSV 업로드(00 §3.2 E3의 폴백 경로) 값 사용. CSV도 없으면 **잔여를 한도 전액으로 보고**(보수적 — 알림이 초과 발생해도 손실이 없고, 미발생이 손실이다) + "납입액 미확인" 문구를 알림에 병기한다.

> **[DD-10-7] 한계세율 입력 `tax.user_marginal_credit_rate`**
> - 결정: 세액공제율 사용자 입력 키(기본값 `0.132` — 보수적 하한)를 두고, 알림 문구의 "예상 세액공제 Y원 (한계세율 Z% 가정)"(02 §1.3.2-3)에 사용한다. 키 등재는 04 문서에 위임.
> - 근거: 공제율은 총급여 구간(5,500만 기준 13.2%/16.5% — 05 §9.3)에 의존하는 사용자 정보다. 하한 기본값이면 과대 약속이 없다.
> - 계획 문서와의 관계: 02 §1.3.2 문구의 Z% 입력 여백을 채움. 충돌 없음.

### 7.3 알림·오류 경로

```
잔여_총 > 0 → critical: "12월 20일까지 {잔여_총:,}원 추가 이체 필요,
              예상 세액공제 {est_credit:,}원 (한계세율 {rate:.1%} 가정)"
              + 재알림 D-12/D-5/D-1 (02 §1.3.2-4)
잔여_총 = 0 → info 1건("공제 한도 소진 완료") — 무소식이 무점검과 구분되지 않으면
              dead-man 관점에서 실패다 [DD-10-8]
집계 실패   → §7.2 폴백 3단. 어떤 실패도 잡을 조용히 스킵하지 않는다(catch-up 창 12/19)
```

> **[DD-10-8] 잔여 0원에도 info 1건 발송**
> - 결정: 상동.
> - 근거: 79~99만원 확정 손실 경로(05 §9.3)에서 "알림 없음"이 "확인 완료"와 "잡 미실행"을 구분하지 못하면 침묵 실패가 된다. info 1건은 알림 피로 기준(03 §7.2 info 등급) 안이다.
> - 계획 문서와의 관계: 02 §1.3.2는 잔여 >0만 규정 — 여백 채움. 충돌 없음.

### 7.4 검증 항목

- [ ] 02 §1.3.2 ★ 케이스: 연금저축 800만 기납입(`fill_pension_to_limit`) + IRP 100만 → 잔여_총 = 900 − (600+100) = 200만(연금저축 0 / IRP 200만).
- [ ] IRP 단독 900만 기납입 → 잔여_총 0 (계좌별 독립 차감이면 잘못 600만을 요구하는 케이스).
- [ ] M6 DoD 6 드라이런(11/1 이전이면 날짜 주입).
- [ ] catch-up: 11/1 다운 → 11/3 재기동 시 실행됨(창 12/19).

---

## 8. 금소세·건보 임계 추적

### 8.1 누적기 구성·입력

```python
# src/omra/tax/income.py
class FinancialIncomeTracker:
    """YTD 금융소득 누적기 (정본: 02 §5.2). 과세연도(YTD) 기준 — 1/1 리셋.
    정본 입력은 증권사 집계(T1=A0)이고 자체 계산은 시뮬·경고 전용."""

    def on_settlement(self, ev: TaxLedgerEvent) -> None: ...
    def snapshot(self, asof: date) -> IncomeSnapshot: ...
    def tier(self, asof: date) -> IncomeTier: ...
```

구성 요소(02 §5.2):

| 항목 | 소스 | 비고 |
|---|---|---|
| 배당·분배금 | `기간별계좌권리현황조회` / `period_rights` (00 §3.2 T1) — 분배금·원천징수액 포함 여부는 **SP-C6(M6)** | SP-C6 실패 시 `tax_events`의 현금 유입 관측 + 수동 입력 폴백 |
| 국내상장 해외 ETF 매매차익 | 자체: `min(실차익, 과표기준가 상승분)`(§10) / 정본: 증권사 실현손익 집계 | 일반계좌 보유분만 (02 §5.2) |
| **국내상장 해외 ETF**의 해지상환 차익 | E7·상폐 이벤트의 실현분 — 배당소득으로 계상 | 05 §7.4, 06 §8.4 (국내주식형 ETF는 매매차익 비과세이므로 제외) |
| 외부 금융소득 | `external_income.yaml` 계산식 (§8.3) | T2 |

> **[DD-10-9] "모든 배당·분배금"의 계좌 범위 한정**
> - 결정: 누적기에는 **일반위탁(과세 계좌) 발생분만** 합산한다. ISA 내 소득(계좌 내 통산·초과분 9.9% 분리과세)과 연금저축·IRP 내 소득(과세이연)은 금융소득종합과세 합산 대상이 아니므로 제외한다.
> - 근거: 05 §2.3의 계좌별 과세 체계. 02 §5.2의 문언 "모든 배당·분배금"은 누적기의 목적(금소세 2,000만·건보 1,000만 합산 추적)상 "합산 과세 대상인 모든"으로 읽는 것이 정합하다 — ISA·연금 분을 넣으면 임계 도달이 체계적으로 과대해져 soft-stop이 오발동한다(과대 방향이지만 목적 왜곡).
> - 계획 문서와의 관계: 02 §5.2 문언의 해석 확정. 05 §2.3과 정합. 충돌 없음.

**갱신·판정 주기**: `krx_eod`(15:40)·`us_reconcile` 서브스텝에서 갱신, 07:30 계획 수립 시 `blocked_for_sell`이 전일 스냅샷을 읽는다. 브로커 집계와의 월 1회 대사는 월간 runbook(03 §6.1)과 `monthly_report`에 편입.

### 8.2 티어 판정 — api / fallback 이중 임계

`tax.basis_price_source` 스위치(config — [DD-10-16] 소속표) 하나로 임계 집합을 바꾼다(정본: 02 §5.3).

| 티어 | api 경로 | fallback 경로 | 동작 |
|---|---|---|---|
| `HEALTH` 건보 | 1,000만 | 1,000만 (법정 기준 — 변경 없음) | 알림 + 건보 자격별 분기(§8.2.1) |
| `INFO` | 1,200만 | 1,400만 | 알림 |
| `WARN` 경고 | 1,600만 | 1,800만 | 국내상장 해외 ETF **매도 주문에 확인 요구**(A3, 타임아웃 7일 → 해당 레그만 보류 — 03 §5.3.2) |
| `SOFT_STOP` | 1,800만 | 1,900만 | 해당 자산군 자동 매도 정지 → `sell_blocked` 마스크. 매도 필요 시 이연 또는 해외상장 대체 제안. **E7 유래 주문 면제**(02 §5.6-(c) 불변식 5) |

```python
class IncomeTier(StrEnum):
    NONE = "none"; HEALTH = "health"; INFO = "info"; WARN = "warn"; SOFT_STOP = "soft_stop"

def tier(self, asof: date) -> IncomeTier:
    alerts = settings.cfg.income_alerts          # mapping {api: …, fallback: …} (04 §4.2)
    tiers = (alerts.api if settings.cfg.basis_price_source == "api" else alerts.fallback)
    total = snapshot(asof).total_krw     # 배당 + 국내상장 해외 ETF 차익 + 외부소득
    # 단조 판정: soft_stop ≥ warn ≥ info ≥ health. 티어 진입 시 1회 알림
    # (동일 티어 재알림 금지 — 03 §7.2 info 규율), 하향 이탈(연초 리셋)에 리셋.
```

#### 8.2.1 건보 자격 분기

> **[DD-10-10] 건보 자격 config `tax.health_insurance_status`**
> - 결정: enum `employee(직장) | regional(지역) | dependent(피부양자)` 사용자 입력 키. `dependent`면 HEALTH 티어 알림을 "피부양자 자격 상실 경고 — 세금보다 큰 현금 유출 가능"(02 §5.2 문구)으로 승격(warning 등급). 키 등재는 04에 위임.
> - 근거: 02 §5.2가 "건보 자격을 config로 받아 정책 분기"를 요구하나 키를 명명하지 않았다.
> - 계획 문서와의 관계: 여백 채움. 충돌 없음.

### 8.3 외부 금융소득 (T2)

```yaml
# config/external_income.yaml — 스키마 정본은 04 문서. tax 소비 필드 (02 §5.2: {원금·이율·만기·지급주기})
- id: bank_deposit_1
  kind: deposit            # deposit | bond | other
  principal_krw: 50000000
  annual_rate: 0.035
  maturity: 2027-03-31
  payout: at_maturity      # monthly | quarterly | annual | at_maturity
```

```
연간 귀속 계산: payout 주기에 따라 해당 과세연도에 지급되는 이자를 산출해
ytd_external_income에 가산한다 (만기 일시지급형은 만기 연도에 전액 귀속).
확인 질의(A3): 누적 합계가 SOFT_STOP 임계의 70%에 도달한 때에만 발송
  (00 §3.2 T2 — "임계 70% 도달 시에만"), 타임아웃 14일 → 보수적(과대) 가정 유지
  (03 §5.3.2). 미입력·미응답 = 등록된 계산식 그대로(과대 방향) 유지.
```

### 8.4 soft-stop과 매도 차단 연계

- `SOFT_STOP` 도달 시: 자산군 = "국내상장 해외 ETF"(`universe.yaml`의 `asset_class` 판정 — 02 §1.2 표1의 배당소득 과세 자산군) × 일반위탁 계좌의 매도 레그를 `sell_blocked`에 편입한다. **매수 레그는 유지**(방향 마스크 — 02 §5.4).
- 보류 레그의 잔여 드리프트는 03 §4.6 TE 분해 **①(비용)**에 계상한다(③이 아니다 — 02 §5.4).
- `WARN` 티어의 확인 요구는 `approval_requests(kind='income_warn_sell')`로 생성되고, 승인되면 해당 주문 건에 한해 마스크를 통과시킨다(§13.1).
- 해외상장 대체 제안(02 §5.2 soft-stop 행): 같은 자산군 노출을 해외상장 ETF(02 §2.2)로 얻는 A3 제안을 월간 리포트에 첨부한다 — 주문 자동 생성은 없다.

### 8.5 검증 항목

- [ ] 티어 경계 test vector(api/fallback 두 집합 × 4티어).
- [ ] soft-stop 하에서 매도 레그만 제거되고 매수 레그가 살아남는다(02 §4.3 마스크 계약).
- [ ] E7 주문이 soft-stop을 통과한다(불변식 5).
- [ ] 외부소득 70% 도달 시에만 질의가 생성된다(69%에서 0건).
- [ ] 연초(1/1) YTD 리셋 — ISA 누적(§9)은 리셋되지 **않는다**는 대비 테스트.

---

## 9. ISA 비과세 한도 소진률

### 9.1 계약기간 누적(contract-to-date) 정의

- **YTD가 아니다.** 기준일 = `tax.isa_contract_start_date`, 리셋은 만기·해지·재가입 시에만(정본: 02 §5.2 ★). YTD로 구현하면 회전율 관리가 무의미해진다.
- 실현 순이익 = **계좌 내 매매차익 + 배당·분배금 − 실현손실(계좌 내 통산)**, 귀속 결제일(정본: 02 §5.2).
- 시스템 도입 전 기실현분은 `tax.isa_usage_opening_amount`(+`opening_as_of`)로 1회 입력받고, **`opening_as_of` 이후 실현분만 시스템이 누적**한다(02 부록 A).

```python
# src/omra/tax/isa.py
class IsaUsage(BaseModel, frozen=True):
    state: Literal["known", "unknown"]
    accumulated_krw: Decimal | None      # unknown이면 None — 수치 가정 금지 (02 §5.2)
    limit_krw: Decimal
    ratio: Decimal | None                # accumulated / limit

class IsaUsageTracker:
    def usage(self, asof: date) -> IsaUsage: ...
    def on_settlement(self, ev: TaxLedgerEvent) -> None: ...   # ISA 계좌 이벤트만
    def reset_on_contract_event(self, kind: Literal["maturity", "close", "reopen"],
                                new_start: date) -> None: ...  # 사용자 조작(A5)로만 호출
```

### 9.2 `unknown` 3상태 처리 (정본: 02 §5.2 표)

| 소진률 | 동작 |
|---|---|
| `unknown`(개시 잔액 미입력) | **70% 행과 동일** — ISA 내 매도에 확인 요구(A3, 7일 → 레그만 보류). 100% 행 동작(9.9% 안내 후 진행) 적용 금지. **§13.4 매도 우선순위 강등도 적용하지 않는다**(근거 없는 종목 선택 왜곡 금지) |
| ≥ 70% (`tax.isa_usage_alert`) | ISA 내 매도 주문 확인 요구(A3, 타임아웃 7일 → **해당 종목 레그만 보류, 나머지 정시 집행** — 03 §5.3.2). 브리핑에 잔여 한도 표시 |
| ≥ 100% | 초과분 9.9% 분리과세 안내 후 **계속 진행**(정지 아님 — 9.9%는 일반 15.4%보다 유리) |

폴백을 수치로 가정하지 않는 이유(02 §5.2): 100% 가정과 70% 가정이 서로 다른 처분(진행 vs 확인)을 부르므로 어느 쪽도 안전하지 않다 — 그래서 `unknown`은 별도 상태다.

### 9.3 소비자 4곳 (02 §5.2가 열거)

1. **70% 매도 확인 게이트** — §13.1 (`approval_requests` kind=`isa_sell_confirm` — kind 이름 정본: 03 [DD-03-12]).
2. **§13.4 매도 우선순위 강등** — ≥70%일 때 ISA 내 매도를 3~4순위 사이로(`unknown`은 강등 없음).
3. **E7 분기** — §14.1 (ISA <70% 행 생성 / ≥70% 또는 `unknown` → A3 큐).
4. **대시보드 세금 패널** — `unknown`은 수치 대신 "`unknown`(개시 잔액 미입력)"으로 표기(03 §7.1-8). 화면 설계는 [13-web-and-telegram.md](13-web-and-telegram.md).

### 9.4 검증 항목

- [ ] 연초에 리셋되지 않는다(contract-to-date).
- [ ] `unknown`에서 매도 확인이 생성되고 강등은 생성되지 않는다.
- [ ] opening_as_of 이전 이벤트가 누적에서 제외된다.
- [ ] 계좌 내 손실이 누적을 감소시킨다(통산).
- [ ] 100% 초과 시 차단이 없다(진행 + 안내).

---

## 10. 과표기준가 (SP-C1)

### 10.1 이중 경로 (정본: 02 §5.3)

```
과세 차익(국내상장 해외 ETF) = min(실제 매매차익, 과표기준가 상승분)   # 보유기간과세 (05 §2.3)
tax.basis_price_source:
  api      → 야간 배치가 과표기준가 적재 (SP-C1 성공 시. 적재 서브스텝 편성은 12 문서,
             스토어는 03 문서 소유) + 매수·매도 시점 스냅샷 저장
  fallback → 과표 상승분 항을 생략하고 실차익 사용(과대추정 방향으로 안전)
             + §8.2 임계를 fallback 집합으로 전환
```

- 2026-07 재조사에서도 공개 API를 찾지 못했다(05 §2.3, 04 부록 B) — **fallback이 기본 경로가 될 가능성이 높다.** 코드에서 `fallback`이 기본값이며, `api`는 SP-C1 성공 시에만 켠다.
- `taxbase_snapshots.source`의 값 집합은 **[확인 필요]** — SP-C1 실증으로 확정한다(03 [DD-03-11]의 조율 요청 수용). 폴백 확정 시 이 테이블은 **적재되지 않고 스키마만 남으며**, tax는 §10.2의 쓰기 경로를 호출하지 않는다.
- 과대추정 폭 가정 ~15%는 **추측**이며 M6 이후 실현손익 대비 실측으로 재조정한다(02 §5.3).

### 10.2 스냅샷 저장

```python
# src/omra/tax/basis_price.py
class BasisPriceService:
    def snapshot_on_trade(self, key: InstrumentKey, trade_date: date) -> None:
        """api 모드에서만: 매수·매도 시점 과표기준가를 taxbase_snapshots(instrument_key,
        as_of, taxbase_price, source, fetched_at)에 저장 — DDL 정본 03 §3.3.8
        (02 §5.3 '매수·매도 시점 과표기준가를 스냅샷 저장')."""
    def taxable_gain(self, realized: Decimal, key, buy_date, sell_date) -> Decimal:
        """api: min(realized, 과표상승분 × 수량). fallback: realized 그대로."""
```

### 10.3 검증 항목

- [ ] 스위치 전환 시 §8.2 임계 집합이 함께 바뀐다(둘이 따로 움직이면 티어 하나가 소실 — 02 §5.3).
- [ ] fallback에서 taxable_gain ≥ api 값(과대추정 방향 property).

---

## 11. 연말 하베스팅 (T3)

### 11.1 시즌·마감 계산

```
시즌: tax.harvest_start(11/25)부터 D*−2까지의 매 거래일, 잡 = `tax_harvest`
      (등록·catch-up(until D*−2)은 12 문서 — 정본: 01 §4.2·§4.2.1)
D*   = 매도 결제일이 12/31 이내인 마지막 미국 거래일 (미국 T+1 결제·미국 거래일
       캘린더 기준 — 결제일 계산기는 06 문서 / 연내 인정 규정: 05 §2.3, 02 §5.1-2)
주문 마감일 = D* − 2 (미국 거래일 기준 안전마진 2영업일 — 02 §5.1)
D*−2 이후의 모든 해외 매도 주문(하베스팅 여부 무관)에 "내년 귀속" 경고 태그
       (02 §5.1-5) — tax_overlay가 부착 (§13.3)
```

### 11.2 목표 산정 — 분기 a/b/c (정본: 02 §5.1)

```python
class HarvestTarget(BaseModel, frozen=True):
    mode: Literal["TLH", "TGH", "NONE"]
    target_realize_krw: Decimal    # 이번 시즌에 실현할 손익 목표(부호 있음)

def harvest_target(G: Decimal, params: TaxParams) -> HarvestTarget:
    D = params.overseas_cg_deduction_krw               # 250만
    if G > D:        return HarvestTarget("TLH", -(G - D))       # a) G′ → 250만까지
    if 0 <= G <= D:  return HarvestTarget("TGH", D - G)          # b) step-up, 세금 0
    return HarvestTarget("TGH", abs(G) + D)                       # c) 상계 + 공제 (G < 0)
```

- `G` = YTD 실현손익(결제일 귀속·결제일 환율·이동평균 — §4). **E7 강제 이전의 실현분과 대주주·비상장 등 수동 입력 통산분을 포함**한다(02 §5.1·§5.1.1).
- 예상 절세액(게이트 입력): TLH = `overseas_cg_rate × min(|목표실현|, G − 250만)`, TGH = `overseas_cg_rate × 실현 이익`(0% 구간에서의 step-up이 미래 과세분을 제거). 산술 유도는 05 §2.3의 세율·공제에서 직접 나온다.

### 11.3 후보 선정·수량 산정 (02 §5.1.2의 1:1 구현)

```python
def select_harvest_legs(
    target: HarvestTarget,
    holdings: Sequence[HoldingView],       # 일반위탁 · 해외상장만 (1단계)
    basis: CostBasisCalculator,
    prices: PriceView, fx: Decimal,
    settings: TaxSettings, ctx: HarvestContext,   # 게이트 계수 = settings.law, 버퍼 = settings.cfg
) -> list[HarvestLeg]:
```

```
1. 후보 = 일반위탁 보유 해외상장 종목 중 미실현 손익 부호가 목표 방향과 일치
2. 1차 정렬 = §13.4 매도 우선순위(세목 기준) 그대로 — 덮어쓰지 않는다.
   동순위 내부 2차 키 = 실현손익 1원당 왕복비용
     (수수료+슬리피지+환전스프레드) × 2 × p_i / |p_i − 평단_i|   오름차순
   (비용 추정치는 02 §8.1 비용 모델 기본값: 미국 수수료 0.09%·슬리피지 3bp·환전 왕복 0.2%)
3. q_i = min(보유수량_i, floor(잔여목표 / |p_i − 평단_i|)); 잔여목표 갱신하며 순차
   — 이동평균 체계에서 매도가 평단을 바꾸지 않으므로 이 식은 정확하다
4. 왕복비용 게이트(비용 < 절세액 × harvest_cost_gate_factor)는 종목 단위.
   탈락 종목 제거 후 3부터 재실행
5. 밴드 검사: 기본 경로(동일 종목 즉시 재매수)는 순포지션 불변 → 미적용.
   [옵션] 대체 ETF 경로·재매수 미체결분에만 |w_total 사후 − sub_total| ≤ b 검사
   → 통과 수량까지 축소
6. 재매수: 같은 잡·같은 날 미국 기본 경로(LOC — 02 §4.1)로 생성,
   금액 = 매도 예상 대금 × (1 − harvest_rebuy_buffer_pct).
   매수 여력은 D+2 예수금 규칙(02 §3.3 2단계) — 통합증거금의 매도대금 즉시 반영은
   미확인이므로 낙관 가정 금지, 부족 시 재매수 익일 이월 + 지시서 표기
7. 평단 갱신 순서: 재매수는 실제 체결일 기준으로 평단 원장을 갱신하고,
   그 갱신 이후에 다음 종목의 3단계를 계산 (평단 오염 효과의 집행 측 표현)
8. 목표 미달분은 연말 절세 리포트에 "미달분" 계상
```

### 11.4 게이트 4종 (정본: 00 §3.2 T3)

| 게이트 | 판정 | 실패 시 |
|---|---|---|
| 왕복비용 < 절세액 × 0.5 | 종목 단위 (§11.3-4) | 해당 종목 탈락 |
| 밴드 위반 없음 | 대체 페어·재매수 미체결 경로만 (§11.3-5) | 수량 축소 |
| 연 하베스팅 주문금액 ≤ NAV 20% | `harvest_ledger` 누적으로 판정 | 초과분 계획 축소 + info |
| D\*−2 준수 | 마감일 이후 신규 하베스팅 매도 생성 금지 | 잔여 목표 → 리포트 "미달분" |

> **[DD-10-11] "연 하베스팅 주문금액"의 산정 = 매도+재매수 합산**
> - 결정: NAV 20% 게이트의 분자를 하베스팅 유래 주문(매도·재매수 포함) 금액 합으로 정의한다.
> - 근거: 00 §3.2 T3의 문언이 산정 방식을 정하지 않았다. 합산(보수 방향)이면 게이트가 더 일찍 걸리고, 게이트의 목적(과매매·시장 노출 변동 상한)에 부합한다.
> - 계획 문서와의 관계: 여백 채움, 보수 방향. 충돌 없음.

### 11.5 산출물과 실행 경로

```python
class HarvestProposal(BaseModel, frozen=True):
    asof: date
    G_ytd: Decimal
    target: HarvestTarget
    legs: list[HarvestLeg]                 # (instrument, qty, side, est_pnl, est_cost, est_saving)
    rebuy: list[HarvestLeg]
    gates: GateReport                      # 4게이트 판정 근거 — 감사로그·브리핑 공용
    deadline: date                         # D*−2
```

- **1년차(A3)**: 지시서 + 수동 승인만 — 자동 매도 없음(00 §3.2 T3, 04 §2 M6 "첫 해"). 타임아웃 D\*−2 → 무행동(03 §5.3.2).
- **2년차+(A1)**: 자동 실행 + 72h 거부권. 단 **SAFE_MODE 중에는 A3**(03 §5.3.2·§2.2 세금 행 — 자동 실행 금지), [DD-10-3] 강등 조건 충족 시에도 A3.
- 모드 전환 키는 [DD-10-14]로 선언한다.
- 실행은 `tax_harvest` 잡이 `HarvestProposal`을 확정하면 execution이 주문으로 변환한다 — 매도는 `intent=HARVEST × side=SELL`, 재매수는 `intent=HARVEST × side=BUY`다(값 정본: 02 §7.2 [DD-02-17]-③, §2.2 정규화표). 흐름 설계는 [08-execution.md](08-execution.md).
- 산출물: 연말 절세 리포트(실현 내역·절세액·5월 신고용 예상세액 — 02 §5.1) + 브리핑 info(03 §7.2).

> **[DD-10-14] 하베스팅 자동 실행 승격 키 `tax.harvest_auto_enabled`**
> - 결정: 기본값 `false`(= 1년차 A3). 첫 시즌 완주 후 사람이 `true`로 올려야 2년차+ A1이 켜진다. 키 등재는 04 문서에 위임.
> - 근거: 00 §3.2 T3의 "1년차 A3 → 2년차+ A1"은 **연차**로 서술돼 있는데, 시스템이 "1년차가 끝났다"를 스스로 판정해 자동 매도를 켜면 승격 자체가 무인 결정이 된다. 승격을 명시적 config 조작으로 두면 사다리가 사람 손을 한 번 거친다 — 03 §5.3.2의 "하베스팅 1년차 A3 / 2년차+ A1" 두 행 사이의 전이 주체를 명확히 하는 최소 장치다.
> - 계획 문서와의 관계: 등급 자체는 바꾸지 않고 전이 트리거만 명시. 충돌 없음.

> **[DD-10-17] T3(하베스팅 2년차+ A1)의 `/revert` 의미 — 미집행 잔여의 시즌 중단이며 체결분 되돌리기는 없다**
> - 결정: 하베스팅 A1의 72h 사후 거부권(`/revert <change_id>`, 상호작용 소유: 13 §5.3)은 아래 셋만 한다. ① **미제출·미체결 레그 취소** — 해당 `HarvestProposal`에서 아직 주문으로 나가지 않았거나 미체결 상태인 매도·재매수 레그를 전량 취소한다(취소 프로토콜은 08 소유). ② **잔여 시즌 중단** — 그 해 `tax_harvest` 잡이 새 제안을 만들지 않도록 시즌 플래그를 내리고(연내 재개는 사람이 `/approve` 경로로만), 미달분은 §11.3-8대로 리포트에 계상한다. ③ **감사·리포트 표기** — 되돌린 시점까지의 실현손익을 "사용자 중단" 사유와 함께 연말 절세 리포트에 남긴다. **이미 체결된 매도·재매수는 되돌리지 않는다** — 되돌리기 매매(반대매매)를 자동 생성하지 않으며, `/revert` 응답에 "체결분 N건은 유지됩니다(실현손익 X원 확정). 노출 복원이 필요하면 다음 리밸런싱 밴드가 처리합니다"를 명시한다. 재매수만 체결되고 매도가 취소되는 반쪽 상태가 생기면 그 종목은 다음 밴드 판정의 정상 입력이 된다.
> - 근거: 13 §13-12의 조율 요청("`T3` 하베스팅 2년차+의 `/revert` 의미 정의 — 소유 문서 10")에 대한 회신이다. 체결된 매도의 실현손익은 결제일 귀속으로 **이미 발생한 세법상 사실**이고(02 §5.1), 이를 반대매매로 되돌리면 ① 왕복비용이 한 번 더 들고 ② 실현손익이 상쇄되기는커녕 반대 부호로 한 번 더 쌓여 `G`가 두 번 흔들리며 ③ 재매수 시점 이동평균단가가 오염된다. 자동 반대매매는 02 §4.1 재호가 규율("자동 시장가 폴백 없음")의 취지와도 어긋난다. 취소 가능한 것(미체결분)만 되돌리는 것이 A1 거부권의 실질을 유지하는 최대 범위다.
> - 계획 문서와의 관계: 00 §3.1 A1의 72h 거부권 자체는 유지하고, 계획이 정하지 않은 "무엇을 되돌리는가"의 여백만 채운다. 00 §3.2 T3의 등급·게이트는 불변. 충돌 없음. 13은 이 정의를 받아 `revert()`의 T3 분기를 "부작용 없이 거부"에서 위 ①②③으로 교체한다(13 §5.3·§13-12).

### 11.6 12월 3중 충돌 조정 (정본: 03 §2.5)

```
우선순위 (SAFE_MODE 동시 발동 포함):
① E7 상폐 D−10 사전 이전  — SAFE_MODE에서도 자동 실행 (매도 금지의 명시 예외)
② 하베스팅 D*−2 마감      — SAFE_MODE 중 자동 실행 금지 (A3 승인 후에만)
③ 밴드 리밸런싱           — SAFE_MODE 밴드 2배 하에서 계속

def resolve_december_conflicts(proposal: HarvestProposal,
                               e7_pending: Sequence[PendingTransfer]) -> HarvestProposal:
    """①이 ②를 흡수: pending_transfers에 있는 종목을 하베스팅 후보에서 제거하고,
    E7 슬라이스의 (예상) 실현손익을 G 계산 입력에 반영한다 — 같은 종목에 별도
    하베스팅 주문을 내지 않는다 (03 §2.5, 02 §5.1.1)."""
```

- 이 시나리오는 M4 부재 시뮬레이션 필수 케이스(판정만)·M6 실집행 검증(04 §2 M6 DoD 2) 대상이다. 테스트 시계열 주입 설계는 [16-testing-and-quality.md](16-testing-and-quality.md)가 수거한다.

### 11.7 오류 경로

| 상황 | 동작 |
|---|---|
| YTD G 산출 실패(원장 공백·대사 미완) | 그날 제안 생성 스킵 + warning. 시즌 내 재시도(일간 배치) |
| 재매수 미체결 D+1 이월 실패 반복(3일) | warning + 노출 공백 금액을 브리핑에 표기 — 자동 시장가 폴백 없음(02 §4.1 재호가 규율 준수) |
| D\*−2 당일 미승인(1년차) | 무행동 확정 + "올해 기회 소멸, 예상 절세액 X원" info (03 §5.3.2) |
| HALTED·PAUSED_ALL·STOPPED | 제안 생성 자체를 중단(상태 게이트 — 03 §1.6 단계 7이 어차피 거부) |

### 11.8 검증 항목

- [ ] 분기 a/b/c 표 기반 test vector (G = 400만/100만/−80만).
- [ ] §11.3 순차 수량 산정에서 평단 갱신 순서(7단계)가 지켜진다 — 재매수 체결 전후로 다음 종목 계산이 달라지는 케이스.
- [ ] 왕복비용 게이트 탈락 후 재실행(4단계)이 수렴한다.
- [ ] NAV 20% 게이트 — `harvest_ledger` 누적 경계.
- [ ] SAFE_MODE에서 A1이 A3로 강등된다.
- [ ] 12월 충돌: E7 종목이 후보에서 제거되고 그 실현분이 G에 반영된다.

---

## 12. 양도세 집계·판정·신고서 초안 (T4~T6)

### 12.1 연간 파이프라인 (일정 정본: 03 §6.1·§7.2)

| 시점 | 잡/행위 | 등급 |
|---|---|---|
| 연중 | 실현손익·원천징수 집계(§4) — `해외주식 기간손익`(032) 월 1회 대사 | T1 A0 |
| **1/15** | 전년도 250만 초과 판정 + 신고서 초안·대사표 생성 (잡 이름 제안 `capital_gains_annual_report` — [DD-10-15]) | T4 A0 |
| **4/1** | 대행신고 알림: 예상세액 + 증권사 대행신고 신청 딥링크 + 마감 카운트다운 (04 §2 M6) | critical ⑨ (03 §7.2) — T5는 A5(대리권 — 05 §9.1) |
| **5/1** | 납부 알림: 산출세액·기한·납부 링크 (00 §3.2 T6) | critical ⑨ — T6 A5 |

- **미초과 시 개입 0회**: 250만 이하면 1/15 판정 결과를 info 1건으로 통보하고 4/1·5/1 알림을 생성하지 않는다(00 §3.2 T4 — "미초과 시 개입 0회").
- 잡 등록·catch-up 분류는 12 문서(연 1회 잡 — `until` 창은 각 마감일).

> **[DD-10-15] tax가 요구하는 신규 잡·서브스텝 2건 (이름은 제안, 등록은 12 문서)**
> - 결정: ① 연 1회 `capital_gains_annual_report`(1/15, catch-up `until` = 각 마감일) ② 일 1회 `sync_pending_tax_events` 서브스텝(`daily_planner` 07:00 이후 · `signal_and_plan` 07:30 이전). 두 잡의 **본체 함수는 tax가 소유**하고, 잡 이름·시각·catch-up 분류의 확정 권한은 [12-scheduling-and-operations.md](12-scheduling-and-operations.md)에 있다.
> - 근거: 01 §4.2 잡 표에 이 두 행이 없다. 그런데 03 §6.1 연간 캘린더는 "1월 15일 양도세 판정·신고서 초안 자동 생성"을, 02 §5.6-(b)2는 "tax 모듈이 `pending_tax_events` 행을 읽어 `pending_transfers`를 생성"을 요구하므로 **실행 주체가 되는 잡이 반드시 필요**하다. 01 §4.2.1의 커버리지 불변식("모든 잡은 catch-up 표의 한 행에 속한다")상 이름 없이 둘 수 없다.
> - 계획 문서와의 관계: 01 §4.2 표의 여백을 채움. 잡 등록 소유권은 12 문서이므로 이름은 제안이며, 12가 다른 이름을 택하면 이 문서의 §12.1·§14.1 표기를 따라 바꾼다. 충돌 없음.

### 12.2 신고서 초안 구조

```python
class TaxFilingDraft(BaseModel, frozen=True):
    year: int
    per_instrument: list[FilingRow]     # 종목별: 취득가액(이동평균)·양도가액·필요경비·손익(KRW, 결제일 환율)
    manual_items: list[FilingRow]       # 대주주·비상장 등 수동 입력 통산분 (02 §5.1)
    total_gain_krw: Decimal
    deduction_krw: Decimal              # 250만
    taxable_krw: Decimal                # max(0, total − deduction)
    est_tax_krw: Decimal                # taxable × 22% (05 §2.3)
    reconcile: LedgerReconcileResult    # 증권사 산출 손익 vs 자체 계산 대사표 (00 §3.2 T4)
    disclaimer: str                     # "이 초안은 참고용이며 증권사 대행신고 산출액이 정본이다"
                                        # — 삽입 필수 (00 §3.2 T4, 02 §5.1)
```

> **[DD-10-12] 산출 형식·저장 경로**
> - 결정: 초안·대사표·절세 리포트는 마크다운 + CSV 쌍으로 `var/reports/tax/{year}/`에 쓴다(§ 산출물은 `var/` — 01 §6.1의 입력물/산출물 분리 규칙 준용). 웹 대시보드 세금 패널(03 §7.1-8)이 이를 렌더링한다(화면은 13 문서).
> - 근거: 계획이 산출물의 파일 형식을 정하지 않았다. 사람이 읽고(마크다운) 홈택스·증권사 양식에 옮겨 적을 수 있는(CSV) 두 형태가 최소.
> - 계획 문서와의 관계: 여백 채움. 충돌 없음.

### 12.3 검증 항목

- [ ] 250만 경계(249.9/250.0/250.1만) 판정 test vector.
- [ ] disclaimer 문구가 모든 산출물에 존재한다(문자열 어서션 — 16 문서 수거).
- [ ] 수동 입력 통산분이 합산·공제 순서에 반영된다.
- [ ] 미초과 연도에 4/1·5/1 알림이 0건이다.

---

## 13. 매도 우선순위·`tax_overlay`·게이트 API

### 13.1 승인 연동 — `TaxApprovalRegistry`

세금 유래 A3 항목의 판정·대기 상태는 tax가 소유하고, 상호작용(버튼·타임아웃 집행)은 rpc/13 문서가 소유한다. 파라미터 정본은 03 §5.3.2. **저장은 전용 테이블이 아니라 `approval_requests`의 kind별 행**이며(DDL 정본: 03 §3.3.9 [DD-03-12], `kind`는 개방 집합), 아래 `kind` 이름 중 `isa_sell_confirm`·`e7_demoted`·`e5_transfer`는 03이 이미 명명한 값을 그대로 쓴다.

| kind | 생성 조건 | 타임아웃(`grace_deadline`) | 만료 동작(`timeout_action`) |
|---|---|---|---|
| `income_warn_sell` | WARN 티어 × 국내상장 해외 ETF 매도 레그 | 7일 | 해당 레그만 보류 지속(`sell_blocked` 유지) |
| `isa_sell_confirm` | ISA ≥70% 또는 `unknown` × ISA 내 매도 레그 | 7일 | 상동 |
| `harvest_y1` / `harvest_safemode` | §11.5 | D\*−2 | 무행동 |
| `e7_demoted` (E7 A3 강등 큐) | §14.1 | 없음(A3) | 무행동 |
| `external_income_confirm` | §8.3 70% 도달 | 14일 | 보수적 가정 유지 |
| `e5_transfer` (워터폴 이체 지시) | §6.4-3 | `transfer_reserve_expiry_days`(승인 후 7일) | `EXPIRED` — 예약 해제 |

### 13.2 `assert_not_blocked` — pre-trade 단계 2.5

```python
def assert_not_blocked(self, order: Order) -> None:
    if order.side is OrderSide.BUY:
        return                                    # 매도 방향에만 적용 (03 §1.6)
    if order.intent is OrderIntent.E7_TRANSFER:   # ★ side는 이미 SELL — intent × side (02 [DD-02-17]-③)
        return                                    # E7 면제 (02 §5.6-(c) 불변식 5)
    mask = self.blocked_for_sell([(order.account_id, order.instrument_key)])
    entry = mask.get((order.account_id, order.instrument_key))
    if entry and not self.approvals.is_cleared(order, entry.reason):
        raise TaxSellBlockedError(order, entry.reason)   # 예외 계층: 02-domain-model.md
```

- 호출 지점·순서는 09 문서 소유(03 §1.6 체인 — 단계 2 감시 다음, 단계 3 매수가능금액 앞). tax는 이 함수의 **의미론만** 소유한다.
- 계획 단계(07:30)의 `blocked_for_sell`과 pre-trade의 `assert_not_blocked`는 같은 마스크를 읽는다 — 계획에서 걸러진 주문이 pre-trade에서 다시 걸리는 것은 정상적으로 0건이어야 하며, 발생하면 계획-집행 사이 상태 변화(승인 만료 등)이므로 거부가 옳다.

### 13.3 `tax_overlay` — 적용 범위와 순서

```
입력: generate_orders(plan) 산출 주문 리스트 (02 §4.3 의사코드 (7) 호출 지점)
동작 (순서 고정):
1. sell_blocked 레그 제거 — 매도 방향만. 사유를 감사로그 `guard_verdict` 이벤트로
   기록한다: `verdict=None` + `blocked_by ∈ {TAX_SOFT_STOP, TAX_ISA_LIMIT}`
   (값 집합 정본: 03 §7.2 `BlockedBy` 8값 [DD-03-34] — 02 §8.1.1의 6값 + 세금 2값.
   이 문서의 신설 요청이 수용된 결과다). 귀속은 02 §5.4·03 §4.6 ① 행대로
   **TE ①(비용)**이며, 다른 6값(③④)과 귀속 축이 다르다.
2. E7 슬라이스 병합 지점 확인 — mandatory_orders는 (7)에서 별도 병합되므로
   overlay는 중복 생성이 없음을 어서션만 한다
   ※ 02 §5.6-(b)4는 "tax_overlay가 그날 슬라이스를 계획에 추가"로 쓰지만,
     02 §4.3 의사코드 (7)은 `tax.mandatory_orders(...)`를 별도 리스트로 병합한다.
     **의사코드가 집행 스펙의 구체형이므로 후자를 채택**하고, §5.6-(b)4의
     "tax_overlay"는 세금 엔진 전체를 가리키는 총칭으로 읽는다.
3. 현금 조달형 매도 — `side=SELL ∧ intent ∈ {WITHDRAWAL, HARVEST, CASHFLOW}` 에만
   §13.4 우선순위로 종목·수량 재배열. ★ 밴드 복귀 매도
   (`intent ∈ {BAND_RESTORE, CLASS_BAND, TARGET_SHIFT}`)의 종목·수량은 불변 —
   연말 게이트·차단만 적용 (02 §5.4 적용 범위, 값 집합: §2.2 정규화표)
4. 연말 태그: D*−2 이후 해외 매도 전 건에 "내년 귀속" 경고 태그 부착 (02 §5.1-5)
```

### 13.4 매도 우선순위 구현 (정본: 02 §5.4)

```python
def sell_priority_rank(h: HoldingView, isa: IsaUsage, income: IncomeTier) -> tuple:
    """1. 비과세(국내주식형 ETF) → 2. 과세 자산 중 손실 중 → 3. 해외상장(공제·통산)
       → 4. 국내상장 해외 ETF(금소세 여유 확인 후 마지막).
       ISA 내 매도: 소진률 ≥70%면 3~4순위 사이로 강등, unknown이면 강등 없음.
       legacy 자산(02 §4.3.0-g)은 전 순위에 앞서는 1순위 후보다."""
```

- 하베스팅의 2차 정렬(§11.3-2)은 이 1차 정렬의 **동순위 내부에만** 적용된다(02 §5.4).
- 인출(T8)의 월간 집행 매도, 02 §3.3.1 유니버스 축소 잔여(legacy)의 자연 처분, E7은 전부 이 우선순위의 소비자다 — 호출자는 07(인출)·08(집행)이며 tax는 순위 함수만 제공한다.

### 13.5 `TaxOverlayStub` — M4 시나리오용 스텁 계약 (16의 요청 수용)

> **[DD-10-18] `TaxOverlayPort` 프로토콜과 `TaxOverlayStub` 계약**
> - 결정: §2.2 파사드의 4개 메서드를 `typing.Protocol` `TaxOverlayPort`로 뽑고, `TaxEngine`(실구현)과 `TaxOverlayStub`(테스트 대역)이 둘 다 이를 만족한다. 스텁은 `tax/` 패키지가 아니라 테스트 픽스처에 살지만 **계약(아래 시그니처·반환 규약)의 소유는 10**이다.
> - 근거: [16-testing-and-quality.md](16-testing-and-quality.md) §13-7의 조율 요청 — M4 필수 시나리오(12월 3중 충돌 판정)는 `tax` 실구현이 아니라 스텁을 주입받는다(04 §2 M4, 03 §4.7). 스텁이 파사드와 다른 모양이면 M4에서 통과한 시나리오가 M6 실구현 교체 때 전부 다시 깨진다 — 프로토콜을 한 벌 두는 것이 그 재작업을 막는 최소 장치다.
> - 계획 문서와의 관계: 04 §2 M4가 "실집행 없이 판정만"으로 마일스톤을 정의한 여백을 채움. 충돌 없음.

```python
# 계약(소유: 10) — 구현체는 tax.engine.TaxEngine, 대역은 tests의 TaxOverlayStub
class TaxOverlayPort(Protocol):
    def blocked_for_sell(self, keys) -> SellBlockMask: ...
    def mandatory_orders(self, state, accounts) -> list[OrderDraft]: ...
    def tax_overlay(self, orders: list[OrderDraft], ctx) -> list[OrderDraft]: ...
    def assert_not_blocked(self, order) -> None: ...
```

스텁의 반환 규약(M4 범위에서 이것만 보장한다):

| 메서드 | 스텁 동작 |
|---|---|
| `blocked_for_sell` | **빈 마스크**(차단 없음). 금소세·ISA 임계 추적은 M6 범위이므로 M4에서 판정하지 않는다 |
| `mandatory_orders` | 시나리오가 주입한 고정 E7 슬라이스 리스트를 그대로 반환(계산 없음). `intent=E7_TRANSFER`, `side` 지정 |
| `tax_overlay` | **우선순위 ①>②>③만** 적용 — 같은 `(account_id, instrument_key)`에 복수 레그가 있으면 `E7_TRANSFER`(①) > `HARVEST`(②) > 밴드 3값(`BAND_RESTORE`·`CLASS_BAND`·`TARGET_SHIFT`, ③) 순으로 **하나만 남기고 제거**한다(03 §2.5). 종목 우선순위(§13.4)·연말 태그·비용 게이트는 적용하지 않는다 |
| `assert_not_blocked` | `intent is E7_TRANSFER`면 즉시 반환, 그 외에도 no-op(예외를 던지지 않는다) |

- 스텁이 **하지 않는 것**을 명시한다: 하베스팅 후보 선정·수량 산정(§11.3), 워터폴(§6), 원장 갱신(§4). M4 시나리오가 이 값들에 의존하면 그것은 시나리오의 결함이다.
- 실구현 교체 시 회귀 기준: 같은 M4 시나리오를 `TaxEngine`으로 돌렸을 때 **①>②>③ 판정 결과가 동일**해야 한다(§11.6 `resolve_december_conflicts`가 같은 우선순위를 구현한다).

### 13.6 검증 항목

- [ ] 밴드 복귀 매도가 overlay 전후로 종목·수량 불변(property-based — 02 §5.4의 수렴 성질 보호).
- [ ] `sell_blocked` 레그가 `UnexecutedOrder`로 기록된다(TE ① 입력).
- [ ] E7 주문이 2.5 단계를 면제 통과한다.
- [ ] 우선순위 정렬 test vector — ISA 70%/unknown 강등 유무 분기 포함.
- [ ] 출처 태그 소스 스캔: `tax/` 안에 타입명 `OrderOrigin`이나 `*_SELL`/`*_BUY` 접미 출처 값이 없다(02 §7.2 교차 문서 계약 테스트 — 16 수거).
- [ ] `TaxOverlayStub`과 `TaxEngine`이 같은 M4 시나리오에서 동일한 ①>②>③ 판정을 낸다([DD-10-18]).

---

## 14. E7 세금 측 절차 — `pending_tax_events` → `pending_transfers`

집행 절차 전체 정본은 02 §5.6이다. 이 절은 tax가 소유하는 부분(**eligibility 판정·행 생성·슬라이스 수량 산출**)만 설계한다. 주문 제출·체결·잔량 처리와 **상태 전이 정의**는 [08-execution.md](08-execution.md) §14.2, KR-04 감지는 [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md).

### 14.1 eligibility — 계좌별 분기 (정본: 02 §5.6-(b)2, 00 §3.2 E7 상한 ④)

```python
def e7_eligibility(account: AccountView, isa: IsaUsage,
                   ev: PendingTaxEvent) -> Literal["CREATE", "SKIP", "APPROVAL"]:
    if not ev.cross_checked:            return "APPROVAL"   # 2소스 불일치 → A3 (상한 ③)
    match account.type:
        case AccountType.GENERAL:       return "CREATE"
        case AccountType.PENSION | AccountType.IRP:
            return "SKIP"               # 과세이연 — 시점 통제 이득 0 (상한 ④)
        case AccountType.ISA:
            if isa.state == "known" and isa.ratio < Decimal("0.70"):
                return "CREATE"
            return "APPROVAL"           # ≥70% 또는 unknown → A3 큐 (02 §5.6-(b)2)
```

`sync_pending_tax_events`(일 1회, `daily_planner` 이후·07:30 이전 — 07:30 계획이 슬라이스를 읽으므로. 잡 신설 근거는 [DD-10-15]): `persistence.ro`로 `pending_tax_events` 신규 행을 읽어, 계좌별 예상 실현손익·예상 과세소득을 산출(국내상장 해외 ETF면 배당소득 — 금소세 누적기 예약 반영, 06 §8.4)하고 위 분기대로 `pending_transfers` 행을 만든다(state=PENDING). `substitute_key`는 `universe.yaml`의 `approved_substitutes` 1:1 페어(상한 ①)이며 페어가 없으면 행을 만들지 않고 A3 큐(`ESC_REPLACE` 승인 경로와 동일 취급 — 11 문서).

### 14.2 상태 전이 — 정의 정본은 08

`pending_transfers`의 상태 전이도(PENDING→RUNNING→DONE/ABORTED)와 전이 트리거·`slices_done` 증가 시점의 **정의 정본은 [08-execution.md](08-execution.md) §14.2**다(E7 절차·상태 전이의 소유는 08 — 브리프 §2.1, 08의 조율 요청 수용). 이 문서는 종전 §14.2에 두었던 중복 전이도를 삭제하고 **행 생성(eligibility) 시점의 진입 조건과 tax 측 제약**만 남긴다.

- **진입(행 생성 → `state=PENDING`)**: §14.1 `e7_eligibility`가 `CREATE`를 반환한 경우에만. 이 시점에 00 §3.2 E7 상한 4개가 전부 봉인된다(08 §14.4 "행이 존재하면 상한이 충족된 것으로 신뢰한다").
- **슬라이스 1개가 되는 경우**(D−3 이후 뒤늦게 감지): 자동 실행하지 않고 A3 승인 큐(02 §5.6-(c) 불변식 2 — 1회 전량 매도 금지). RUNNING 전이 거부의 집행은 08 §14.4-2.
- **상태 게이트**: `SAFE_MODE`에서는 실행, `HALTED`(등급 불문)·`PAUSED_ALL`·`STOPPED`에서는 실행하지 않는다(불변식 4). 판정은 `mandatory_orders` 진입부에서 `state.effective_constraints`로 한다 — 03 §1.6 단계 7을 우회하는 경로는 없다.
- **`ESC_REPLACE` 중복 배제**(불변식 3): 같은 종목에 `pending_transfers` 행이 존재하면 감시의 `ESC_REPLACE` 제안을 생성하지 않는다 — 판정 주체는 11 문서의 제안 생성기이며, tax는 행 존재 조회 API(`transfers.has_pending(instrument_key)`)를 제공한다.

### 14.3 슬라이스 산출 — `mandatory_orders` 내부

```python
def due_slices(self, asof: date, state: BotStateView) -> list[OrderDraft]:
    orders = []
    for t in repo.running(asof):                       # state == RUNNING
        remaining_days = t.slices_total - t.slices_done
        executed = self.executed_qty(t)                # ★ 아래 주석 — 파생값(컬럼 아님)
        qty = ceil((t.total_qty - executed) / remaining_days)         # 02 §5.6-(b)4
        sell = OrderDraft(t.account_id, t.instrument_key, OrderSide.SELL, qty,
                          limit_price=None, origin=OrderIntent.E7_TRANSFER,
                          paired=False, transfer_key=(t.account_id, t.instrument_key))
        buy_qty = floor(est_proceeds(sell) / price(t.substitute_key))  # 노출 공백 방지
        buy = OrderDraft(t.account_id, t.substitute_key, OrderSide.BUY, buy_qty,
                         limit_price=None, origin=OrderIntent.E7_TRANSFER,
                         paired=False, transfer_key=(t.account_id, t.instrument_key))
        orders += [sell, buy]                          # 같은 계획에 동시 편입 (02 §5.6-(b)4)
    return orders
```

- 매도/매수 세분은 enum 값이 아니라 `intent × side`다 — 둘 다 `intent=E7_TRANSFER`이고 방향만 다르다(02 [DD-02-17]-③, §2.2 정규화표). `OrderDraft` 필드 구성 정본은 08 §4.1이며 `transfer_key`는 E7 슬라이스에만 채운다.
- `slices_total` = D−10 ~ D−3 사이 거래일 수(캘린더 계산 — 06 문서, XKRX 거래일 확정은 08 [DD-08-12]). 슬라이스 미체결분은 다음 거래일 잔여 균등식이 자연 흡수한다(분자에 기집행 수량 반영).
- **`executed_qty`(= 02 §5.6-(b)4의 "기집행")는 `pending_transfers` 컬럼이 아니라 파생값이다 — 확정**: 03 [DD-03-36]이 전용 컬럼 신설을 기각하고 `fills ⨝ orders(intent='e7_transfer', account_id, instrument_key)`의 `SUM(qty)` 파생으로 확정했다(지원 인덱스 `ix_orders_intent`·`ix_fills_order`, 파생 질의 계약 03 §3.5). `slices_done`은 계획 02 §5.6 정의 그대로 **회차 카운터**로 남으며, 부분 체결 시 회차와 수량이 어긋나는 문제는 이 파생식이 해소한다.
- 매수 레그 수량식(floor(예상 매도대금/대체가))은 계획의 "동시에 substitute 매수를 같은 계획에 넣어 노출 공백을 만들지 않는다"(02 §5.6-(b)4)의 산술 구체화다. 매도 먼저·체결 확인 후 매수의 집행 순서는 08 문서(02 §4.3 기타 규칙).
- E7 주문은 금소세 soft-stop·ISA 확인의 적용을 받지 않는다(불변식 5 — §13.2 면제). 실현분은 금소세 누적기·하베스팅 G 계산에 반영된다(§8.1, §11.6).

### 14.4 검증 항목

- [ ] eligibility 분기 표 전체(계좌 4유형 × ISA 3상태 × cross_checked 2값).
- [ ] 균등 분할 수량식 — 중도 미체결·부분 체결 시 잔여 균등 재계산.
- [ ] 상태 게이트: SAFE_MODE 실행 / HALTED·PAUSED_ALL·STOPPED 미실행(03 §4.7 M4 판정 케이스).
- [ ] 불변식 1(주문 생성 주체 tax+execution뿐): surveillance가 pending_transfers를 쓰지 못한다 — 아키텍처 테스트(01 §2.2 계약).
- [ ] D−3 이후 감지 → A3 큐(자동 실행 0건).

---

## 15. 계획 문서 추적표

| 계획 조항 | 이 문서의 반영 위치 | 비고 |
|---|---|---|
| 00 §3.2 T1~T9·E4·E5·E7 | §1.1 매핑표, 각 절 | 등급·타임아웃 준수 |
| 00 §2.2-④ / 05 §9.3 (개입 0회 금지·79~99만원) | §7 전체 | T9를 자동화하지 않는 근거 |
| 02 §1.2 (asset location·표1·표2·AccountMode) | §5, [DD-10-4] | 분해 알고리즘 입력 |
| 02 §1.3·§1.3.1·§1.3.2 (워터폴·3층·gap check 산술) | §6, §7 | 결합제약 캡 구현 |
| 02 §4.2 (`pending_transfer_reserve`·만료 7일) | §6.4 | `allocatable_cash` 연계는 07 |
| 02 §4.3.0-(b) (분해 절차·불변식) | §5.2 | 1:1 의사코드 |
| 02 §4.3 의사코드 (1)(7)·보조 정의 (`blocked_for_sell`·`mandatory_orders`·`tax_overlay`) | §2.2, §13 | 시그니처 계약 |
| 02 §5.1 (이동평균·TLH/TGH·D\*−2·게이트·첫해 지시서) | §4, §11 | |
| 02 §5.1.1 / 03 §2.5 (12월 3중 충돌) | §11.6 | ①>②>③, ①이 ② 흡수 |
| 02 §5.1.2 (후보 선정·수량 8단계) | §11.3 | 1:1 구현 |
| 02 §5.2 (금소세 누적기·티어·ISA 소진률·unknown) | §8, §9, [DD-10-9] | |
| 02 §5.3 (과표기준가 이중 경로·티어별 폴백) | §10, §8.2 | fallback 기본 |
| 02 §5.4 (매도 우선순위·적용 범위·sell_blocked 귀속) | §13.3, §13.4 | 밴드 복귀 불변 |
| 02 §5.5 (tax.yaml 외부화·분리과세 키 금지) | §3 | |
| 02 §5.6 (E7 절차·불변식 5개) | §14 | DDL은 03 문서, 상태 전이는 08 §14.2 |
| 02 §7.2 (`OrderIntent` — 출처 태그 단일 정본) | §2.2 정규화표, §13.2·§13.3, §14.3 | 값 집합 정본은 02 [DD-02-17](11값), 방향 세분은 `intent × side` |
| 02 부록 A (`tax.*`·`waterfall.*` 키·기본값) | §3.1, [DD-10-16] | 법령값은 `tax.yaml`, 운영 키는 `config.yaml` |
| 03 §3.3.8·§3.3.9·§3.2.1·§3.5 (세금 원장·승인 큐·`positions`·파생 질의) | §2.3 | 테이블명·컬럼명 정본은 03 |
| 03 §1.6 단계 2.5 (`assert_not_blocked`·E7 면제) | §13.2 | 체인 소유는 09 |
| 03 §2.2 세금 행 / §2.5 (SAFE_MODE 하베스팅 금지) | §11.5, §11.6 | |
| 03 §5.3.2 (세금 A3 파라미터: 7일/14일/D\*−2) | §13.1 | UX는 13 문서 |
| 03 §6.1·§7.2 (연간 캘린더·critical ⑧⑨) | §7.1, §12.1 | |
| 03 §4.6 TE ① (세금 보류 레그 귀속) | §8.4, §13.3 | |
| 01 §4.2·§4.2.1 (`waterfall_gap_check`·`tax_harvest` 시각·catch-up) | §7.1, §11.1 | 등록은 12 문서 |
| 01 §6.1 (effective-date = 주문 제출 KST) | §3.2 | |
| 01 §2.2 (import 계약·repos 화이트리스트) | §2.1, [DD-10-2] | |
| 05 §2.3 (세제 수치 전체) | §3.1, §8, §9, §12 | 등급: 높음 |
| 05 §9.5 (세무 자동화 한계선·이동평균 재설계) | §1.2, §4 | |
| 06 §8.4 (`pending_tax_events` 사실 필드·tax가 손익 산출) | §14.1 | surveillance -/-> tax |
| 05 §7.4 / 06 §8.2 (해지상환 = 배당소득) | §8.1, §14.1 | |
| 04 §2 M6 (DoD 2·3·5·6, 검증 거래, 첫해 지시서) | §4.4, §7.4, §11 | 마일스톤 참조 |

## 16. 설계 결정(DD) 목록

| ID | 제목 | 위치 |
|---|---|---|
| DD-10-1 | `tax/` 내부 파일 분할과 `TaxEngine` 파사드 | §2.1 |
| DD-10-2 | tax 쓰기 리포지토리(`repos.tax_events`·`pending_transfers`·`approvals`)와 import 자기 제한 *(03 [DD-03-32]·§4 수용으로 개정)* | §2.3 |
| DD-10-3 | 브로커 대사 불일치 2회 연속 시 하베스팅 A1 → A3 강등 | §4.4 |
| DD-10-4 | 표2(계좌 선호)의 `universe.yaml` `account_preference` 컬럼 승격 | §5.1 |
| DD-10-5 | 비정기 유입의 `horizon_lt_3y` 질의·기본값 false | §6.3 |
| DD-10-6 | 정기분 자동이체 설계 제안 헬퍼(연 1회 리포트) | §6.5 |
| DD-10-7 | 한계세율 입력 키 `tax.user_marginal_credit_rate`(기본 13.2%) | §7.2 |
| DD-10-8 | gap check 잔여 0원에도 info 1건 발송 | §7.3 |
| DD-10-9 | 금소세 누적기의 계좌 범위 = 과세 계좌(일반위탁) 한정 | §8.1 |
| DD-10-10 | 건보 자격 config `tax.health_insurance_status` | §8.2.1 |
| DD-10-11 | 하베스팅 NAV 20% 게이트 분자 = 매도+재매수 합산 | §11.4 |
| DD-10-12 | 신고서 초안·리포트의 형식(md+CSV)·경로(`var/reports/tax/`) | §12.2 |
| DD-10-13 | 집계 경로의 effective-date 기준 = 이벤트 결제일(집행 경로는 01 §6.1 유지) | §3.2 |
| DD-10-14 | 하베스팅 자동 실행 승격 키 `tax.harvest_auto_enabled`(기본 false) | §11.5 |
| DD-10-15 | 신규 잡·서브스텝 2건(`capital_gains_annual_report`·`sync_pending_tax_events`) 이름 제안 | §12.1 |
| DD-10-16 | 세법 파라미터 이중 정의 해소 — `tax.yaml`=법령값 / `config.yaml`=운영 키, 결합 뷰 `TaxSettings` | §3.1 |
| DD-10-17 | T3 하베스팅 A1의 `/revert` 의미 — 미집행 잔여 취소·시즌 중단, 체결분 되돌리기 없음 | §11.5 |
| DD-10-18 | `TaxOverlayPort` 프로토콜과 M4용 `TaxOverlayStub` 반환 규약 | §13.5 |

## 17. 미해결 항목·스파이크 종속

| # | 항목 | 종속 | 이 설계의 현재 가정 |
|---|---|---|---|
| 1 | 과표기준가 자동 수집 가능성 | **SP-C1**(M1) | `fallback` 기본(실차익 과대추정 + fallback 임계 집합). 04 부록 B도 fallback 확정 권고 |
| 2 | 절세계좌 API 주문·잔고 조회(ISA 계좌상품코드 포함) | **SP-C4**(M1) | `AccountMode` 격리로 양쪽 경로 설계 완료(분기 A: AUTO / 분기 B: BROKER_SCHEDULED+INSTRUCTION). 잔고 조회 실패 시 납입액 집계는 월 1회 CSV(E3 폴백) |
| 3 | `period_rights`가 분배금·원천징수액을 담는가 | **SP-C6**(M6) | 실패 시 §8.1 원장 관측 + 수동 입력 폴백 유지 |
| 4 | KIS 해외주식 정산이 실제로 이동평균인가 | **M6 진입 게이트**(검증 거래 — 02 §5.1) | `CostBasisCalculator` 주입으로 구현체 교체 가능 |
| 5 | 국내상장 ETF 원가의 이동평균 관행 | 미확인(02 §5.2) | 동일 가정 + 폴백 여유(~15%)로 흡수, M6 DoD 3 1회 대사 |
| 6 | 통합증거금에서 매도대금의 매수 여력 즉시 반영 여부 | 미확인(02 §5.1.2-6) | 낙관 가정 금지 — D+2 예수금 규칙, 부족 시 재매수 익일 이월 |
| 7 | 과대추정 폭 ~15% 가정 | 추측(02 §5.3) | M6 이후 실측 재조정 항목 |
| 8 | YTD 납입액 집계용 KIS 입금 내역 TR·필드 | **[확인 필요]** — SP-C4 실증·공식 문서 확인 | 3단 폴백(§7.2)으로 미확인 상태에서도 동작 |
| 9 | `해외주식 기간손익`(032)·`기간별계좌권리현황조회`의 정확한 TR ID·응답 필드 | **[확인 필요]** — 공식 문서/실측(계획은 이름·(032)만 제공) | 어댑터 계층(05-broker-gateway)에 위임, tax는 집계 결과 모델만 소비 |
| 10 | 가상자산 과세 시행 여부·시점 | `tax.yaml` 훅만 유지(02 §7) | `crypto_tax_enabled: false` |
| 11 | **밴드 복귀**의 세금 비대칭 ρ(EX-2 — 매도/매수·계좌별 분리, 02 §4.3·§8.2 표) | M2 실험(02 §8.2) — 추측 항목이므로 미개선이면 채택하지 않음 | 하베스팅 로직이 아니라 07 문서(리밸런서)의 파라미터다. tax는 미실현손익 부호만 제공하며 본 설계에 반영분 없음 |
| 12 | `backtest.account_model: multi`(4계좌+워터폴 시뮬) | SP-C4 확정 후 **M8**(02 §8.1) | §5.2 분해 함수를 순수 함수로 유지해 재사용 대비 |
| 13 | **이견 등재(잔존)** — 계획 01 §6.1의 effective-date 규칙("주문 제출 KST 날짜, 체결일·결제일이 아니다")을 집계 경로에까지 적용하면 연말 경계(12/30 체결·1/2 결제)에서 귀속 연도와 적용 버전이 어긋난다 | **[확인 필요]** — 계획 01 §6.1을 "주문 경로 한정"으로 읽는지 "모든 경로"로 읽는지의 판정. 확인 방법: 01 문서(계획) 개정 또는 설계 01 문서의 명시 회신 | [DD-10-13]으로 집행/집계 경로를 분리했고 **설계 04 §6.2가 이를 수용**했다("집계 경로는 결제일 기준 버전 — 어느 날짜를 넣을지는 소비자(10)가 정한다"). 계획 01 §6.1이 "모든 경로"로 확정되면 DD-10-13을 철회하고 §7·§12 연말 경계 test vector를 재작성한다 |
| 14 | ~~E7 기집행 수량(`executed_qty`)의 보관 위치~~ | **해소** | 03 [DD-03-36]이 전용 컬럼을 기각하고 `fills ⨝ orders(intent='e7_transfer')` 파생으로 확정(§14.3 반영, 파생 질의 계약 03 §3.5) |
| 15 | ~~`PlannedOrder.origin` 값 집합(8종)의 확정~~ | **해소** | 02 [DD-02-17]이 `OrderIntent` 11값으로 단일화하고 방향 세분을 `intent × side`로 확정. §2.2 정규화표로 교체하고 §13.2·§13.3·§14.3 분기를 그에 맞춰 재작성(타입명 `OrderOrigin`·필드명 `PlannedOrder.origin` 폐지) |
| 16 | ~~`UnexecutedOrder.blocked_by`에 세금 사유 값이 없다~~ | **해소** | 03 [DD-03-34]가 `BlockedBy` 8값(02 §8.1.1 6값 + `TAX_SOFT_STOP`·`TAX_ISA_LIMIT`)과 TE ① 귀속 사상을 확정(§13.3 반영). 15 §7.3도 03 §7.2 참조로 정정됨 |
| 17 | 04 상호 제약 **C-29**(`config.yaml`과 `tax.yaml`의 동명 키 값 일치 강제)는 [DD-10-16]의 분리가 서면 **교집합이 사라져 무효 조건**이 된다 | 04 문서 소유 — 제거 요청 | 04 §14-15 권고대로 02 부록 A의 `tax.deduction`·`tax.isa_free_limit`·`waterfall.pension_deduct_cap_*`를 `tax.yaml` 별칭으로 재해석해 `AppConfig`에서 제거하고, [DD-04-4] 검사 ⓒ에 "`tax.yaml` 스키마 키는 `AppConfig` 필드가 없어도 통과" 예외를 추가한다. **10·04 동시 반영 필요** |
| 18 | `pending_transfer_reserve` 파생 조건의 상태 범위 — 03 §3.5·07 §9·09는 `state='PENDING'`만 세는데 02 §4.2 정의는 "승인 대기 **또는 승인·미이행**"이다 | 03(파생 질의 계약)·07·09와 조율 | 값 산출 소유는 10이므로 §6.4의 정의(PENDING + `APPROVED ∧ payload_json.fulfilled_at IS NULL`)를 정본으로 두고 파생 조건 확장을 요청한다. 미반영 시 승인~입금 확인 구간에 cash-flow first가 이체 예정 현금을 소진할 수 있다 |
