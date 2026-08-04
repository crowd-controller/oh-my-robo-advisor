# 15. 백테스트·검증 (Backtest & Validation)

> **범위**: `src/omra/backtest/` 패키지 전체 — 일 단위 종가 리밸런싱 시뮬레이터(라이브와 계산 로직 공유·in-memory 원장), 보수적 체결·비용·세금 가정, 자산 생애주기, 윈도우 데이터 접근자(`BarView` — 구조적 lookahead 방지), 시뮬 모드 2종(`clean`/`with_guards`), Walk-Forward 러너, lookahead 자동탐지, 검증 게이트(코어 C1~C3 / 위성 S1~S4 / 가드 A-B / 챌린저 `G2`), DSR·시도 수 `N` 집계 연계, 성과지표(QuantStats + 자체), 스냅샷 회귀 CI 계약, tracking error 5항목 분해 계산기, block bootstrap 몬테카를로 러너, `tools` 컨테이너 실행 경로와 결과 파일 계약.
> **계획 정본**: 02 §8 전체(§8.1·§8.1.1·§8.1.2·§8.2·§8.3·§8.4)·§9 · 02 §3.2(변동성 지표 2종)·§3.3(정수화)·§4.5(체결 가정 정렬)·§4.7(FX)·§2.3(as-of 필터)·부록 A(`backtest.*`·`mc.*`·`gk.*`) · 03 §4.4(백테스트 게이트 CI)·§4.5·§4.6(TE 5항목) · 05 §1.5(zipline 패턴)·§4.6(block bootstrap)·§4.7(skfolio)·§10.3(백테스트 증거론) · 07 §7.2·§7.3(`G2`)·§13(실험 원장) · 01 §1.5·§1.6(tools 실행 경로 정본)·§2·§6.3 · 04 §2 M2.
> **선행 문서**: [02-domain-model.md](02-domain-model.md)(Order·Fill·Instrument·Decimal 규약·`SimClock`·예외), [03-data-and-persistence.md](03-data-and-persistence.md)(Parquet 레이아웃·DuckDB 뷰·`experiments` DDL·감사로그 스키마·`VACUUM INTO` 스냅샷), [06-market-data-and-calendar.md](06-market-data-and-calendar.md)(`ParquetStore.read_asof`·캘린더·결제일·FX), [10-tax-engine.md](10-tax-engine.md)(`TaxEngine` 파사드·`CostBasisCalculator`), [01-system-architecture.md](01-system-architecture.md)(CLI 카탈로그·`tools` 서비스·import 계약 파일).
> **이 문서가 소유하는 정의**: 브리프 §2.1 "백테스트 시뮬·검증 게이트 구현". 인접 경계 — 최적화·리밸런서·정수화·몬테카를로 **경로 생성 커널**은 [07-portfolio-engine.md](07-portfolio-engine.md) 소유(백테스트는 호출자), 세금 로직은 [10-tax-engine.md](10-tax-engine.md) 소유, DDL·Parquet 스키마·감사로그 봉투는 [03](03-data-and-persistence.md) 소유, CI 파이프라인 구성은 [16-testing-and-quality.md](16-testing-and-quality.md) 소유(이 문서는 게이트 러너의 호출 계약만), 실험 원장의 `G0` 워크플로·롤백 트리거는 [14-research-and-labs.md](14-research-and-labs.md) 소유.

---

## 1. 개요 — 설계 대상과 책임

### 1.1 책임 요약

`backtest/`는 **"이 시스템의 숫자를 우리가 스스로 검증하는 유일한 장치"**다. 05 §10.3의 판정 — *외부 백테스트 숫자는 그 자체로 증거가 아니며, 비용 모델이 0이 아닌 순간 엔진마다 결론이 갈린다* — 이 패키지의 존재 이유이자 설계 제약이다. 그래서 이 패키지의 1급 요건은 성능이 아니라 **재현성·비용 정확성·lookahead 부재**다.

| 축 | 책임 | 절 |
|---|---|---|
| 시뮬레이션 커널 | 일 단위 종가 리밸런싱 루프, t+1 종가 체결, in-memory 원장, 자산 생애주기 | §3·§4·§5 |
| 데이터 접근 규율 | `BarView` 윈도우 접근자, PIT 유니버스 as-of 재평가 | §6 |
| 시뮬 모드 | `clean`(TE 분해 기준선) / `with_guards`(가드 A-B 게이트) | §7 |
| 검증 | Walk-Forward, lookahead 자동탐지, 게이트 C1~C3·S1~S4·가드 A-B·`G2` | §8·§9·§10 |
| 통계 | TE 5항목 분해, DSR·시도 수 `N`, 성과지표(QuantStats + 자체) | §7.4·§11·§12 |
| 예측 | 몬테카를로 러너(모니터링 전용 — 수치 커널은 [07](07-portfolio-engine.md) §14) | §13 |
| 실행 경로 | `tools` 컨테이너 CLI, 결과 파일 계약, 실행 자원 예산 | §14 |

### 1.2 설계 불변 원칙

1. **라이브와 계산 로직을 공유한다.** 밴드 판정·정수화·세금은 `engine`·`tax`의 **같은 함수**를 호출하고, 다른 것은 원장 구현(in-memory vs SQLite)과 시계(`SimClock` vs `SystemClock`)뿐이다 (정본: 02 §8.1, freqtrade `LocalTrade`/`Trade` 패턴 — 00 §4). 시뮬 전용 사본을 만드는 순간 이 하네스는 자기 자신을 검증하는 장치가 된다.
2. **당일 종가 체결 금지.** t일 신호 → **t+1일 종가** 체결 (정본: 02 §8.1·§4.5).
3. **거래비용 0 백테스트는 산출 자체가 금지다.** 비용 모델 비활성 옵션을 만들지 않는다 (정본: 05 §10.3, 07 §4.4 HR-2).
4. **lookahead는 탐지 이전에 접근 불가로 막는다.** 전략·최적화 함수에는 DataFrame 전체가 아니라 `BarView(as_of)`만 주입되고, `as_of` 이후 인덱스는 **물리적으로 존재하지 않는다** (정본: 02 §8.1, 05 §1.5 zipline `BarData`). §9의 자동탐지는 2차 방어선이다.
5. **결정론.** 같은 사양·같은 데이터 스냅샷 → 같은 결과 파일(수치·해시). 벽시계·전역 난수·딕셔너리 순회 순서에 의존하는 코드를 두지 않는다. 이것이 게이트 C3(스냅샷 회귀)의 전제다.
6. **봇 프로세스에서 실행 금지.** 백테스트·`G2`는 `docker compose run --rm tools …`의 별도 프로세스이고 봇은 결과 파일만 읽는다 (정본: 01 §1.6 — 하드 규칙).
7. **시뮬은 자기가 모르는 것을 안다고 말하지 않는다.** `clean` 모드에 가드·감시·SAFE_MODE가 없다는 것은 누락이 아니라 경계이며, 그 경계는 결과 파일에 명시된다 (정본: 02 §8.1.1).

### 1.3 이웃 문서와의 경계

| 주제 | `backtest`가 하는 것 | 이웃이 하는 것 |
|---|---|---|
| 목표비중·밴드·정수화 | 호출자. `as_of`·`BarView`를 주입하고 결과를 원장에 반영 | 알고리즘 구현은 [07-portfolio-engine.md](07-portfolio-engine.md) (정본: 02 §3·§4.3) |
| 세금 | `TaxEngine`을 시뮬 시각·in-memory 원장에 붙여 연 단위 호출 | 세금 로직 전체는 [10-tax-engine.md](10-tax-engine.md) (정본: 02 §5) |
| 원장 타입 | `PortfolioLedger` 프로토콜의 **in-memory 구현**(§4) | 프로토콜·포지션/NAV 계산은 `portfolio/`([07](07-portfolio-engine.md)·[08-execution.md](08-execution.md) 분담 — 01 §2) |
| 데이터 | `ParquetStore.read_asof`·DuckDB 뷰 소비 | 스토어·뷰·PIT 스냅샷은 [06](06-market-data-and-calendar.md)·[03](03-data-and-persistence.md) |
| 가드·감시 재생 | `with_guards`에서 **같은 판정 함수**를 호출 | 가드·SV 등급·브레이커 정의는 [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md)·[09-safety-protections.md](09-safety-protections.md) |
| 실험 원장 | 결과 파일 생성 + ingest 입력 규약(§11.4) | 테이블 DDL은 [03](03-data-and-persistence.md) §3.3.11, `G0` 워크플로·롤백은 [14](14-research-and-labs.md) |
| CI | 게이트 러너 CLI와 종료 코드 계약 | 워크플로 YAML·트리거·잡 배치는 [16-testing-and-quality.md](16-testing-and-quality.md) |
| 몬테카를로 | 러너(입력 시계열 조립·현금흐름/시평 사양·`rng` 주입·산출물 파일) | **수치 커널 전부**(경로 생성·GK·성공확률·팬차트·처방 역산) = `engine/montecarlo.py`는 [07](07-portfolio-engine.md) §14 (정본: 02 §9, 01 §2) |

---

## 2. 모듈 구조

```
src/omra/backtest/
├── __init__.py
├── spec.py             # BacktestSpec·RunKind·SimMode·CostModel — pydantic 사양 모델 + spec_hash
├── runner.py           # BacktestRunner 파사드: 사양 → 시뮬 → 지표 → 게이트 → 결과 파일
├── engine_loop.py      # 일간 시뮬 커널(§3) — 하루 = 8단계
├── barview.py          # BarView / BarViewFactory — 윈도우 접근자(§6)
├── ledger.py           # SimLedger(in-memory 원장) · SimAccount · SimPosition(§4)
├── broker_sim.py       # CloseFillSimulator — t+1 종가 체결·수량/틱 라운딩·거부 사유(§5.1)
├── costs.py            # CostModel 적용: 수수료·거래세·슬리피지·환전 스프레드(§5.2)
├── corporate.py        # 자산 생애주기: auto_close 청산·CA 비율 조정·배당/분배금(§5.3·§5.6)
├── modes.py            # sim_mode clean / with_guards 조립(§7)
├── unexecuted.py       # UnexecutedOrder 기록 → 감사로그 GuardVerdictPayload 매핑(§7.3)
├── tracking.py         # TE 5항목 분해 계산기(§7.4)
├── walkforward.py      # Walk-Forward · CPCV 분할 러너(§8)
├── lookahead.py        # lookahead 자동탐지(§9)
├── gates/
│   ├── base.py         #   Gate ABC · GateResult · GateRegistry(§10.1)
│   ├── core.py         #   C1·C2·C3(§10.2·§10.3)
│   ├── satellite.py    #   S1~S4(§10.4)
│   ├── guard_ab.py     #   가드 on/off A-B 게이트(§10.5)
│   └── challenger.py   #   G2 조립(§10.6, 조건부)
├── stats/
│   ├── metrics.py      #   자체 지표 — 게이트 판정의 정본(§12.2)
│   ├── dsr.py          #   Deflated Sharpe Ratio · 시도 수 N 조회(§11)
│   ├── bootstrap.py    #   stationary block bootstrap 유틸(부트스트랩 CI · MC 공용)
│   └── report.py       #   QuantStats tear sheet 생성(사람용 전용 — §12.1)
├── mc_runner.py        # 몬테카를로 러너(§13) — 수치 계산은 전부 engine.montecarlo.simulate 호출
├── snapshot.py         # 스냅샷 회귀 비교기·기준 파일 I/O(§10.3)
└── result.py           # BacktestResult 직렬화·결과 파일 계약(§14.3)
```

**import 규율** — `backtest`는 `core·config·calendar·data·engine·tax·portfolio·protections·surveillance·audit·persistence.ro`를 import한다. `brokers·execution·rpc·web·scheduler·realtime·runtime`은 import하지 않는다(§17 [DD-15-16]). 계약 파일의 유일 원문은 [01-system-architecture.md](01-system-architecture.md) §8.2이며(계획 정본: 01 §2.2), 이 문서는 요구만 등록한다. 프로세스 경계 쪽 절반은 `.env.tools`의 자격증명 부재와 기동 셀프체크 SC-13이 담당한다(정본: 01 §1.6).

> **[DD-15-1] `backtest/` 파일 분할과 `BacktestRunner` 파사드**
> - 결정: 위 트리로 분할하고, 외부(=`labs`·CLI)가 보는 진입점은 `BacktestRunner`와 `GateRegistry` 두 개로 고정한다. 내부 모듈은 러너를 거치지 않고 직접 호출되지 않는다.
> - 근거: 01 §2가 `backtest/`를 "일 단위 시뮬, Walk-Forward 러너, lookahead 탐지" 세 단어로만 정의했다. `labs.challenger`가 별도 프로세스 CLI로만 호출한다는 규율(07 §7.3)을 지키려면 진입점이 좁아야 한다.
> - 계획 문서와의 관계: 여백 채움. 충돌 없음.

---

## 3. 시뮬레이션 커널 — 일 단위 종가 루프

### 3.1 사양 모델 (`spec.py`)

```python
class SimMode(StrEnum):                      # 정본: 02 §8.1.1
    CLEAN       = "clean"                    # 런타임 가드·SV 동결·SAFE_MODE 없음 (기본)
    WITH_GUARDS = "with_guards"              # PIT 감시 스냅샷 재생 + SAFE_MODE 상태기계

class RunKind(StrEnum):                      # 실험 원장 적재 자격의 판정 키 (§11.4, 07 §13)
    MANUAL      = "manual"                   # 사람이 돌린 사양 탐색 → 원장 기록 대상
    CHALLENGER  = "challenger"               # G2 러너 → 원장 기록 대상
    GATE        = "gate"                     # 게이트 러너(CI 외) — 07 §13 "수동 백테스트"의
                                             #   하위 종류로 취급해 기록 대상. N은 DISTINCT
                                             #   spec_hash이므로 같은 사양의 재실행은 N을 늘리지 않는다
    CI_SNAPSHOT = "ci_snapshot"              # 스냅샷 회귀 → ★ 원장 기록 제외 (07 §13)

class BacktestSpec(BaseModel, frozen=True):
    # ── 기간·유니버스 ────────────────────────────────────────────────
    start: date; end: date                   # 게이트 C1 기본 구간은 10년 (04 §2 M2 DoD)
    universe_ref: str                        # universe.yaml 버전 해시 (04 소유 스키마)
    risk_level: int                          # 02 부록 A `risk.level`
    account_model: Literal["single", "multi"] = "single"   # 02 부록 A `backtest.account_model`
    sim_mode: SimMode = SimMode.CLEAN
    # ── 비용·세금 ────────────────────────────────────────────────────
    costs: CostModel                         # §5.2 — 기본값은 02 §8.1 전재. 0 비용 사양은 거부
    tax_track: Literal["both", "pretax_only"] = "both"     # 02 §8.1 "세전/세후 두 트랙"
    # ── 파라미터 오버레이(챌린저·실험) ────────────────────────────────
    param_overrides: Mapping[str, str] = {}  # 허용 키는 run_kind에 따라 갈린다 — 아래 표
    benchmark: BenchmarkSpec                 # §10.2 — 기본 60/40 (02 §8.2 게이트 C1)
    seed: int = 20260101                     # bootstrap·표본 추출의 유일한 난수 원천
    run_kind: RunKind = RunKind.MANUAL

    @property
    def spec_hash(self) -> str: ...          # §11.3 정규화 해시 (DSR N의 집계 키)
```

`param_overrides` 검증은 **`run_kind`에 따라 갈린다** — 07 §7.1이 규율하는 대상은 "챌린저가 될 수 있는 키"이지 "사람이 백테스트로 재어 볼 수 있는 키"가 아니기 때문이다.

| `run_kind` | 허용 범위 | 근거 |
|---|---|---|
| `CHALLENGER` | 07 §7.1 `tuning_space` 화이트리스트(`rebalance.cooldown_days`·`mvo.turnover_gamma`·`cov.lookback_days`·`bl.tau`) **뿐**. 밖이면 `SpecValidationError`(→ `ConfigError` 하위, [02](02-domain-model.md) §10)로 즉시 거부 | 화이트리스트 밖은 `T2`(로직)이며 PR의 대상이다(정본: 07 §7.1). `band.*`·`crypto.*`·`satellite.*`·`safe_mode.*`·`protections.*`는 영구 제외(00 §3.2 P7 hard rail 포함) |
| `MANUAL` · `GATE` | 위 화이트리스트 **+ 계획이 명시적으로 요구한 실험 축**: EX-1의 `band.restore_fraction`(ρ ∈ {0.75, 0.875, 1.0} — 02 §8.2, 04 §2 M2 추가 항목 1), EX-4의 크립토 `crypto.vol_target` ±25%(02 §8.2 EX-4 = 게이트 S2 §10.4). 그 밖의 키는 거부 | 계획이 지정한 실험을 코드가 막으면 M2 DoD·M7 위성 게이트가 실행 불가가 된다 |

`MANUAL`·`GATE`의 추가 축을 쓴 run은 결과 파일 `assumptions.param_overrides`에 전량 열거하고, **산출값을 config에 쓰지 않는다**(파라미터 확정은 사람의 행위 — §18-13, §12.2). `CHALLENGER`에서의 hard rail 오버라이드가 물리적으로 불가능한 것이 이 분기의 핵심이다.

### 3.2 하루 = 8단계 (의사코드)

시뮬 타임라인의 마스터 캘린더는 **KRX 거래일**이고, 각 자산의 체결일은 자기 venue 캘린더에서 결정된다([DD-15-5]). `SimClock`은 매일 07:30 KST로 설정되어 라이브 판정 시각과 동일한 시각축을 공유한다(정본: 02 §4.1 판정 표, `SimClock` 정의 정본: [02-domain-model.md](02-domain-model.md) §8).

