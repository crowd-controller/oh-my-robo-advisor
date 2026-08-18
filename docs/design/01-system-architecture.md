# 01. 시스템 아키텍처

> **범위**: 프로세스 모델(단일 asyncio 프로세스), asyncio 태스크 토폴로지, 기동/종료 시퀀스와 기동 셀프체크, Docker Compose 배포 토폴로지(app/litestream/tools), import-linter 계약 파일의 구체 구현, 저장소 스캐폴드와 패키지 배치.
> **계획 정본**: 00 §5(설계 원칙)·§6, 01 전체(특히 §1.3~§1.6, §2, §4.2.1, §5.1, §6.4~§6.5, §9), 03 §2(상태 모델)·§3(fail-safe)·§5.1(전환 절차)·§6.3(배포 절차), 06 §12(모듈 설계), 07 §8(카나리)·§10(롤백 트리거 R1~R5)·§13(실험 원장 적재 경로), 04 §2 M0~M1.
> **선행 문서**: 없음(이 문서가 세트의 구조적 기점이다).
> **이 문서가 소유하는 정의**: 프로세스 토폴로지, 기동 시퀀스, import-linter 계약 파일, Docker (브리프 §2.1). 도메인 모델은 [02](02-domain-model.md), DDL·alembic·Litestream 복구는 [03](03-data-and-persistence.md), 잡 정의·run ledger·모니터링 항목은 [12](12-scheduling-and-operations.md), 주문 프로토콜·`order_lock`은 [08](08-execution.md), WS 세션 내부는 [05](05-broker-gateway.md), CI·테스트 구성은 [16](16-testing-and-quality.md)이 소유한다.

## 1. 개요 — 설계 대상과 책임

이 문서는 "시스템이 **하나의 프로세스로 어떻게 조립되고, 켜지고, 꺼지고, 배포되는가**"를 코드 작성 가능 수준으로 확정한다. 구체적으로:

1. **프로세스 모델** — 봇 엔진·스케줄러·FastAPI·Telegram·T0 WS를 하나의 asyncio 프로세스에 조립하는 composition root와, `RELOAD_CONFIG`가 요구하는 "봇 객체 전체 재생성" 단위 (정본: 00 §5-1, 03 §2.1).
2. **asyncio 태스크 토폴로지** — 상시 태스크 목록·감독(supervision)·재시작 정책·큐/락 배치, 단일 루프 보호 규율 (정본: 01 §1.4, §2.4, §9.2).
3. **기동/종료 시퀀스** — 기동 셀프체크 항목 카탈로그(진행 중 카나리 복원 포함), 자기복구 사다리와의 결합, graceful shutdown과 자발적 종료(`os._exit(1)`) (정본: 01 §6.4, 03 §3).
4. **Docker Compose 배포 토폴로지** — app/litestream/tools 3서비스, tools의 스냅샷 읽기 경로와 단방향 적재, 이미지 태깅·롤백 (정본: 01 §1.6, 03 §6.3).
5. **import-linter 계약 파일** — 01 §2.2 원문(유일 원문)을 기계 계약(`pyproject.toml [tool.importlinter]`)으로 1:1 번역하고, 계약이 못 막는 것을 보완하는 아키텍처 테스트 목록을 [16](16-testing-and-quality.md)에 넘긴다.
6. **저장소 스캐폴드** — 01 §2 트리를 최종 시스템 기준으로 확정하고, 이 문서가 신설하는 `runtime/` 패키지의 좌표를 고정한다.

**설계하지 않는 것**: 잡별 로직(12), 주문 집행(08), 상태머신 5축 결합의 판정 구현(09), WS 파싱·재연결 절차의 구현(05). 이들은 각 소유 문서에 있으며, 이 문서는 그것들이 **어느 태스크에서, 어떤 순서로 기동되는가**만 정의한다.

## 2. 저장소 스캐폴드와 패키지 배치

### 2.1 전체 트리 (정본: 01 §2 + 이 문서의 추가분)

계획 01 §2의 트리를 그대로 채택하고, 아래에 **이 문서가 추가·구체화하는 항목만** `★`로 표기한다. 나머지 항목의 의미는 계획 01 §2 원문과 동일하며 각 소유 설계서가 상세를 정의한다.

```
oh-my-robo-advisor/
├── pyproject.toml             # ★ §2.3 — 의존성 + [tool.importlinter] 계약(§8)
├── uv.lock
├── Dockerfile                 # ★ §7.2
├── docker-compose.yml         # ★ §7.1
├── .env / .env.litestream / .env.tools    # 시크릿 3분할 (정본: 01 §1.6·§6.1)
├── CONTRIBUTING.md            # branch·commit·검증·자동화 신원 규칙
├── config/                    # 사람이 편집하는 입력물, 컨테이너에 :ro 마운트 (정본: 01 §2)
│   ├── config.yaml / config.live.yaml / config.paper.yaml
│   ├── universe.yaml / targets.yaml / goals.yaml / tax.yaml
│   ├── surveillance.yaml / market_weights.yaml
│   ├── external_schedules.yaml / external_income.yaml
│   ├── secrets_registry.yaml / tr_ids.kis.yaml
│   └── litestream.yml         # ★ §7.1 — litestream 컨테이너에 :ro 마운트 (정본: 01 §6.5)
├── docs/
│   ├── plan/                  # 계획 정본 00~07
│   ├── design/                # 이 설계서 세트
│   ├── engineering/           # 일반 개발 workflow·문서 이관 감사(제품 정본 아님)
│   └── runbook/               # secret-rotation.md, restore-drill.md, spike-c4.md (구조는 12 §runbook)
├── src/omra/
│   ├── __main__.py            # ★ §3.1 — cli의 Typer 앱에 위임하는 별칭
│   ├── runtime/               # ★ [DD-01-1] 신설 — composition root·생명주기 (이 문서 소유)
│   │   ├── worker.py          #   프로세스 수명 루프(RELOAD_CONFIG 재생성 포함)
│   │   ├── bot.py             #   Bot 조립·기동·해체 (§3.2)
│   │   ├── tasks.py           #   TaskSpec·TaskSupervisor (§4.2)
│   │   ├── selfcheck.py       #   기동 셀프체크 러너 (§5)
│   │   └── shutdown.py        #   graceful shutdown 시퀀서 (§6.1)
│   ├── cli/                   # Typer CLI (§2.3 명령 표). `python -m omra.cli <cmd>`가
│   │                          #   컨테이너 호출 형식의 정본이다 (정본: 01 §1.6)
│   ├── core/                  # 도메인 모델 — 정의 정본: 02-domain-model.md
│   ├── config/                # 설정 로딩·계층 병합 — 정의 정본: 04-configuration-and-secrets.md
│   ├── calendar/              # 캘린더·세션 — 정의 정본: 06-market-data-and-calendar.md
│   ├── brokers/               # BrokerGateway — 정의 정본: 05-broker-gateway.md
│   │   ├── base.py / paper.py
│   │   ├── kis/  (client.py · auth.py · ratelimit.py · tr_map.py · ws/{session,registry,decoder,events}.py)
│   │   └── upbit/ (client.py · auth.py · ratelimit.py · ws/{public,private}.py · events.py)
│   ├── collectors/            # 중립 수집 (http.py · robots.py · dedup.py) — 14
│   ├── surveillance/          # sources/ · flags.py · gate.py — 11
│   ├── realtime/              # verdict.py · guards.py · execution_hint.py · fallback.py — 11
│   ├── data/                  # TET Fetcher·quote·Parquet·DuckDB — 06
│   ├── engine/                # 순수 함수 수치 엔진 — 07
│   │   ├── expected_returns.py · covariance.py · optimizer.py · sanity.py
│   │   ├── covariance_monitor.py   # ★ [DD-01-9] Σ_monitor(EWMA) 분리 좌표 (근거: 02 §3.2)
│   │   ├── rebalancer.py · montecarlo.py · overlay/
│   ├── tax/                   # — 10
│   ├── execution/             # router.py 포함 — 08
│   ├── protections/           # P1~P15 — 09
│   ├── portfolio/             # 포지션·NAV·원장 — 07/08 분담
│   ├── persistence/           # — 03 (내부 설계). ★ 모듈 경계 좌표만 이 문서가 고정(§8.1):
│   │   ├── session.py         #   ★ rw 세션 팩토리 — 관측 4레이어 import 금지의 초크포인트
│   │   ├── ro.py              #   읽기 전용 세션 팩토리
│   │   ├── models/            #   SQLAlchemy 모델
│   │   ├── migrations/        #   alembic (단일 헤드 — 정본: 01 §1.3)
│   │   └── repos/             #   테이블별 쓰기 리포지토리 (열거 §8.1.1)
│   ├── scheduler/             # 잡 등록·run ledger·시간 예산 — 12
│   ├── rpc/                   # RPCManager·telegram·smtp·webhook — 13
│   ├── web/                   # FastAPI 라우터·템플릿 — 13
│   ├── research/              # LLM 레이어 — 14
│   ├── labs/                  # 자가 개선 오케스트레이션 — 14
│   ├── backtest/              # — 15
│   ├── audit/                 # append-only JSONL 로거 — 03(스키마)/12(운영)
│   └── monitoring/            # healthcheck·heartbeat·DMS·loop lag — 12. ★ watchdog 태스크는 §4.5
├── tests/                     # — 16
├── scripts/                   # restore_drill.sh 등 — 12
└── var/ (컨테이너 볼륨: db/ data/ logs/ policy/)   # 산출물 — config/와 분리 (정본: 01 §6.1)
```

> **[DD-01-1] `omra.runtime` 패키지 신설 — composition root의 좌표 고정**
> - 결정: Worker/Bot 생명주기·태스크 감독·기동 셀프체크를 `omra/runtime/`에 모은다. `runtime`은 모든 패키지를 import할 수 있는 유일한 조립층이며, 역으로 `cli`·`__main__` 외의 어떤 패키지도 `runtime`을 import할 수 없다(§8.2 계약 C11).
> - 근거: 계획 01 §2 트리에는 "봇 객체 전체 재생성"(03 §2.1 `RELOAD_CONFIG`)과 기동 셀프체크(03 §3)를 담을 자리가 없다. freqtrade의 Worker(프로세스 수명) / FreqtradeBot(재생성 단위) 분리는 계획이 채택한 패턴이다(정본: 00 §4, 05 §1).
> - 계획 문서와의 관계: 충돌 없음 — 계획 01 §2가 비워 둔 엔트리포인트 계층의 여백을 채운다.

### 2.2 패키지 → 소유 설계서 매핑

| 패키지 | 상세 설계 소유 | 이 문서가 정의하는 것 |
|---|---|---|
| `runtime/`, `cli/`, `__main__.py` | **01(이 문서)** | 전부 (§3~§6) |
| `persistence/` | 03 | 모듈 경계 좌표(session/ro/repos)만 — 계약의 초크포인트(§8.1) |
| `scheduler/`, `monitoring/` | 12 | 태스크로서의 기동 위치·재시작 정책(§4), watchdog 종료 의미론(§4.5) |
| `brokers/` | 05 | T0 세션 태스크의 감독 정책(§4.1), decoder→소비자 배선(§4.3) |
| `execution/` | 08 | `order_lock`·가드 예산 복원의 기동 훅(§5.3) |
| `labs/` | 14 | 카나리 복원의 기동 훅(§5.3), tools 단방향 적재 경로(§7.3) |
| 그 외 | 각 문서 | import 계약(§8)과 스캐폴드 좌표만 |

### 2.3 pyproject·엔트리포인트·CLI

- Python **3.12**, 패키지 관리 **uv** + lockfile (정본: 01 §1.1). 의존성은 계획 01 §1.5 표(httpx, websockets, skfolio, QuantStats, FinanceDataReader, pykrx, exchange_calendars, python-telegram-bot v21+, tenacity, structlog, pydantic-settings, anthropic)와 01 §1.2~§1.4·§2에 명시된 스택(FastAPI, uvicorn, Jinja2, SQLAlchemy 2.0, alembic, APScheduler, pyarrow, duckdb, Typer)을 그대로 쓴다.
- mypy/ruff 구성은 [16](16-testing-and-quality.md) 소유. `[tool.importlinter]`는 이 문서 §8이 소유한다.

CLI 명령 카탈로그 (`src/omra/cli/`, Typer. 근거: 01 §2 "run/backtest/report/health/plan" + 01 §6.1 `omra config show` + 07 §13 `experiment ingest`). **호출 형식은 계획 01 §1.6의 표기를 그대로 따른다 — `python -m omra.cli <명령>`**:

| 명령 | 실행 위치 | 동작 |
|---|---|---|
| `run` | app 컨테이너 CMD | Worker 기동(§3.1). 유일한 상시 실행 명령 |
| `health` | app 내부(Docker healthcheck) | loopback `/healthz` 조회 → exit 0/1 (§7.4) |
| `backtest …` | **tools 전용** | 백테스트·챌린저 G2 러너. 봇 프로세스 내 실행 금지 (정본: 01 §1.6) |
| `report …` | tools 또는 app 일회성 | 리포트 재생성 |
| `plan --dry` | app 일회성 | 오늘 계획 미리보기(주문 제출 없음) |
| `config show` | app 일회성 | 실효 설정 덤프(시크릿 마스킹 — 정본: 01 §6.1) |
| `config validate` | app·tools 일회성 / CI | 04 §9.1 단계 ①스키마 ②상호제약 ③4블록 키 정합을 실행하고 exit 0/1. 검증 규칙 정본은 [04](04-configuration-and-secrets.md) §9, 호출자는 CI J9 게이트([16](16-testing-and-quality.md) §10.2). [DD-01-16] |
| `experiment ingest <path>` | **app 전용** | tools 산출 `var/data/experiments/<run_id>.json` → `persistence.repos.experiments` 적재. DB 쓰기 주체는 언제나 app (정본: 01 §1.6, 07 §13) |
| `research probe` | **tools 전용** | SP-R1 소스 신선도 1주 실측 러너. 산출은 `var/data/`의 결과 파일뿐이며 DB에 쓰지 않는다(요청: [14](14-research-and-labs.md) §22 #18). [DD-01-16] |

> **[DD-01-16] CLI 카탈로그 추가 2종 — `config validate` · `research probe`**
> - 결정: 위 표에 두 명령을 등재한다. ① `config validate`는 기동 phase A2의 config 검증기(SC-1과 동일 코드)를 CLI로 노출해 CI의 J9 게이트가 프로세스를 띄우지 않고 같은 판정을 재사용하게 한다. ② `research probe`는 tools 전용이며 `.env.tools`(자격증명 부재, SC-13)의 격리를 그대로 받는다.
> - 근거: 요청 출처는 ① [16](16-testing-and-quality.md) §16 미해결 12 — "04 §9.1은 단계만 정하고 실행 형태를 정하지 않았고 01 §2.3 카탈로그에 `config validate`가 없다", ② [14](14-research-and-labs.md) §22 #18 — "등록되지 않으면 SP-R1은 임시 스크립트로 수행되고 결과가 기록되지 않는다". CLI 카탈로그의 소유는 이 문서(§2.3)이므로 여기서 확정한다. 계획 01 §2의 명령 목록(run/backtest/report/health/plan)은 열거이지 상한이 아니며, `config show`(01 §6.1)·`experiment ingest`(07 §13)도 같은 방식으로 추가되어 있다.
> - 계획 문서와의 관계: 충돌 없음 — 계획이 정한 명령을 바꾸지 않고 두 개를 더한다. 검증 규칙(04)·잡 명령줄(16 §10.2 J9)의 갱신은 §11 미해결 15·16.

### 2.4 검증 항목

- 스캐폴드의 모든 패키지가 §8.2 계약의 모듈 명과 1:1 대응한다(존재하지 않는 모듈을 계약이 참조하면 import-linter가 에러를 내므로, **전 패키지는 M0부터 빈 패키지로라도 존재해야 한다** — 04 §2 M0 "저장소 구조" DoD와 정합).
- `backtest`가 app 컨테이너에서 호출되면 즉시 에러로 거부한다(§7.3의 프로세스 경계 확인과 동일 코드).

## 3. 프로세스 모델 — 단일 asyncio 프로세스

### 3.1 Worker / Bot 2층 구조

단일 프로세스·단일 진실원(정본: 00 §5-1). 프로세스 안을 두 층으로 나눈다:

- **`Worker`** — 프로세스와 수명이 같다. 시그널 핸들링, Bot 재생성 루프(`RELOAD_CONFIG`), 최종 종료 코드 결정.
- **`Bot`** — `RELOAD_CONFIG` 시 통째로 재생성되는 단위(핫스왑 아님, DB에서 복원 — 정본: 03 §2.1). 설정 스냅샷 1개에 결합된 모든 서브시스템(스케줄러·브로커·웹·Telegram·T0 세션·모니터링)을 소유한다.

```python
# src/omra/cli/__main__.py — `python -m omra.cli run` 진입점 (호출 형식 정본: 01 §1.6).
# src/omra/__main__.py 는 같은 Typer 앱에 위임하는 별칭일 뿐이다.
import asyncio, typer
from omra.runtime.worker import Worker

@app.command("run")                      # app 컨테이너 CMD — 유일한 상시 실행 명령
def run_cmd(set_: list[str] = typer.Option([], "--set")) -> None:
    raise SystemExit(asyncio.run(Worker(set_).run()))   # CLI 인자 = 설정 최상위 계층 (01 §6.1)
```

```python
# src/omra/runtime/worker.py
class ExitReason(StrEnum):
    SHUTDOWN = "shutdown"        # SIGTERM/SIGINT/치명 오류 → 프로세스 종료
    RELOAD = "reload"            # /reload_config → Bot 재생성 (프로세스 유지)

class Worker:
    def __init__(self, cli_overrides: list[str]) -> None: ...   # `--set 섹션.키=값`

    async def run(self) -> int:
        self._install_signal_handlers()          # SIGTERM/SIGINT → bot.request_shutdown()
        while True:
            bot = Bot(bootstrap=self._bootstrap) # config는 Bot 내부에서 로드 (§6.3)
            reason, code = await bot.run()       # 기동 → 상시 운용 → 해체까지 블록
            if reason is ExitReason.SHUTDOWN:
                return code                      # 0=정상, 1=자기복구 필요(§4.5는 여기 오지 않고 os._exit)
            # RELOAD: 루프 계속 → 새 Bot이 새 config로 조립된다
```

### 3.2 Bot 조립 순서 (composition root)

```python
# src/omra/runtime/bot.py — 의사코드. 실제 하위 생성자는 각 소유 문서 정본.
class Bot:
    async def run(self) -> tuple[ExitReason, int]:
        # ── phase A. DB 이전 (§5.1 A) ─────────────────────────────
        kill = kill_file_present()                       # var/data/KILL (정본: 03 §2.6)
        cfg  = load_and_validate_config()                # fail-fast (정본: 01 §6.1) + live 3중 일치 (03 §5.1)
        # ── phase B. DB·마이그레이션 (§5.1 B) ─────────────────────
        db   = open_sqlite(cfg)                          # WAL, busy_timeout=5000, synchronous=NORMAL (01 §1.3)
        prev = read_bot_state(db)                        # 단일 행
        migrated = maybe_migrate(db, kill, prev)         # KILL 또는 STOPPED면 스킵 (01 §1.3)
        # ── phase C. 컴포넌트 조립 (I/O 없는 생성만) ──────────────
        ctx = build_context(cfg, db)                     # brokers, calendar, engine, execution,
                                                         # protections, surveillance, realtime,
                                                         # scheduler, rpc, web, monitoring, labs …
        # ── phase D~F. 기동 셀프체크·대사·잡 등록 (§5) ────────────
        boot = await run_selfcheck(ctx, kill=kill, prev=prev, migrated=migrated)
        # ── phase G. 상시 태스크 기동 (§4) ────────────────────────
        sup = TaskSupervisor(ctx)
        await sup.start_all(boot.effective_state)
        # ── phase H. 상태 확정·운용 ───────────────────────────────
        audit(state_transition, to=boot.effective_state, actor="scheduler")
        reason = await self._until_shutdown_or_reload()  # 이벤트 대기
        await graceful_shutdown(ctx, sup, reason)        # §6.1
        return reason, 0
```

조립 규칙:

1. **phase C까지는 네트워크 I/O 금지.** 브로커 토큰 확인·대사 등 I/O는 전부 셀프체크(§5) 안에서, 명시된 순서로만 일어난다 — 실패 지점을 셀프체크 항목 ID로 특정하기 위함이다.
2. 조립은 생성자 주입(수동 DI)이다. 레지스트리·플러그인 로더는 Protections 체인(09 소유)과 TET provider 레지스트리(06 소유)뿐이며, `runtime`은 그 로더를 호출만 한다.
3. `Bot`은 서브시스템의 소멸까지 소유한다 — `RELOAD_CONFIG`가 "재생성"으로 정의되는 근거(03 §2.1)가 이 소유 구조다.

### 3.3 실행 모드와 프로세스의 관계

- 실행 모드 3종 `dry_run`/`paper`/`live`는 **프로세스 구조를 바꾸지 않는다.** 분기는 `BrokerGateway` 최하단 한 곳(정본: 01 §3.2), `AccountMode` 분기는 `execution/router.py` 한 곳(정본: 00 §5-2)이다. Worker·태스크 토폴로지·셀프체크 목록은 세 모드에서 동일하다(모의 rate limit 프로파일 등 값만 config로 바뀐다 — 01 §5.2).
- SP-C4 분기(E2 절세계좌 경로 A/B)도 프로세스 모델에 영향이 없다 — 분기 실체는 `router.py`의 `AccountMode`이며 [08](08-execution.md) 소유. **조건부(SP-C4)임을 명시**하고, 이 문서 수준에서는 두 분기 모두 동일 토폴로지다.
- `tools` 컨테이너는 **같은 이미지의 별도 프로세스**이며 Worker를 기동하지 않는다 — `backtest` 등 일회성 CLI만 실행하고, 기동 셀프체크의 tools 변형(§5.2 SC-13)이 브로커 자격증명 부재를 확인한다(정본: 01 §1.6).

### 3.4 검증 항목

- 동일 config로 `Bot`을 2회 연속 생성·해체해도 태스크·소켓·파일핸들 누수가 없다(RELOAD 20회 반복 테스트).
- phase C까지 네트워크 호출이 없다(httpx transport mock으로 0건 단정).
- 모드 3종에서 조립 그래프(컴포넌트 목록)가 동일함을 스냅샷 테스트로 고정.

## 4. asyncio 태스크 토폴로지

### 4.1 상시 태스크 카탈로그

단일 이벤트 루프 위의 상시 태스크는 아래 **9종이 전부**다. 이 표에 없는 상시 태스크를 추가하는 것은 아키텍처 변경이며 이 문서의 개정을 요구한다.

| # | 태스크 | 내용 (상세 소유) | 재시작 정책 | 실패가 봇에 미치는 영향 |
|---|---|---|---|---|
| T-01 | `scheduler` | APScheduler `AsyncIOScheduler` — 모든 잡의 발화점 (12) | `ESCALATE` | 스케줄러 사망 = 봇 사망(치명). Worker 종료 → Docker 재기동 |
| T-02 | `web` | uvicorn `Server.serve()`를 태스크로 임베드 (13. 패턴 정본: 01 §1.2) | `ALWAYS` | 웹이 죽어도 거래는 계속. 재시작 3연속 실패 시 warning + 태스크 포기 |
| T-03 | `telegram` | python-telegram-bot 폴링 (13) | `ALWAYS` | 발송 실패 3연속 → SMTP 단독 운용 + warning (정본: 01 §6.2) |
| T-04 | `ws_kis` | KIS WS 세션 1소켓(T0 체결통보 2건 + 조건부 T1 구독) (05) | `SELF` | 워치독·백오프 자체 관리. **degrade only — HALT 유발 금지** (정본: 01 §4.2 `realtime_t0`, §5.3) |
| T-05 | `ws_upbit_public` | 업비트 public ticker BTC·ETH (05) | `SELF` | 동일 |
| T-06 | `ws_upbit_private` | 업비트 `myOrder`·`myAsset` (05) | `SELF` | 동일 |
| T-07 | `fill_consumer` | `fill_queue` 소비 → 체결 반영 (08) | `ALWAYS`+critical | **Fill은 절대 drop 금지** (정본: 01 §2.4). 예외 시 이벤트를 큐에 되돌리고 재시작 |
| T-08 | `watchdog` | heartbeat·loop lag 감시 → 자발적 종료 (§4.5) | `ESCALATE` | watchdog 사망 자체가 감시 불능이므로 치명 취급 |
| T-09 | `dms_pinger` | dead-man's switch webhook ping (12 — 조건 정본: 01 §6.4) | `ALWAYS` | ping 누락은 외부 감시가 탐지(그것이 DMS의 목적) |

`SELF` = 태스크 내부의 재연결 루프(백오프 1→2→…→60s full jitter, 10회 연속 실패 시 당일 REST 폴백 모드 — 정본: 01 §5.3)가 스스로 관리하며, 감독자는 태스크가 **반환/예외로 끝났을 때만** `ALWAYS`처럼 재기동한다.

일회성·주기 작업(감시 폴, 집행, 배치…)은 태스크가 아니라 **APScheduler 잡**이다(T-01 안에서 발화, 정의 정본: [12](12-scheduling-and-operations.md)). 잡 등록 기본값 `max_instances=1`·`coalesce=True`·`misfire_grace_time=<시간 예산>`은 계획 01 §1.4가 정본이다.

### 4.2 태스크 감독 — 시그니처

```python
# src/omra/runtime/tasks.py
class RestartPolicy(StrEnum):
    ALWAYS = "always"        # 지수 백오프(1→2→4→…→60s)로 재기동, 3연속 실패 시 warning
    SELF = "self"            # 내부 재연결 루프가 관리. 태스크 종료 시 ALWAYS와 동일 처치
    ESCALATE = "escalate"    # 재기동하지 않고 Worker 종료(critical) → Docker restart로 회복

@dataclass(frozen=True)
class TaskSpec:
    name: str                                    # 표 §4.1의 식별자
    factory: Callable[[], Coroutine[Any, Any, None]]
    policy: RestartPolicy
    start_in_states: frozenset[BotState] | None = None   # None = 전 상태에서 기동

class TaskSupervisor:
    def __init__(self, ctx: BotContext) -> None: ...
    async def start_all(self, state: BotState) -> None: ...
    async def stop_all(self, budget: ShutdownBudget) -> None: ...   # §6.1
    def snapshot(self) -> list[TaskStatus]:      # /healthz·대시보드용 (12가 소비)
        ...
```

- **모든 상시 태스크는 `STOPPED`·`HALTED`를 포함한 전 상태에서 기동한다**(`start_in_states=None`). `STOPPED`의 "전 집행 정지, 데이터 적재만"(정본: 03 §2.1)은 태스크를 죽여서가 아니라 **상태 게이트(5축 결합, 09 소유)가 주문 경로를 차단**해서 달성된다. 근거: `STOPPED` 탈출에 Telegram `/resume`이 필요하므로(03 §2.6) T-03은 살아 있어야 하고, 데이터 적재 잡은 계속되어야 하므로 T-01도 살아 있어야 한다.
- 감독자의 재기동 백오프 파라미터는 WS 재연결 백오프(01 §5.3)와 동일 수열을 재사용한다 — 두 벌의 백오프 구현을 만들지 않는다.

### 4.3 큐·락·직접 호출 — 데이터 흐름

계획이 확정한 비대칭(정본: 01 §2.4, 00 §6.3)을 그대로 구현한다. **큐는 `fill_queue` 하나뿐이다.**

```
ws_kis / ws_upbit_public / ws_upbit_private (T-04·T-05·T-06)
   └ decoder.on_message(raw)          # MarketStatus는 KIS H0STMKO0(T1 조건부)에서만 나온다
        ├ Fill()          → await fill_queue.put(ev)         # 유일한 큐 — drop 금지
        ├ MarketStatus()  → surveillance.ingest_ws(ev)       # 직접 호출 (11 소유)
        └ BookTop()/QuoteTick()/NavTick()
                          → realtime.guards.on_market(ev)    # 직접 호출, 예외는 호출부에서 격리
fill_consumer (T-07)
   └ fill_queue.get() → execution 체결 추적 (08 소유)
```

**배선 지점 — decoder 핸들러·장중 여부 술어·WS `start_delay`** (요청: [05](05-broker-gateway.md) §7.5 [DD-05-1]). `brokers`는 `surveillance`·`realtime`·`calendar`를 import하지 않으므로(05 §2 자기 제약), 위 화살표는 **조립 루트가 phase C(§3.2)에서 주입한 콜백**으로 실현된다. 이 배선은 `runtime/bot.py`의 `build_context()` 안에서만 일어나며, 그것이 이 문서가 소유하는 부분이다:

```python
# src/omra/runtime/bot.py — phase C 배선 구간. 메서드 시그니처 정본: 05 §7.5·§7.7
dec = ctx.kis_ws.decoder
dec.bind_market_status(ctx.surveillance.ingest_ws)          # MarketStatus → 감시 (11 소유)
dec.bind_market("guards", ctx.realtime.guards.on_market)    # 호가·체결가·NAV → 가드 (11 소유)
# 업비트 세션의 이벤트 핸들러도 같은 방식으로 주입한다(대응 API는 05 §8 소유).
```

- **장중 여부 술어**: KIS WS 워치독의 "장중 30초 무메시지 → 강제 재연결" 규칙(정본: 01 §5.3)은 장외에 적용할 수 없으므로, 세션은 장중 여부를 판정하는 **callable을 생성 인자로 주입받는다**(인자 이름·시그니처는 05 §7.5 소유). 조립 루트가 그 자리에 `calendar`(06 소유)의 세션 질의를 넘긴다 — `brokers → calendar` import를 만들지 않기 위한 유일한 경로다.
- **WS 순차 재연결의 조율자**: 소켓 3개가 동시에 끊겼을 때의 **3초 간격 순차 재수립**(정본: 01 §5.3)은 각 세션이 받는 `start_delay` 인자로 구현되고(05 §7.5), 그 값을 부여하는 주체는 **T-04~T-06을 기동하는 `TaskSupervisor`**다: `start_all()`이 WS 태스크에 `start_delay = 3.0 × (T-04, T-05, T-06 순서 인덱스)` = 0/3/6초를 전달한다. 재연결 시점의 지연도 같은 값을 재사용하므로 세션 간 조율 채널이 따로 필요 없다.

> **[DD-01-17] decoder 핸들러·세션 인자 배선의 단일 지점 = `runtime/bot.py` phase C**
> - 결정: `bind_market_status`·`bind_market`·장중 여부 술어·`start_delay` 4종의 주입은 **조립 루트에서만** 수행한다. 어떤 잡·태스크도 실행 중 핸들러를 재바인딩하지 않으며, 재바인딩이 필요하면 `RELOAD_CONFIG`(§6.3)로 Bot을 재생성한다.
> - 근거: 요청 출처는 [05](05-broker-gateway.md) §7.5 [DD-05-1] ("조립 루트가 등록한 콜백을 decoder가 동기 직접 호출") 및 §11.1 조율표 C6. 런타임 재바인딩을 허용하면 "직접 호출"의 호출 그래프가 시점에 따라 달라져 예외 격리 카운터(01 §2.4)의 의미가 흐려지고, `Bot`이 서브시스템의 소멸까지 소유한다는 §3.2-3의 전제가 깨진다.
> - 계획 문서와의 관계: 충돌 없음 — 계획 01 §2.4의 "decoder가 가드 함수를 직접 호출"의 물리적 배선 위치라는 여백을 채운다.

- `fill_queue: asyncio.Queue[FillEvent]` — **무제한(maxsize=0)**. 시세와 달리 Fill은 유실 불가이므로 배압으로 버리는 선택지가 없다.

> **[DD-01-3] `fill_queue` 무제한 + 고수위 경보**
> - 결정: `maxsize=0`(무제한), 크기 1,000 초과 시 warning(수위는 config `runtime.fill_queue_warn`).
> - 근거: 계획 01 §2.4 "Fill은 절대 drop 금지"와 §9.1 "메모리: Fill 큐만 유지 — 수십 MB 증가"가 무제한 큐를 전제한다. 개인 계좌의 체결 이벤트량에서 1,000건 적체는 정상 경로에서 불가능하므로 경보 수위로 적절하다.
> - 계획 문서와의 관계: 충돌 없음 — drop 금지의 구현 파라미터를 채운다.

- 시세 계열은 큐 없이 **최신값 슬롯**(종목당 마지막 이벤트 1개 보관, 낡으면 덮어씀 — 정본: 01 §9.2-3)이다. 슬롯 자료구조는 `realtime`(11)이 소유한다.
- 핸들러 예외 격리: warning + 감사로그, 3회 연속 시 해당 가드 비활성 + critical (정본: 01 §2.4). 연속 실패 카운터는 `execution` 소유의 `execution_state`에 영속화된다(정본: 01 §3.5 — 복원은 §5.3).
- **`order_lock`**: 주문 생성·제출과 순매수 회계는 단일 `asyncio.Lock` 안에서 원자적으로 실행된다(정본: 01 §1.4-2). 락 객체는 `execution`이 소유하고([08](08-execution.md) §order_lock 정본), 허용되는 유일한 중첩 획득은 **`order_lock` → `token_lock`**이다. 역순(`token_lock` 보유 중 `order_lock` 대기)과 그 밖의 락 중첩을 금지한다. 프로세스 간 토큰 파일락 `/app/var/db/.token.lock`은 별개 층이다(정본: 01 §5.1).

### 4.4 이벤트 루프 보호 규율

단일 루프 점유가 이 설계의 최대 실질 위험이다(정본: 01 §9.2). 완화 5종(T1 집행 창 한정 / 호가 구독 최소화 / 큐 비대칭 / blocking 금지 / 예외 격리)은 계획이 정본이고, 이 문서는 **blocking 금지의 구현 규칙**을 확정한다:

1. WS 핸들러·fill_consumer·웹 핸들러에서 동기 I/O·CPU 연산(파싱 초과분) 금지. import-linter가 대부분 막고(§8), 나머지는 [16](16-testing-and-quality.md)의 리뷰 체크리스트 항목이다.
2. 스케줄러 잡 내부의 CPU-bound 수치 단계(LW 공분산·MVO·몬테카를로)는 `asyncio.to_thread()`로 오프로드한다.

> **[DD-01-4] 스케줄러 잡의 CPU-bound 단계는 `asyncio.to_thread` 오프로드**
> - 결정: `monthly_targets_batch`·`mc_projection`의 수치 단계는 `await asyncio.to_thread(pure_fn, …)`로 실행한다. 조건 2개 — ① 오프로드 대상은 `engine`의 순수 함수만(공유 상태 접근 없음) ② `order_lock` 보유 중 오프로드 금지.
> - 근거: 업비트 ticker T0 채널은 24/7이므로(정본: 01 §4.2) 03:30 배치 중에도 루프는 살아 있어야 한다. `engine`은 순수 함수 계층(정본: 01 §2)이라 스레드 오프로드가 안전하다. 백테스트처럼 "수 분~수십 분 점유"가 아니므로 tools로 뺄 대상은 아니다(배제 기준 정본: 01 §1.6).
> - 계획 문서와의 관계: 충돌 없음 — 계획 01 §9.2 "핸들러에 blocking 연산 금지"를 잡 계층까지 연장한 구현 세부다.

3. 시간 예산은 취소가 아니라 **협조적 체크포인트**로 강제한다(정본: 01 §1.4-3). 체크포인트 헬퍼는 `scheduler`(12)가 소유한다.
4. SQLite 쓰기 트랜잭션은 잡별 짧은 세션, 트랜잭션 연 채 `await` 금지, `SQLITE_BUSY`는 tenacity 3회 (정본: 01 §1.4-4).

### 4.5 워치독과 자발적 종료

Docker restart policy는 `unhealthy`에 반응하지 않으므로(정본: 01 §6.4) **"프로세스가 죽지 않고 응답만 멈추는" 실패는 봇 내부 워치독이 자발적 종료로 변환**해야 restart가 발동한다.

```python
# monitoring 소유 로직을 runtime 태스크로 배선 (항목 정의 정본: 01 §6.4 / 12)
async def watchdog_task(ctx: BotContext) -> None:
    consecutive = 0
    while True:
        lag_ms = await measure_loop_lag()            # asyncio 타이머 오차 실측
        hb_age = heartbeat_age_sec(ctx)
        if lag_ms > ctx.cfg.watchdog.loop_lag_exit_ms or \
           hb_age > ctx.cfg.watchdog.heartbeat_max_age_sec:     # 180s / 5000ms (정본: 01 §6.4)
            consecutive += 1
        else:
            consecutive = 0
        if consecutive >= ctx.cfg.watchdog.consecutive:          # 3 (정본: 01 §6.4)
            append_restart_mark()                    # [DD-01-14] — os._exit 전 마커 기록
            os._exit(1)                              # 의도적 비정상 종료 → restart: unless-stopped 발동
        await asyncio.sleep(ctx.cfg.watchdog.interval_sec)
```

- `os._exit(1)`은 **의도적으로 graceful shutdown을 건너뛴다** — 루프가 이미 멈춘 상태에서 협조적 정리를 기다리는 것은 모순이다. 정합성은 persist-then-submit(정본: 01 §3.2)과 재기동 강제 대사(03 §3)가 회복한다. F21(SIGKILL 주입)이 같은 경로를 검증한다.
- 크래시 루프 방지: 10분 내 자발적 종료 3회 초과 → 재기동 후 셀프체크가 `STOPPED` 고정 + critical (정본: 01 §6.4, 구현은 §5.2 SC-3).

> **[DD-01-14] 자발적 종료 마커 파일**
> - 결정: `os._exit(1)` 직전에 `var/db/restart_marks.jsonl`에 `{ts, reason, lag_ms, hb_age}` 1행을 동기 append(fsync)한다. 기동 셀프체크 SC-3이 이 파일에서 최근 10분 창의 자발적 종료 횟수를 센다.
> - 근거: 계획 01 §6.4의 "10분 내 자발적 종료 3회 초과" 판정은 재시작을 넘는 영속 카운터를 요구하는데, 그 시점의 프로세스는 DB 트랜잭션을 신뢰할 수 없다(루프 정지 상태). 파일 append는 이벤트 루프와 무관한 동기 연산이라 실패 표면이 최소다. Docker `RestartCount`는 `os._exit` 외 원인(OOM 등)과 구분되지 않아 쓰지 않는다.
> - 계획 문서와의 관계: 충돌 없음 — 카운터의 물리 위치라는 여백을 채운다.

### 4.6 검증 항목

- 태스크 카탈로그 스냅샷 테스트: 기동 후 상시 태스크 이름 집합 == §4.1의 9종 (신규 상시 태스크의 무단 추가를 차단).
- `fill_queue` drop 불가: 인위적 소비 지연 하에 1만 건 주입 → 전량 소비 단정.
- 가드 핸들러에서 예외 3연속 → 해당 가드 비활성 + critical, 디코더 생존 단정 (01 §2.4).
- watchdog: 루프에 동기 sleep 주입 → 연속 3회 초과 시 `os._exit(1)` 경로 진입(테스트에서는 exit 함수를 주입으로 대체), 마커 파일 기록 확인.
- `order_lock`→`token_lock` 순서 위반 탐지(락 래퍼에 순서 단정 삽입, 위반 시 테스트 실패).

## 5. 기동 시퀀스와 기동 셀프체크

### 5.1 기동 단계 (의사코드)

```
A. DB 이전 단계
   A1  data/KILL 존재 여부 확인 → 존재 시: 목표 상태 = STOPPED, 마이그레이션 금지 플래그 셋
       (정본: 03 §2.6 "루프 진입부에서 무조건 STOPPED", 01 §1.3)
   A2  config 로드·스키마 검증(fail-fast). env: live면 `live_confirmation`
       "<계좌 뒤 4자리>-I-UNDERSTAND" 3중 일치 검사 — 불일치 시 기동 거부(프로세스 종료,
       상태 기록 없음) (정본: 03 §5.1-2, 01 §6.1)
B. DB·마이그레이션
   B1  SQLite open — WAL·busy_timeout=5000·synchronous=NORMAL (정본: 01 §1.3)
   B2  bot_state 단일 행 읽기 (없으면 최초 기동 — dry_run은 RUNNING, live 최초 기동은
       SAFE_MODE로 시작: [DD-01-11])
   B3  KILL 없고 상태 ≠ STOPPED 일 때만 alembic upgrade head(단일 헤드 검증).
       스킵됐는데 스키마 불일치면: STOPPED 유지 + critical (마이그레이션은 사람이
       KILL 제거·/resume 후 재기동 시 수행) (정본: 01 §1.3)
C. 컴포넌트 조립 (네트워크 I/O 없음 — §3.2)
D. 기동 셀프체크 (§5.2 표의 순서대로. 실패 시 §5.4 분류에 따라 처리)
E. 강제 대사 — 대사 통과 전 주문 금지 (셀프체크 SC-11로 포함. 정본: 03 §3)
F. 잡 등록 + catch-up 판정 (선언적 재등록 — 01 §1.4. 3분류 판정 정본: 01 §4.2.1, 구현: 12)
G. 상시 태스크 기동 (§4.1 — 복원된 상태와 무관하게 전부)
H. 상태 확정 — effective_state를 감사로그 state_transition으로 기록, 브리핑 채널에
   "재기동: 상태 X 복원, 셀프체크 결과 요약" info 발송
```

상태 복원 원칙: **상태는 언제나 DB가 정본이다**(정본: 03 §3 "프로세스 재시작" 행). 셀프체크는 상태를 임의로 개선하지 않는다 — `HALTED`로 죽었으면 `HALTED`로 깨어난다. 셀프체크가 상태를 **악화**시키는 것(→ `SAFE_MODE`/`STOPPED`)만 허용된다.

> **[DD-01-11] 최초 기동(상태 행 부재)의 초기 상태**
> - 결정: `bot_state` 행이 없으면 `dry_run`/`paper`는 `RUNNING`, `live`는 `SAFE_MODE`로 생성한다.
> - 근거: live 최초 기동은 03 §5.1 전환 절차의 첫 주 `manual_approve: true` 구간과 겹친다 — 보수적 시작이 "의식적 마찰" 원칙과 정합한다. 계획은 최초 상태를 정의하지 않았다.
> - 계획 문서와의 관계: 충돌 없음. `SAFE_MODE` 이탈은 03 §2.1대로 `/resume`이므로 사용자가 명시적으로 평시 진입을 선언하게 된다.

### 5.2 셀프체크 항목 카탈로그 (정본 조합: 03 §3 + 01 §6.4 + 01 §4.2.1 + 07 §8·§10)

실행 순서 = 표 순서. 각 항목은 `SelfCheckItem`으로 등록되며 결과는 감사로그와 `/healthz`에 남는다.

| ID | 항목 | 내용 | 실패 분류(§5.4) | 정본 |
|---|---|---|---|---|
| SC-1 | config | 스키마·상호 제약 검증, live 3중 일치 (phase A에서 선행 실행되지만 항목으로 계상) | FATAL-EXIT | 01 §6.1, 03 §5.1 |
| SC-2 | 스키마 | alembic 현재 리비전 == head, 단일 헤드 | FATAL-STOP | 01 §1.3 |
| SC-3 | 크래시 루프 | `restart_marks.jsonl` 최근 10분 자발적 종료 > 3 → `STOPPED` 고정 + critical | FATAL-STOP | 01 §6.4 |
| SC-4 | 토큰 | 브로커 토큰 캐시 유효성(캐시 재사용 우선, 없으면 1회 발급 시도. EGW00133 시 70초 대기 1회) | LADDER | 01 §5.1 |
| SC-5 | 캘린더 | XKRX·XNYS 캘린더 로드 + 오늘 세션 판정 가능. KIS 휴장일 TR 교차검증은 `daily_planner` 소관이므로 여기서는 캐시 존재·신선도만 | LADDER | 01 §4.1 |
| SC-6 | **카나리 복원** | 진행 중 카나리 α 단계를 DB에서 복원(아래 §5.3-a) | LADDER | 01 §1.3, 07 §8, 03 §3 |
| SC-7 | 예산 복원 | 변경 예산 카운터(연간 total/하위) 복원·정합 검사(소진 시 A3 강등 상태 재적용) | LADDER | 01 §1.3, 00 §3.2 |
| SC-8 | 외부 스케줄 재전개 | `external_expectations_sync` 1회 실행 — 당월+익월 30일분을 멱등 키로 전개 | LADDER | 01 §4.2, 03 §1.3.1 |
| SC-9 | **가드 예산 복원** | 당일 `run_date`의 연기 횟수·누적 연기 분·시장 단위 `ABORT`·가드 연속 실패 카운터 복원(§5.3-b) | LADDER | 01 §3.5, 03 §3·§4.3 F22 |
| SC-10 | catch-up 커버리지 | 등록된 모든 잡이 catch-up 3분류 표의 한 행에 속함(속하지 않으면 실패) | FATAL-STOP | 01 §4.2.1 |
| SC-11 | **강제 대사** | 잔고·미체결 대조. 선행: `SUBMITTING` 고아 주문 흡수(튜플 매칭 ±5분, `kind=orphan_order` 화이트리스트 — 절차 정본: 01 §3.2/[08](08-execution.md)). 불일치 시 자가치유 사다리 3회([09](09-safety-protections.md)) | LADDER→`HALTED` | 03 §3, 01 §3.2 |
| SC-12 | 재현성 불변식(R5) | 직전 세션의 섀도 불일치·스냅샷 회귀 실패 플래그 존재 시 롤백 트리거 R5 통지([14](14-research-and-labs.md)) | DEGRADE | 07 §10 R5 |
| SC-13 | 자격증명 배치 | **app**: 필수 시크릿 존재(브로커·Telegram 또는 SMTP). **tools**: 브로커·Telegram·SMTP 자격증명 **부재** 확인 — 존재하면 즉시 종료 | FATAL-EXIT | 01 §1.6, §6.1 |

```python
# src/omra/runtime/selfcheck.py
class CheckClass(StrEnum):
    FATAL_EXIT = "fatal_exit"    # 프로세스 종료(상태 기록 없음) — config/자격증명 오류
    FATAL_STOP = "fatal_stop"    # STOPPED로 기동 고정 + critical
    LADDER = "ladder"            # 자기복구 사다리 경로 (§5.5)
    DEGRADE = "degrade"          # 기동은 계속, 해당 서브시스템 통지·강등

@dataclass(frozen=True)
class SelfCheckItem:
    id: str
    check: Callable[[BotContext], Awaitable[CheckOutcome]]
    on_fail: CheckClass

@dataclass(frozen=True)
class BootResult:
    effective_state: BotState        # 복원 상태에 셀프체크 결과(악화만)를 반영한 최종값
    outcomes: list[CheckOutcome]     # 감사로그·브리핑 요약의 입력

async def run_selfcheck(ctx: BotContext, *, kill: bool,
                        prev: BotState | None, migrated: bool) -> BootResult: ...
```

### 5.3 복원 절차 2건 — 훅 시그니처

**(a) 진행 중 카나리 복원** (SC-6). 카나리 α 단계·변경 예산은 run ledger와 별개 테이블로 영속화되어 있다(정본: 01 §1.3). 재시작이 α를 리셋하면 전 단계를 건너뛰고 α=1이 적용될 수 있으므로(정본: 07 §8) 복원은 기동의 필수 관문이다.

```python
# labs 소유 로직의 기동 훅 (블렌딩 로직 정본: 14-research-and-labs.md §canary)
class CanaryRestoreResult(BaseModel, frozen=True):
    active: list[ActiveCanary]       # 필드명 = 03 §3.3.10 `canary_state` DDL 컬럼명 그대로:
                                     #   (change_id, target_kind, ladder_json, step_index,
                                     #    alpha_current, step_started_on, state)
    consistent: bool                 # 원장 이벤트와 카운터의 정합 여부

async def restore_canaries(repo: BudgetRepo, clock: Clock) -> CanaryRestoreResult:
    """① repos.budget.active_canaries()로 활성 카나리 행 로드 (03 §4.3)
       ② 각 행의 α 단계(`step_index`)가 사다리(`ladder_json` — 1/3→2/3→1 × 5거래일 등,
          값 정본: 01 §8.2)상 유효한지 검증
       ③ 경과 거래일 계산은 '재시작 시점'이 아니라 `step_started_on` 기준 — 재시작이
          단계 시계를 되돌리지 않는다
       ④ 정합 실패(원장 이벤트와 카운터 불일치) → consistent=False → LADDER 처리"""
```

`ActiveCanary`의 필드명은 **03 §3.3.10 `canary_state` DDL 컬럼명과 문자 단위로 같다**(요청: [14](14-research-and-labs.md) §22 #17 — 훅 반환 타입이 DDL과 다른 이름을 쓰면 복원 코드가 이름 매핑을 한 곳 더 갖는다). 14 §14.2~§14.3의 `restore()`가 이 계약의 구현이다.

복원된 `active` 목록은 `engine.rebalancer`가 실효 목표비중을 계산할 때 α 블렌딩 입력으로 소비한다(소비 설계: [07](07-portfolio-engine.md), 카나리 로직: [14](14-research-and-labs.md)).

**(b) 당일 가드 예산·시장 ABORT 복원** (SC-9). 카운터의 소유자는 `execution`이고 저장 키는 `(run_date, venue, instrument_key, counter_kind, value)`다(정본: 01 §3.5).

```python
# execution 소유 로직의 기동 훅 (카운터 의미론 정본: 08-execution.md)
async def restore_guard_budgets(repo: ExecutionStateRepo, clock: Clock) -> GuardBudgetSnapshot:
    """venue별 '현지 거래일' 기준 오늘 run_date의 카운터 전량 로드.
       복원 실패 시 보수 방향: 카운터를 0이 아니라 **상한 소진 상태로 가정**한다 —
       상한이 조용히 무효화되는 것(F22가 막으려는 사고)보다 당일 보수적 집행이 낫다."""
```

### 5.4 실패 분류와 처리

| 분류 | 처리 | 근거 |
|---|---|---|
| `FATAL_EXIT` | 프로세스 즉시 종료(exit 2). Docker는 재기동하지만 같은 이유로 다시 죽는다 — 사람이 config를 고쳐야 하는 오류를 상태 기계로 흡수하지 않는다 | 03 §5.1 "기동 거부" |
| `FATAL_STOP` | `STOPPED`로 기동 고정 + critical. 태스크는 §4.2대로 전부 기동(모니터링·`/resume` 경로 유지) | 01 §6.4 크래시 루프, 01 §4.2.1 커버리지 불변식 |
| `LADDER` | §5.5 자기복구 사다리로 진입 | 03 §3 |
| `DEGRADE` | 기동 계속 + 해당 서브시스템 강등·통지(예: R5 → labs 롤백 트리거) | 07 §10 |

### 5.5 자기복구 사다리와의 결합 (정본: 01 §6.4, 03 §3)

사다리 (a)~(e)를 기동 관점으로 구현하면:

```
(a) Docker restart          — 이미 일어난 사건(우리가 지금 기동 중인 이유)
(b) 기동 셀프체크           — §5.2. LADDER 항목 실패 시 항목별 1회 재시도 후 (c)로
(c) 대사 자가치유 3회       — SC-11 한정. 수량 일치 조건 자가치유(정본: 03 §1.3, 구현: 09)
(d) SAFE_MODE 강등          — (b)(c)로 해소되지 않는 비무결성 실패(토큰·캘린더·카나리 정합):
                              effective_state = 더 제한적인(복원 상태, SAFE_MODE)
(e) HALTED + 일 1회 재시도  — 무결성 실패(대사 불일치 지속): HALTED 기동, 스케줄러가
                              일 1회 SC-11만 재실행(주 1회만 알림)
최종: 사다리 전 단계 실패   — STOPPED (정본: 03 §3 "기동 셀프체크 실패 → 최종 STOPPED")
```

`(d)`의 "더 제한적인" 결합은 09의 5축 결합 구현을 호출한다 — 이 문서는 호출 지점만 정의한다.

### 5.6 검증 항목

- 부팅 매트릭스: {KILL 유무} × {prev ∈ RUNNING/SAFE_MODE/PAUSED/HALTED/STOPPED/행 부재} × {셀프체크 전 항목 성공/항목별 실패} 조합에서 effective_state가 §5.1 원칙("악화만 허용")을 위반하지 않음(property-based).
- F21: 제출 직후 SIGKILL → 재기동 → SC-11에서 고아 주문 흡수, P8 미발동 (정본: 03 §4.3 F21).
- F22: 집행 창 도중 재시작 → SC-9 복원으로 가드 예산 누적 유지 (정본: 03 §4.3 F22).
- 카나리 복원: 재시작 전후 α 단계·잔여 거래일 동일(07 §14 체크리스트 항목과 동일).
- SC-13 tools 변형: `.env.tools`에 `KIS_APP_KEY`를 주입하면 기동 실패.
- 마이그레이션 스킵 경로: KILL 존재 + 구 스키마 → STOPPED 기동 + critical, 어떤 DDL도 실행되지 않음.

## 6. 종료 시퀀스 · RELOAD_CONFIG

### 6.1 graceful shutdown (SIGTERM/SIGINT/`RELOAD_CONFIG` 공용)

```python
# src/omra/runtime/shutdown.py
@dataclass(frozen=True)
class ShutdownBudget:
    total_sec: float = 30.0          # [DD-01-5]
    jobs_sec: float = 10.0           # 실행 중 잡의 협조적 종료 대기
    ws_sec: float = 5.0              # T1 구독 해제 + graceful close
    drain_sec: float = 5.0           # fill_queue 드레인

async def graceful_shutdown(ctx, sup, reason) -> None:
    # 1. 신규 발화 차단: scheduler.pause() — 이미 실행 중인 잡은 협조적 체크포인트가
    #    shutdown 이벤트를 보고 스스로 종료(이미 커밋된 부분은 유효 — 정본: 01 §1.4-3)
    # 2. 실행 중 잡 대기 (jobs_sec). 초과 시 태스크 취소 — 부분 완료는 재기동 대사가 회수
    # 3. T1 구독 전량 해제 시도(tr_type="2") → WS 3소켓 graceful close (ws_sec)
    #    실패해도 진행 — WS는 진실원이 아니다 (정본: 01 §5.3 불변식 1)
    # 4. telegram·web 태스크 정지
    # 5. fill_queue 드레인 (drain_sec). 미소비 잔량은 로그로 남기고 폐기 —
    #    체결의 정본은 REST 대사이므로 유실이 아니다 (정본: 01 §5.3 불변식 1)
    # 6. audit flush(fsync) → DB close
    # 상태 저장 단계는 없다 — 상태 전이는 발생 시점에 이미 커밋되어 있다 (03 §2.1 저장 규칙)
```

> **[DD-01-5] 종료 시간 예산 30초 / compose `stop_grace_period: 40s`**
> - 결정: 내부 예산 합계 30초, Docker `stop_grace_period`는 40초(내부 예산 + 10초 마진). 초과 시 Docker의 SIGKILL을 그대로 수용한다.
> - 근거: 계획에 종료 예산 수치가 없다. SIGKILL로 죽어도 정합성이 회복된다는 것이 persist-then-submit + 강제 대사(01 §3.2, 03 §3)의 설계 보장이므로, 예산은 "보통의 경우 깔끔하게"를 위한 값이면 충분하다.
> - 계획 문서와의 관계: 충돌 없음.

### 6.2 비정상 종료 경로

| 경로 | 정리 수준 | 정합성 회복 수단 |
|---|---|---|
| watchdog `os._exit(1)` (§4.5) | 없음(의도) | 재기동 강제 대사 + persist-then-submit |
| SIGKILL(OOM·`docker kill`) | 없음 | 동일. F21이 최악 지점(제출 직후)을 검증 |
| 미처리 예외로 태스크 `ESCALATE` | graceful shutdown 시도 후 exit 1 | restart policy 재기동 |

### 6.3 RELOAD_CONFIG 재생성 시퀀스 (정본: 03 §2.1·§6.3)

```
1. /reload_config 수신 → 상태 RELOAD_CONFIG 전이(전이 자체가 매수·매도 전면 차단 —
   5축 표의 RELOAD_CONFIG 행, 정본: 03 §2.1) + 감사로그
2. graceful_shutdown(§6.1) — 프로세스는 유지, Worker 루프가 ExitReason.RELOAD 수신
3. 새 config 로드·검증(fail-fast)
   실패 시 → [DD-01-6]: 새 config 폐기, 직전 유효 config로 Bot 재생성 + critical
4. Bot 재생성 → 기동 셀프체크 전체 실행(§5 — 대사 포함. external_schedules.yaml 해시가
   변했으면 SC-8이 재전개를 수행한다 — 정본: 03 §6.3-3)
5. 직전 상태로 복원 — 복원 소스는 bot_state.prev_state (컬럼 정본: 03 §3.2.1 [DD-03-27],
   갱신·복귀 규칙 정본: 09 §7.4 전이표). since는 시각이므로 복원 소스가 아니다
   (복원 요건 자체의 정본: 계획 03 §2.1)
```

> **[DD-01-6] RELOAD 시 config 검증 실패의 처리**
> - 결정: 새 config가 검증에 실패하면 직전 유효 config로 Bot을 재생성하고 critical을 발송한다. 직전 config마저 로드 불가(파일 훼손)면 `FATAL_EXIT`.
> - 근거: fail-safe 방향(00 §5-5) — 설정 오타 하나가 운용 정지가 되어서는 안 된다. 03 §3의 "실패는 안전한 쪽으로: 직전 상태 유지" 패턴과 동형이다.
> - 계획 문서와의 관계: 충돌 없음 — 계획은 RELOAD 실패 경로를 정의하지 않았다.

### 6.4 kill 파일·`/panic` 상호작용

- `data/KILL`은 기동 phase A1과 **모든 잡 발화 직전**(스케줄러 디스패치 래퍼, 12 구현)에서 검사한다 — "루프 진입부에서 무조건 STOPPED"(정본: 03 §2.6)의 구현 지점 2곳.
- `/panic` → 미체결 전량 취소 → `STOPPED` DB 영속 → critical (정본: 03 §2.6). 프로세스는 종료하지 않는다 — `STOPPED`에서도 태스크는 전부 살아 있다(§4.2).
- `STOPPED` 탈출: KILL 제거 선행 → `/resume <당일 확인코드>` → 목적지 `SAFE_MODE` (정본: 03 §2.6). 전이 구현은 09.

### 6.5 검증 항목

- SIGTERM 수신 → 30초 내 exit 0, fill_queue 드레인·audit fsync 완료 로그 확인.
- RELOAD 중 상태: 재생성 완료까지 신규 주문 0건(5축 RELOAD_CONFIG 행 준수), 완료 후 `bot_state.prev_state` 값으로 직전 상태 복원(컬럼 정본: [03](03-data-and-persistence.md) §3.2.1 [DD-03-27], 복귀 규칙: [09](09-safety-protections.md) §7.4 전이표).
- RELOAD에 깨진 YAML 주입 → 직전 config로 운용 계속 + critical([DD-01-6]).
- F17: `/panic` → `STOPPED` 영속, 재시작 후에도 `STOPPED`, KILL 제거+`/resume` 후 `SAFE_MODE` (정본: 03 §4.3 F17).

## 7. Docker Compose 배포 토폴로지

### 7.1 docker-compose.yml (계획 01 §1.6을 완성형으로)

계획 01 §1.6의 골격·주석을 그대로 유지하고, 계획이 문장으로 요구한 항목(non-root·read-only·tmpfs — 01 §1.6/§7-6)과 이 문서의 DD 추가분을 반영한 완성본:

```yaml
name: omra

services:
  app:            # 봇 엔진 + 스케줄러 + FastAPI + Telegram + T0 WS (단일 프로세스 — 00 §5-1)
    build: .
    image: "omra:${OMRA_TAG:-dev}"          # [DD-01-10] 태깅 §7.2
    init: true                               # PID 1 시그널 전달 (graceful shutdown 전제)
    restart: unless-stopped
    stop_grace_period: 40s                   # [DD-01-5]
    user: "1000:1000"                        # non-root (정본: 01 §7-6)
    read_only: true
    tmpfs: [/tmp]
    env_file: [.env]                         # 시크릿 (chmod 600, git 제외 — 01 §6.1)
    environment:
      - OMRA__RUNTIME__ROLE=app              # SC-13 자격증명 배치 검사의 입력
    volumes:
      - ./config:/app/config:ro
      - omra-db:/app/var/db                  # SQLite + 토큰 파일락 + restart_marks
      - omra-data:/app/var/data              # Parquet + RO 스냅샷 + 실험 결과 JSON + KILL
      - omra-logs:/app/var/logs              # 운영 로그 + 감사로그
      - omra-policy:/app/var/policy          # 잡 산출 정책물 (targets/universe) — rw
    ports:
      - "100.x.y.z:8080:8080"                # Tailscale 인터페이스에만 바인딩 (01 §7-1)
    healthcheck:                             # 관측 전용 — 재시작을 유발하지 않는다(§7.4)
      test: ["CMD", "python", "-m", "omra.cli", "health"]   # 호출 형식 정본: 01 §1.6
      interval: 60s
      timeout: 10s
      retries: 3
    logging:                                 # [DD-01-13] stdout 로그 상한
      driver: json-file
      options: { max-size: "50m", max-file: "3" }

  litestream:     # SQLite 실시간 복제 (RPO≈초 — 01 §6.5)
    image: litestream/litestream
    restart: unless-stopped
    depends_on: [app]
    command: replicate -config /etc/litestream.yml
    user: "1000:1000"
    read_only: true
    env_file: [.env.litestream]              # 오브젝트 스토리지 키만
    volumes:
      - omra-db:/app/var/db                  # 복제 대상 (01 §1.6)
      - ./config/litestream.yml:/etc/litestream.yml:ro

  tools:          # 일회성 실행 전용 (백테스트·챌린저 G2). 상시 기동 없음 (01 §1.6)
    build: .
    image: "omra:${OMRA_TAG:-dev}"
    profiles: ["tools"]                      # 기본 up 대상에서 제외
    user: "1000:1000"
    read_only: true
    tmpfs: [/tmp]
    env_file: [.env.tools]                   # 브로커·Telegram·SMTP 키 없음 (01 §1.6·§6.1)
    environment:
      - OMRA__RUNTIME__ROLE=tools            # SC-13이 자격증명 '부재'를 강제
    volumes:
      - ./config:/app/config:ro
      - omra-data:/app/var/data              # 스냅샷 읽기 + 결과 쓰기
      - omra-logs:/app/var/logs
      # omra-db는 마운트하지 않는다 — §7.3 스냅샷 경로 (정본: 01 §1.6)

volumes:
  omra-db: {}
  omra-data: {}
  omra-logs: {}
  omra-policy: {}
```

> **[DD-01-13] stdout 로그 로테이션 상한**
> - 결정: json-file 드라이버 50MB × 3. 파일 로그(14일 로테이션 — 01 §6.3)와 별개로 Docker 레이어의 디스크 잠식을 막는다.
> - 근거: 계획 O3(00 §3.2)의 "디스크·로그 자가관리"는 앱 파일 로그만 다룬다. 컨테이너 stdout은 Docker가 관리하므로 여기서 상한을 고정해야 한다.
> - 계획 문서와의 관계: 충돌 없음.

Compose에 없는 것(의도): 사이드카(autoheal 등 — `/var/run/docker.sock`을 주지 않는다, 정본: 01 §6.4), Redis/메시지큐/PostgreSQL(정본: 00 §5-1·§6.3), 상시 tools.

### 7.2 Dockerfile·이미지 태깅·롤백

```dockerfile
# Dockerfile — 2-stage. uv 바이너리 공급 방식은 [확인 필요]: uv 공식 문서의
# 권장 고정 태그(COPY --from=ghcr.io/astral-sh/uv:<버전>)를 빌드 시점에 확정한다.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project     # 의존성 레이어 캐시
COPY src/ src/
RUN uv sync --frozen --no-dev                          # 프로젝트 설치

FROM python:3.12-slim
RUN groupadd -g 1000 omra && useradd -u 1000 -g 1000 -m omra
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY config/ /app/config/                              # 기본값만 — 런타임엔 :ro 마운트가 덮음
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER omra
CMD ["python", "-m", "omra.cli", "run"]                # 호출 형식 정본: 01 §1.6
```

> **[DD-01-10] 이미지 태깅·롤백 규칙**
> - 결정: 배포 스크립트가 `omra:<git-short-sha>`로 빌드하고 `.env`의 `OMRA_TAG`를 갱신한다. 직전 태그는 `OMRA_TAG_PREV`로 보관한다. 롤백 = `OMRA_TAG=$OMRA_TAG_PREV docker compose up -d app` 1줄.
> - 근거: 03 §6.3-4 "롤백: 직전 이미지 태그로 즉시 복귀"와 01 §1.3 "다운그레이드 미지원(롤백은 직전 이미지 태그 + Litestream 복원)"이 태그 보존을 전제하는데 태깅 규칙 자체는 계획에 없다. `latest` 단일 태그는 직전 이미지를 파괴하므로 배제.
> - 계획 문서와의 관계: 충돌 없음. 단 DB 마이그레이션이 이미 적용된 뒤의 코드 롤백은 구 코드×신 스키마 조합이 되므로, 스키마 변경이 낀 롤백은 Litestream 시점 복원과 함께 수행한다(절차 정본: 03 §6.3, 복원 구현: [03](03-data-and-persistence.md)).

배포 절차 자체(CI green → 장 마감 후 pull·빌드 → 재시작 → 셀프체크 통과 확인)의 정본은 03 §6.3이며, runbook 구조화는 [12](12-scheduling-and-operations.md)가 소유한다. **O2 = A5: 자동 배포(CD)는 금지다**(정본: 00 §3.2 O2, §6.2).

### 7.3 tools 실행 경로 — 스냅샷 읽기와 단방향 적재 (정본: 01 §1.6, 07 §13)

```
[읽기]  app: weekly_maintenance 및 backtest 실행 직전
            → VACUUM INTO '/app/var/data/snapshots/omra-ro.sqlite'   (일관 스냅샷)
        tools: 그 스냅샷만 읽는다. 결과 파일에 스냅샷 나이(mtime·원본 체크포인트)를 기록
        (omra-db 볼륨은 tools에 존재하지 않는다 — :ro WAL 리더의 조건부 실패 회피)

[쓰기]  tools → var/data/experiments/<run_id>.json              (omra-data 볼륨)
        app  → `python -m omra.cli experiment ingest <path>`    (사람이 실행)
             → persistence.repos.experiments                     (DB 쓰기 주체는 언제나 app)
        ※ 이 적재를 스케줄러 잡으로 자동화하려면 [12]의 잡 카탈로그와 catch-up 3분류
          표(01 §4.2.1)에 먼저 등재되어야 한다 — 미등재 잡은 SC-10 커버리지 불변식에
          걸린다. 계획 01 §4.2 잡 표에는 해당 잡이 없으므로 이 문서는 CLI 경로만 확정한다.

[기동]  docker compose run --rm tools python -m omra.cli backtest …
        기동 주체는 사람 또는 호스트 cron — 봇 스케줄러가 아니다 (정본: 01 §1.6)
```

스냅샷 생성 시그니처(잡 구현은 12, 호출 계약만 여기서 고정):

```python
async def make_ro_snapshot(db: Engine, dest: Path) -> SnapshotMeta:
    """VACUUM INTO로 일관 스냅샷 생성. 반환 메타(생성 시각·원본 DB 페이지 수)는
       tools 결과 파일에 복사되어 재현성 근거가 된다 (정본: 01 §1.6)."""
```

- 스냅샷이 없거나 나이가 임계를 넘으면 `backtest`는 **실행을 거부**하고 "app에서 스냅샷 먼저 생성"을 안내한다([DD-01-12]).
- tools의 네트워크는 차단하지 않는다(리서치 수집기 — 정본: 01 §1.6). 격리의 실체는 **자격증명 부재**(SC-13)다.

> **[DD-01-12] tools 스냅샷 신선도 임계 = config `tools.snapshot_max_age_h`, 기본 168h**
> - 결정: 스냅샷 나이가 임계를 넘으면 tools CLI가 실행을 거부한다. 기본값 168h는 `weekly_maintenance`(일요일 03:00 — 정본: 01 §4.2) 주기와 같다. 키는 [04](04-configuration-and-secrets.md) 스키마에 등록한다.
> - 근거: 계획 01 §1.6은 "스냅샷 나이는 결과 파일에 기록해 재현성을 보장한다"까지만 정하고 **낡은 스냅샷으로 검증 게이트를 도는 것**을 막지 않는다. 스냅샷 생성 주체가 `weekly_maintenance`이므로 그 주기가 자연스러운 상한이다.
> - 계획 문서와의 관계: 충돌 없음 — 기록 요건에 거부 임계를 더한다.

### 7.4 healthcheck 의미론 (정본: 01 §6.4)

- `health`(CLI)는 loopback `http://127.0.0.1:8080/healthz`를 조회해 exit 0/1을 반환한다 — 이벤트 루프가 실제로 응답하는지를 검사하는 것이 목적이므로 프로세스 존재 확인으로 대체하지 않는다. `/healthz` 항목 구성(heartbeat 나이·DB 쓰기·토큰·loop lag·WS 상태·감시 신선도)의 정본은 01 §6.4이고 구현은 [12](12-scheduling-and-operations.md).
- **healthcheck는 관측 전용이다.** `unhealthy`는 재시작을 유발하지 않으며(Docker 문서화된 동작 — 정본: 01 §6.4), 재시작 유발은 §4.5 워치독의 자발적 종료가 담당한다. 이 역할 분리를 주석으로 compose에 명시한다.

### 7.5 검증 항목

- `docker compose up` → 헬스체크 응답(M0 DoD — 정본: 04 §2 M0).
- `read_only: true` 하에서 전 볼륨 쓰기 경로 정상(쓰기는 named volume으로만 — 위반 시 즉시 크래시로 발견된다).
- tools에서 `omra-db` 접근 시도 → 경로 부재로 실패(마운트 자체가 없음을 compose config 스냅샷 테스트로 고정).
- 롤백 리허설: `OMRA_TAG_PREV`로 재기동 → 셀프체크 통과 → 상태 복원.
- litestream 컨테이너가 `.env`(브로커 키 포함)가 아닌 `.env.litestream`만 로드함을 compose config로 단정.

## 8. import-linter 계약 파일 구현

### 8.1 2층 구조와 초크포인트 (정본: 01 §2.2)

- **① 기계 강제(import-linter)** — 아래 §8.2의 `[forbidden]` 계약. 열거되지 않은 간선의 기본값은 **허용**이다(정본: 01 §2.2 "계약 타입 표기").
- **② 쓰기 권한 강제(패키지 분할)** — 쓰기는 `persistence.repos.*` 테이블별 리포지토리로만. 관측 4레이어는 `persistence.ro` + 자신의 허용 repo만 import 가능. "RO"는 주석이 아니라 import 가능 모듈 집합이다.

이를 위해 `persistence`의 모듈 경계를 다음과 같이 고정한다(내부 설계는 [03](03-data-and-persistence.md) 소유, **경계 좌표는 계약이 참조하므로 이 문서가 고정**):

- `omra.persistence.session` — **rw 세션 팩토리. 유일한 쓰기 세션 공급원**이며 관측 4레이어에게 금지된다.
- `omra.persistence.ro` — 읽기 전용 세션 팩토리.
- `omra.persistence.repos.<table>` — 테이블별 쓰기 리포지토리(내부적으로 `session`을 import).

#### 8.1.1 repos 모듈 열거 (계약 열거의 입력)

**모듈명의 정본은 [03](03-data-and-persistence.md) §2.1 파일 트리다**(repos 화이트리스트 소유 = 03 — 브리프 §2.1). 아래 표는 그 트리를 §8.2 금지 열거의 입력으로 옮긴 것이며, **쓰기 허용 주체**만 이 문서가 계약 관점에서 고정한다. 03 트리에 모듈이 추가·개명되면 같은 커밋에서 이 표와 §8.2 C04b·C05b·C07b를 갱신해야 하고, 누락은 AT-1이 CI에서 차단한다([DD-01-7]).

| repos 모듈 (03 §2.1 트리) | 쓰기 허용 주체 | 근거 |
|---|---|---|
| `research_extractions` | `research`만 | 01 §2 |
| `surveillance_flags` | `surveillance`만 | 01 §2 |
| `pending_tax_events` | `surveillance`만 | 01 §2 |
| `experiments` | `labs`만 (`experiments`·`experiment_events` 양 테이블, append-only, DB 트리거) | 01 §2, §1.3 |
| `budget` | `labs`만 (`canary_state`·`change_budget`) | 01 §2 |
| `execution_state` | `execution`만 (가드 예산) | 01 §3.5 |
| `protections` | `protections`만 (`protection_state`·`protection_counters`) | [09](09-safety-protections.md) [DD-09-4], 03 §2.2 |
| `orders` · `fills` · `plans` · `reconcile` | `execution` | 03 §2.1·§2.2. `reconcile` = `reconcile_expectations` |
| `positions` · `nav_snapshots` · `decomposition` · `satellite` | `portfolio` | 03 §2.2. `decomposition`은 [07](07-portfolio-engine.md) [DD-07-10] |
| `pending_transfers` | `tax`(행 생성·슬라이스 산출) · `execution`(상태 전이·`slices_done` 진행) | [08](08-execution.md) §14.1, [10](10-tax-engine.md) §2.3 |
| `tax_events` | `tax` (`tax_events`·`taxbase_snapshots` 등 세금 원장 계열 — TABLES 정본: 03 §4.3) | 03 §2.2 |
| `run_ledger` · `holidays` · `notifications` | `scheduler` (`holidays` 접근 API는 `calendar` — 06 [DD-06-10]) | 03 §2.2 |
| `state` | 상태머신(09) · `runtime`(기동 시 상태 확정) — `bot_state`·`sleeve_state`·`presence` | 03 §4.3, 09 §2.3 |
| `policy_versions` | `scheduler`(정책물 버전 확정 잡) | 03 §2.1 |
| `approvals` | `rpc`(A3 큐 결정·만료) — `approval_requests`. 요청 행 생성은 각 기능 모듈이 같은 repo로 수행한다(예: `tax`의 `kind='harvest_y1'`·`'e5_transfer'` — 03 §3.3.9 [DD-03-12]) | [13](13-web-and-telegram.md) §2.2 [DD-13-1]·§5 |
| `tokens` | `brokers`(TokenManager) — `broker_tokens` | 01 §5.1 |

> **[DD-01-7] repos 모듈 좌표는 03 트리를 따른다 + 완전열거 동기화 테스트**
> - 결정: ① repos 모듈명의 정본은 03 §2.1 트리이며, 01은 그 이름을 **그대로** §8.2 금지 열거에 옮긴다(이 문서가 이름을 새로 만들지 않는다). ② 아키텍처 테스트 **AT-1**이 `persistence/repos/*.py` 파일 집합과 §8.2 C04b·C05b·C07b의 금지 열거 집합을 **양방향** 대조해, 어느 한쪽에만 있으면 CI를 실패시킨다(대조 집합에서 `base.py`·`__init__.py`는 테이블 쓰기 모듈이 아니므로 제외 — 판정 구현은 [16](16-testing-and-quality.md) §6.1).
> - 근거: 계획 01 §2.2는 "열거되지 않은 모듈은 전부 금지줄로 명시(완전열거)"를 요구한다. 초판은 `states`·`broker_tokens`·`reconcile_expectations`·`tax_ledger`라는 **03에 존재하지 않는 이름**을 열거하고 `plans`·`holidays`·`approvals`·`nav_snapshots`·`decomposition`·`satellite`·`notifications`·`protections` 8개를 빠뜨려, 관측 3레이어가 그 8개를 default-allow로 import할 수 있었다(03 §2.1 말미가 지적한 정합 항목). ③ import-linter의 forbidden 매칭 의미론은 도구 버전 의존이다 — **[확인 필요]: 하위 모듈(descendant) 자동 포함·와일드카드 지원 여부, 그리고 `forbidden` 계약이 간접(전이) import까지 위반으로 보는지**(후자가 기본값이면 `research → repos.research_extractions → persistence.session` 같은 정당한 체인이 오탐이 되므로 해당 계약에 `allow_indirect_imports`를 켜야 한다). 확인 방법은 공식 문서 + M0 CI에서 위반 커밋 실차단(AT-7). 확인 결과와 무관하게 AT-1이 열거 누락을 기계적으로 막으므로 default-allow 구멍은 생기지 않는다.
> - 계획 문서와의 관계: 충돌 없음 — 완전열거 요구의 집행 메커니즘을 채운다.

### 8.2 계약 파일 전문 (`pyproject.toml [tool.importlinter]`)

계획 01 §2.2 원문이 **유일 원문**이며, 아래 **C01~C07b·C10·C11은 그것의 1:1 기계 번역**이다. 차이가 발견되면 계획 01 §2.2가 이기고 이 파일을 고친다. **C08·C09·C12~C15는 각 소유 설계서가 자기부과한 추가 봉인**으로, 계획이 default-allow로 남긴 간선을 좁히기만 한다([DD-01-15] — 등재 근거·요청 출처는 그 블록의 표). 주석의 C·번호는 추적용이다.

> **[DD-01-8] 설정 위치 = `pyproject.toml`, 그리고 "brokers → 전략"의 열거 확정**
> - 결정: ① 계약은 별도 `.importlinter` 파일이 아니라 `pyproject.toml`에 둔다(단일 설정 파일 — uv·ruff와 일관). ② 01 §2.2의 "brokers → engine · 전략 금지"에서 '전략'을 다음으로 확정 열거한다: `engine, execution, tax, protections, portfolio, data, collectors, surveillance, realtime, research, labs, backtest, scheduler, rpc, web, monitoring, runtime, cli`. 즉 brokers가 import할 수 있는 1차 패키지는 `core, config, audit, persistence(repos.tokens·session), calendar`뿐이다(모듈명 정본: 03 §2.1 — `tokens` = `broker_tokens` 테이블).
> - 근거: "브로커는 전략을 모른다"(01 §2.2)의 의도는 brokers를 최하층으로 못박는 것이다. 열거형 금지가 default-allow 하에서 그 의도를 기계화하는 유일한 방법이다. `calendar`는 주문 TR의 시장 세션 판정에 필요할 수 있어 허용측에 남긴다.
> - 계획 문서와의 관계: 충돌 없음 — 원문의 축약어를 집행 가능한 목록으로 펼쳤다.

**금지줄 생성 규칙**(계획 01 §2.2 "각 레이어의 허용 집합은 아래 목록이 완전열거"의 기계화): 봉인 대상 레이어의 `forbidden_modules`는 **`omra.*` 1차 패키지 전체 − 허용 목록 − 자기 자신**이다. 단 **허용이 서브모듈 단위로 주어진 경우**(계획 01 §2.2가 `surveillance.gate`·`data.quote`·`brokers.*.ws.events`처럼 점 표기로 적은 것)에는 1차 패키지를 통째로 허용으로 취급하지 않고 **비허용 서브모듈을 열거해 금지**한다 — C05a(`brokers.*.client`)·C06a(`surveillance.*`·`data.*`)가 그 방식이다. 열거하지 않으면 default-allow가 나머지 서브모듈을 조용히 연다. 아래 두 예외는 명시적으로 금지하지 않은 항목이다.

- `omra.config`는 `research`·`surveillance`의 허용 목록에 없지만 금지줄에 넣지 않았다 — `config/surveillance.yaml`(감시 등급 매핑, 정본: 01 §2)이 `surveillance`의 직접 입력이고 `research`도 LLM 예산·모델 키를 읽어야 한다. 계획 01 §2.2가 `realtime`·`labs`에만 `config`를 적은 것이 **의도인지 누락인지는 [확인 필요]**(계획 개정 사항, §11-12).
- `omra.core`는 `labs`의 허용 목록에 없지만 같은 이유로 금지하지 않는다(도메인 타입 없이는 실험 원장 레코드를 만들 수 없다).

`research`·`surveillance`·`realtime`의 `engine` 금지는 **패키지 전체**다 — 계획 01 §2.2는 `engine.optimizer`·`engine.rebalancer`(·`expected_returns`)를 명시하지만 04 §2 M1이 "'관측 계층 → `engine` 금지'는 정확히는 `research · surveillance · realtime -/-> engine`"으로 확정했고, 01 §2.2의 허용 목록에도 `engine`이 없다(`labs`만 순수함수 호출 허용).

> **[DD-01-15] 소유 문서가 자기부과한 금지줄의 계약 파일 등재 — C08·C09·C12·C13·C14·C15**
> - 결정: 계획 01 §2.2가 봉인하지 않아 default-allow였던 6개 소스에 대해 아래 계약을 등재한다. 각 줄의 **의미론적 소유자는 요청 문서**이고 이 문서는 계약 파일의 형식만 소유한다 — 간선을 넓혀야 하면 계약이 아니라 요청 문서의 DD를 먼저 고친다.
>
>   | 계약 | 소스 → 금지 | 요청 출처 |
>   |---|---|---|
>   | C08 | `data` → `engine`·`execution`·`protections`·`realtime`·`surveillance`·`labs`·`research` | [06](06-market-data-and-calendar.md) §2 [DD-06-1] |
>   | C09 | `protections` → `execution`·`brokers.*.client`·`engine.optimizer`·`engine.rebalancer` | [09](09-safety-protections.md) §2.3 [DD-09-2] |
>   | C12 | `web` → `execution`·`brokers`·`engine`·`tax`·`protections` | [13](13-web-and-telegram.md) §2.4 [DD-13-2] |
>   | C13 | `rpc` → `web` | [13](13-web-and-telegram.md) §2.4 [DD-13-2] |
>   | C14 | `backtest` → `brokers`·`execution`·`rpc`·`web`·`scheduler`·`realtime` (`runtime`은 C11이 이미 봉인) | [15](15-backtest-and-validation.md) §2 [DD-15-16] |
>   | C15 | `tax` → 아래 C15 열거 (허용 = `core`·`config`·`calendar`·`data`·`audit`·`persistence.ro`+자기 repo) | [10](10-tax-engine.md) §2.1 [DD-10-2] |
>
> - 근거: 네 문서가 자기 격리를 "설계 규율"로 선언했는데 계약이 침묵하면 **강제 수단 표기가 사실과 달라진다** — 특히 13 §9.1은 하드 규칙 "'지금 매매' 버튼을 만들지 않는다"의 강제 수단을 "import-linter + 폼 검사 테스트"로 적어 두었고, C12 없이는 `web → execution`이 현재 설계상 허용이었다. 15 [DD-15-16]의 `labs → backtest → execution` 우회 경로, 09 [DD-09-2]의 "차단 판정기가 주문 생성기를 호출" 순환도 같은 성격의 구멍이다. 등재하지 않는 대안은 요청 문서 4곳의 DD를 모두 반려하는 것인데, 반려할 근거(계획이 그 간선을 허용으로 선언했다는 사실)가 어느 줄에도 없다.
> - 계획 문서와의 관계: 충돌 없음. 계획 01 §2.2의 "관측 4레이어만 금지줄로 봉인한다"는 **당시 계약 목록의 서술**이고, 같은 절이 "열거되지 않은 간선의 기본값은 허용"이라고 규정하므로 추가 금지줄은 계획이 **허용으로 선언한 간선**을 제거하지 않는 한 원문과 모순되지 않는다. 실제로 이 6개 계약 중 계획의 허용 줄과 겹치는 간선은 하나도 없다(`execution·protections·engine.rebalancer → surveillance.gate`, `execution·protections → tax`, `execution → realtime`, `realtime → data.quote`, `labs → backtest`, `labs → protections`는 전부 그대로 유효).

```toml
[tool.importlinter]
root_packages = ["omra"]

# ── 코어 방향 규율 (01 §2.2) ─────────────────────────────────────────
[[tool.importlinter.contracts]]
name = "C01 engine은 brokers를 모른다"
type = "forbidden"
source_modules = ["omra.engine"]
forbidden_modules = ["omra.brokers"]

[[tool.importlinter.contracts]]
name = "C02 brokers는 전략을 모른다 [DD-01-8]"
type = "forbidden"
source_modules = ["omra.brokers"]
forbidden_modules = [
  "omra.engine", "omra.execution", "omra.tax", "omra.protections",
  "omra.portfolio", "omra.data", "omra.collectors",
  "omra.surveillance", "omra.realtime", "omra.research", "omra.labs",
  "omra.backtest", "omra.scheduler", "omra.rpc", "omra.web",
  "omra.monitoring", "omra.runtime", "omra.cli",
]

# ── collectors — 중립 프레임워크: core·audit 외 전부 금지 (01 §2.2) ──
[[tool.importlinter.contracts]]
name = "C03 collectors는 core·audit만 안다"
type = "forbidden"
source_modules = ["omra.collectors"]
forbidden_modules = [
  "omra.brokers", "omra.config", "omra.calendar", "omra.data",
  "omra.engine", "omra.tax", "omra.execution", "omra.protections",
  "omra.portfolio", "omra.persistence", "omra.scheduler", "omra.rpc",
  "omra.web", "omra.research", "omra.labs", "omra.backtest",
  "omra.monitoring", "omra.surveillance", "omra.realtime", "omra.runtime",
  "omra.cli",
]

# ── research — LLM 격리 (01 §2.2) ────────────────────────────────────
[[tool.importlinter.contracts]]
name = "C04a research 기능 격리"
type = "forbidden"
source_modules = ["omra.research"]
forbidden_modules = [
  "omra.execution", "omra.brokers", "omra.engine", "omra.tax",
  "omra.surveillance",                       # prompt injection 격리
  "omra.protections", "omra.scheduler", "omra.web", "omra.rpc",
  "omra.backtest", "omra.labs", "omra.realtime", "omra.portfolio",
  "omra.calendar", "omra.monitoring", "omra.runtime", "omra.cli",
]

[[tool.importlinter.contracts]]
name = "C04b research 쓰기 화이트리스트 = repos.research_extractions 뿐"
type = "forbidden"
source_modules = ["omra.research"]
# 열거 = 03 §2.1 repos 트리 전체 − {research_extractions}. AT-1이 양방향 대조한다.
forbidden_modules = [
  "omra.persistence.session",                       # rw 세션 금지 (§8.1 초크포인트)
  "omra.persistence.repos.experiments",             # 01 §2.2 명시
  "omra.persistence.repos.budget",                  # 01 §2.2 명시
  "omra.persistence.repos.surveillance_flags",      # 01 §2.2 명시
  "omra.persistence.repos.pending_tax_events",
  "omra.persistence.repos.execution_state", "omra.persistence.repos.protections",
  "omra.persistence.repos.orders", "omra.persistence.repos.fills",
  "omra.persistence.repos.positions", "omra.persistence.repos.plans",
  "omra.persistence.repos.reconcile", "omra.persistence.repos.pending_transfers",
  "omra.persistence.repos.tax_events", "omra.persistence.repos.run_ledger",
  "omra.persistence.repos.state", "omra.persistence.repos.policy_versions",
  "omra.persistence.repos.tokens", "omra.persistence.repos.holidays",
  "omra.persistence.repos.approvals", "omra.persistence.repos.nav_snapshots",
  "omra.persistence.repos.decomposition", "omra.persistence.repos.satellite",
  "omra.persistence.repos.notifications",
]

# ── surveillance — 감시는 주문하지 않는다 (01 §2.2) ──────────────────
[[tool.importlinter.contracts]]
name = "C05a surveillance 기능 격리"
type = "forbidden"
source_modules = ["omra.surveillance"]
forbidden_modules = [
  "omra.research",                            # prompt injection 격리
  "omra.execution",
  "omra.brokers.kis.client", "omra.brokers.upbit.client",   # brokers.*.client 금지
  "omra.engine",                              # 01 §2.2는 optimizer·rebalancer 명시,
                                              # 04 §2 M1이 engine 전체로 확정
  "omra.tax",
  "omra.rpc", "omra.web", "omra.labs", "omra.backtest",
  "omra.protections", "omra.scheduler", "omra.runtime",
  "omra.realtime",                            # 허용 방향은 realtime → surveillance.gate 뿐
  "omra.portfolio", "omra.monitoring", "omra.calendar", "omra.cli",
]

[[tool.importlinter.contracts]]
name = "C05b surveillance 쓰기 화이트리스트 = flags·pending_tax_events 뿐"
type = "forbidden"
source_modules = ["omra.surveillance"]
# 열거 = 03 §2.1 repos 트리 전체 − {surveillance_flags, pending_tax_events}
forbidden_modules = [
  "omra.persistence.session",
  "omra.persistence.repos.experiments", "omra.persistence.repos.budget",
  "omra.persistence.repos.research_extractions",    # 01 §2.2 명시
  "omra.persistence.repos.execution_state", "omra.persistence.repos.protections",
  "omra.persistence.repos.orders", "omra.persistence.repos.fills",
  "omra.persistence.repos.positions", "omra.persistence.repos.plans",
  "omra.persistence.repos.reconcile",
  "omra.persistence.repos.pending_transfers",        # E7 불변식 1(02 §5.6)의 기계화 —
                                                     #   감시는 이전 지시를 만들지 않는다
  "omra.persistence.repos.tax_events", "omra.persistence.repos.run_ledger",
  "omra.persistence.repos.state", "omra.persistence.repos.policy_versions",
  "omra.persistence.repos.tokens", "omra.persistence.repos.holidays",
  "omra.persistence.repos.approvals", "omra.persistence.repos.nav_snapshots",
  "omra.persistence.repos.decomposition", "omra.persistence.repos.satellite",
  "omra.persistence.repos.notifications",
]

# ── realtime — 축소 방향 전용 (01 §2.2) ──────────────────────────────
[[tool.importlinter.contracts]]
name = "C06a realtime 기능 격리 — 스스로 주문·조회하지 않는다"
type = "forbidden"
source_modules = ["omra.realtime"]
forbidden_modules = [
  "omra.execution",
  "omra.brokers.kis.client", "omra.brokers.upbit.client",
  "omra.engine",                              # 01 §2.2는 optimizer·rebalancer·
                                              # expected_returns 명시, 04 §2 M1이 전체로 확정
  "omra.tax",
  "omra.research", "omra.labs", "omra.backtest", "omra.rpc",
  "omra.web", "omra.scheduler", "omra.protections", "omra.portfolio",
  "omra.collectors", "omra.monitoring", "omra.runtime",
  "omra.calendar", "omra.cli",
  # ★ 01 §2.2의 realtime 허용은 **서브모듈 단위**다(`surveillance.gate` · `data.quote`).
  #   패키지 전체를 허용으로 두면 default-allow가 나머지 서브모듈을 조용히 열어 준다 —
  #   `surveillance.flags`는 C06b(상태 쓰기 금지)를 우회하는 경로가 되고,
  #   `data.providers`는 06 §1-4 "data.quote가 realtime의 유일한 REST 경로"를 무효화한다.
  #   C05a가 `brokers.*.client`에 쓴 것과 같은 서브모듈 열거 방식으로 봉인한다.
  "omra.surveillance.flags", "omra.surveillance.sources",
  "omra.surveillance.catalog", "omra.surveillance.models",
  "omra.data.providers", "omra.data.store", "omra.data.fetchers",
]

[[tool.importlinter.contracts]]
name = "C06b realtime은 어떤 상태도 쓰지 않는다 — persistence 전체 금지"
type = "forbidden"
source_modules = ["omra.realtime"]
forbidden_modules = ["omra.persistence"]      # ro 포함 — 허용 목록(01 §2.2)에 ro가 없다

# ── labs — 실험은 주문을 낼 수 없다 (01 §2.2) ────────────────────────
[[tool.importlinter.contracts]]
name = "C07a labs 기능 격리"
type = "forbidden"
source_modules = ["omra.labs"]
forbidden_modules = [
  "omra.execution", "omra.brokers", "omra.rpc", "omra.research",
  "omra.collectors",                          # labs는 수집하지 않는다
  "omra.surveillance", "omra.realtime", "omra.tax",
  "omra.web", "omra.scheduler", "omra.calendar", "omra.monitoring",
  "omra.runtime", "omra.portfolio", "omra.cli",
]

[[tool.importlinter.contracts]]
name = "C07b labs 쓰기 화이트리스트 = experiments·budget 뿐"
type = "forbidden"
source_modules = ["omra.labs"]
# 열거 = 03 §2.1 repos 트리 전체 − {experiments, budget}
forbidden_modules = [
  "omra.persistence.session",
  "omra.persistence.repos.research_extractions",    # 01 §2.2 명시
  "omra.persistence.repos.surveillance_flags",      # 01 §2.2 명시
  "omra.persistence.repos.pending_tax_events",
  "omra.persistence.repos.execution_state", "omra.persistence.repos.protections",
  "omra.persistence.repos.orders", "omra.persistence.repos.fills",
  "omra.persistence.repos.positions", "omra.persistence.repos.plans",
  "omra.persistence.repos.reconcile", "omra.persistence.repos.pending_transfers",
  "omra.persistence.repos.tax_events", "omra.persistence.repos.run_ledger",
  "omra.persistence.repos.state", "omra.persistence.repos.policy_versions",
  "omra.persistence.repos.tokens", "omra.persistence.repos.holidays",
  "omra.persistence.repos.approvals", "omra.persistence.repos.nav_snapshots",
  "omra.persistence.repos.decomposition", "omra.persistence.repos.satellite",
  "omra.persistence.repos.notifications",
]

# ── data — 공급 계층은 판단 계층을 모른다 [DD-01-15] (요청: 06 [DD-06-1]) ──
[[tool.importlinter.contracts]]
name = "C08 data는 판단 계층을 import하지 않는다"
type = "forbidden"
source_modules = ["omra.data"]
forbidden_modules = [
  "omra.engine", "omra.execution", "omra.protections", "omra.realtime",
  "omra.surveillance", "omra.labs", "omra.research",
]

# ── protections — 차단 판정기는 주문 생성기를 부르지 않는다 [DD-01-15] (요청: 09 [DD-09-2]) ──
[[tool.importlinter.contracts]]
name = "C09 protections는 집행·목표산출을 import하지 않는다"
type = "forbidden"
source_modules = ["omra.protections"]
forbidden_modules = [
  "omra.execution",
  "omra.brokers.kis.client", "omra.brokers.upbit.client",
  "omra.engine.optimizer", "omra.engine.rebalancer",
]
# 허용은 그대로다: protections → surveillance.gate · tax · calendar
#                   · persistence.ro · persistence.repos.{state,protections} (09 §2.3)

# ── Σ_monitor 분리 (정본: 02 §3.2 "optimizer에서 import 불가") ────────
[[tool.importlinter.contracts]]
name = "C10 Σ_monitor는 목표비중 산출에 닿지 않는다 [DD-01-9]"
type = "forbidden"
source_modules = ["omra.engine.optimizer", "omra.engine.rebalancer",
                  "omra.engine.expected_returns"]
forbidden_modules = ["omra.engine.covariance_monitor"]

# ── composition root 격리 [DD-01-1] ──────────────────────────────────
[[tool.importlinter.contracts]]
name = "C11 runtime은 엔트리포인트 전용"
type = "forbidden"
source_modules = [
  "omra.core", "omra.config", "omra.calendar", "omra.brokers",
  "omra.collectors", "omra.surveillance", "omra.realtime", "omra.data",
  "omra.engine", "omra.tax", "omra.execution", "omra.protections",
  "omra.portfolio", "omra.persistence", "omra.scheduler", "omra.rpc",
  "omra.web", "omra.research", "omra.labs", "omra.backtest",
  "omra.audit", "omra.monitoring",
]
forbidden_modules = ["omra.runtime"]

# ── web·rpc — 웹에 주문 경로를 만들지 않는다 [DD-01-15] (요청: 13 [DD-13-2]) ──
[[tool.importlinter.contracts]]
name = "C12 web은 주문·평가 계층을 import하지 않는다"
type = "forbidden"
source_modules = ["omra.web"]
forbidden_modules = [
  "omra.execution", "omra.brokers", "omra.engine", "omra.tax", "omra.protections",
]
# 웹의 쓰기 경로는 omra.rpc.commands 하나뿐이고 읽기는 persistence.ro다 (13 §2.4)

[[tool.importlinter.contracts]]
name = "C13 rpc → web 단방향 고정"
type = "forbidden"
source_modules = ["omra.rpc"]
forbidden_modules = ["omra.web"]

# ── backtest — tools 프로세스 격리의 코드 레벨 절반 [DD-01-15] (요청: 15 [DD-15-16]) ──
[[tool.importlinter.contracts]]
name = "C14 backtest는 브로커·집행·운영 계층을 import하지 않는다"
type = "forbidden"
source_modules = ["omra.backtest"]
forbidden_modules = [
  "omra.brokers", "omra.execution", "omra.rpc", "omra.web",
  "omra.scheduler", "omra.realtime",     # omra.runtime은 C11이 이미 봉인
]

# ── tax 자기 제한 [DD-01-15] (요청: 10 [DD-10-2]) ─────────────────────
[[tool.importlinter.contracts]]
name = "C15 tax 자기 제한 — 허용은 core·config·calendar·data·audit·persistence(ro+자기 repo)"
type = "forbidden"
source_modules = ["omra.tax"]
forbidden_modules = [
  "omra.execution", "omra.brokers", "omra.engine", "omra.protections",
  "omra.portfolio", "omra.collectors", "omra.surveillance", "omra.realtime",
  "omra.research", "omra.labs", "omra.backtest", "omra.scheduler",
  "omra.rpc", "omra.web", "omra.monitoring", "omra.runtime", "omra.cli",
]
# 소비 방향(execution·protections → tax)은 계획 01 §2.2 허용 그대로다 —
# 산출물은 execution이 '가져간다'(10 §2.1).
```

허용 간선(01 §2.2의 "허용" 줄들 — `execution·protections·engine.rebalancer → surveillance.gate`, `execution → realtime`, `execution → persistence.repos.execution_state`, `realtime → data.quote`, `surveillance → brokers.*.ws.events` 등)은 **계약이 필요 없다** — default-allow이므로 금지줄에 없다는 사실 자체가 허용이다. 문서화 목적으로 계약 파일 상단 주석에 원문 링크만 남긴다.

> **[DD-01-9] `Σ_monitor` 좌표 = `omra/engine/covariance_monitor.py`**
> - 결정: EWMA 모니터링 공분산(Σ_monitor)을 `covariance.py`(Σ_strategic)와 별도 모듈로 분리한다. 계약 C10이 소비 방향을 봉인한다.
> - 근거: 02 §3.2 "Σ_monitor는 engine/optimizer.py에서 import 불가하도록 import-linter로 강제(01 §2)" — import-linter는 모듈 단위로만 검사하므로 같은 파일 안의 두 함수를 구분할 수 없다. 분리는 강제의 전제 조건이다. `rebalancer`·`expected_returns`를 소스에 추가한 것은 "목표 산출 경로 전체"라는 02 §3.2의 취지를 기계화한 확장이다.
> - 계획 문서와의 관계: 충돌 없음 — 02의 요구를 실행 가능하게 만드는 좌표 결정.

**단계 활성화**: `labs` 관련 계약(C07a/b)은 M10a 착수 시 활성화한다(정본: 04 §2 M1 — "labs 관련 계약은 M10a 착수 시 활성화"). 다만 §2.4의 이유(계약이 참조하는 모듈은 존재해야 한다)로 `labs/` 패키지는 M0부터 빈 패키지로 존재하므로, **계약 자체는 M0부터 전량 등록해도 무해하다** — 빈 패키지는 위반 간선을 가질 수 없다. 따라서 구현은 "전량 등록"을 기본으로 하고, 활성화 단계 구분은 문서 관점의 마일스톤 표기로만 남긴다(04 M1 "계약 전량을 CI에 등록"과 정합).

### 8.3 계약이 못 막는 것 — 보완 메커니즘 (구현: [16](16-testing-and-quality.md))

| ID | 항목 | 왜 import-linter로 안 되는가 | 보완 |
|---|---|---|---|
| AT-1 | repos 완전열거 동기화 | default-allow — 새 repo 파일이 자동 허용됨 | `persistence/repos/*.py` 파일 집합 ↔ C04b·C05b·C07b 금지 열거의 **양방향** 대조 테스트(`base.py`·`__init__.py` 제외, 각 열거는 "전체 − 해당 레이어 화이트리스트"와 일치해야 한다 — [DD-01-7], 구현: [16](16-testing-and-quality.md) §6.1) |
| AT-2 | persist-then-submit | 호출 순서는 간선이 아니다 | 아키텍처 테스트로 강제 (정본: 01 §3.2-1) |
| AT-3 | `guard.oneway` — `sides` 축소만 | 값 공간 제약 | property-based (정본: 01 §3.5) |
| AT-4 | realtime의 장운영 필드 소비 금지 | 같은 events 모듈의 필드 구분 불가 | `MarketStatus` 타입을 `realtime.guards` 시그니처에서 배제 + 테스트 (정본: 01 §2.3) |
| AT-5 | catch-up 커버리지 불변식 | 런타임 등록 정보 | CI + 기동 셀프체크 SC-10 (정본: 01 §4.2.1) |
| AT-6 | RateLimiter 불변식 4종 | 수치 불변식 | CI 아키텍처 테스트 (정본: 01 §5.2, 구현: 05) |
| AT-7 | 계약 실차단 검증 | 계약 파일 오등록은 조용히 통과 | 위반 커밋을 의도적으로 만들어 CI 실패 확인 (정본: 07 §14 체크리스트) |
| — | **프로세스 경계 격리** | import는 프로세스를 넘지 못한다 | `.env.tools` 자격증명 부재 + SC-13 (정본: 01 §1.6) |

### 8.4 검증 항목

- `lint-imports` CI green이 M0 DoD (정본: 04 §2 M0).
- AT-7: `realtime`에서 `omra.execution`을 import하는 커밋 → CI 실패 실증.
- AT-1: ① `persistence/repos/new_table.py` 추가 후 계약 미갱신 → CI 실패 실증 ② 계약에만 있고 파일이 없는 모듈을 넣어도 CI 실패(양방향 대조).
- C11: `web`에서 `omra.runtime` import 시도 → 실패.
- [DD-01-15] 신설 계약의 실차단 실증 6건: `data → omra.engine`(C08) · `protections → omra.execution`(C09) · `web → omra.execution`(C12, 13 §9.1 하드 규칙의 강제 수단) · `rpc → omra.web`(C13) · `backtest → omra.brokers`(C14) · `tax → omra.execution`(C15) 각각의 위반 커밋이 `lint-imports`를 실패시킨다.
- C04b/C05b/C07b 열거 == 03 §2.1 트리 − 해당 레이어 화이트리스트(집합 비교. 이름이 03과 어긋나면 AT-1이 먼저 실패한다).

## 9. 계획 문서 추적표

| 계획 조항 | 이 문서의 반영 위치 | 비고 |
|---|---|---|
| 00 §5-1 단일 프로세스·단일 진실원 | §3 | Worker/Bot 2층으로 구체화 |
| 00 §5-9 관측 계층 봉인 (import-linter) | §8.2 C04~C07 | |
| 00 §6.3 EventBus·구독 사다리 배제 | §4.3 | fill_queue 단일 큐 |
| 01 §1.3 SQLite 파라미터·마이그레이션 정책 | §5.1 B, §7.2 | alembic 내부는 03 |
| 01 §1.3 영속성 요건 2건(카나리·예산) | §5.2 SC-6/SC-7, §5.3-a | |
| 01 §1.4 동시성 규율 4항 | §4.3, §4.4 | order_lock 상세는 08, 잡 기본값은 12 |
| 01 §1.6 Docker Compose·tools 격리·스냅샷 경로 | §7.1~§7.3 | |
| 01 §2 저장소 구조 | §2.1 | runtime/ 추가는 [DD-01-1] |
| 01 §2.1 패키지 4종 배치 근거 | §2.1 트리 주석 | 근거 서술은 계획 참조로 대체 |
| 01 §2.2 import-linter 계약 (유일 원문) | §8.2 C01~C07b·C10·C11 | 1:1 기계 번역, 충돌 시 계획 우선. 금지줄은 "1차 패키지 − 허용 목록"으로 생성 |
| 01 §2.2 ② repos 완전열거(“열거되지 않은 모듈은 전부 금지줄로 명시”) | §8.1.1 표, §8.2 C04b·C05b·C07b | 모듈명 정본은 03 §2.1 트리. 동기화 강제는 AT-1([DD-01-7]) |
| 01 §2.2 “열거되지 않은 간선의 기본값은 허용” 여백 | §8.2 C08·C09·C12·C13·C14·C15 | 소유 문서 자기부과분의 등재 — [DD-01-15] (출처: 06·09·13·15·10) |
| 04 §2 M1 "관측 계층 → engine 금지 = research·surveillance·realtime" | §8.2 C04a/C05a/C06a | `labs`는 engine 순수함수 허용이므로 제외 |
| 01 §2.3 거래정지·VI 단일 소유권 | §4.3 배선, §8.3 AT-4 | 판정은 11 |
| 01 §2.4 decoder 직접 호출 + Fill 큐 | §4.3 | |
| 01 §3.2 persist-then-submit·고아 주문 | §5.2 SC-11, §8.3 AT-2 | 프로토콜 정본은 08 |
| 01 §3.5 가드 예산 execution 영속화·복원 | §5.2 SC-9, §5.3-b | |
| 01 §4.2 `realtime_t0` 상시 잡 | §4.1 T-04~T-06 | 잡 시각표는 12 |
| 01 §4.2.1 catch-up 3분류·커버리지 불변식 | §5.1 F, §5.2 SC-10 | 판정 구현은 12 |
| 01 §5.1 TokenManager 파일락·기동 선제 갱신 | §4.3 락 순서, §5.2 SC-4 | 구현은 05 |
| 01 §5.3 세션 생명주기·재연결·폴백 등가성 | §4.1 SELF 정책, §4.3 배선(`start_delay` 3초 순차 재연결의 조율자) | 구현은 05 [DD-01-17] |
| 01 §6.1 설정 계층·시크릿 3분할·입력/산출 분리 | §7.1 env_file·볼륨 | 스키마는 04 |
| 01 §6.2 시크릿 만료 대장·자동 조치 | §7.5 검증, 감시 잡은 12 | |
| 01 §6.4 watchdog·자발적 종료·크래시 루프·자기복구 사다리 | §4.5, §5.2 SC-3, §5.5, §7.4 | |
| 01 §6.5 Litestream 구성·VACUUM 충돌 | §7.1 litestream 서비스 | 백업·복구 절차는 03 |
| 01 §9.2 단일 루프 안정성 완화 5종 | §4.4 | |
| 03 §2.1 상태 2계층·전이·RELOAD_CONFIG | §3.1, §6.3 | 5축 결합 구현은 09 |
| 03 §2.6 Kill Switch·data/KILL·STOPPED 탈출 | §6.4 | 명령 카탈로그는 13 |
| 03 §3 fail-safe 표(재시작 행·셀프체크 실패 행) | §5.1~§5.5 | |
| 03 §4.3 F17·F21·F22 | §5.6, §6.5 검증 항목 | 시나리오 구현은 16 |
| 03 §5.1 live 3중 일치·manual_approve | §5.1 A2, [DD-01-11] | |
| 03 §6.3 배포 절차·롤백 | §7.2 | 절차 정본 유지, 태깅만 DD |
| 06 §12 모듈 설계·계약 발췌 | §8.2 | 발췌와 어긋나면 01 §2.2가 이긴다(계획 명시) |
| 07 §8 카나리 α 영속·복원 | §5.2 SC-6, §5.3-a | 블렌딩 로직은 14 |
| 07 §10 R5(재현성 불변식) 기동 검출 | §5.2 SC-12, §5.4 DEGRADE | 트리거 정본 유지 |
| 07 §13 실험 원장 단방향 적재 | §2.3 CLI, §7.3 | 원장 로직은 14 |
| 04 §2 M0/M1 DoD (compose up·CI green·계약 전량 등록) | §2.4, §7.5, §8.4 | 로드맵은 범위를 자르지 않음(브리프 §0) |

## 10. 설계 결정(DD) 목록

| ID | 제목 | 위치 |
|---|---|---|
| DD-01-1 | `omra.runtime` 패키지 신설 — composition root 좌표·entrypoint 전용 격리 | §2.1, §8.2 C11 |
| DD-01-3 | `fill_queue` 무제한 + 고수위 경보 1,000건 | §4.3 |
| DD-01-4 | 스케줄러 잡 CPU-bound 단계의 `asyncio.to_thread` 오프로드 | §4.4 |
| DD-01-5 | 종료 시간 예산 30초 / `stop_grace_period` 40초 | §6.1 |
| DD-01-6 | RELOAD 시 config 검증 실패 → 직전 유효 config로 재생성 + critical | §6.3 |
| DD-01-7 | 코어 repos 모듈 좌표 고정 + 열거 동기화 테스트(AT-1) | §8.1.1 |
| DD-01-8 | 계약 위치 = pyproject.toml, "brokers → 전략" 열거 확정 | §8.2 |
| DD-01-9 | `Σ_monitor` 좌표 = `engine/covariance_monitor.py` + 계약 C10 | §8.2 |
| DD-01-10 | 이미지 태깅 `omra:<git-sha>` + `OMRA_TAG_PREV` 롤백 포인터 | §7.2 |
| DD-01-11 | 최초 기동 초기 상태: dry_run/paper=RUNNING, live=SAFE_MODE | §5.1 |
| DD-01-12 | tools 스냅샷 신선도 임계 `tools.snapshot_max_age_h`(기본 168h) 미달 시 실행 거부 | §7.3 |
| DD-01-13 | 컨테이너 stdout 로그 로테이션 상한(50MB×3) | §7.1 |
| DD-01-14 | 자발적 종료 마커 파일(`restart_marks.jsonl`)로 크래시 루프 카운트 | §4.5 |
| DD-01-15 | 소유 문서 자기부과 금지줄의 계약 등재(C08 data·C09 protections·C12 web·C13 rpc·C14 backtest·C15 tax) | §8.2 |
| DD-01-16 | CLI 카탈로그 추가 2종 — `config validate`(J9 진입점)·`research probe`(tools 전용) | §2.3 |
| DD-01-17 | decoder 핸들러·장중 여부 술어·WS `start_delay` 배선의 단일 지점 = `runtime/bot.py` phase C | §4.3 |

> **DD-01-2는 결번이다** — 정합화 과정에서 다른 항목에 통합·폐기됐다. 타 문서에서 `DD-01-2`를 인용하는 곳은 없다(전 설계서 검색 0건). 뒤 번호를 앞당기지 않는 이유는 15건의 상호 참조를 동시에 갱신해야 하고, 재번호 자체가 인용 오류의 원인이 되기 때문이다.

## 11. 미해결 항목·스파이크 종속

| # | 항목 | 종속 | 영향 |
|---|---|---|---|
| 1 | **[확인 필요]** import-linter `forbidden` 계약의 ① descendant 매칭·와일드카드 지원 ② **간접(전이) import를 위반으로 보는지**(기본값이 그렇다면 `research → repos.research_extractions → persistence.session` 같은 정당한 체인이 오탐이므로 C04b·C05b·C07b에 `allow_indirect_imports`를 켜야 한다) — 공식 문서 + M0 위반 커밋 실차단(AT-7)으로 확인 | M0 | ①은 확인 결과와 무관하게 AT-1이 default-allow 구멍을 막지만, 지원되면 §8.2의 열거를 와일드카드로 축약 가능. ②는 계약 3개의 옵션 1줄 |
| 2 | **[확인 필요]** uv 바이너리 공급 이미지의 버전 고정 태그 — uv 공식 문서로 확인 | M0 | Dockerfile 1행 |
| 3 | **[확인 필요]** python-telegram-bot v21의 기존 루프 임베드 API 형태(폴링 태스크 통합) — 공식 문서/실측 | M3 | T-03 factory 구현 세부. 토폴로지 불변 |
| 4 | SP-C5(앱키 1개 복수 CANO) 실패 시 TokenManager·RateLimiter 앱키 단위 다중화 — `.env` 키 구조와 SC-4 항목이 계좌별로 늘어난다 | M1 스파이크 | §5.2 SC-4, §7.1 env |
| 5 | SP-C3b(모의 도메인 WS 지원·URL·체결통보 tr_id) — 미지원이면 M4에서 T0 검증 불가 → REST 폴백 원용, T0 실사격은 M5 첫 주로 이월 (정본: 04 §2 SP-C3) | M1 스파이크 | §4.1 T-04의 paper 프로파일 |
| 6 | SP-B3(앱키당 동시 세션 수 = 1인가) — 1이면 tools·수동 CLI가 WS를 절대 열지 않는다는 규칙을 SC-13에 추가 | M1 W7 | §5.2, §7.3 |
| 7 | M2 DoD 10년 백테스트 VPS 실측 — 30분 초과 시 런타임 G2 게이트 5년 축소·삭제 (정본: 01 §1.6). tools 리소스 제한(`cpus`) 추가 여부도 이때 판단 | M2 | §7.1 tools |
| 8 | `approval_key` 유효기간·재발급의 기존 세션 영향(M1 W7) — T-04의 07:00 재수립 절차 파라미터 (정본: 01 §5.1, 구현: 05) | M1 W7 | §4.1 |
| 9 | T1 계층(M9 조건부) — 채택 시에도 상시 태스크는 늘지 않는다(T-04 소켓에 구독 추가·해제뿐). M9 취소 시 §4.1·§4.3은 그대로 유효하며 T1 관련 구독 코드 경로만 비활성 | M9 게이트(04 정본) | §4.1, §4.3 — 양쪽 경로 모두 본 설계로 커버 |
| 10 | `wss://` 지원 여부(M9 착수 시) — 미지원 시 잔여 리스크 등재(정본: 01 §7-10). compose·토폴로지 영향 없음 | M9 | — |
| 11 | ~~이견: healthcheck 명령의 모듈 경로~~ **해소** — 계획 01 §1.6이 네 곳(healthcheck·tools backtest·`omra.cli backtest`·`experiment ingest`) 모두 `python -m omra.cli <명령>`으로 표기하므로 이 문서를 계획 표기에 맞췄다(§2.3·§7.1·§7.2·§7.3). `src/omra/__main__.py`는 같은 Typer 앱에 위임하는 별칭으로만 남는다 | — | §2.3, §7.1~§7.3 |
| 12 | **[확인 필요]** 계획 01 §2.2 허용 목록이 `research`·`surveillance`에 `omra.config`를, `labs`에 `omra.core`를 적지 않은 것이 의도인지 누락인지. **확인 방법**: 계획 소유자에게 §2.2 허용 목록 개정 여부를 질의(설계로 판단하지 않는다 — 브리프 §1-4). 의도로 회신되면 C04a·C05a에 `omra.config`를, C07a에 `omra.core`를 추가한다. 현 설계는 "누락"으로 보고 금지하지 않았다(§8.2 금지줄 생성 규칙) | 계획 개정 | §8.2 |
| 13 | 이 문서가 신설한 config 키(`runtime.role`(=`OMRA__RUNTIME__ROLE`, app\|tools)·`runtime.fill_queue_warn`·`watchdog.{interval_sec,loop_lag_exit_ms,heartbeat_max_age_sec,consecutive}`·`tools.snapshot_max_age_h`)는 [04](04-configuration-and-secrets.md) 스키마 등록이 선행되어야 한다 | 04 | §4.3, §4.5, §7.1, §7.3 |
| 14 | 실험 결과 적재(`experiment ingest`)를 잡으로 자동화할지 여부 — 계획 01 §4.2 잡 표에 없으므로 [12](12-scheduling-and-operations.md)가 잡 카탈로그·catch-up 3분류에 등재해야 SC-10을 통과한다 | 12 | §7.3 |
| 15 | `config validate`([DD-01-16]) 신설의 후속 — [16](16-testing-and-quality.md) §10.2 J9 잡의 명령줄을 `python -m omra.cli config validate`로 교체(현재 `pytest tests/arch/test_config_keys.py` 잠정 표기, 16 §16 미해결 12)하고, [04](04-configuration-and-secrets.md) §9가 이 명령을 검증 규칙 ①②③의 실행 진입점으로 참조해야 한다. **단계 정의는 04 소유이며 이 문서는 명령 좌표만 확정했다** | 04·16 | §2.3 |
| 16 | repos 모듈 집합의 계속적 동기화 — §8.1.1 표·§8.2 C04b·C05b·C07b는 [03](03-data-and-persistence.md) §2.1 트리(2026-08 시점: 24개 모듈)의 스냅샷이다. 03이 모듈을 추가·개명하면(예: `tax_events` TABLES에서 `contribution_ledger`·`harvest_ledger`를 분리하는 경우 — 03 [DD-03-32]) **같은 커밋에서** 세 열거를 갱신한다. 미갱신은 AT-1이 CI에서 차단 | 03 | §8.1.1, §8.2 |
| 17 | `pending_transfers` 쓰기 주체 표기 정합 — 이 문서는 `tax`(행 생성) + `execution`(상태 전이)로 확정했다([08](08-execution.md) §14.1 역할 분담, 02 §5.6 불변식 1 "주문 생성 주체는 tax+execution뿐"). [03](03-data-and-persistence.md) §2.2 쓰기 토폴로지 그림은 `tax` 단독으로 그려져 있으므로 그림 보강을 요청한다(테이블당 쓰기 **모듈**은 여전히 1개이므로 03 §4.3 검사 2와 충돌하지 않는다) | 03 | §8.1.1 |
| 18 | C05a·C06a·C07a에 "1차 패키지 − 허용 목록" 규칙으로 **파생**된 금지 간선(`surveillance -/-> calendar·realtime·portfolio·monitoring`, `realtime -/-> calendar`, `labs -/-> portfolio`)은 계획 01 §2.2의 명시 금지줄이 아니라 허용 목록 완전열거의 기계화다. M0 CI에서 실구현이 이 중 하나를 필요로 하면 **계약을 완화하지 말고 계획 §2.2 허용 목록 개정을 먼저 요청**한다(계약은 계획의 번역이지 독립 정책이 아니다 — §8.2 서두) | M0 CI | §8.2 C05a·C06a·C07a |
| 19 | C15(tax 자기 제한, [DD-01-15])의 허용 목록 폭 — [10](10-tax-engine.md) §2.1이 `core`·`config`·`calendar`·`data`·`audit`·`persistence`(ro+자기 repo)로 자기 제한했으므로 `engine`·`portfolio`가 금지 쪽에 있다. 구현에서 tax가 이 둘을 필요로 하면 **계약이 아니라 10 [DD-10-2]를 먼저 개정**한다(§8.2 [DD-01-15] 규칙) | M6 tax 구현 | §8.2 C15 |