```python
def run_day(t: date, ctx: SimContext) -> DayRecord:
    ctx.clock.set_to(kst(t, "07:30"))                    # 후퇴 금지 (02 문서 SimClock)
    view = ctx.views.at(t)                               # BarView — as_of 이후 물리적 부재 (§6)

    # 1. 미결 체결 큐 소진 — 어제 낸 주문이 오늘 종가로 체결된다 (t+1 종가, 02 §8.1)
    for pending in ctx.queue.due(t):
        fill_or_expire(pending, view, ctx)                # §5.1. 미체결은 이월하지 않는다 (02 §4.1)

    # 2. 자산 생애주기 — auto_close·CA 비율 조정 (§5.6, 05 §1.5)
    corporate.apply(t, ctx)                              # 강제 청산 현금은 (7)의 cash-flow 재원

    # 3. 배당·분배금 — 배당락 인식 + 원천징수 차감 후 현금 유입 (§5.3)
    corporate.credit_distributions(t, view, ctx)

    # 4. 월 1회 목표비중 재계산 — 02 §3, §4.0 축 ①
    #    라이브 잡은 매월 1일 02:30 universe_reeval → 03:30 monthly_targets_batch(01 §4.2)이고,
    #    시뮬 마스터 타임라인은 KRX 거래일이므로 그달 첫 KRX 거래일로 사상한다([DD-15-5] 타임라인 규약).
    if ctx.calendar.is_first_trading_day_of_month("KRX", t):
        uni  = universe.reevaluate_asof(view, ctx.config)   # PIT hard 필터 (§6.3, 02 §2.3)
        tgt  = compute_targets_sim(view, uni, ctx.params, as_of=t)     # §3.3 — 07의 월간 파이프라인 호출
        ctx.state.apply_targets(tgt)                       # 승인 사다리는 시뮬에서 자동 승인 [DD-15-9]

    # 5. 상태 갱신 — clean이면 항상 RUNNING, with_guards면 상태기계 1스텝 (§7.2)
    ctx.state = ctx.mode.step_state(t, view, ctx)

    # 6. 일 1회 드리프트 밴드 판정 — 라이브와 같은 함수 (02 §4.3 의사코드 `daily_rebalance_check`,
    #    구현명·시그니처 정본은 [07](07-portfolio-engine.md) §10.3 `plan_daily`)
    plan = engine.plan_daily(
        targets=ctx.state.targets, decomposition=ctx.decomposition,
        portfolio=ctx.ledger, prices=view, universe=ctx.universe,
        accounts=ctx.accounts, masks=ctx.mode.masks, state=ctx.state.view,
        reserves=ctx.reserves, params=ctx.params)
    ctx.counters.look += 1                                # look/breach/trade 3분 계측 (02 §8.4)

    # 7. 주문 조립 — 정수화·T_min·tax_overlay·safemode_filter (모두 라이브 함수)
    drafts = assemble_sim(plan, ctx)                      # §3.3
    drafts = ctx.mode.apply_interventions(drafts, ctx)    # clean이면 항등, with_guards면 축소만
    for d in drafts:
        ctx.queue.push(d, fill_date=ctx.calendar.next_session(venue_of(d), after=t))

    # 8. EOD — NAV 마킹·지표 누적·세금 원장 결제 반영
    ctx.ledger.mark_to_market(view, ctx.fx.rate_on(t))    # 02 §4.7 백테스트 행: 일별 종가 환율
    ctx.tax.on_settlement_batch(ctx.calendar.settled_on(t))
    return ctx.metrics.record_day(t, ctx)
```

**연 단위 훅** — 12월 하베스팅 시즌(02 §5.1, D\*−2 마감)에 `TaxEngine.harvest`를 라이브와 같은 게이트 4종으로 호출하고, 1/1에 연간 공제·누적기를 리셋한다. 세후 트랙에서만 실행하며 승인 사다리는 자동 승인으로 취급한다([DD-15-9]).

### 3.3 라이브 코드 공유 지점 (정본: 02 §8.1)

| 대상 | 시뮬에서의 처리 |
|---|---|
| 목표비중 산출(BL·LW·MVO·HRP) | **동일 함수**. 입력만 `BarView` 경유. `compute_targets_sim`은 이 문서의 **어댑터 이름**일 뿐이고 내부는 `monthly_targets_batch`와 같은 순서로 [07](07-portfolio-engine.md) §4~§9(`equilibrium_returns` → `bl_posterior` → `estimate_strategic` → `solve_continuous` → `hrp_check`)를 호출한다 — **엔진 API의 정본은 07** |
| 드리프트 밴드 판정 `plan_daily` | **동일 함수**([07](07-portfolio-engine.md) §10.3 = 02 §4.3 `daily_rebalance_check`). `masks`·`state`·`tax`를 시뮬 어댑터로 주입 |
| 정수화 2단계 `engine.quantize_partial` | **동일 함수**. `V_a`에 단일 계좌 평가액 주입 (정본: 02 §3.3 2단계·§8.1 계좌 모델) |
| `tax_overlay`·`blocked_for_sell`·하베스팅 | **동일 함수**(`TaxEngine` — [10](10-tax-engine.md) §2.2) |
| 호가단위·수량 라운딩 | **동일 함수**(`core.tick`·`core.money` — [02](02-domain-model.md) §5·§6) |
| 주문 조립(`execution.assembler`) | **재사용하지 않는다.** `execution`은 브로커·락·라우터에 결합되어 있어 `backtest`가 import하지 않는다(§2). 대신 `assemble_sim`이 [08-execution.md](08-execution.md) §4.2 `assemble`과 동일한 **순서**(`engine.quantize_partial`[정수화·`T_min`] → `tax_overlay` → 병합[cashflow·mandatory·constraint_cure] → `safemode_filter` → 순매수 상한 사전 투영 → `T_min` 재확인)를 따르고, 그 순서 동일성을 계약 테스트로 고정한다([16](16-testing-and-quality.md) 수거). 이 순서는 02 §4.3 의사코드의 마지막 4줄(`tax_overlay(generate_orders(plan))` → 병합 → `safemode_filter` → route)과 02 §3.3 2단계(정수화 안에 `T_min` 필터)를 합친 것이다 |
| 원장 | in-memory `SimLedger`(§4)가 `PortfolioLedger` 프로토콜을 구현 |
| 시계 | `SimClock`(02 문서 §8) |

### 3.4 오류 경로

| 상황 | 처분 |
|---|---|
| 필수 바 결측(보유 종목의 거래일 바 없음) | 해당 자산의 당일 판정 제외 + `DayRecord.data_gaps`에 기록. 결측률이 `backtest.data.max_gap_pct`(**임의 초기값 0.5% — 계획 근거 없음, M2 재설정 대상 §18-16**) 초과면 **실행 실패**(무결성 우선 — 조용한 편향 금지) |
| 최적화 solver infeasible | 직전 유효 목표 유지 + 카운트(정본: 02 §3.3 "실패 시 직전 유효 목표 유지 + 플래그"). 축소 유니버스 infeasible은 02 §3.3.1 ④ 폴백 순서를 그대로 탄다 |
| 현금 음수 발생 | `InvariantViolation` — 즉시 중단. 라이브 불변식 1(02 §3.3)과 같은 규칙이며 시뮬에서 완화하지 않는다 |
| `SimClock` 후퇴 | `InvariantViolation`(02 문서 §8 — 시간이 뒤로 가는 시뮬은 버그) |
| FX 스냅샷 결측 | 직전 영업일 값 캐리포워드 + 결과 파일 플래그. 5영업일 초과 캐리포워드는 실행 실패 |

### 3.5 검증 항목 (§3)

- 하루 8단계의 순서 고정 테스트(단계 호출 순서를 기록하는 스파이 컨텍스트).
- t+1 체결 규약: t일 생성 주문이 t일 원장에 반영되지 않음(속성 테스트 — 전 구간).
- `assemble_sim`과 [08-execution.md](08-execution.md) §4.2 `assemble` 단계 순서의 동치 계약 테스트(02 §4.3·§3.3 2단계가 그 순서의 계획 근거).
- 결측률 임계 초과 시 실행 실패(조용한 통과 금지).

---

## 4. In-memory 원장 (`ledger.py`)

### 4.1 구조

freqtrade `LocalTrade`/`Trade` 패턴의 이식이다 — **원장 저장 매체만 다르고 계산은 같은 모듈**(정본: 02 §8.1, 00 §4).

```python
class SimPosition(BaseModel):                 # 계좌 × 종목
    account_id: str
    instrument: Instrument                    # 정의 정본: 02-domain-model.md §4
    qty: Dec                                  # lot_step 격자 (qty_floor 규약)
    avg_price_ccy: Dec                        # 이동평균단가 — 갱신 주체는 tax.CostBasisCalculator
    currency: Literal["KRW", "USD"]

class SimAccount(BaseModel):
    account: Account                          # 정의 정본: 02-domain-model.md §3.3
    cash_krw: Dec
    positions: dict[str, SimPosition]         # key = instrument_key

class SimLedger:
    """PortfolioLedger 프로토콜의 in-memory 구현.
    프로토콜(apply_fill·nav·weights·holdings)의 정의 정본은 portfolio/ (07·08 분담)."""
    def apply_fill(self, order: Order, fill: Fill) -> None: ...
    def nav_krw(self) -> Dec: ...
    def weights_total(self) -> dict[tuple[str, str], Dec]: ...   # (account_id, instrument_key) → w
    def held(self, account_id: str, key: str) -> Dec: ...
    def mark_to_market(self, view: BarView, fx: Dec) -> None: ...
    def snapshot(self) -> LedgerSnapshot: ...                    # 일별 기록·재현성용 동결 사본
```

- **불변식(매 스텝 어서션)**: ① 모든 계좌의 `cash_krw ≥ 0` ② `Σ 비중 = 1 ± ε`(ε = 1e-9) ③ `qty ≥ 0`이고 `lot_step` 격자 ④ 모든 금액은 `Decimal`(float 유입은 `Dec` 검증기가 생성 시점에 거부 — 02 문서 §5.1). ①②는 03 §4.1의 property-based 불변식과 **같은 문장**이며, 시뮬과 라이브가 같은 어서션을 공유한다.
- `Order`·`Fill`은 도메인 모델을 그대로 쓴다(재정의 금지 — 정의 정본: [02-domain-model.md](02-domain-model.md) §7.3). `Order.dry_run = True`, `Order.intent`는 라이브와 같은 값을 실어 사후 집계(경로별 회전율)를 가능하게 한다.
- `account_model: single`에서 `SimAccount`는 1개(`AccountType.GENERAL`)다. **ISA 비과세 한도·연금 과세이연·IRP 위험자산 70%는 적용하지 않는다** — 세후 수치는 절세계좌 편익을 포함하지 않는 **하한**이다(정본: 02 §8.1 계좌 모델). `multi`(4계좌 + 워터폴 + 계좌별 hard 제약)는 SP-C4 확정 후 M8 착수이며(정본: 02 §8.1), `SimLedger`는 계좌 dict 구조를 처음부터 갖되 `single`에서는 원소가 1개다 — 양경로 대응이 자료구조 수준에서 이미 끝나 있게 한다.

> **[DD-15-2] in-memory 원장의 배치와 공유 방식**
> - 결정: `PortfolioLedger` 프로토콜과 포지션/NAV **계산 함수**는 `portfolio/`(07·08 소유)에 두고, `backtest/ledger.py`는 그 프로토콜의 in-memory 구현만 제공한다. 라이브 SQLite 원장과 시뮬 원장은 **같은 계산 함수를 호출**하고 저장 매체만 다르다.
> - 근거: 02 §8.1이 요구한 "계산 로직 동일 모듈"을 코드 배치로 강제하는 유일한 방법이다. 시뮬이 자체 NAV 계산을 가지면 TE 분해(03 §4.6)의 기준선이 라이브와 다른 산식을 쓰게 되고, 그 차이가 ⑤ 잔차로 계상되어 R1을 오탐시킨다(07 §10.3).
> - 계획 문서와의 관계: 01 §2 트리의 `portfolio/` 주석("라이브 DB / 백테스트 in-memory 로직 공유")의 구현. 충돌 없음.

### 4.2 검증 항목 (§4)

- 불변식 4종의 property-based 테스트(hypothesis) — 03 §4.1과 같은 시나리오 집합을 시뮬 원장에도 적용.
- 라이브 원장 ↔ 시뮬 원장 등가성: 동일 `Fill` 시퀀스 주입 후 NAV·비중·평단이 자릿수까지 일치.
- `LedgerSnapshot` 직렬화 왕복 항등(재현성).

---

## 5. 체결·비용·세금·생애주기 가정

### 5.1 체결 모델 (`broker_sim.py`)

```python
class PendingOrder(BaseModel, frozen=True):
    draft: OrderDraft                          # 조립 산출 (형태 정본: 08-execution.md §4.1)
    decided_on: date                           # 신호일 t
    fill_date: date                            # t의 다음 venue 세션 (calendar 소유 — 06)

class CloseFillSimulator:
    def fill(self, p: PendingOrder, view: BarView) -> Fill | Rejection: ...
```

체결 규칙 (전부 보수적 방향):

1. **체결가 = `fill_date`의 종가**(정본: 02 §8.1). 시가·VWAP·중간값을 쓰지 않는다.
2. **부분 체결·큐 우선순위를 시뮬하지 않는다.** 전량 체결 또는 전량 미체결이다. 편향 방향은 **낙관**이며 결과 파일에 명시한다 — 개인 규모에서 마켓 임팩트 ≈ 0이라는 판정(02 §4.1.2)이 그 근거이고, 실전과의 차이는 TE 분해 ②(체결 시점 괴리)가 흡수한다.
3. **슬리피지는 종가에 방향성으로 가산**한다(매수 +, 매도 −). 값은 §5.2 표.
4. **수량은 `qty_floor(lot_step)`, 지정가는 틱 규칙 스냅**([02](02-domain-model.md) §5.3·§6). 미국 수량 산정에는 `fx_buffer 0.005`를 적용한다(정본: 02 §3.3 2단계·§4.7-(b)).
5. **`T_min` 미만 주문은 스킵**하고 스킵 사유를 카운트한다 — `T_min` 스킵 비율은 EX-1의 판정 지표다(정본: 02 §8.2, §3.3.1 알려진 한계).
6. **미체결은 이월하지 않는다**(정본: 02 §4.1 국내·미국 공통). 익일 07:30 재판정이 흡수한다.
7. **현금 부족 시 거부**(`Rejection(reason="insufficient_cash")`) — 부분 축소 체결로 구제하지 않는다. 라이브 pre-trade가 매수가능금액에서 막는 것과 같은 방향이다.

> **[DD-15-5] 체결일 결정 규칙 — venue별 다음 세션**
> - 결정: 시뮬 마스터 타임라인은 KRX 거래일이고, 주문의 체결일은 `calendar.next_session(venue, after=t)`다. 미국 자산은 미국 캘린더의 다음 세션 종가(KST로는 t+1 새벽), 크립토는 다음 일봉 종가(09:00 KST 판정 기준). 마스터 타임라인 휴장으로 판정이 없는 날에는 체결도 발생하지 않는다.
> - 근거: 02 §8.1은 "t+1일 종가"만 규정하고 캘린더가 갈리는 경우를 정하지 않았다. venue 캘린더를 쓰지 않으면 미국 휴장일에 체결이 생기거나(허구) KRX 휴장 구간에서 미국 주문이 사라진다(누락). 캘린더 소유는 06이므로 시뮬은 호출만 한다.
> - 계획 문서와의 관계: 02 §4.5(미국 LOC = 종가 체결로 시뮬-실전 정합)와 정합. 충돌 없음.

### 5.2 비용 모델 (`costs.py`) — 값의 정본은 02 §8.1

```python
class CostModel(BaseModel, frozen=True):
    fee_kr: Dec = Dec("0.00015")          # 국내 수수료 0.015%
    fee_us: Dec = Dec("0.0009")           # 미국 수수료 0.09%
    tax_sell_kr_stock: Dec = Dec("0.0015")# 국내 개별주 매도 거래세 0.15% (ETF 면제)
    slip_kr_etf_bp: Dec = Dec("5")        # 국내 ETF 5bp
    slip_us_bp: Dec = Dec("3")            # 미국 3bp
    slip_crypto_bp: Dec = Dec("10")       # 크립토 10bp
    fee_crypto: Dec = Dec("0.0005")       # 업비트 수수료 0.05%
    fx_spread_roundtrip: Dec = Dec("0.002")  # 환전 스프레드 왕복 0.2%

    @model_validator(mode="after")
    def _reject_zero(self) -> "CostModel":
        """모든 항이 0인 사양은 ConfigError. '거래비용 0 백테스트'는 증거가 아니다
        (정본: 05 §10.3, 07 §4.4 HR-2)."""
```

- **ETF 매도 거래세 면제**는 `Instrument.asset_class`로 판정한다(ETF 어휘는 [02](02-domain-model.md) §4.2). 개별주(`us_stock`은 미국이라 해당 없음, 국내 개별주는 현 유니버스에 없음)에만 0.15%를 적용하며, 유니버스에 개별주가 없더라도 **코드 경로는 남긴다**(위성·대체 페어 교체 사고 방지).
- **환전 스프레드**는 미국 자산 매수·매도의 KRW 환산 금액에 편도 0.1%(왕복 0.2%의 절반)로 적용한다. 라이브 스펙의 "환전 없음(통합증거금 자동환전)"과 모순이 아니라 **같은 비용의 다른 이름**이며, 라이브 측 실효 환전 스프레드는 TE 분해 ①에 같은 항목으로 계상한다(정본: 02 §4.7-(e)).
- 총비용률·리밸런싱당 평균 거래비용은 이 모듈의 누적기가 산출한다(§12.2).

> **[DD-15-4] `backtest.*` config 블록 확정**
> - 결정: 02 부록 A에 이미 있는 `backtest.account_model`·`backtest.gates.core`·`backtest.gates.satellite` 외에 아래 키를 `backtest.*` 블록에 신설한다: `backtest.sim_mode`, `backtest.costs.*`(위 8개, 값은 02 §8.1 전재), `backtest.data.max_gap_pct`, `backtest.lookahead.samples`(기본 10 — 02 §8.3), `backtest.lookahead.weight_tolerance`, `backtest.snapshot.tolerance_pct`(기준 파일 `tolerance` 맵에 없는 지표의 기본값 — §10.3-3), `backtest.benchmark.*`, `backtest.tax.harvest_enabled`, `backtest.seed`, `backtest.gates.challenger_years`(§10.6 분기 B), `backtest.us_fill_basis`(§15-1 SP-C3 양경로). 스키마 등록은 [04-configuration-and-secrets.md](04-configuration-and-secrets.md)에 위임한다.
> - 근거: 02 부록 A 규칙 1("자기 블록에만 있는 키는 그 문서가 이름까지 정본")에 따라 백테스트 전용 키는 이 문서가 이름을 정한다. 계획이 `sim_mode:`를 접두사 없이 표기했으나 CI 키 화이트리스트(02 부록 A 규칙 3)가 블록 단위로 동작하므로 `backtest.` 접두사를 붙인다.
> - 절대 기준(`absolute_floor.sharpe_min`·`mdd_max`)은 **config 키로 두지 않는다** — 기준 파일(`tests/snapshots/backtest/<baseline_id>.json`)에 실리며 포맷 정본은 16 §9.2다(§10.3). 게이트 하한을 런타임 config로 바꿀 수 있으면 "CI 우회 경로"가 생기고, 16 §9.2의 `gate-floor-change` 승인 라벨이 무력화된다.
> - 계획 문서와의 관계: 값이 계획 전재가 아닌 키는 셋뿐이며 각각의 처분은 다음과 같다 — ① `backtest.snapshot.tolerance_pct`: **값을 정하지 않고 M2 실측으로 남긴다**([DD-15-10]·[DD-15-17]) ② `backtest.data.max_gap_pct`(기본 0.5%): 무결성 임계이며 계획에 근거가 없는 **이 문서의 임의 초기값**이므로 M2에서 실제 결측률 분포를 보고 재설정한다(§18-16) ③ `backtest.lookahead.weight_tolerance`(기본 `1e-9`): '같음'의 수치 정의이며 근거는 [DD-15-8]. 나머지는 전부 계획 전재. 충돌 없음.

### 5.3 배당·분배금·원천징수

- 배당락일(ex-date)에 가격은 데이터 소스의 조정 규약을 따르고(수정종가 `adj_close` — [03](03-data-and-persistence.md) §5.2), 현금 배당은 **지급일에 원천징수 차감 후** 계좌 현금으로 유입한다: 미국 15% / 국내 15.4%(정본: 02 §8.1).
- 유입된 현금은 다음 판정일의 cash-flow first 재원이 된다 — 라이브와 **동일 경로**다(정본: 02 §8.1·§4.2).
- 국내상장 해외 ETF의 분배금은 세후 트랙에서 금소세 누적기에 반영한다(정본: 02 §5.2, 소비 API는 [10](10-tax-engine.md) §8).
- **[확인 필요]** 배당 이벤트 시계열(ex-date·지급일·주당 배당금)의 소스가 계획에 명시되지 않았다. 확인 방법: M2에서 `ohlcv_daily.adj_close` 대비 총수익 재구성 가능 여부를 실측하고, 불가하면 배당 데이터셋을 [06](06-market-data-and-calendar.md)의 Fetcher 카탈로그에 추가 요청한다. 확정 전에는 `adj_close` 기반 총수익 근사를 쓰되 **결과 파일에 근사 플래그를 남긴다**(세후 트랙의 배당 원천징수가 근사로 계산됨을 숨기지 않는다).

### 5.4 FX

| 용도 | 규약 | 출처 |
|---|---|---|
| 일별 NAV·밴드 판정 | 일별 종가 환율(Parquet `fx_rates`) | 02 §4.7-(b) 백테스트 행 |
| 미국 주문 수량 산정 | 같은 일별 종가 환율 × `(1 + 0.005)` 보수화 | 02 §3.3 2단계·§4.7-(b) |
| 세금 원장 | 결제일 환율 | 02 §4.7-(b) 세금 행 |
| 반올림 | KRW 원 단위 절사, 수량 floor | 02 §4.7-(d) |

FX 조회는 `FxService`의 시뮬 어댑터(Parquet 직접 조회)를 통한다 — 서비스 정의 정본은 [06-market-data-and-calendar.md](06-market-data-and-calendar.md) §9.

### 5.5 세금 트랙

- **세전/세후 두 트랙을 동시에 산출**한다(정본: 02 §8.1). 세전 트랙은 세금 이벤트를 원장에 반영하지 않는 **평행 NAV 시계열**이며, 주문 결정은 세후 트랙 기준으로 한 번만 내린다(두 트랙이 서로 다른 주문을 내면 비교 가능성이 사라진다).
- 세후 과세 규칙은 일반위탁 고정: 해외상장 양도세 22%·연 250만원 공제, 국내상장 해외 ETF 매매차익·분배금 15.4%, **손실 이월 불가**(정본: 02 §8.1).
- `TaxEngine`을 시뮬 원장·`SimClock`에 붙여 라이브와 같은 메서드를 호출한다([10](10-tax-engine.md) §2.2). `CostBasisCalculator`는 `MovingAverageCalculator`를 그대로 쓴다 — 재매수의 평단 오염 효과가 시뮬에 반영되어야 한다는 요구(02 §5.1)가 자동으로 충족된다.
- `tax_drag` = (세전 CAGR − 세후 CAGR)로 산출한다(§12.2).

> **[DD-15-9] 시뮬의 승인 사다리·하베스팅 처리**
> - 결정: ① 목표비중 승인 사다리(≤3%p 자동 / 3~8%p 카나리 / 8~20%p 승인 / >20%p REJECT — 02 §3.3)는 시뮬에서 **>20%p 자동 REJECT만 재현**하고 나머지는 자동 승인으로 취급한다. 카나리 α 블렌딩도 재현하지 않는다. ② 연말 하베스팅(02 §5.1)은 세후 트랙에서 실행하되 승인은 자동으로 보고 **게이트 4종(왕복비용 < 절세액×0.5, 밴드 위반 없음, 연 하베스팅 주문금액 ≤ NAV 20%, D\*−2 준수 — 정본: 00 §3.2 T3, 구현: [10](10-tax-engine.md) §11.4)은 라이브 코드 그대로 적용**한다. `backtest.tax.harvest_enabled`로 on/off A-B 산출이 가능하다.
> - 근거: 승인·카나리는 사람의 응답 시간과 변경 예산이라는 **시뮬레이션 불가능한 입력**을 갖는다. 반면 REJECT(>20%p)는 데이터 오염 방어이므로 재현하지 않으면 백테스트가 오염 데이터를 그대로 먹는다. 하베스팅 게이트는 순수 함수라 재현 비용이 0이고, 세후 수치의 상당 부분을 좌우한다.
> - 계획 문서와의 관계: 02 §8.1이 "세금은 §5 로직 그대로 호출"을 요구하고 승인 사다리 재현은 요구하지 않았다. 여백을 명시적으로 채운다. 재현하지 않는 항목은 결과 파일 `assumptions` 절에 열거한다.

### 5.6 자산 생애주기 (`corporate.py`) — 정본: 02 §8.1, 05 §1.5

```python
class Lifecycle(BaseModel, frozen=True):
    instrument_key: str
    start_date: date                 # 상장일 — 유니버스 편입 하한
    end_date: date | None
    auto_close_date: date | None     # = master_pit PIT 스냅샷의 lstg_abol_dt (03 설계서 §5.2)
                                     #   취득 경로: MasterService.as_of(d) — 06 §8.1(API)·§8.2(PIT
                                     #   스냅샷 규약). 시뮬은 다른 소스를 만들지 않는다
```

1. `auto_close_date`에 **최종 NAV(국내 ETF = 해지상환가)로 강제 청산·현금화** → cash-flow first 재투자.
2. 유효구간 밖 자산은 그 시점 유니버스에서 제외하며 **분모(비중 계산)에도 넣지 않는다**.
3. 분할·병합은 야간 마스터 diff의 CA 비율로 수량·단가를 조정한다(diff 산출 정본: [06](06-market-data-and-calendar.md) §8.3).
4. 청산 손익의 세목은 02 §5.1.1·05 §7.4를 그대로 참조한다 — 국내상장 해외 ETF의 해지상환은 **배당소득**이므로 금소세 누적기에 반영한다.
5. **과잉 구현 금지**: hard 필터 통과 종목의 상폐 base rate는 연 0~1회이므로 이것은 정확성 요건이지 성능 요건이 아니다(정본: 02 §8.1). 복잡한 상폐 시나리오 엔진을 만들지 않는다.

> **[DD-15-6] 해지상환가 데이터 부재 시의 청산가 폴백**
> - 결정: `auto_close_date`의 최종 NAV 시계열이 없으면 **직전 거래일 종가**로 청산하고, 결과 파일 `data_flags`에 `redemption_price_fallback: [<종목>]`을 기록한다. 폴백이 발생한 run은 게이트 C3 스냅샷 **기준값 갱신 대상이 될 수 없다**.
> - 근거: 02 §8.1은 청산가를 "최종 NAV(국내 ETF = 해지상환가)"로 규정하나, NAV 시계열의 소스는 06 §7.3 표에서 아직 [확인 필요] 상태다. 데이터가 없다고 청산을 건너뛰면 포지션이 영구 존속해 CAGR·MDD가 왜곡된다(02 §8.1이 막으려던 바로 그 오류). 종가 폴백은 방향 편향이 작고, 기준값 갱신을 막는 것이 조용한 오염을 막는다.
> - 계획 문서와의 관계: 계획 요구(청산은 반드시 한다)를 유지하면서 미확정 데이터를 정직하게 표기. 충돌 없음.

### 5.7 검증 항목 (§5)

- 비용 0 사양이 `ConfigError`로 거부됨(HR-2의 코드화).
- 슬리피지 부호: 매수는 불리, 매도는 불리 방향으로만 적용(속성 테스트).
- 상폐 골든 케이스: `auto_close_date` 도래 → 포지션 0 + 현금 증가 + 분모 제외 + (세후) 배당소득 계상.
- CA 비율 조정 후 평가액 연속성(분할 전후 NAV 점프 없음).
- 세전/세후 트랙이 **같은 주문 시퀀스**를 갖는다(트랙 분기 금지 어서션).
- `T_min` 스킵 카운터가 EX-1 지표로 결과 파일에 노출됨.

---

## 6. 윈도우 데이터 접근자 `BarView` (구조적 lookahead 방지)

### 6.1 API (정본: 02 §8.1 데이터 접근 계약, 05 §1.5 zipline `BarData`)

```python
class Field(StrEnum):
    OPEN = "open"; HIGH = "high"; LOW = "low"; CLOSE = "close"
    ADJ_CLOSE = "adj_close"; VOLUME = "volume"; VALUE_TRADED = "value_traded"

class BarView:
    """as_of 시점의 창(window) 뷰. as_of 이후 인덱스는 이 객체에 물리적으로 존재하지 않는다.
    ★ 이 클래스는 engine의 `PriceView` Protocol을 **구조적으로**(mypy 적합) 구현한다 —
      아래 `close`·`history`·`fx_planning` 3메서드가 Protocol 면이고 나머지는 백테스트 전용
      확장이다. Protocol 정의 정본: [07-portfolio-engine.md](07-portfolio-engine.md) §3.2.
      인자명(`bar_count`)·`field`의 `str` 계약은 Protocol 소유자인 07이 확정했고
      (07 §3.2 주석 — 15의 조율 요청 회신, 07 §21.1-5 '해소'), 이 문서는 그 이름을 그대로 쓴다."""
    as_of: date

    # ── PriceView Protocol 면 (시그니처 정본: 07 §3.2) ────────────────────────
    def close(self, key: str) -> Dec:
        """판정 기준가(전일 종가) = `current(key, Field.CLOSE)`의 별칭."""

    def history(self, key: str, field: str | Field, bar_count: int) -> Sequence[Dec]:
        """as_of를 마지막 원소로 하는 길이 bar_count 시계열. 부족하면 NotEnoughHistory.
        `field` 애노테이션이 `str | Field`인 것은 Protocol 인자 타입 반변 때문이다 —
        `Field(StrEnum)` 값이 그대로 들어간다(07 §3.2)."""

    def fx_planning(self) -> Dec:
        """계획 시각 FX. 라이브는 07:00 스냅샷(06 §9.1 `FxService.planning_rate`),
        시뮬은 as_of 일별 종가 환율(02 §4.7 백테스트 행) — `fx("USDKRW")`와 같은 값이다."""

    # ── 백테스트 전용 확장 (Protocol 밖 — [DD-15-3]) ─────────────────────────
    def current(self, key: str, field: Field) -> Dec:
        """as_of 기준 '가장 최근에 관측 가능한' 값.
        venue 캘린더상 as_of 세션이 없으면 직전 세션 값(미국 자산의 '당일 새벽 마감가' 규약)."""

    def matrix(self, keys: Sequence[str], field: Field, bar_count: int) -> "np.ndarray":
        """공분산·모멘텀 입력용 (T×N) float64 행렬. 결측은 NaN이 아니라 예외 —
        엔진이 NaN을 조용히 흡수하는 경로를 만들지 않는다."""

    def fx(self, pair: str = "USDKRW") -> Dec: ...
    def master_asof(self, key: str) -> MasterRow: ...    # PIT 상태 플래그 (03 §5.2 master_pit)

class BarViewFactory:
    def __init__(self, store: ParquetStore, calendar: TradingCalendar, keys: Sequence[str]) -> None:
        """생성 시 `store.read_asof(ds, as_of=spec.end)`로 전 구간을 1회 로드해
        (T×N) ndarray + 날짜 인덱스로 보유한다. `ParquetStore.read_asof`는 lookahead 방지의
        **스토어 계층 절반**이고(정본: [06-market-data-and-calendar.md](06-market-data-and-calendar.md) §7.1
        — "백테스트 BarView의 데이터측 절반"), 뷰 절단(§6.2-1)이 나머지 절반이다.
        §9의 적재 단계 절단 실험은 이 팩토리를 `as_of=T`로 다시 만들어 수행한다."""
    def at(self, as_of: date) -> BarView: ...            # O(1) 슬라이스 뷰 — 복사 없음
```

### 6.2 구현 규약과 오류 경로

1. **절단은 인덱스 상한 고정으로 구현한다.** `at(as_of)`는 `idx = searchsorted(dates, as_of, side="right")`를 계산해 `data[:idx]`의 **읽기 전용 뷰**만 노출한다(`ndarray.flags.writeable = False`). 뷰 밖 접근은 파이썬 예외가 아니라 **존재하지 않는 인덱스**다.
2. `history`의 `bar_count`가 창을 넘으면 `NotEnoughHistory`(→ `DataError` 하위, [02](02-domain-model.md) §10) — 조용히 짧은 배열을 반환하지 않는다. 짧은 배열 반환은 룩백 756일 가정을 무성의하게 깨뜨린다.
3. `current`는 **미래 보간을 절대 하지 않는다.** 결측이면 직전 관측치이고, 직전 관측치도 없으면 `NotEnoughHistory`.
4. `matrix`는 float64를 반환한다 — skfolio·numpy 경계이며, 이 경계 밖(원장·주문)은 Decimal이다([DD-15-12]).
5. `BarView`는 **frozen**이며 내부 상태가 없다. 같은 `as_of`로 두 번 만들면 동일 객체 의미론(동치)이 성립한다 — 결정론의 전제.

> **[DD-15-3] `BarView` 인터페이스 확정**
> - 결정: Protocol 면 3메서드(`close`·`history`·`fx_planning` — 시그니처 정본 07 §3.2) + 확장 4메서드(`current`·`matrix`·`fx`·`master_asof`)를 확정하고, 엔진 함수에 넘기는 데이터 타입은 `BarView` **하나로 고정**한다. `BarView`는 [07](07-portfolio-engine.md) §3.2 `PriceView` Protocol의 상위집합이며 **어댑터 없이 구조적으로 적합**하다(mypy `Protocol` 검사가 계약 테스트다 — §6.4). Protocol 자체의 정의 정본은 07이다(이 문서는 구현만 소유). `pd.DataFrame`·`dict[str, Series]` 등 전체 데이터를 담은 타입을 시뮬 경로에서 인자로 받는 함수는 아키텍처 테스트로 금지한다([16](16-testing-and-quality.md) 수거).
> - 근거: 02 §8.1은 `current`/`history` 두 개만 명시했다. 그러나 공분산 추정(N×T 행렬)·FX 환산·PIT 상태 플래그 조회가 전부 데이터 접근이며, 이들이 뷰 밖 경로로 들어오면 lookahead 방지가 무의미해진다. "접근 자체를 불가능하게 만든다"는 원칙을 실행하려면 **모든** 데이터 접근이 이 객체를 통과해야 한다.
> - 계획 문서와의 관계: 02 §8.1의 2메서드 명세를 상위집합으로 확장. 충돌 없음.

### 6.3 PIT 유니버스 as-of 재평가

hard 필터는 **as-of 기준으로 재평가**한다 — 현재 플래그로 과거 유니버스를 구성하면 그 자체가 생존 편향이자 lookahead다(정본: 02 §2.3, 05 §1.5).

```python
def reevaluate_asof(view: BarView, cfg: UniverseConfig) -> UniverseSnapshot:
    """02 §2.3 필터 파이프라인을 as_of 시점 데이터로 재실행.
    0단계(상태 hard): master_asof(key)의 tr_stop_yn·admn_item_yn·
                      etf_etn_ivst_heed_item_yn·lstg_abol_dt·ptp_item_yn·
                      |etp_chas_erng_rt_dbnb| ≤ 1  (04 §2 M2 추가 항목 4)
    1~3단계(생존·비용·품질): 지표 입력이 미상인 항목은 통과가 아니라 '보류'(02 §2.3 5단계 방향)
    반환: 통과 종목 집합 + 보류 사유 목록(결과 파일에 그대로 실린다)"""
```

- 입력은 `master_pit` Parquet(as-of 조회 뷰 `v_master_asof` — [03](03-data-and-persistence.md) §6)과 `ohlcv_daily` 롤링 지표다.
- **AUM·TER·60일 평균 스프레드·추적오차의 소스가 아직 미확정**이다(06 §7.3 표의 [확인 필요] 행). 확정 전에는 해당 필터를 **보류 처리**하고 결과 파일에 `filters_deferred: [aum, ter, spread_60d, tracking_error_1y]`를 남긴다 — 통과로 처리하면 백테스트가 실제보다 넓은 유니버스에서 돌게 되고, 그 위에서 확정된 C3 기준값은 나중에 필터가 붙는 순간 전부 무효가 된다.
- 플래그 인코딩(`Y/N` vs `0/1`)은 SP-A2 종속이다(03 설계서 §5.2). 파서는 두 인코딩을 모두 수용하고 **미지 값은 hard 통과로 해석하지 않는다**(fail-safe 방향).

### 6.4 검증 항목 (§6)

- `BarView`가 [07](07-portfolio-engine.md) §3.2 `PriceView` Protocol을 **어댑터 없이** 만족(mypy 구조적 적합 어서션 + `close`/`history`/`fx_planning` 호출 스모크). 07 §17(백테스트와의 공유 규율 — "가격 접근: `PriceView` ↔ `BarView(as_of)` Protocol 공유", "두 sim_mode가 같은 엔진 코드로 동작")이 이 적합성에 의존한다.
- `at(d)`가 노출하는 배열 길이가 `d` 이하 세션 수와 정확히 일치(전 구간 property).
- 뷰 밖 인덱스 접근이 물리적으로 불가능(쓰기 금지 플래그·슬라이스 상한 테스트).
- 의도적 lookahead 코드(예: `history(..., -1)` 시도)가 예외로 실패.
- `reevaluate_asof`가 미래 스냅샷을 절대 참조하지 않음([03](03-data-and-persistence.md) §5.4의 `master_pit` property 테스트와 짝).
- `current`의 미국 자산 규약: KRX t일 판정이 미국 t−1 종가를 본다(캘린더 골든 케이스).

---

## 7. 시뮬 모드 — `clean` / `with_guards`

### 7.1 정의 (정본: 02 §8.1.1)

| 모드 | 내용 | 용도 |
|---|---|---|
| `clean`(기본) | 런타임 가드·SV 동결·SAFE_MODE **없음**. 단 **PIT 데이터 규율은 적용**(유니버스·hard 필터·상태 플래그를 as-of 재평가) | TE 분해 ③④의 **기준선**. 03 §4.6·07 R1의 입력 |
| `with_guards` | 위에 더해 PIT 감시 스냅샷에서 그 시점 SV 등급을 재생하고 SAFE_MODE 상태기계를 함께 돌린다 | 03 §4.4의 **가드 A/B 게이트**(`clean` vs `with_guards`) |

**"PIT 상태 플래그를 쓰는가"(→ 언제나 쓴다)와 "런타임 가드를 재생하는가"(→ 모드에 따라 다르다)는 다른 질문이다**(정본: 02 §8.1.1).

### 7.2 `with_guards` 재생 범위

```python
class ModeAdapter(Protocol):
    surveillance: SurveillanceGateLike          # gate 6종 API (정본: 11 문서, 계획 06 §7.2)
    def step_state(self, t, view, ctx) -> SimState: ...
    def apply_interventions(self, drafts, ctx) -> list[OrderDraft]: ...   # 축소 방향 전용
```

| 재생 대상 | `with_guards` 처리 | 근거·한계 |
|---|---|---|
| SV 등급(SV0~SV3)·`unknown` | `master_pit` as-of 플래그 → **라이브와 같은 매핑 함수**(`surveillance.yaml` risk_type → 등급)로 재생. `partition_by_tradability`·`blocked_for_buy`가 계획 축소를 만든다 | 정본: 02 §8.1.1, 06 §7.2. 매핑 함수 소유는 [11](11-realtime-and-surveillance.md) |
| SAFE_MODE 상태기계 | P1(MDD −15%)·P1b(−25%)·P13(동결 자산 비중) 등 **일간 데이터로 판정 가능한 브레이커**만 재생. 밴드 2배·순매수 상한(일 3%/월 10%)·목표 동결·`safemode_filter` 적용 | 정본: 03 §2.2·§2.4, 02 §4.6. 판정 함수 소유는 [09](09-safety-protections.md) |
| 일중 가드(PriceGuard·PremiumGate·KimchiGuard·CryptoDropGuard) | **재생하지 않는다.** 일 단위 종가 데이터에 호가·iNAV·김프가 존재하지 않는다 | 결과 파일 `assumptions.guards_not_replayed`에 열거 |
| MoveGuard | **일간 프록시**만 제공([DD-15-7]) | 03 §4.4의 "REST 60초 샘플 기준 캘리브레이션"은 별도 하네스(§18 미해결 3) |
| E7(상폐 D−10 사전 이전) | 재생하지 않는다. 상폐는 §5.6의 `auto_close` 강제 청산으로 처리된다 | base rate 연 0~1회 — 02 §8.1 "과잉 구현 방지" |
| 승인·grace·거부권 | 재생하지 않는다(사람 입력) | [DD-15-9] |

> **[DD-15-7] MoveGuard 일간 프록시와 그 한계 표기**
> - 결정: `with_guards`에서 MoveGuard는 "당일 NAV 가중 수익률의 절대값이 `guard.move_guard.nav_weighted_move_pct`(기본 3.0%)를 넘고 해당 종목 수가 `min_symbols`(기본 2) 이상이면 당일 시장 단위 `ABORT`"라는 **일간 프록시**로 재생하고, 결과 파일에 `move_guard_proxy: daily_close`를 명시한다. 이 프록시는 **캘리브레이션 근거로 쓸 수 없고** 가드 A/B 게이트의 민감도 참고로만 쓴다.
> - 근거: 03 §4.4는 MoveGuard 캘리브레이션을 "REST 60초 샘플 기준"으로 하라고 못 박았다. 일 단위 시뮬은 그 정의를 만족할 수 없다. 프록시 없이 MoveGuard를 통째로 빼면 2020-03·2024-08 구간의 A/B 비교에서 가장 큰 개입이 사라져 게이트가 무력해지고, 프록시를 캘리브레이션에 쓰면 틱-REST 정의 혼동을 계획이 금지한 방식으로 재현하게 된다. 둘 다 피하는 유일한 방법이 "제공하되 용도를 봉인"이다.
> - 계획 문서와의 관계: 03 §4.4·06 §1.2와 충돌하지 않음(캘리브레이션 경로를 침범하지 않는다). 프록시 자체는 계획에 없는 신설이므로 DD.

### 7.3 미집행 주문 기록 (필수 요건 — 정본: 02 §8.1.1, 03 §4.6, 00 §5 원칙 4)

```python
class UnexecutedOrder(BaseModel, frozen=True):     # 02 §8.1.1 필드 4개를 그대로 사상
    would_be_order: OrderDraft        # 판정이 없었다면 냈을 주문(종목·방향·수량·지정가)
    blocked_by: BlockedBy             # ★ 값 집합의 정본은 03 §7.2 `BlockedBy`(8값) —
                                      #   이 문서는 재열거하지 않고 import해 쓴다
    reference_price: Dec              # 판정 시점 기준가 — 사후 기회손익의 입력
    decided_at: datetime              # SimClock 시각
```

- `with_guards`에서 축소된 모든 레그는 이 레코드를 만든다. **선택이 아니라 필수 요건**이며, 없으면 TE 분해 ①③④를 계산할 수 없고 롤백 엔진이 노이즈에 반응한다(정본: 02 §8.1.1).
- **`blocked_by`의 값 집합은 [03](03-data-and-persistence.md) §7.2 `BlockedBy`가 정본**이다 — 계획 02 §8.1.1의 6값(`DEFER`·`SHRINK`·`ABORT`·`SV2`·`SV3`·`SAFE_MODE_CAP`) + 세금 축 2값(`TAX_SOFT_STOP`·`TAX_ISA_LIMIT`, 요청 출처 10 §17-16) = **8값**이며 03 [DD-03-34]가 확정했다. 이 문서는 `Literal`을 자체 열거하지 않는다(두 벌이 되는 순간 어긋난다).
- 시뮬도 **라이브와 같은 감사로그 스키마**로 기록한다 — `event_type="guard_verdict"`, payload는 `GuardVerdictPayload`(+`CounterfactualOrder`), 봉투의 `actor="labs"`, `correlation.run_id = <백테스트 run_id>` (스키마 정본: [03](03-data-and-persistence.md) §7.2, 계획 01 §6.3 "백테스트도 동일 스키마로 기록해 라이브와 비교 가능"). `blocked_by`는 `GuardVerdictPayload`의 **필수 필드**이고 `verdict`는 가드 판정 유래일 때만 값을 갖는 nullable이므로(03 [DD-03-34]), 감시 등급·SAFE_MODE·세금 유래 미집행은 `verdict=None` + `blocked_by=<해당 값>`으로 기록된다. **사유 축은 `blocked_by` 하나이며 `guard` 필드에 사유를 겹쳐 싣지 않는다.**
- 시뮬 감사로그의 출력 경로는 `var/logs/audit/backtest/<run_id>.jsonl`이다 — 라이브 월 파일(`var/logs/audit/{yyyy-mm}.jsonl`)을 오염시키지 않는다([DD-15-13]). 이 경로는 파일 레이아웃 소유 문서인 03 §7.3 표에 **등재 완료**다([DD-03-35], §18-19 해소).

### 7.4 TE 5항목 분해 계산기 (`tracking.py`)

03 §4.6이 정의한 5항목 분해의 **계산기**를 이 패키지가 소유한다. 입력의 절반이 "동일 기간 백테스트 시뮬 수익률"이기 때문이다.

```python
class TeDecomposition(BaseModel, frozen=True):
    period: tuple[date, date]
    total_gap_pp: Dec          # 실계좌 수익률 − 동일 기간 clean 시뮬 수익률
    cost_pp: Dec               # ① 수수료·세금·스프레드 + 세금 제약 보류 레그의 잔여 드리프트
    timing_pp: Dec             # ② 체결 시점 괴리 (국내 장중 vs 시뮬 종가 — 설계된 불일치)
    guard_pp: Dec              # ③ DEFER/SHRINK/ABORT/SV2/SV3 미집행분의 기회손익
    safemode_pp: Dec           # ④ 밴드 2배·순매수 상한 미집행분
    residual_pp: Dec           # ⑤ 잔차 — 임계(월 0.3%p)는 여기에만 적용

def decompose(live: LiveReturnSeries, audit: AuditReader, spec: BacktestSpec) -> TeDecomposition:
    """1. clean 모드로 같은 기간·같은 시작 포지션 재생 → 기준선 수익률
       2. 감사로그의 guard_verdict(counterfactual)에서 ①③④의 기회손익 산출.
          귀속 사상의 정본은 03 [DD-03-34] — blocked_by 8값을 아래 표로 전수 분류한다.
       3. 체결 건별 implementation shortfall 합계 → ②
       4. 비용 원장(수수료·세금·스프레드) + 2단계에서 분류된 세금 유래 미집행분
          (blocked_by ∈ {TAX_SOFT_STOP, TAX_ISA_LIMIT}) + sell_blocked 잔여 드리프트 → ①
       5. ⑤ = total − (①+②+③+④)"""
```

**`blocked_by` → TE 항목 귀속 (정본: [03](03-data-and-persistence.md) §7.2 [DD-03-34]. 03 §7.5와 같은 표를 쓴다)**

| `blocked_by` | TE 항목 | 근거 |
|---|---|---|
| `DEFER` · `SHRINK` · `ABORT` | **③** 가드 미집행 | 02 §8.1.1 가드 판정 |
| `SV2` · `SV3` | **③** 감시 등급 미집행 | 02 §8.1.1 |
| `SAFE_MODE_CAP` | **④** 밴드 2배·순매수 상한 | 02 §4.6, 03 §2.4 |
| `TAX_SOFT_STOP` · `TAX_ISA_LIMIT` | **①** 비용 | 03 §4.6 ① 행, 요청 출처 10 §17-16 |

- **세금 사유는 ①에 계상한다** — ③의 정의를 세금까지 넓히면 R1의 입력 정의가 흔들린다(정본: 03 §4.6 ① 행, 조율 요청: 10 §17-16 "두 축을 섞으면 롤백 트리거 R1이 오탐한다"). 두 축이 같은 `event_type`·같은 필드에 모이되 **귀속만 갈린다**는 것이 [DD-03-34]의 요점이며, 소비자인 이 계산기가 그 사상을 하드코딩하지 않고 위 표 1곳에서만 정의한다.
- **자산군 갭 미해소분도 ①에 계상**한다(정본: 02 §4.3 기타 규칙).
- 소비자: 주간 점검 화면·월간 리포트([12](12-scheduling-and-operations.md)·[13-web-and-telegram.md](13-web-and-telegram.md)), 롤백 트리거 R1([14](14-research-and-labs.md), 정본: 07 §10). **임계 판정·알림·롤백은 이 모듈이 하지 않는다** — 계산과 판정을 분리한다.

> **[DD-15-14] TE 5항목 분해 계산기를 `backtest/tracking.py`에 배치**
> - 결정: 계산기는 15가 소유하고, 잡 등록·알림은 12, 롤백 판정은 14가 소비한다.
> - 근거: 분해의 기준선이 "동일 기간 백테스트 시뮬 수익률"(03 §4.6)이라 시뮬레이터 재생 능력이 필수 입력이다. 12나 14에 두면 그 문서가 백테스트 커널을 import해야 하고, 그러면 `labs`·`scheduler`가 시뮬 내부 구조에 결합된다.
> - 계획 문서와의 관계: 03 §4.6은 분해 **정의**의 정본이고 구현 위치를 정하지 않았다. 여백 채움, 충돌 없음.

### 7.5 검증 항목 (§7)

- 같은 사양·`clean`에서 가드 관련 미집행 레코드가 **0건**(모드 격리 어서션).
- `with_guards`의 산출 계획은 언제나 `clean`의 **부분집합**(단조 축소성 — 00 §5 원칙 9의 시뮬 측 대응물, 03 §4.1 property와 동일 문장).
- `blocked_by` **8값** → TE ①③④ 분류의 전수 매핑 테스트 — 03 §7.5의 같은 이름 검증 항목과 **동일 표**를 참조해야 한다(두 문서가 다른 표를 쓰면 R1 입력이 갈린다).
- `GuardVerdictPayload` 직렬화 왕복: 시뮬이 쓴 라인을 라이브 리더가 파싱하고 `blocked_by`가 보존됨(01 §6.3 "라이브와 비교 가능").
- 합성 데이터로 ①~⑤를 인위 주입해 `residual_pp ≈ 0`이 나오는지(분해 정확성 회귀).

---

## 8. Walk-Forward · CPCV 러너 (`walkforward.py`)

### 8.1 분할 생성

```python
class WalkForwardSplit(BaseModel, frozen=True):
    train: tuple[date, date]      # 5년
    test:  tuple[date, date]      # 1년

def walk_forward_splits(start: date, end: date, calendar: TradingCalendar,
                        train_years: int = 5, test_years: int = 1) -> list[WalkForwardSplit]:
    """게이트 C1: 학습 5년 / 검증 1년 롤링 (정본: 02 §8.2, 02 부록 A backtest.gates.core).
    분할 인덱스 생성은 skfolio의 WalkForward를 쓰되(정본: 01 §1.5·05 §4.7),
    시뮬 실행은 우리 커널이 한다 — skfolio는 '언제부터 언제까지'만 알려준다."""

def cpcv_splits(start: date, end: date, *, purge_days: int = 21,
                embargo_days: int = 5, n_groups: int = 6) -> list[CpcvSplit]:
    """게이트 S1(위성 전용): CPCV purge 21일 / embargo 5일 (정본: 02 §8.2).
    ★ n_groups는 계획이 규정하지 않은 값이다 — 경로 수(=조합 수)와 실행 시간의 트레이드오프이며
      사양에 노출해 M7 위성 게이트 착수 시 실측으로 정한다(§18-17). 기본 6은 잠정값이다."""
```

**학습 구간의 의미** — 우리 코어 전략에는 피팅되는 파라미터가 없다(표본평균 기대수익은 코드 경로 자체가 없다 — 02 §3.1-5). 따라서 `train`은 **룩백 워밍업 구간**(756영업일 공분산·BL 입력)이고 `test`는 그 이후 out-of-sample 운용 구간이다. 이 구분을 명시하지 않으면 "학습 5년"이 파라미터 탐색으로 오해되어 우리가 하지 않기로 한 hyperopt(00 §4 "채택하지 않은 것")를 되살리는 문이 된다.

### 8.2 게이트 C1 판정

```
전 test 구간에서 모두 참이어야 통과:
  (a) 변동성 조건 : |ex_ante_vol_dev| ≤ 25%
                    ex_ante_vol_dev = √(wᵀΣ_strategic w) / σ_target(level) − 1   (02 §3.2 표)
  (b) MDD 조건    : MDD(전략) ≤ MDD(정적 벤치마크) + 5%p                          (02 §8.2)
진단 병기(판정에는 쓰지 않음):
  realized_vol_dev = 사후 실현변동성 / σ_target − 1     (±30%는 알림 전용 — 02 §3.2)
```

- 02 §3.2의 지표 분리표가 `ex_ante_vol_dev` ±25%를 **게이트 C1**에, `realized_vol_dev` ±30%를 **알림 전용**에 배정했으므로 판정은 사전 변동성으로 한다. 02 §8.2 본문의 "사후 변동성이 목표 ±25%"라는 문언과 표기 차이가 있어 **두 값을 모두 산출·기록**하고, 문언 차이는 §18 미해결 1로 등재한다.
- 벤치마크 사양은 `backtest.benchmark.*`로 둔다: 구성(기본 60/40 — 02 §8.2 "동일 리스크 정적 벤치마크(60/40 등)"), 리밸런싱 주기(기본 연 1회), **동일 비용 모델 적용**(비용 없는 벤치마크와 비교하면 우리 쪽만 비용을 내는 비대칭 비교가 된다), 세전 트랙 기준 비교. 04 §2 M2 게이트 미통과 시 허용 조치 (c)("벤치마크를 60/40에서 계좌 유형별 정적 배분으로 교체")는 이 config의 값 변경으로 수행되며 **시뮬의 계좌 분리가 아니다**.

### 8.3 의사코드

```python
def run_walk_forward(spec: BacktestSpec, ctx: RunnerContext) -> WalkForwardResult:
    splits = walk_forward_splits(spec.start, spec.end, ctx.calendar)
    per_split = []
    for s in splits:
        sim = run_simulation(spec.model_copy(update={"start": s.train[0], "end": s.test[1]}), ctx)
        seg = sim.slice(s.test)                       # test 구간만 평가 (워밍업 제외)
        bmk = run_benchmark(spec.benchmark, s.test, ctx)
        per_split.append(SplitMetrics(
            ex_ante_vol_dev=seg.ex_ante_vol_dev, realized_vol_dev=seg.realized_vol_dev,
            mdd=seg.mdd, mdd_benchmark=bmk.mdd, sharpe=seg.sharpe_after_tax))
    return WalkForwardResult(splits=per_split,
                             passed=all(abs(m.ex_ante_vol_dev) <= Dec("0.25")
                                        and m.mdd <= m.mdd_benchmark + Dec("0.05")
                                        for m in per_split))
```

- **in-sample 대비 붕괴 없음**(04 §2 M2 DoD)은 `test` 구간 Sharpe가 전체 구간 Sharpe 대비 급락하지 않는지를 진단 지표로 기록해 사람이 판정한다 — 자동 임계를 만들지 않는다(임계 근거가 계획에 없고, 성과 기반 자동 판정 불가 논거가 05 §10.5에 있다).

### 8.4 검증 항목 (§8)

- 분할 경계에서 워밍업 데이터가 test 구간 판정에 새어 들어가지 않음(경계 property).
- CPCV purge/embargo 일수가 실제 인덱스에서 제거됨(전수 검사).
- 벤치마크가 전략과 **동일 비용 모델·동일 캘린더**로 계산됨.

---

## 9. Lookahead 자동탐지 (`lookahead.py`, 게이트 C2)

### 9.1 알고리즘 (정본: 02 §8.3 — freqtrade lookahead-analysis 이식)

```python
def detect_lookahead(spec: BacktestSpec, ctx: RunnerContext,
                     samples: int = 10) -> LookaheadReport:
    """1. spec.seed로 결정된 난수로 시점 T를 samples개(기본 10 — 02 §8.3) 뽑는다.
          표본은 '목표비중이 실제로 계산되는 날'(월 첫 거래일)에서만 뽑는다 —
          그 외의 날에는 비교 대상 산출물이 없다.
       2. 각 T에 대해:
          full  = compute_targets_sim(BarViewFactory(전체 데이터).at(T), ...)   # §3.3 어댑터
          trunc = compute_targets_sim(BarViewFactory(T까지만 적재).at(T), ...)
             ★ trunc는 뷰 절단이 아니라 '적재 단계 절단'이다 — 적재 경로의 as-of 필터까지
               함께 검사하려면 팩토리 자체를 다시 만들어야 한다.
       3. max_i |full_i − trunc_i| > backtest.lookahead.weight_tolerance 이면 위반 1건.
       4. 위반 0건이 아니면 C2 실패. 위반 항목의 (T, 종목, 차이, 입력 해시)를 리포트."""
```

**2차 방어선의 위치** — 뷰 절단(§6)이 1차 방어선이고 이 탐지는 2차다. 2차가 잡는 것은 **데이터 적재 단계에서 뚫리는 경우**다: 수정주가 소급 반영(과거 바가 오늘 다시 쓰인 값), 지연 상장 종목의 소급 편입, 마스터 스냅샷의 사후 갱신(정본: 02 §8.3, 03 설계서 §5.3-3 "`master_pit` 스냅샷은 생성 후 수정하지 않는다").

### 9.2 결정론과 허용오차

> **[DD-15-8] lookahead 비교 허용오차와 솔버 결정론 규약**
> - 결정: ① 비교는 `backtest.lookahead.weight_tolerance`(기본 `1e-9`) 절대차 기준으로 하고, 이를 넘는 차이만 위반으로 센다. ② 최적화 솔버는 시뮬 경로에서 결정론 옵션(고정 시드·고정 반복 한도·경고를 오류로)을 강제하며, 같은 입력에서 두 번 호출한 결과가 tolerance를 넘게 다르면 **lookahead 판정 이전에 `NonDeterministicSolver`로 실행을 실패**시킨다.
> - 근거: 02 §8.3은 "불일치 = 미래 참조"라고만 하고 수치 비교 규약을 정하지 않았다. CVXPY/skfolio 해는 비트 단위 재현이 보장되지 않으므로 tolerance 없이는 게이트가 상시 실패하고, tolerance만 두고 결정론을 강제하지 않으면 진짜 lookahead가 수치 잡음으로 위장된다. **결정론 실패를 별도 오류로 분리**하는 것이 두 실패 모드를 섞지 않는 유일한 방법이며, 이는 게이트 C3(스냅샷 회귀)의 전제이기도 하다.
> - 계획 문서와의 관계: C2의 "0건" 기준은 유지된다(허용오차는 '같음'의 정의이지 위반 허용치가 아니다). 04 §2 M2 주의점 ③("C2·C3는 완화 대상이 아니다")과 충돌 없음.

### 9.3 실패 리포트와 오류 경로

```python
class LookaheadViolation(BaseModel, frozen=True):
    as_of: date; instrument_key: str
    weight_full: Dec; weight_truncated: Dec; abs_diff: Dec
    suspect_inputs: list[str]      # 두 실행의 inputs_hash 차이가 난 데이터셋 이름
```

`suspect_inputs`는 `TargetWeights.inputs_hash`(01 §3.1 규약, [02](02-domain-model.md) §7.4)를 데이터셋 단위로 분해해 채운다 — 어느 입력이 달라졌는지를 지목하지 못하는 위반 리포트는 디버깅에 쓸모가 없다.

### 9.4 검증 항목 (§9)

- **양성 대조군(필수)**: 의도적으로 미래를 보는 전략 변형(예: 다음 달 수익률로 정렬)을 주입하면 탐지가 **반드시 실패로 잡는다**. 탐지기가 아무것도 못 잡는 상태로 green을 유지하는 것이 이 게이트의 가장 위험한 실패 모드다.
- 음성 대조군: 정상 전략에서 위반 0건 + 결정론 재실행 2회 동일.
- 적재 단계 as-of 필터 회귀: 수정주가 소급 시나리오 주입 → 탐지.

---

## 10. 검증 게이트 (`gates/`)

### 10.1 레지스트리와 결과 타입

```python
class GateId(StrEnum):
    C1 = "C1"; C2 = "C2"; C3 = "C3"                  # 코어 (02 §8.2)
    S1 = "S1"; S2 = "S2"; S3 = "S3"; S4 = "S4"       # 위성 전용
    GUARD_AB = "guard_ab"                            # 03 §4.4 가드 A/B

class GateResult(BaseModel, frozen=True):
    gate: GateId
    passed: bool
    metrics: Mapping[str, str]        # Decimal 문자열 — 결과 파일에 그대로 실린다
    detail: str                       # 실패 사유(사람이 읽는 한 문단)
    waivable: bool                    # C2·C3는 False (04 §2 M2 주의점 ③)

class Gate(ABC):
    id: GateId
    @abstractmethod
    def evaluate(self, run: SimulationResult, ctx: RunnerContext) -> GateResult: ...

class GateRegistry:
    def core(self) -> list[Gate]: ...        # C1·C2·C3 — config backtest.gates.core
    def satellite(self) -> list[Gate]: ...   # S1~S4 — config backtest.gates.satellite
    def for_challenger(self) -> list[Gate]: ...  # G2 = S1~S3 (07 §7.3)
```

**게이트 코드는 CI와 런타임이 재사용한다** — 03 §8 리스크 등록부("게이트는 CI 게이트 코드를 런타임 재사용, 새 코드 최소화")의 직접 구현이며, 그래서 `Gate`는 프로세스 종류를 모른다.

### 10.2 코어 게이트 C1·C2 (정본: 02 §8.2)

| 게이트 | 판정 | 구현 |
|---|---|---|
| **C1** Walk-Forward | 학습 5년/검증 1년 롤링, 전 구간 `\|ex_ante_vol_dev\| ≤ 25%` **AND** `MDD ≤ 벤치마크 MDD + 5%p` | §8.2 |
| **C2** Lookahead | 자동탐지 위반 **0건** | §9 |

### 10.3 게이트 C3 — 스냅샷 회귀 (`snapshot.py`)

정본: 02 §8.2 C3, 03 §4.4. **"몰래 바뀐 백테스트"를 잡는 장치**다.

**기준 파일의 포맷·갱신 프로토콜 정본은 [16-testing-and-quality.md](16-testing-and-quality.md) §9.2**다(브리프 §2.1 — 16이 CI 배치·파일 포맷을 소유). 이 절은 **판정 측**이 그 파일에서 무엇을 읽고 어떻게 비교하는가만 정한다. 아래는 판정에 쓰이는 필드의 요약 인용이다(정의 정본: 16 §9.2).

```
기준 파일: tests/snapshots/backtest/<baseline_id>.json   (리포지토리 내 — 07 §13 "기록은 스냅샷 파일이 담당")
{ "baseline_id": "core-2015-2024",
  "spec_hash":   "<sha256>",                      # 사양이 바뀌면 비교 자체가 성립하지 않는다
  "inputs": { … "data_snapshot_id": "…" },        # = data_fingerprint 역할 (16 §9.2 필드명 정본)
  "metrics": { "cagr": "...", "sharpe": "...", "mdd": "...",
               "turnover_yr": "...", "trade_count": ... },        # 03 §4.4 지정 5종
                                                  # 이름은 16 §9.2 표기. `turnover_yr`는
                                                  # PerformanceMetrics.turnover_annual(§12.2)에 대응
  "tolerance": { … },  "absolute_floor": { "sharpe_min": null, "mdd_max": null },
  "history": [ … ],                               # 갱신 사유 이력 — 프로토콜은 16 §9.2
  "generated_at": "...", "code_version": "<git sha>" }
```

판정 절차:

1. `spec_hash` 불일치 → **실패**(“기준과 다른 사양을 비교하려 함”). 의도한 사양 변경이면 새 baseline을 만들고 사유를 커밋 메시지에 남긴다.
2. `inputs.data_snapshot_id`(= 이 문서가 산출하는 `data_fingerprint`) 불일치 → **실패 + 별도 사유 코드**. 데이터가 바뀐 것과 코드가 바뀐 것을 섞지 않는다.
3. 지표 5종 각각 `|new − base| ≤ tolerance[metric]` → 초과 시 실패. **지표별 허용오차는 기준 파일의 `tolerance` 맵이 우선**하고(정본: 16 §9.2 — `trade_count`는 0), 맵에 없는 지표에만 `backtest.snapshot.tolerance_pct`를 상대오차 기본값으로 적용한다.
4. **절대 기준**: `sharpe < absolute_floor.sharpe_min` 또는 `mdd > absolute_floor.mdd_max`이면 **스냅샷 갱신 자체를 거부**한다(정본: 03 §4.4). 즉 사람이 "의도한 변경"이라고 선언해도 갱신되지 않는다. **`null` = 명시적 비활성**이며 이때는 C1 판정식(§8.2)이 실질 하한 역할을 한다(16 §9.2). **키 자체의 부재는 비활성이 아니라 실패**다 — 누락과 "임계 없음"을 구분한다([DD-15-10]). 값 확정 경로는 [DD-15-17].
5. **CI 트리거에 `config/*.yaml` 변경을 포함한다**(정본: 02 §8.2 ★, 03 §4.4, 04 §2 M2 추가 항목 3). 잡 산출물(`var/policy/targets.yaml`·`universe.yaml`)은 대상이 아니다 — 입력물·산출물 분리(01 §6.1). 워크플로 정의는 [16](16-testing-and-quality.md) 소유.
6. C3 실행은 `run_kind = CI_SNAPSHOT`이며 **실험 원장에 적재되지 않는다**(§11.4, 정본: 07 §13).

> **[DD-15-10] 스냅샷 회귀의 판정 계약과 절대 기준의 값 미정 처리**
> - 결정: **파일 포맷·갱신 프로토콜은 16 §9.2가 정본**이고 이 문서는 판정 절차 1~4단계(5·6은 트리거·원장 규율)를 소유한다. `absolute_floor.sharpe_min`·`absolute_floor.mdd_max`와 `backtest.snapshot.tolerance_pct`는 **키 존재가 필수**이되 **값은 이 문서가 정하지 않는다** — M2에서 기준 전략 10년 실측치를 얻은 뒤 확정한다([DD-15-17]). 키 부재는 실패, `null`은 **명시적 비활성**으로 구분한다(16 §9.2의 초기값 `null` 규약과 정합).
> - 근거: 03 §4.4는 "절대 기준(Sharpe < 임계, MDD > 임계)"만 규정하고 수치를 주지 않았다. 계획에 없는 수치를 지금 창작하면 그 값이 곧 게이트의 정본이 되어 버린다. 반면 키를 만들지 않으면 M2에서 구조를 새로 짜야 한다. "부재=실패 / `null`=비활성"의 2분법은 16이 파일 초기값을 `null`로 두면서도 "누락을 조용히 통과시키지 않는다"는 이 문서의 요건을 동시에 만족시키는 유일한 해석이다.
> - 계획 문서와의 관계: 여백을 "구조는 확정, 값은 실측"으로 채움. 04 §2 M2 DoD(실측 항목)와 정합. 포맷 소유를 16으로 명시한 것은 16 §미해결 3의 조율 회신이다.

> **[DD-15-17] `absolute_floor` 값의 M2 실측 확정 경로 (요청 출처: 16 §미해결 3)**
> - 결정: 절대 기준의 확정은 아래 4단계로만 이뤄지며, 그 밖의 경로로 값이 채워지는 것을 금지한다.
>   1. **산출**: M2에서 기준 사양(`baseline_id = core-2015-2024`, `sim_mode: clean`, 세후 트랙)을 `omra backtest run`으로 10년 1회 실행하고, 결과 파일 `metrics.aftertax`의 `sharpe`·`mdd`와 §8.2 C1 Walk-Forward의 **분할별 최솟값**(`min(sharpe)`·`max(|mdd|)`)을 함께 얻는다.
>   2. **후보값**: `sharpe_min = floor2(min_split_sharpe × 0.7)`, `mdd_max = ceil2(max_split_mdd × 1.3)` 를 **제안값으로만** 산출해 결과 파일 최상위 `floor_candidates`(§14.3)에 싣는다. 계수 0.7·1.3은 계획 근거가 없는 이 문서의 제안 여유이며 **판정에 쓰이지 않는다**(§18-5).
>   3. **확정**: 사람이 값을 기준 파일에 기입하고 `gate-floor-change` 라벨로 승인한다(프로토콜 정본: 16 §9.2 갱신 프로토콜 2). 러너·CI는 **값을 자동으로 쓰지 않는다**.
>   4. **확정 전**: `null`(비활성) 유지 + C3 실행 시 `detail`에 "absolute_floor 미확정 — C1 판정식이 실질 하한"을 매번 첨부한다(조용한 통과 금지).
> - 근거: 16 §미해결 3이 "M2 DoD 기준 전략 실측 후 확정"만 정하고 **누가 무엇을 산출해 어디에 넣는가**를 15에 남겼다. 백테스트 러너만이 실측치를 만들 수 있으므로 산출은 15, 기입·승인은 16의 갱신 프로토콜이라는 분담이 소유권 경계와 일치한다. 제안값을 결과 파일에 싣되 자동 기입을 금지한 것은 §12.2·[DD-15-9]와 같은 원칙(파라미터 확정은 사람의 행위)의 반복이다.
> - 계획 문서와의 관계: 03 §4.4(절대 기준의 존재)·04 §2 M2(실측 항목)를 절차로 구체화. 수치를 창작하지 않으므로 충돌 없음.

### 10.4 위성 게이트 S1~S4 (자유도가 있는 전략에만)

| 게이트 | 판정 (정본: 02 §8.2) | 구현 메모 |
|---|---|---|
| **S1** CPCV | purge 21일 / embargo 5일, **경로별 Sharpe 5백분위 > 0** | §8.1 `cpcv_splits`. 경로 = 조합별 test 병합 시계열 |
| **S2** 파라미터 이웃 안정성 | 핵심 파라미터 **±25% 섭동**에서 Sharpe 저하 **<20%**, **부호 반전 없음** | 섭동 격자는 사양의 `param_overrides` 축을 그대로 사용(§3.1 `run_kind`별 허용 범위 표). EX-4(크립토 `crypto.vol_target` 40% ±25%)가 이 게이트의 첫 소비자 |
| **S3** DSR | **DSR > 0.95**, `N`은 실험 로그에서 자동 집계 | §11 |
| **S4** 부트스트랩 | 코어 단독 대비 **세후 위험조정수익 개선**을 부트스트랩 신뢰구간으로 확인 + **듀얼모멘텀 DD 축소 규칙 on/off A/B** 동시 산출 | `stats/bootstrap.py`의 stationary block bootstrap 재사용(블록 평균은 §13과 공유) |

- **EX-4 추가 판정 지표**: 크립토 vol targeting은 `unmanaged`(스케일링 없음) 대비 **세후 Sharpe**를 함께 산출한다 — Cederburg의 결과가 이 규칙에 부정적이므로 최소한 열위가 아님을 우리 데이터로 확인한다(정본: 02 §8.2 EX-4, 05 §10.4).
- `for_challenger()`는 S1~S3를 반환한다 — 챌린저는 파라미터 자유도를 도입하는 행위이므로 자유도 있는 전략과 같은 무거운 게이트를 적용한다(정본: 07 §7.3).

### 10.5 가드 A/B 게이트 (`gates/guard_ab.py`) — 정본: 03 §4.4

```python
class GuardAbGate(Gate):
    """동일 기간·동일 데이터에서 sim_mode: clean vs with_guards를 비교해
    세후 위험조정수익이 열위면 병합 거부 (03 §4.4).
    필수 포함 구간(하드코딩 아닌 config 기본값): 2020-02~04 / 2022 전년 / 2024-08."""
    REQUIRED_WINDOWS: Final = ("2020-02-01/2020-04-30", "2022-01-01/2022-12-31",
                               "2024-08-01/2024-08-31")
```

- 판정: 필수 3구간 각각에서 `with_guards`의 세후 Sharpe가 `clean` 대비 열위이면 실패. **어느 구간에서 실패했는지**를 `detail`에 남긴다 — 03 §1.5의 정직성 표기("P1을 SAFE_MODE로 바꾼 것의 순이득은 논증이지 실증이 아니다")를 사전 점검하는 것이 이 게이트의 목적이므로, 통과/실패보다 구간별 수치가 산출물이다.
- 필수 구간이 `spec.start~end` 밖이면 게이트는 통과가 아니라 **`skipped` + CI 경고**다(조용한 통과 금지).
- §7.2의 재생 한계(일중 가드 미재생·MoveGuard 프록시)를 `detail`에 매번 첨부한다.

### 10.6 챌린저 게이트 `G2` — 조건부 양경로 (정본: 02 §8.1.2, 07 §7.3, 01 §1.6)

| 분기 | 조건 | 설계 |
|---|---|---|
| **A. 유지** | M2 실측 10년 1회 실행 ≤ 30분 | 월 1회 `omra backtest challenger --spec <path>` 실행. `for_challenger()`(S1~S3) 적용. 결과 파일 → `omra experiment ingest` |
| **B. 축소** | 30분 초과 | 구간을 **5년**으로 축소(`backtest.gates.challenger_years: 5`)하고 나머지 동일 |
| **C. 삭제** | 축소로도 예산 초과 | `G2`를 레지스트리에서 제거하고 **CI 스냅샷 회귀(C3)가 그 역할을 대신한다**. `GateRegistry.for_challenger()`가 빈 리스트를 반환하며, `labs.challenger`는 `G1 → G3`로 직행한다 |

세 분기 모두에서 **실행 주체는 `tools` 컨테이너이고 봇은 결과 파일만 읽는다**(하드 규칙 — 01 §1.6). 분기 판정 입력(실행 시간 실측)은 §14.5.

### 10.7 게이트 미통과 절차 (정본: 04 §2 M2)

게이트 러너는 실패 시 **허용된 3개 시도만** 사양으로 받아들인다: (a) `risk.level` 하향 1단계 (b) 승인된 대체 페어 범위 내 유니버스 1:1 교체 (c) 벤치마크 교체. 각 시도는 `spec_hash`와 함께 실험 원장에 기록된다. **3회 시도 후 미통과면 러너는 "재검토 필요"를 반환하고 추가 시도를 거부한다** — 무한 튜닝 루프를 코드가 막는다. `C2`·`C3`는 어떤 경우에도 완화 대상이 아니므로 `waivable=False`다.

### 10.8 검증 항목 (§10)

- 각 게이트의 통과/실패 골든 케이스(합성 결과 주입).
- `waivable=False` 게이트에 대한 우회 시도가 실패.
- 스냅샷 절대 기준 위반 시 **갱신 커맨드 자체가 거부**됨.
- 게이트 미통과 4회차 시도 요청이 거부됨.
- 게이트 코드가 CI·런타임 양쪽에서 동일 모듈임을 아키텍처 테스트로 고정.

---

## 11. DSR · 시도 수 `N` 집계 (`stats/dsr.py`)

### 11.1 Deflated Sharpe Ratio

```python
def deflated_sharpe(observed_sr: float, *, n_obs: int, n_trials: int,
                    skew: float, kurtosis: float, sr_variance_trials: float) -> float:
    """다중검정 보정 Sharpe. 게이트 S3 통과 조건은 DSR > 0.95 (정본: 02 §8.2).
    [확인 필요] 공식의 정확한 형태(기대 최대 SR 항의 근사식·Euler-Mascheroni 상수 사용 여부)는
    Bailey & López de Prado 원논문 대조로 확정한다 — 계획 문서는 임계값(0.95)과 N의 출처만
    규정하고 산식을 주지 않았다. 확정 전에는 이 함수가 NotImplementedError를 던지고
    게이트 S3는 'blocked'로 보고한다(추정 산식으로 게이트를 통과시키지 않는다)."""
```

- **`blocked`는 통과가 아니다.** S3가 blocked인 채로는 위성 전략을 활성화할 수 없다(위성 활성화는 M7 — 04 §M7). 이것이 미확인 산식으로 게이트를 통과시키는 것보다 안전한 방향이다.
- 입력 `n_obs`·`skew`·`kurtosis`는 해당 전략의 수익률 시계열에서, `n_trials`는 §11.2에서 온다.

### 11.2 시도 수 `N`

```python
def n_specs_tried(snapshot_db: Path) -> int:
    """N = COUNT(DISTINCT experiments.spec_hash)  (정본: 07 §13, 03 설계서 §3.5 파생 질의 계약)
    tools 컨테이너는 omra-db를 마운트하지 않으므로 VACUUM INTO 스냅샷 파일에 대한
    SQLAlchemy ro 연결로 읽는다 (정본: 01 §1.6, 03 설계서 §8.2)."""
```

- `N`은 **원장의 파생값이며 사람이 입력하지 않는다**(정본: 02 §8.2, 07 §7.2·§13). 물리적으로도 입력할 수 없다 — `experiments`에 `n_specs_tried_to_date` 컬럼이 없다(03 §3.3.11 [DD-03-14]).
- `G0` 사전등록 여부와 무관하게 센다(정본: 07 §13 — 그것으로 좁히면 M7에서 `N`이 0이 된다).
- 스냅샷이 없거나 `tools.snapshot_max_age_h`(기본 168h — 01 설계서 §7.3)를 넘으면 **실행 거부**한다. `N`을 모르는 채 DSR을 계산하는 경로를 만들지 않는다.

### 11.3 `spec_hash` 정규화

> **[DD-15-11] `spec_hash` 정의**
> - 결정: `spec_hash = sha256(canonical_json(BacktestSpec 중 사양 필드))`. **포함**: 기간·유니버스 버전·리스크 레벨·계좌 모델·`sim_mode`·비용 모델·세금 트랙·`param_overrides`·벤치마크 사양. **제외**: `run_id`·타임스탬프·스냅샷 나이·`run_kind`·`seed`·코드 버전. canonical JSON은 키 정렬 + Decimal의 `format(d, "f")` 표기([02](02-domain-model.md) §5.2 정규형 재사용) + 비ASCII 이스케이프 금지.
> - 근거: 07 §13이 `N`을 "서로 다른 사양 해시의 수"로 정의했으므로 해시의 정규화 규약이 곧 DSR의 정의다. `seed`를 제외하는 이유는 같은 사양의 난수 재실행이 새로운 "시도"가 아니기 때문이고, `run_kind`를 제외하는 이유는 같은 사양을 수동으로 한 번·챌린저로 한 번 돌린 것이 두 시도로 세어지면 게이트가 과도하게 보수화되기 때문이다.
> - 계획 문서와의 관계: 07 §13·03 §3.3.11의 여백 채움. 충돌 없음.

### 11.4 실험 원장 적재 경로 (정본: 01 §1.6, 07 §13)

```
tools:  omra backtest … → var/data/experiments/<run_id>.json      (omra-data 볼륨)
app:    omra experiment ingest <path> → persistence.repos.experiments
        ★ DB 쓰기 주체는 언제나 app 하나다
```

**ingest 입력 규약(이 문서 소유 — 03 §3.3.11 [DD-03-14]가 위임)**:

1. `run_kind == "ci_snapshot"`인 파일은 **거부**한다(종료 코드 2 + 사유). CI 재현 실행을 세면 DSR의 `N`이 부풀어 게이트가 과도하게 보수화된다(정본: 07 §13).
2. `spec_hash`·`experiment_id`·`sample_from/to`·`payload_json`이 필수. 누락 시 거부.
   - **`G0` 사전등록 4컬럼(`hypothesis`·`primary_metric`·`secondary_metrics`·`stop_conditions`)은 `NULL`로 적재한다** — 03 [DD-03-33]이 이 4컬럼의 `NOT NULL`을 해제하고 **sentinel을 두지 않기로** 확정했다(요청 출처: 이 문서 §18-18). 이들은 `G0`(챌린저층, 07 §7.2) 산출물이고 M2의 `manual`·`gate` 실행에는 값이 존재하지 않으므로 **ingest는 값을 창작하지 않는다**(가설 없는 실행에 가설을 지어 넣으면 원장이 거짓말을 한다). `G0` 등록 여부의 판정식은 `hypothesis IS NOT NULL`이다(03 §3.3.11).
   - `run_kind == "challenger"` 결과 파일은 4값이 **전부 있어야** 한다 — `registered_by='challenger_pipeline'` 행에 대한 필수화는 `repos.experiments.register()`가 애플리케이션 계층에서 수행하므로(03 [DD-03-33]), ingest는 누락 시 종료 코드 `2`로 **선차단**해 repo 예외보다 먼저 사유를 남긴다.
3. 같은 `experiment_id` 재적재는 `experiments` UPDATE가 아니라 `experiment_events` 행 추가로 표현된다(append-only — 03 §3.4 트리거가 물리적으로 강제).
4. M2 시점에는 `registered_by='human'` + `event_kind ∈ {run_started, run_finished}`만 사용하고, `G0` 워크플로·나머지 `event_kind`는 챌린저층 착수 시 활성화한다(정본: 07 §13 착수 2단계).

### 11.5 검증 항목 (§11)

- `ci_snapshot` 결과 파일의 ingest 거부(종료 코드·사유 고정).
- `run_kind ∈ {manual, gate}` 결과 파일이 `G0` 4컬럼 `NULL`로 적재 성공 / `run_kind == challenger`인데 4값 누락이면 종료 코드 `2`([03](03-data-and-persistence.md) §3.6의 같은 이름 검증 항목과 짝 — §3.3.11 [DD-03-33]).
- `N` 질의가 스냅샷 ro 연결로만 수행되고 `omra-db` 접근을 시도하지 않음(경로 부재 테스트 — 01 설계서 §7.5와 짝).
- `spec_hash` 안정성: 필드 순서·Decimal 표기·플랫폼이 달라도 동일 해시.
- S3가 `blocked`일 때 위성 활성화 경로가 막힘.

---

## 12. 성과지표 (`stats/`)

### 12.1 QuantStats의 경계

> **[DD-15-12] 게이트 판정 지표는 자체 구현이 정본, QuantStats는 사람용 tear sheet 전용**
> - 결정: ① `stats/metrics.py`의 자체 구현이 게이트·스냅샷·실험 원장에 들어가는 모든 수치의 정본이다. ② QuantStats는 `stats/report.py`에서 HTML tear sheet 생성에만 쓰고 그 산출물은 사람이 읽는 리포트로만 흐른다. ③ 수치 경계: 원장·주문·금액은 `Decimal`, 통계 계산은 float64로 변환하되 **결과는 지표별 고정 자릿수로 라운딩한 Decimal 문자열**로 직렬화한다(라운딩 규약: 비율 지표 소수 6자리 반올림, 금액 원 단위 절사).
> - 근거: 01 §1.5가 QuantStats를 "성과 tear sheet"로 배정했다. 게이트 판정을 외부 라이브러리에 맡기면 라이브러리 업그레이드가 곧 C3(스냅샷 회귀) 실패가 되고, 그때 "몰래 바뀐 백테스트"와 "라이브러리가 바뀐 백테스트"를 구분할 수 없다. 07 §3.2가 QuantStats 릴리스를 `P0` 감시 대상에 넣은 것도 같은 위험의 인식이다.
> - 계획 문서와의 관계: 02 §8.4 "QuantStats + 자체"의 경계를 확정. 충돌 없음.

### 12.2 지표 카탈로그 (정본: 02 §8.4)

```python
class PerformanceMetrics(BaseModel, frozen=True):
    # ── 02 §8.4 기본 목록 ────────────────────────────────────────────
    cagr_pretax: Dec; cagr_aftertax: Dec
    vol_annual: Dec; sharpe: Dec; sortino: Dec
    mdd: Dec; calmar: Dec; monthly_win_rate: Dec
    tax_drag: Dec                       # = cagr_pretax − cagr_aftertax
    turnover_annual: Dec                # 회전율 정의 정본은 03 §1.2(P10·P11·07 R3 공통):
                                        #   turnover(기간) = Σ_i min(Σ매수체결금액_i, Σ매도체결금액_i) / NAV_기말
                                        #   — 편도 기준, 순유입 일방 매수는 계상하지 않는다.
                                        #   백테스트가 다른 산식을 쓰면 R3·P10·P11과 비교 불가가 된다
    total_cost_ratio: Dec               # (수수료+거래세+슬리피지+환전스프레드) / 평균 NAV
    tracking_error_vs_benchmark: Dec; excess_return_vs_benchmark: Dec
    band_triggers_per_year: Dec         # 밴드 트리거 횟수/년
    avg_cost_per_rebalance: Dec         # 리밸런싱당 평균 거래비용
    # ── 신규 3종 (02 §8.4) ───────────────────────────────────────────
    effective_fx_hedge_ratio: Dec       # Σ(헤지형 자산 비중) / Σ(해외자산 비중)
    cvar_5pct: Dec; cdar: Dec           # 목적함수로는 거부, 리포팅으로는 채택 (02 §3.6)
    look_count: int; breach_count: int; trade_count: int   # look/breach/trade 3분 계측
    # ── EX-1·M2 DoD 부산물 ──────────────────────────────────────────
    tmin_skip_ratio: Dec                # T_min 스킵 비율 (02 §8.2 EX-1 판정 지표)
    turnover_per_trigger: list[Dec]     # 밴드 트리거 1회당 회전율 분포 (04 §2 M2 DoD)
```

- **`look/breach/trade` 3분 계측**: `look` = 판정 실행 횟수(일 1회), `breach` = 밴드 breach 감지 건수, `trade` = 실제 체결 건수. `trade/look` 비율 상승 = 과매매로 새는 중(정본: 02 §8.4). 이 계측이 없으면 실시간 도입이 값을 하는지 사후 판정 자체가 불가능하다.
- **`turnover_per_trigger` 분포**는 M2 DoD가 요구하는 산출물이며, **P11 이월 상한을 95백분위 × 1.5로 재설정**하는 입력이다(정본: 04 §2 M2 DoD, 03 §1.2). 백테스트는 분포만 산출하고 **값을 config에 쓰지 않는다** — 파라미터 확정은 사람의 행위다.
- **`effective_fx_hedge_ratio`**는 유니버스 항목의 환헤지 여부 속성을 요구한다. `universe.yaml` 스키마에 `fx_hedged: bool` 필드가 필요하며 등록은 [04-configuration-and-secrets.md](04-configuration-and-secrets.md)에 요청한다(계획 02 §8.4가 지표를 요구했으나 속성 필드는 명시하지 않았다).
- **`cvar_5pct`·`cdar`는 리포팅 전용**이다. 이 값이 목적함수·게이트 판정에 들어가는 경로를 만들지 않는다(정본: 02 §3.6, 05 §10.2, 07 §4.4 HR-6).

### 12.3 검증 항목 (§12)

- 지표 골든 벡터: 고정 수익률 시계열에 대한 `PerformanceMetrics` 전 필드의 기댓값 테이블(회귀).
- 자체 구현 ↔ QuantStats 교차 확인(허용오차 내 일치 — **불일치 시 자체 구현이 정본**이고 차이를 리포트에 남긴다).
- `tax_drag ≥ 0` 속성(세후가 세전을 넘으면 버그).
- `look/breach/trade` 카운터가 시뮬 이벤트 수와 정확히 일치.

---

## 13. 몬테카를로 러너 (`mc_runner.py`)

### 13.1 경계와 배치

> **[DD-15-15] MC 수치 커널은 `engine`, I/O 러너는 `backtest`**
> - 결정: 몬테카를로의 **수치 계산 전부** — stationary block bootstrap 경로 생성, 월 스텝 전개(비용·인플레 차감), Guyton-Klinger 규칙, 인출기 세금 근사, 성공확률·백분위 팬차트, 처방 역산 — 은 `engine/montecarlo.py`의 `simulate(...) -> McResult`가 담당한다(**정의 정본: [07-portfolio-engine.md](07-portfolio-engine.md) §14**, 01 §2 트리 지정). `backtest/mc_runner.py`는 그 순수 함수의 **호출부**로서 ① 입력 시계열 조립(자산군 지수 월간 수익률·대리지수 백필) ② `Goal`·현금흐름·시평(horizon) 사양 구성 ③ `rng` 주입([DD-07-15] 시드 유도 규약) ④ 결과 파일 생성만 담당한다. 이 문서는 `McResult`·`McParams`·GK 규칙을 **재정의하지 않는다**.
> - 근거: 01 §2가 커널을 `engine/`에 배치했고 `engine`은 순수 함수 계층이다(Clock·I/O 없음 — [02](02-domain-model.md) [DD-02-11]). 반면 러너는 파일 I/O·캘린더·목표(goal) 조회를 필요로 해 `engine`에 둘 수 없다. 경계를 "경로 생성만 engine"으로 그으면 GK·성공확률 산식이 07과 15에 이중 정의되어 반드시 어긋난다.
> - 계획 문서와의 관계: 02 §9(파라미터·규칙 정본)·01 §2(모듈 배치)와 정합. 충돌 없음.

### 13.2 러너 절차 (파라미터 정의 정본: [07](07-portfolio-engine.md) §14.1 `McParams`·`McResult` / 값의 정본: 02 §9, 02 부록 A `mc.*`·`gk.*`)

러너는 커널 파라미터를 **재정의하지 않고 조립만** 한다. 값(`mc.paths` 5,000 · `mc.block` 평균 6개월 · 실효 비용 연 0.35% · 인플레 2.0% · `mc.success_bands` 75%/60% · 시평 최대 40년 · t(ν=5)는 스트레스 전용)의 정본은 02 §9이고, 그 값을 담는 타입은 07 §14.1 `McParams`다.

```python
def run_projection(goal: Goal, ledger_snapshot: LedgerSnapshot,
                   params: McParams, ctx: RunnerContext) -> McResult:
    """1. 입력 조립: 자산군 지수 월간 수익률(최소 20년, 부족 자산은 대리지수 백필) +
          현재 비중(glide path 반영) + 적립/인출 현금흐름 + horizon_months(goal 잔여기간)
       2. rng 유도: seed = int(sha256(inputs_hash)[:8], 16)  ([DD-07-15] — 실행 시각 비의존)
       3. engine.montecarlo.simulate(...) 1회 호출
          ★ 경로 생성·월 스텝 전개·GK 가드레일·세금 근사·성공확률·팬차트·처방 역산은
            전부 커널 안에서 끝난다(07 §14.2~§14.4). 러너는 산식을 갖지 않는다.
       4. McResult → 결과 파일 직렬화. 경로·적재 규약의 정본은 07 [DD-07-15]
          (`var/policy/mc/{as_of}.json`, 정책 산출물이 아니라 모니터링 산출물)."""
```

- **매매 경로와 완전 분리 — 모니터링 전용**이다(정본: 02 §9). `McResult`는 어떤 주문·목표비중도 만들지 않으며, 이는 00 §5 원칙 9(일방향 밸브)의 적용이다.
- 실행 주기: 분기 첫 영업일 04:00 `mc_projection` 잡 + 월간 −10% 초과 급변 시 임시(정본: 01 §4.2). **이 잡은 봇 스케줄러가 인-프로세스로 돌린다** — 백테스트와 달리 수 분~수십 분 루프 점유가 아니기 때문이다(배제 기준 정본: 01 §1.6). 잡 등록·시각은 [12](12-scheduling-and-operations.md) 소유, 루프 점유 회피(`asyncio.to_thread` 오프로드)는 07 §14.5 소유이며, 이 문서는 러너 본체 함수와 `omra backtest mc` 수동 재실행 경로만 소유한다.
- 결정론: 시드 유도 규약 + numpy `Generator` 주입(전역 `np.random` 금지 — 07 [DD-07-1] ③). 같은 입력 → 같은 성공확률.

### 13.3 검증 항목 (§13)

커널(블록 길이 분포·GK 골든 케이스·고정 인출 대비 실패율 방향·처방 역산 수렴)의 검증 항목은 [07](07-portfolio-engine.md) §14.6이 소유한다. 러너 측만 여기서 수거한다.

- 입력 조립 재현성: 같은 `ledger_snapshot`·같은 `goal`에서 `inputs_hash`가 동일 → 유도 시드 동일 → 결과 파일 동일([DD-07-15]와 짝).
- 대리지수 백필이 적용된 자산군이 결과 파일에 명시됨(근사 은폐 금지).
- `McResult`가 주문·목표비중 타입을 **포함하지 않음**(타입 수준 어서션 — 00 §5 원칙 9).

---

## 14. `tools` 실행 경로 · CLI · 결과 파일 계약

### 14.1 CLI 서브커맨드 (상위 카탈로그 정본: 01 설계서 §2.3, 계획 01 §1.6·§2)

`omra backtest`는 **tools 전용**이며 app 컨테이너에서 호출되면 즉시 거부된다([01-system-architecture.md](01-system-architecture.md) §2.4 검증 항목). **호출 형식의 정본은 [01](01-system-architecture.md) §2.3**(`python -m omra.cli backtest …` — 계획 01 §1.6 표기)이며, 아래 표의 `omra backtest …`는 같은 엔트리포인트의 축약 표기다. 서브커맨드 구성은 이 문서가 소유한다.

| 서브커맨드 | 용도 | 기본 `run_kind` |
|---|---|---|
| `omra backtest run --spec <path>` | 단일 시뮬 + 지표 산출 | `manual` |
| `omra backtest gates --spec <path> [--only <ids>] [--satellite]` | 코어 C1~C3(옵션: S1~S4) 일괄. `--only`로 부분집합 실행([DD-15-18]) | `gate` |
| `omra backtest lookahead --spec <path> [--samples <n>]` | C2 단독(빠른 CI 잡). `n` 기본 10, nightly 100([DD-15-18]) | `gate` |
| `omra backtest snapshot --baseline <id> [--update]` | C3 비교(기본) / 기준 갱신(`--update`, 절대 기준 통과 시에만) | `ci_snapshot` |
| `omra backtest guard-ab --spec <path>` | clean vs with_guards A/B(03 §4.4) | `gate` |
| `omra backtest challenger --spec <path>` | `G2` 러너(조건부 — §10.6) | `challenger` |
| `omra backtest mc --goal <id>` | 몬테카를로 투영(수동 재실행용) | — |

종료 코드: `0` 통과 / `1` 게이트 실패 / `2` 사양·입력 오류(거부) / `3` 실행 불가(스냅샷 없음·데이터 결측 임계 초과). CI는 `1`과 `3`을 구분해 알림 문구를 바꾼다.

**CI 잡별 호출 계약** (잡 배치·트리거·산출물 보관은 [16](16-testing-and-quality.md) §9.1·§10 소유. 아래는 **15가 제공하는 실행 인터페이스**다):

| CI 잡 | 호출 | 산출물 |
|---|---|---|
| **J8** (매 PR) | `omra backtest gates --spec <path> --only c2,c3` + `omra backtest guard-ab --spec <path>` | 결과 파일 + `gates[]` |
| **J11** (nightly) | ① `omra backtest gates --spec <path> --only c1` ② `omra backtest lookahead --spec <path> --samples 100` ③ (M7 이후) `omra backtest gates --spec <path> --satellite` | 잡별 결과 파일 1개씩 |

**조율 표기** — 16 §10.2의 J8 행이 쓰는 `omra backtest --gate c2,c3,ab`는 서브커맨드 없는 축약형이다. CLI 표면의 소유가 이 문서이므로(§14.1) **위 표의 형식이 정본**이며, 16의 잡 표는 이 형식으로 정정이 필요하다(요청).

> **[DD-15-18] 게이트 러너의 잡 단위 실행 인터페이스 — `--only`·`--samples`·`--satellite` (요청 출처: 16 §미해결 9)**
> - 결정: `gates` 서브커맨드에 `--only <gate_id[,gate_id…]>` 옵션을 신설해 CI 잡이 게이트 부분집합을 지정할 수 있게 하고, `lookahead`에 `--samples <int>`(기본값은 `backtest.lookahead.samples` = 10)를 신설한다. 위성 게이트 S1~S4 하네스의 실행 인터페이스는 **별도 서브커맨드를 만들지 않고 `gates --satellite`**로 고정한다. 규약: ① `--only`에 나열되지 않은 게이트는 결과 파일 `gates[]`에서 **생략이 아니라 `"skipped"` 항목**으로 남는다(무엇을 안 돌렸는지가 산출물에 남아야 한다 — §10.5의 `skipped` 규율과 동일) ② `--satellite`는 `GateRegistry.satellite()`(S1~S4)를 코어에 **추가**로 붙이며, S3가 `blocked`(§11.1)이면 잡 전체 종료 코드는 `1`이 아니라 `3`이다(미확정 산식은 실패가 아니라 실행 불가다) ③ nightly의 `--samples 100`은 결과 파일 `assumptions`에 실측 표본 수로 기록되어 매 PR 실행(10개)과 구분된다.
> - 근거: 16 §9.1이 C1을 nightly(J11), C2·C3를 매 PR로 **다른 잡에 배치**하고 §9.4가 "nightly에서는 T를 100개로 확대"를 요구했으나, 그 배치를 실행할 CLI 표면이 이 문서에 없어 16이 잡 정의를 쓸 수 없는 상태였다(16 §미해결 9 — "구현 소유는 15이며 이 문서는 J11 배치만 정한다"). CLI 서브커맨드 구성은 이 문서 소유(§14.1)이므로 여기서 확정한다. 별도 하네스 커맨드를 만들지 않은 이유는 위성 게이트가 코어와 **같은 시뮬 산출물**을 소비하기 때문이다 — 두 번 돌리면 결정론 비교 대상이 두 벌이 되고 실행 예산(§14.5)도 두 배가 된다.
> - 계획 문서와의 관계: 02 §8.2(게이트 집합)·02 §8.3(무작위 T **10개**)·03 §4.5(lookahead의 CI 포함)와 충돌 없음 — 계획이 정한 기본값 10을 그대로 두고 **확대 경로만** 옵션으로 노출한다(축소는 사양 오류로 거부: `--samples < backtest.lookahead.samples`는 종료 코드 `2`).

### 14.2 프로세스 경계 (정본: 01 §1.6)

```
[읽기]  app  : weekly_maintenance 및 omra backtest 실행 직전
               → VACUUM INTO /app/var/data/snapshots/omra-ro.sqlite
        tools: 그 스냅샷만 읽는다 (omra-db 볼륨은 tools에 존재하지 않는다)
[쓰기]  tools → var/data/experiments/<run_id>.json
        app   → omra experiment ingest <path> → persistence.repos.experiments
[기동]  docker compose run --rm tools python -m omra.cli backtest …    (호출 형식 정본: 01 설계서 §2.3)
        기동 주체는 사람 또는 호스트 cron — 봇 스케줄러가 아니다
```

- 스냅샷 부재·나이 초과(`tools.snapshot_max_age_h`, 기본 168h) → 종료 코드 `3` + "app에서 스냅샷 먼저 생성" 안내(01 설계서 §7.3).
- `tools`에는 브로커·Telegram·SMTP 자격증명이 없고 기동 셀프체크 SC-13이 부재를 강제한다(01 설계서 §5.2). **이것이 격리의 실체이며 import 계약의 프로세스 경계 쪽 절반이다.**

### 14.3 결과 파일 계약 (`result.py`)

```json
{ "schema_version": 1,
  "run_id": "01J...",                       // ULID (core.ids.new_id)
  "run_kind": "manual|challenger|gate|ci_snapshot",
  "spec_hash": "<sha256>",
  "spec": { },                              // BacktestSpec 전문
  "code_version": "<git sha>",
  "snapshot_meta": { "created_at": "...", "source_pages": 12345 },   // 01 §1.6 재현성 근거
  "data_fingerprint": "<sha256>",
  "started_at": "...", "finished_at": "...", "wall_seconds": 0,
  "metrics": { "pretax": { }, "aftertax": { } },   // §12.2 — Decimal 문자열
  "gates": [ { "gate": "C1", "passed": true, "metrics": { }, "detail": "" } ],
  "assumptions": { "sim_mode": "clean",
                   "guards_not_replayed": ["PriceGuard", "PremiumGate", "KimchiGuard",
                                           "CryptoDropGuard"],
                   "move_guard_proxy": "daily_close",
                   "approval_ladder": "auto_approved_except_reject_gt_20pp",
                   "account_model": "single",
                   "param_overrides": { },        // §3.1 — 적용한 오버라이드 전량
                   "lookahead_samples": 10,       // [DD-15-18] ③ — nightly는 100
                   "aftertax_is_lower_bound": true },
  "data_flags": { "filters_deferred": [], "redemption_price_fallback": [],
                  "fx_carry_forward_days": 0, "data_gaps_pct": "0.0" },
  "floor_candidates": { "sharpe_min": "…", "mdd_max": "…" },   // [DD-15-17] — 제안값.
                                             // 판정에 쓰이지 않고 사람이 기준 파일에 기입한다.
                                             // C1 Walk-Forward를 돌린 run에서만 존재
  "ledger_eligible": true                    // run_kind != ci_snapshot 일 때만 true
}
```

> **[DD-15-13] 결과 파일 스키마와 감사로그 분리**
> - 결정: ① 위 JSON을 `var/data/experiments/<run_id>.json`에 쓰고 이것이 `omra experiment ingest`의 유일한 입력이다. ② 시뮬 감사로그는 `var/logs/audit/backtest/<run_id>.jsonl`로 **분리**하되 봉투·payload 스키마는 라이브와 동일하다. ③ `assumptions`·`data_flags`는 선택 필드가 아니라 **필수**이며 비어 있어도 키가 존재해야 한다.
> - 근거: 01 §6.3이 "백테스트도 동일 스키마로 기록해 라이브와 비교 가능"을 요구하는 동시에 감사로그는 "왜 그 주문이 나갔는가"의 진실원이다. 같은 파일에 섞으면 실계좌 재구성 시 시뮬 이벤트를 걸러내야 하고 그 필터가 한 번만 틀려도 감사 신뢰성이 무너진다. `assumptions`를 필수로 만든 것은 02 §8.1.1의 "시뮬레이터가 모르는 것"을 결과물 자체가 항상 말하게 하기 위함이다.
> - 계획 문서와의 관계: 01 §6.3·02 §8.1.1·07 §13의 요구를 물리 계약으로 고정. 충돌 없음.

### 14.4 산출물 경로

| 경로 | 내용 | 쓰기 주체 |
|---|---|---|
| `var/data/experiments/<run_id>.json` | 결과 파일(위 스키마) | tools |
| `var/logs/audit/backtest/<run_id>.jsonl` | 시뮬 감사로그 | tools |
| `var/reports/backtest/<run_id>/tearsheet.html` | QuantStats tear sheet(사람용) | tools |
| `var/reports/backtest/<run_id>/te_decomposition.json` | TE 5항목 분해(§7.4) | tools 또는 app |
| `tests/snapshots/backtest/<baseline_id>.json` | C3 기준 파일(리포지토리 내) | 사람(커밋) |

### 14.5 실행 자원 — M2 DoD 실측 (정본: 02 §8.1.2, 01 §9.1, 04 §2 M2)

- 결과 파일의 `wall_seconds`가 실측 산출물이다. **M2 DoD**: 기준 전략 10년 백테스트 1회 실행 시간을 VPS 사양(1 vCPU)에서 실측한다.
- **30분 초과 시** §10.6의 분기 B/C로 간다. 판정은 사람이 하고 코드는 값을 제공한다.
- 성능 설계(예산 안에 들어가기 위한 구조): ① 전 구간 시세를 1회 로드해 ndarray로 보유하고 `BarView.at`은 O(1) 슬라이스(§6.1) ② skfolio 재최적화는 월 1회(10년 = 약 120회)만 ③ Decimal 연산은 원장·주문 경로에만(통계는 float64 — [DD-15-12]) ④ 세후 트랙은 평행 NAV 시계열이지 두 번째 시뮬이 아니다(주문 결정은 1회) ⑤ 프로파일 결과를 결과 파일 `wall_seconds`와 함께 단계별로 기록해 병목을 지목 가능하게 한다.

### 14.6 검증 항목 (§14)

- `omra backtest`가 app 컨테이너에서 거부됨(01 설계서 §7.3과 같은 코드 재사용).
- 스냅샷 부재 시 종료 코드 `3`.
- `gates --only c2,c3`가 C1을 **생략이 아니라 `skipped`**로 결과 파일에 남김([DD-15-18] ①).
- `gates --satellite`에서 S3가 `blocked`이면 종료 코드가 `1`이 아니라 `3`([DD-15-18] ②).
- `lookahead --samples 100`의 표본 수가 `assumptions`에 기록되어 매 PR 실행과 구분됨.
- 결과 파일 스키마 검증(필수 키 누락 시 ingest 거부).
- 같은 사양 2회 실행의 결과 파일이 `run_id`·타임스탬프·`wall_seconds`를 제외하고 **바이트 동일**(결정론 회귀 — R5의 "재현 실패" 입력, 07 §10.1).

---

## 15. 조건부 요소의 양경로 정리

| # | 조건 분기 | 경로 A | 경로 B | 이 문서의 대응 |
|---|---|---|---|---|
| 1 | **SP-C3** (미국 LOC/MOO/LOO 지원) | 지원 → 시뮬 t+1 종가 체결이 라이브와 정합 | 미지원 → 미국 기본 경로가 장중 지정가. **시뮬의 미국 체결 가정을 장중 집행 기준으로 바꾸고 TE 항목 ②에 미국분 편입** | `backtest.us_fill_basis: close|intraday_limit` 키로 양경로. 기본 `close`. 전환 시 C3 기준값 전면 재생성 필요(정본: 02 §4.5) |
| 2 | **SP-C4** (절세계좌 주문·조회) | 확정 → M8에 `account_model: multi` 착수 | 미확정 → `single` 고정 | `SimLedger`가 계좌 dict 구조를 처음부터 보유(§4.1). `multi` 착수 전까지 `backtest.accounts.yaml`은 존재하지 않는다(정본: 02 §8.1) |
| 3 | **M2 실행시간 실측** | ≤30분 → `G2` 유지 | >30분 → 5년 축소 또는 `G2` 삭제 | §10.6 3분기 전부 설계됨 |
| 4 | **M9 T1 실시간 계층** | 도입 → 일중 가드가 라이브에 존재 | 미도입 | 어느 쪽이든 **일 단위 시뮬은 일중 가드를 재생하지 않는다**(§7.2). T1 도입 시 TE ③의 크기가 커지므로 분해기의 입력만 늘어난다 |
| 5 | **SP-E2** (실시간 NAV) | 통과 → PremiumGate 실시간 경로 | 미통과 → REST 스냅샷 경로 | 두 경로의 **판정 결과는 동일해야 하고 차이는 지연뿐**(02 §4.4 폴백 등가성)이므로 시뮬은 어느 쪽도 재생하지 않는다 |
| 6 | **SP-A1/A2** (마스터 플래그) | 확정 → PIT 필터 완전 가동 | 미확정 → 인코딩 양쪽 수용 + 미지 값은 hard 통과 금지 | §6.3 |

---

## 16. 계획 문서 추적표

| 계획 조항 | 이 문서의 반영 위치 | 비고 |
|---|---|---|
| 02 §8.1 (라이브 코드 공유·t+1 종가·비용·배당·세금·정수화) | §1.2, §3.3, §5.1~§5.5 | 값 전재 |
| 02 §8.1 계좌 모델(`single` 고정·세후 하한·`multi`는 M8) | §4.1, §15-2 | |
| 02 §8.1 자산 생애주기(`auto_close_date`·CA·해지상환) | §5.6, [DD-15-6] | 05 §1.5 채택 |
| 02 §8.1 데이터 접근 계약(`BarView.current/history`) | §6.1, [DD-15-3] | 05 §1.5 zipline |
| 02 §8.1.1 (sim_mode 2종·구조적 괴리 3항목·`UnexecutedOrder`) | §7 전체 | 필드 4개 1:1 |
| 02 §8.1.2 (실행 자원·30분 임계·별도 프로세스) | §10.6, §14.5 | |
| 02 §8.2 게이트 C1~C3 / S1~S4 / 실험 로그·DSR N | §10.2~§10.4, §11 | |
| 02 §8.2 EX-1~EX-4 | §5.1-5(T_min 스킵), §10.4(S2·EX-4), §12.2 | EX-3는 07 소유(병렬 기록) |
| 02 §8.3 lookahead 자동탐지(전체 vs 절단·무작위 T 10개·as-of 필터) | §9 | |
| 02 §8.4 성과지표 + 신규 3종 | §12.2 | 전량 반영 |
| 02 §9 몬테카를로(block bootstrap 5,000·6개월·GK·성공확률 밴드) | §13 | **수치 커널은 [07](07-portfolio-engine.md) §14 소유** — 이 문서는 러너(입력 조립·시드 주입·결과 파일)만 |
| 02 §3.2 (`ex_ante_vol_dev` ±25% = 게이트 C1) | §8.2 | 문언 차이는 §18-1 |
| 02 §3.3 2단계 정수화·불변식 2개 | §3.3, §4.1, §5.1-4 | |
| 02 §3.3.1 축소 유니버스 infeasible 폴백 | §3.4 | M2 DoD 레벨 5·6·7 검증 |
| 02 §2.3 백테스트 as-of 필터 재평가 | §6.3 | 미확정 소스는 보류 |
| 02 §4.5 백테스트 체결 가정 정렬·TE 5항목 | §5.1, §7.4, §15-1 | |
| 02 §4.7 FX(백테스트 = 일별 종가 환율)·(e) 비용 정합 | §5.2, §5.4 | |
| 02 §4.1 미체결 이월 금지 | §5.1-6 | |
| 02 §4.6 SAFE_MODE 집행 제약 | §7.2 | `with_guards`에서만 |
| 02 부록 A (`backtest.*`·`mc.*`·`gk.*`·`trade.min_amount`) | §3.1, §5.2, §13.2, [DD-15-4] | 신규 키는 DD |
| 03 §4.4 백테스트 게이트 CI(스냅샷·config 트리거·가드 A/B 필수 구간·실행시간) | §10.3, §10.5, §14.5 | |
| 03 §4.5 lookahead CI 포함 | §14.1 (`omra backtest lookahead`) | |
| 03 §4.6 TE 5항목 분해·⑤에만 임계 | §7.4 | 계산기 배치는 DD-15-14 |
| 03 §4.1 property-based 불변식 | §4.1 | 같은 문장 공유 |
| 03 §1.5 P1 SAFE_MODE 전환의 A-B 사전 점검 | §10.5 | |
| 05 §1.5 zipline 4패턴(BarData·restrictions·생애주기·비용 분리) | §6, §7.1, §5.6, §5.2 | |
| 05 §4.6 block bootstrap 채택 근거·GK 내장 | §13.2 | |
| 05 §4.7 skfolio(WF·CPCV 내장)·QuantStats | §8.1, §12.1 | API 실측은 §18-6 |
| 05 §10.3 비용 0 백테스트는 증거가 아니다 | §1.2-3, §5.2 검증기 | HR-2 코드화 |
| 05 §10.5 성과 기반 자동 판정 불가 | §8.3(자동 임계 미도입), §7.4 | |
| 07 §7.1 tuning_space 화이트리스트 | §3.1 | 밖은 거부 |
| 07 §7.3 `G2` 조건부·별도 프로세스 | §10.6, §14.2 | |
| 07 §13 실험 원장 요건(N 정의·기록 대상·적재 경로·CI 제외) | §11.2~§11.4 | ingest 규약 소유 |
| 07 §10.1 R5(재현 실패·스냅샷 회귀 실패) | §14.6 | 결정론 회귀 |
| 01 §1.6 tools 실행 경로·스냅샷·단방향 적재·자격증명 부재 | §14.2 | 정본 그대로 |
| 01 §1.5 라이브러리(자체 시뮬·QuantStats·DuckDB) | §12.1, §6.1 | `vectorbt` 배제 유지 |
| 01 §6.3 백테스트도 동일 감사 스키마 | §7.3, [DD-15-13] | 파일만 분리 |
| 01 §2 `backtest/` 배치·`engine/montecarlo.py` | §2, §13.1 | |
| 04 §2 M2 (DoD 항목·추가 항목 6종·미통과 절차) | §6.3, §10.3, §10.5, §10.7, §12.2, §14.5 | |
| 00 §5 원칙 4(미집행 주문 기록)·9(일방향 밸브) | §7.3, §7.5, §13.2 | |

## 17. 설계 결정(DD) 목록

| ID | 제목 | 위치 |
|---|---|---|
| DD-15-1 | `backtest/` 파일 분할과 `BacktestRunner` 파사드 | §2 |
| DD-15-2 | in-memory 원장의 배치와 계산 로직 공유 방식 | §4.1 |
| DD-15-3 | `BarView` 인터페이스 확정(`PriceView` 면 3 + 확장 4, 전 데이터 접근의 유일 통로) | §6.2 |
| DD-15-4 | `backtest.*` config 블록 확정(신규 키 목록, 절대 기준 값은 미정 유지) | §5.2 |
| DD-15-5 | 체결일 = venue별 다음 세션 규칙 | §5.1 |
| DD-15-6 | 해지상환가 부재 시 청산가 폴백 + 기준값 갱신 차단 | §5.6 |
| DD-15-7 | MoveGuard 일간 프록시와 캘리브레이션 용도 봉인 | §7.2 |
| DD-15-8 | lookahead 비교 허용오차와 솔버 결정론 강제(별도 오류 분리) | §9.2 |
| DD-15-9 | 시뮬의 승인 사다리 미재현(>20%p REJECT만) · 하베스팅 게이트 재현 | §5.5 |
| DD-15-10 | 스냅샷 회귀 파일 계약과 절대 기준의 "구조 확정·값 실측" 처리 | §10.3 |
| DD-15-11 | `spec_hash` 정규화 정의(포함·제외 필드) | §11.3 |
| DD-15-12 | 게이트 지표는 자체 구현이 정본, QuantStats는 tear sheet 전용, Decimal/float 경계 | §12.1 |
| DD-15-13 | 결과 파일 스키마 + 시뮬 감사로그 파일 분리 + `assumptions` 필수 | §14.3 |
| DD-15-14 | TE 5항목 분해 계산기를 `backtest/tracking.py`에 배치 | §7.4 |
| DD-15-15 | MC 수치 커널(engine, 07 §14 소유)과 I/O 러너(backtest)의 경계 | §13.1 |
| DD-15-16 | `backtest` 격리 import 계약 신설 요구(계약 파일 소유는 01 §8.2) | §2 |
| DD-15-17 | `absolute_floor` 값의 M2 실측 확정 경로(산출은 15, 기입·승인은 16 프로토콜) | §10.3 |
| DD-15-18 | 게이트 러너의 잡 단위 실행 인터페이스 `--only`·`--samples`·`--satellite` | §14.1 |

> **[DD-15-16] `backtest` 격리 계약 신설 요구**
> - 결정: `omra.backtest`가 `omra.brokers`·`omra.execution`·`omra.rpc`·`omra.web`·`omra.scheduler`·`omra.realtime`·`omra.runtime`을 import하지 못하게 하는 `forbidden` 계약을 [01-system-architecture.md](01-system-architecture.md) §8.2에 추가할 것을 요구한다. 이 문서는 계약 원문을 쓰지 않는다.
> - 근거: 01 §2.2 계약 목록에 `backtest`를 소스로 하는 계약이 없어 default-allow 상태다. 백테스트가 브로커·집행을 import할 수 있으면 "tools에 자격증명을 주지 않는다"는 프로세스 격리가 코드 레벨에서 뒷받침되지 않고, `labs → backtest → execution` 경로로 07 §12의 격리가 우회된다. `realtime` 금지는 §7.2의 "일중 가드는 재생하지 않는다"를 구조로 강제한다(재생하려면 호가가 필요하고, 호가가 없으면 잘못된 프록시가 몰래 들어온다).
> - 계획 문서와의 관계: 01 §2.2의 여백(백테스트 계약 부재)을 채우는 요구이며 기존 계약과 충돌하지 않는다(`labs → backtest`는 계속 허용).

## 18. 미해결 항목 · 스파이크 종속

| # | 항목 | 종속 | 이 설계의 현재 가정 |
|---|---|---|---|
| 1 | **게이트 C1 변동성 조건의 문언 차이** — 02 §8.2는 "사후 변동성 ±25%", 02 §3.2 표는 `ex_ante_vol_dev` ±25%를 게이트 C1에 배정 | 계획 문서 확인 | §8.2에서 `ex_ante`로 판정하고 `realized`를 병기 기록. 계획 정정이 필요한 사항으로 등재(설계를 바꾸지 않고 이견 기록 — 브리프 §1-4) |
| 2 | **10년 백테스트 1회 실행 시간** | **M2 DoD 실측** | `G2` 3분기 전부 설계(§10.6). 결과 파일 `wall_seconds`가 판정 입력 |
| 3 | **MoveGuard 캘리브레이션용 REST 60초 샘플 이력 부재** | 03 §4.4·06 §1.2 | 일간 프록시([DD-15-7])는 A/B 참고 전용. 캘리브레이션은 M4 이후 스냅 축적 후 별도 하네스 |
| 4 | **DSR 산식의 정확한 형태** | **[확인 필요]** — Bailey & López de Prado 원논문 대조. **확인 방법·시점**: 원논문(*The Deflated Sharpe Ratio*, 2014)의 기대 최대 SR 항(Euler-Mascheroni 상수 사용 여부·근사식)을 대조해 `stats/dsr.py`에 산식 + 논문 식 번호 주석을 넣고, 논문 수치 예제를 골든 벡터 테스트로 고정한다. **M7 위성 활성화의 선행 작업**으로 등록한다 | 확정 전 `NotImplementedError` + S3 `blocked`(= 종료 코드 `3`, [DD-15-18] ②). 추정 산식으로 게이트를 통과시키지 않는다(§11.1). 이 상태에서 M7 위성 경로 전체가 막히는 것은 **설계 의도**다 |
| 5 | **스냅샷 절대 기준 임계값(Sharpe 하한·MDD 상한)** | M2 실측 — 확정 **절차는 [DD-15-17]로 확정**(요청 출처: 16 §미해결 3) | 키 필수·값 `null`(비활성) 유지, C1 판정식이 실질 하한. 러너는 제안값(결과 파일 `floor_candidates` — §14.3)만 산출하고 기입·승인은 사람 + 16 §9.2 프로토콜. 남은 미해결은 **수치 자체**뿐 |
| 6 | **skfolio `WalkForward`/CPCV·QuantStats API 시그니처** | **[확인 필요]** — 05 §4.7이 "실제 시그니처를 호출해 본 것은 아니다"로 명시. 확인 방법: M1 버전 고정 시점 실측 | 분할 인덱스 생성만 위임하고 시뮬 실행은 자체 커널이 수행(§8.1) — 라이브러리 변화 표면을 최소화 |
| 7 | **배당 이벤트 시계열 소스**(ex-date·지급일·주당 배당) | **[확인 필요]** — M2에서 `adj_close` 총수익 재구성 가능 여부 실측 | `adj_close` 근사 + 결과 파일 플래그(§5.3). 세후 배당 원천징수가 근사임을 숨기지 않는다 |
| 8 | **NAV(해지상환가) 시계열 소스** | 06 §7.3 표의 [확인 필요](SP-E2 계열) | 종가 폴백 + C3 기준 갱신 차단([DD-15-6]) |
| 9 | **유니버스 hard 필터 입력**(AUM·TER·60일 스프레드·추적오차) | 06 §7.3 — M2 확정 | 보류 처리 + `filters_deferred` 기록(§6.3). 통과로 처리하지 않는다 |
| 10 | **마스터 플래그 인코딩**(`Y/N` vs `0/1`) | **SP-A2** | 양쪽 수용 + 미지 값 hard 통과 금지(§6.3) |
| 11 | **미국 체결 가정 분기** | **SP-C3** | `backtest.us_fill_basis` 양경로(§15-1). 전환 시 C3 기준값 전면 재생성 |
| 12 | **`account_model: multi`(4계좌+워터폴)** | **SP-C4** 확정 후 M8 | `single` 고정. `SimLedger` 자료구조는 처음부터 계좌 dict(§4.1) |
| 13 | **`band.restore_fraction` 확정** | **M2 EX-1** | 잠정 0.5. 백테스트는 후보 ρ ∈ {0.75, 0.875, 1.0}를 `run_kind = MANUAL`·`GATE` 실험 사양으로만 지원하되 값을 config에 쓰지 않는다(§3.1·§12.2) |
| 14 | **P11 이월 상한 재설정**(95백분위 × 1.5) | M2 DoD | `turnover_per_trigger` 분포만 산출. 값 확정은 사람(§12.2) |
| 15 | **`universe.yaml`의 `fx_hedged` 속성** | [04-configuration-and-secrets.md](04-configuration-and-secrets.md)에 등록 요청 | 실효 환헤지비율 지표의 전제(§12.2). 속성 부재 시 지표는 `null`로 보고하고 추정치를 만들어 넣지 않는다 |
| 16 | **`backtest.data.max_gap_pct` 초기값 0.5%** | 계획 근거 없음 — M2 실측 | 이 문서의 임의 초기값([DD-15-4]). M2에서 실제 바 결측률 분포를 보고 재설정하며, 그전까지는 "실행 실패" 방향이라 조용한 편향은 생기지 않는다 |
| 17 | **CPCV `n_groups`(잠정 6)** | 계획 미규정 — M7 위성 게이트 착수 시 실측 | 경로 수 = 조합 수이므로 실행 시간과 직결(§8.1). 사양에 노출해 값을 숨기지 않는다 |
| 18 | ~~**`experiments` DDL의 `G0` 필드 `NOT NULL`과 M2 실행의 불일치**~~ → **해소** | [03-data-and-persistence.md](03-data-and-persistence.md) §3.3.11 [DD-03-33] | 03이 4컬럼의 `NOT NULL`을 **해제**하고 sentinel을 두지 않기로 확정했다. `NULL` = "G0 미등록", 판정식은 `hypothesis IS NOT NULL`, 챌린저 유래 행만 repo가 4값을 필수화한다. §11.4-2가 그대로 반영 |
| 19 | ~~**시뮬 감사로그 경로 `var/logs/audit/backtest/<run_id>.jsonl`**~~ → **해소** | [03-data-and-persistence.md](03-data-and-persistence.md) §7.3 [DD-03-35] | 03 §7.3 파일 레이아웃 표에 "경로(시뮬)" 행으로 **등재 완료**(봉투·payload는 라이브와 동일, `actor="labs"`). 03 §7.5에 라이브 월 파일 무오염 검증 항목도 함께 등재됨 |
| 20 | **`blocked_by` 8값의 소비 정합** | [03-data-and-persistence.md](03-data-and-persistence.md) §7.2 [DD-03-34](정본) | 자체 `Literal` 열거를 제거하고 03 정본 참조로 교체 완료(§7.3), TE 귀속 사상표를 §7.4에 1곳으로 고정(③④ + 세금 ①). 남은 종속은 **생산 측** — 08 §4.4가 SAFE_MODE 제거분을 `event_type="guard_verdict"`·`blocked_by="SAFE_MODE_CAP"`로 기록하고, 10이 세금 보류 레그를 `TAX_*`로 기록해야 이 계산기의 입력이 완성된다(03 §13-18 조율 항목) |
