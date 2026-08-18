# 01. 시스템 아키텍처 & 기술 스택

> 설계 전제: **단일 사용자 · 단일 VPS · 24/7 무인 운용**. 확장성보다 "밤에 죽지 않고, 죽으면 스스로 알리고, 아침에 상태를 복원하는" 견고함을 최우선한다.
> 이 문서가 **모듈 구조·의존 규율·시크릿·토큰 저장·실시간 채널 인프라(세션·재연결·구독 예산)·스케줄 배열의 정본**이다. 집행 시각·주문 전략의 정본은 [02 §4 집행 스펙](02-investment-engine.md), 안전장치 파라미터의 정본은 [03](03-safety-operations.md), **실시간 계층 정의와 감시 정책**의 정본은 [06](06-realtime-and-surveillance.md), 자가 개선의 정본은 [07](07-self-improvement.md), **M9 진입 게이트**의 정본은 [04](04-roadmap.md)다.

## 0. 이 문서의 범위와 [R1]~[R4] 충족 상태

이 문서가 담당하는 것은 네 요구 중 **[R2] (실시간·API 한도)의 전부**와 [R1]·[R3]·[R4]의 **구조적 수용부**(패키지 배치·의존 규율·스케줄·시크릿)다. 정책·파라미터는 각 정본 문서로 넘긴다.

| 요구 | 이 문서가 담당하는 부분 | 충족 | 미충족 / 조건부 |
|---|---|---|---|
| **[R1]** 연동 조작 외 완전 자동 운용 | 봇 상태머신에 `SAFE_MODE` 추가(§3.4), 시크릿 만료 자동 조치(§6.2), 자기복구 사다리의 인프라(§6.4) | 구조 수용 완료 | 절세계좌 주문 경로는 **SP-C4 결과에 종속**. 세액공제 한도 소진 확인 같은 **고가치 개입은 의도적으로 남긴다**(00 §3) |
| **[R2]** API 한도 최대 활용 + 실시간 강화 | §5.3 실시간 채널 T0/T1, §5.4 API 한도 예산표 | **T0는 무조건 채택** | **T1은 조건부**(§5.3 M9 게이트). 일중 목표비중 재계산·일중 드리프트 재판정은 **영구 금지** |
| **[R3]** 공지·시장조치 회피 | `collectors/`·`surveillance/` 패키지 배치와 소유권 분리(§2), 감시 폴 잡 배치(§4.2) | 구조 수용 완료 | KIND·업비트 공지 **스크래핑은 채택하지 않는다**(유지보수 부채, 유니버스 base rate ≈ 0). 실시간 거래정지·VI 감지는 T1 종속이므로 **조건부** |
| **[R4]** 새 개념·변경의 주기적 확인과 자가 보완 | `labs/` 패키지와 봉인 규칙(§2, §8.2), 수집·다이제스트 잡 배치(§4.2) | **M10a(수집기 + 다이제스트)** | 섀도·챔피언-챌린저·카나리 실사격은 **첫 챌린저 후보가 나온 뒤**에 착수한다(07 §7) |

### 0.1 [R2] 실현 범위 — 정직한 기술

> **이 시스템은 API 한도를 최대한 소비하지 않는다 — 소비할 이유가 없기 때문이다**(`intstock-multprice` 1콜 = 30종목). 실시간 채널의 도입은 반응성이 아니라 **세 가지 구체적 결과**로만 정당화된다:
> ① 체결통보 실시간 수신으로 **이중 주문·이중 정정 위험 제거**
> ② 업비트 24/7 급락·김치프리미엄 가드(**사람이 자는 동안 유일하게 열려 있는 시장**)
> ③ **조건부** — 집행 창 한정 iNAV·호가 게이트(SP-E2/SP-E3 게이트 통과 시에만)
>
> 그 외 **모든 판정 주기는 현행과 동일**하며, **일중 목표비중 재계산·일중 드리프트 재판정은 영구 금지**다.

근거: Daryanani(2008)의 주 논지는 "rebalance less frequently, but **look** more frequently"이고 최적 관찰 주기는 5~10거래일이다. 현 설계의 **일 1회 판정 + 매시 모니터는 최적 구간보다 조밀**하므로, 관찰을 더 조밀하게 만드는 것은 순감점이다(05 §4.5.2 — "이미 초과 달성"이라는 표현은 논문이 경고한 daily look 역효과를 가리므로 쓰지 않는다). 실시간의 값어치는 평균 개선(연 1~5bp 추정, 무시 가능)이 아니라 **꼬리 차단**(2020-03 채권 ETF NAV 할인 평균 3.4%·일부 8% 초과가 최대 2주 지속 — 국면당 수백 bp)에 있다. **실시간은 수익 추구 도구가 아니라 보험이다.** 이 프레이밍이 설계 전체를 지배한다(05 §실시간 참조).

## 1. 기술 스택

### 1.1 언어/런타임

| 항목 | 선택 | 근거 |
|---|---|---|
| Python | **3.12** (최소 3.11) | skfolio·bt·pandas 안정 지원, KIS 공식 예제도 3.11+ |
| 패키지 관리 | **uv** + `pyproject.toml` + lockfile | 재현성, Docker 빌드 속도 |
| 품질 | mypy(strict, 금액·수량 모듈 한정) + ruff + import-linter | 금액 계산 모듈의 타입 오류는 곧 돈 |

### 1.2 웹 — FastAPI 임베디드

- FastAPI + uvicorn을 별도 서버가 아니라 **봇 프로세스의 asyncio 루프에 임베드**(freqtrade ApiServer 패턴). SQLite 단일 라이터와 충돌 없고, 봇 상태 객체를 메모리에서 직접 조회.
- 프론트엔드: **Jinja2 + htmx + Chart.js(번들 동봉)**. SPA·Node 빌드체인 없음. 실시간 갱신은 htmx polling(5~10초).
- **실시간 데이터의 UI 격리(필수)**: 기본 화면에 실시간 호가·틱 손익을 노출하지 않는다. Barber-Odean-Huang-Schwarz(JF 2022)는 실시간 UI가 **인과적으로** 거래를 늘린다는 실증을 제시했다. 이 시스템에서 가장 과소평가된 위험은 시장이 아니라 **사용자의 과매매**이므로, 실시간 데이터는 별도 탭에만 두고 "지금 매매" 버튼은 존재하지 않으며 Telegram 실시간 가격 알림은 기본 off다.

### 1.3 저장 — SQLite + Parquet/DuckDB 하이브리드

| 저장소 | 역할 |
|---|---|
| **SQLite** (WAL, SQLAlchemy 2.0, alembic) | 트랜잭션·상태: 주문/체결/포지션/스냅샷/리밸런싱 계획·결정/**브로커 토큰 캐시**/세금 원장(결제일 기준)/실행대장(run ledger)/휴장일 캐시/**감시 플래그**(`surveillance_flags`)/**카나리·변경 예산 카운터**/**실험 원장**(append-only). `busy_timeout=5000`, `synchronous=NORMAL` |
| **Parquet** (pyarrow, 연도·시장 파티션) | 시계열: 일봉 OHLCV, 환율, 종목마스터 point-in-time 스냅샷, 지표 캐시 |
| **DuckDB** (임베디드, 읽기 전용) | 백테스트·리서치·월간 리포트에서 Parquet을 SQL로 조회하는 쿼리 엔진 |

PostgreSQL은 배제(상시 데몬 관리 부담, 단일 사용자 쓰기 부하에 과잉). SQLAlchemy를 쓰므로 훗날 전환은 connection string 교체 수준. **시계열은 Parquet 전용**(SQLite에 넣지 않는다).

**영속성 요건 2건**: ① 카나리 α 단계와 변경 예산 카운터는 프로세스 재시작을 견뎌야 하므로 run ledger와 **별개 테이블로 DB 영속화**하고, 기동 셀프체크에 "진행 중 카나리 복원"을 포함한다. ② 실험 원장(`experiments`, `experiment_events`)은 DB 트리거로 DELETE/UPDATE를 금지한다(07 정본).

#### 핵심 테이블 스키마 (정본)

문서 세트의 `CREATE TABLE`은 `reconcile_expectations`(03 §1.3.1)·`surveillance_flags`(06 §7.1)·`pending_transfers`(02 §5.6) 셋뿐인데, 위 목록의 나머지는 컬럼이 정의되지 않은 채 **구현 제약만**(트리거로 DELETE 금지 등) 확정되어 있었다. 설계서가 처음 만들어야 하는 결정을 없애기 위해 최소 6개를 여기서 고정한다.

```sql
CREATE TABLE orders (             -- §3.1 Order 모델의 물리 스키마
  id                  TEXT PRIMARY KEY,        -- 내부 ULID
  account_id          TEXT NOT NULL,           -- 내부 식별자(계좌번호 아님, §6.3)
  broker_order_id     TEXT, broker_order_org_no TEXT,
  orig_broker_order_id TEXT,                   -- 재호가 체인
  instrument_key      TEXT NOT NULL, side TEXT NOT NULL, order_type TEXT NOT NULL,
  qty                 TEXT NOT NULL, limit_price TEXT,    -- Decimal은 TEXT로 저장
  status              TEXT NOT NULL,           -- SUBMITTING | PENDING | … | EXPIRED_UNKNOWN
  plan_id             TEXT, reprice_count INTEGER NOT NULL DEFAULT 0,
  submitted_at_kst    TEXT, dry_run INTEGER NOT NULL,
  UNIQUE (broker_order_id, account_id)         -- ★ 이중 접수 방지 (§3.2 주문 제출 프로토콜)
);
CREATE INDEX ix_orders_open ON orders(account_id, status)
  WHERE status IN ('SUBMITTING','PENDING');    -- §1.6 단계 8.5 미결제 수 조회

CREATE TABLE fills (
  id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
  qty TEXT NOT NULL, price TEXT NOT NULL, fee TEXT, tax TEXT,
  filled_at_kst TEXT NOT NULL, settle_date TEXT NOT NULL,   -- 세금 원장은 결제일 기준
  broker_exec_id TEXT, UNIQUE (broker_exec_id)              -- ★ 체결통보·REST 중복 반영 방지
);

CREATE TABLE positions (          -- 현재 보유. 원장의 정본은 브로커, 이것은 로컬 사본
  account_id TEXT NOT NULL, instrument_key TEXT NOT NULL,
  qty TEXT NOT NULL, avg_cost TEXT NOT NULL,   -- 이동평균단가(02 §5.1)
  updated_at TEXT NOT NULL, PRIMARY KEY (account_id, instrument_key)
);

CREATE TABLE run_ledger (         -- §1.4 실행대장
  run_date TEXT NOT NULL,         -- ★ venue별 '현지 거래일'
  venue TEXT NOT NULL, task_name TEXT NOT NULL,
  status TEXT NOT NULL,           -- pending | running | done | skipped | failed
  started_at TEXT, finished_at TEXT, note TEXT,
  PRIMARY KEY (run_date, venue, task_name)     -- ★ §4.2.1 '동일 run_date에 done이면
);                                             --   재실행하지 않는다'의 물리적 근거

CREATE TABLE bot_state   (id INTEGER PRIMARY KEY CHECK (id = 1),
                          state TEXT NOT NULL, safe_mode_reasons TEXT, since TEXT NOT NULL);
CREATE TABLE sleeve_state(sleeve_id TEXT PRIMARY KEY,
                          state TEXT NOT NULL, reason TEXT, since TEXT NOT NULL);

CREATE TABLE policy_versions (    -- §6.1 산출물 버전 포인터
  kind TEXT NOT NULL,             -- targets | universe
  version INTEGER NOT NULL, as_of TEXT NOT NULL,
  inputs_hash TEXT NOT NULL, path TEXT NOT NULL,
  PRIMARY KEY (kind, version)
);
```

**마이그레이션 정책**: alembic 단일 헤드, **초기 리비전은 M0**에서 만든다. **다운그레이드는 지원하지 않는다**(롤백은 §6.3대로 직전 이미지 태그 + Litestream 복원). **`data/KILL`이 존재하거나 `BotState = STOPPED`이면 마이그레이션을 실행하지 않는다** — 사람이 멈춘 시스템의 스키마를 자동으로 바꾸지 않는다.

### 1.4 스케줄러 — APScheduler (인-프로세스)

- `AsyncIOScheduler` + cron/date 트리거. Celery/RQ 배제(분산 워커가 풀 문제가 없음).
- 약점(재시작 시 missed job)은 자체 **실행대장(run ledger)** 으로 보완: 파이프라인 단계마다 `(run_date, task_name, status)` 기록 → 기동 시 "오늘 해야 했는데 안 한 일"을 판정해 catch-up 또는 skip+알림. 잡 저장소 영속화는 쓰지 않고 매 기동 시 코드에서 선언적으로 재등록.
- **run ledger의 `run_date` 키는 venue별 현지 거래일** 기준(미국 세션은 KST 자정을 넘으므로 KST 달력일을 쓰면 catch-up 판정이 꼬인다).
- **잡은 시간 예산을 갖는다**: 아침 창(07:00~07:30)처럼 하류 잡이 시각에 묶인 구간은 잡별 타임아웃을 선언하고, 초과 시 미완료를 `unknown`으로 표기한 채 다음 잡을 정시 진행한다(§4.3).

#### 동시성 규율 (정본)

§4.2.1이 정의한 것은 **재시작 축**(run ledger·catch-up 3분류)뿐이고 **런타임 축**은 비어 있었다. `krx_execute`는 10:00~14:30의 장기 실행 잡인데 그 동안 `guard_monitor`가 매시 정각 발화하고 **둘 다 주문 상태와 03 §2.4 순매수 회계를 건드린다.** 넷을 확정한다.

1. **잡 등록 기본값**: `max_instances=1`, `coalesce=True`, `misfire_grace_time=<잡별 시간 예산>`. 예외를 두는 잡은 §4.2 표에 열로 표기한다.
2. **`execution.order_lock` 불변식** — **주문 생성·제출과 03 §2.4 순매수 회계는 단일 `asyncio.Lock` 안에서만 수행**하며, 03 §1.6 pre-trade 1~8.5단계 전체가 이 락 안에서 원자적으로 실행된다. 이것이 없으면 `net_buy_committed` 검사와 주문 생성 사이의 `await` 경계에서 TOCTOU가 발생하고, 그 결과가 03 §2.4의 "**초과** = 정상 경로에서는 발생할 수 없다 → 등급 B\* `HALTED`(부재 사다리 자동 강등 비적용)"로 직행한다. **즉 락이 없으면 §2.4의 근거 문장 자체가 거짓이 된다.**
3. **시간 예산은 취소가 아니라 협조적 체크포인트로 강제한다** — 잡 내부의 종목 루프가 매 반복마다 남은 예산을 확인하고 스스로 종료하며, **이미 커밋된 부분은 유효로 취급**한다. `asyncio.wait_for` 취소는 HTTP 왕복이나 DB 트랜잭션 중간에서 `CancelledError`를 던져 부분 완료 상태를 미정의로 만드는데, §4.3은 "미완료 **종목**을 `unknown`으로 표기"라는 **부분 성공을 전제**하므로 취소 방식과 양립하지 않는다.
4. **SQLite 접근**: 쓰기 트랜잭션은 **잡별 짧은 세션**으로 열고, `SQLITE_BUSY`는 `tenacity` 3회 재시도(`busy_timeout=5000`과 별개의 앱 레벨 방어). 장기 실행 잡이 트랜잭션을 열어 둔 채 `await`하는 것을 금지한다.

### 1.5 핵심 라이브러리

| 영역 | 선택 | 비고 |
|---|---|---|
| HTTP / WS | `httpx`(async) / `websockets` | KIS·업비트 공용 |
| 최적화 | `skfolio` (BSD-3) | BL·LW·MVO·HRP·Walk-Forward 내장. Riskfolio-Lib 병행은 하지 않음(유지비·공격 표면만 증가) |
| 백테스트 | 자체 일 단위 종가 리밸런싱 시뮬 (+`bt` 구조 참조) | freqtrade 캔들 시뮬 이식 금지. `vectorbt`는 Commons Clause 라이선스로 배제 |
| 리포트 | `QuantStats` | 성과 tear sheet |
| 데이터 | `FinanceDataReader`, `pykrx` | pykrx는 야간 저빈도 배치 전용(요청당 1초 지연, 차단 리스크) |
| 캘린더 | `exchange_calendars`(XKRX/XNYS) + KIS 휴장일 TR 교차검증 | |
| Telegram | `python-telegram-bot` v21+ | |
| 메일(2차 알림) | 표준 `smtplib` + `email` | **알림 전용, 명령 수신 금지**(§6.4) |
| 재시도/로깅/설정 | `tenacity` / `structlog`(JSON) / `pydantic-settings` + YAML | |
| LLM | `anthropic` SDK | §8 |

### 1.6 Docker Compose

```yaml
services:
  app:          # 봇 엔진 + 스케줄러 + FastAPI + Telegram + T0 WS (단일 프로세스)
    build: .
    restart: unless-stopped
    env_file: [.env]                  # 시크릿 (chmod 600, git 제외)
    volumes:
      - ./config:/app/config:ro
      - omra-db:/app/var/db           # SQLite
      - omra-data:/app/var/data       # Parquet
      - omra-logs:/app/var/logs       # 로그/감사
      - omra-policy:/app/var/policy   # ★ 잡이 생성하는 정책 산출물(targets/universe) — rw
    ports:
      - "100.x.y.z:8080:8080"         # Tailscale 인터페이스에만 바인딩
    healthcheck:
      test: ["CMD", "python", "-m", "omra.cli", "health"]
      interval: 60s

  litestream:   # SQLite 실시간 복제 (S3 호환 스토리지)
    image: litestream/litestream
    restart: unless-stopped
    depends_on: [app]
    command: replicate -config /etc/litestream.yml
    env_file: [.env.litestream]      # ★ 오브젝트 스토리지 키만
    volumes:
      - omra-db:/app/var/db          # ★ 없으면 복제 대상 파일이 보이지 않는다
      - ./config/litestream.yml:/etc/litestream.yml:ro

  tools:        # 일회성 실행 전용 (백테스트·리서치·챌린저 검증). 상시 기동하지 않는다
    build: .
    profiles: ["tools"]              # 기본 up 대상에서 제외
    env_file: [.env.tools]           # ★ 브로커 키 없음 — 최소권한
    volumes:
      - ./config:/app/config:ro
      - omra-data:/app/var/data      # Parquet 읽기 + RO 스냅샷 읽기 + 결과 파일 쓰기
      - omra-logs:/app/var/logs
      # ★ omra-db 를 마운트하지 않는다 — 아래 "tools의 DB 읽기 경로" 참조
```

**세 서비스 모두 `user:`(non-root) · `read_only: true` · 필요한 `tmpfs:`를 명시한다**(§7-6 컨테이너 원칙). 쓰기는 위 named volume으로만 나간다.

**`tools`의 DB 읽기 경로 — `:ro` 마운트는 조건부라 채택하지 않는다.** §1.3이 SQLite를 **WAL 모드**로 확정했는데, WAL 리더는 원칙적으로 **`-shm` wal-index 공유메모리 파일에 대한 쓰기 권한**(또는 `-shm`이 없을 때 DB 디렉터리 쓰기 권한)을 요구한다. **SQLite 3.22.0(2018-01)에서 완화 경로가 추가되어 `-shm`·`-wal`이 이미 존재하거나 생성 가능하거나 `immutable`이면 read-only로 열 수 있게 되었다** — 즉 "절대 불가능"이 아니라 **조건부**다. 그러나 그 조건이 우리 배치에서 안정적이지 않다:

- `-shm`이 라이터에 의해 초기화된 상태에 의존하므로, **`app`이 죽어 있거나 크래시 직후 WAL 복구가 필요한 시점에는 리더가 실패**한다 — 백테스트를 돌리는 시점이 하필 그 시점일 수 있다.
- 우회 수단인 `immutable=1`은 "파일이 변하지 않는다"는 **단정**이라 `app`이 동시에 쓰는 DB에 쓰면 잘못된 결과를 읽는다.
- `labs`는 `persistence.ro` 접근이 허용되고 `labs/experiments.py`가 **시도 수 `N` 집계**에 DB 읽기를 전제하므로(02 §8.2 DSR), 읽기가 간헐 실패하면 챌린저 검증 게이트가 재현 불가능해진다.

**"가끔 되는 경로"를 무인 운용의 검증 게이트에 두지 않는다**는 것이 판단 근거다.

> **채택: 스냅샷 경로.** `app`이 `weekly_maintenance`와 `omra.cli backtest` 직전에 **`VACUUM INTO /app/var/data/snapshots/omra-ro.sqlite`**로 일관 스냅샷을 만들고, `tools`는 `omra-data`(rw)에 있는 **그 스냅샷만** 읽는다. `omra-db` 마운트를 아예 없애므로 **단일 라이터 전제가 파일시스템 레벨에서 더 강하게 지켜지고**, 스냅샷은 트랜잭션 일관성을 가지므로 `busy_timeout` 경합도 없다. 스냅샷 나이는 결과 파일에 기록해 재현성을 보장한다.

**상시 컨테이너 2개 + 일회성 실행 서비스 1개.** **백테스트·챌린저 검증(`G2`) CLI는 봇 프로세스 안에서 절대 실행하지 않고**, `docker compose run --rm tools python -m omra.cli backtest …`로 일회성 실행한다. **기동 주체는 사람 또는 호스트 cron이며 봇 스케줄러가 아니다.**

**리서치(`research_collect`·`research_rank`·`monthly_report`)는 여기서 제외된다** — 이들은 01 §4.2의 봇 스케줄러가 인-프로세스로 돌린다. 배제 기준은 "LLM인가"가 아니라 **"1 vCPU asyncio 루프를 수 분~수십 분 점유하는가"**다: 10년 백테스트는 점유하고, 야간 HTTP 수집과 LLM API 호출은 대부분 I/O 대기라 점유하지 않는다.

**`tools`는 `omra-db`를 마운트하지 않는다**(위 스냅샷 경로). 쓰기를 허용하면 01 §1.2의 "SQLite 단일 라이터" 전제와 "봇은 결과 파일만 읽는다"가 동시에 깨지고, `:ro`로 허용하면 WAL이 열리지 않는다. 챌린저 결과의 실험 원장 적재는 **tools가 `var/data/experiments/<run_id>.json`으로 쓰고, `app` 컨테이너 안에서 `omra.cli experiment ingest <path>`가 읽어 `persistence.repos.experiments`로 넣는 단방향 경로**로 확정한다 — **쓰기 주체는 언제나 `app` 하나**이며 이것이 단일 라이터 전제를 지키는 방식이다(07 §13). 토큰 파일락은 §5.1대로 `omra-db` 볼륨에 두되, `tools`는 브로커 자격증명이 없어 토큰을 요구하지 않으므로 락 공유가 불필요하다.

**`tools`에 브로커 키를 주지 않는 것이 격리의 핵심이다.** `app`의 `.env`를 그대로 상속하면 `labs -/-> brokers` import 계약이 **프로세스 경계에서 무효화**된다 — import는 막았는데 같은 이미지·같은 자격증명으로 도는 별도 프로세스가 주문을 낼 수 있게 되기 때문이다. `tools`는 `.env.tools`(Parquet·DuckDB·`ANTHROPIC_API_KEY`만)로 기동하며, **브로커 자격증명 부재를 기동 셀프체크가 확인**한다. 네트워크는 차단하지 않는다(리서치 수집기가 외부 소스를 읽어야 한다). 이 규율은 07의 챌린저 검증 게이트에도 그대로 적용된다 — **10년 × 8~12자산 백테스트를 1 vCPU asyncio 루프에서 돌리면 집행 잡과 가드가 밀린다.** M2 DoD에 "기준 전략 10년 백테스트 1회 실행 시간을 VPS 사양에서 실측"을 추가하고, **30분을 초과하면 런타임 백테스트 게이트(`G2`)를 5년으로 축소하거나 삭제**한다(CI 스냅샷 회귀가 이미 같은 역할을 한다).

## 2. 저장소 구조 (정본)

```
oh-my-robo-advisor/
├── pyproject.toml / uv.lock / Dockerfile / docker-compose.yml
├── config/                    # ★ 사람이 편집하는 **입력물**. 컨테이너에 `:ro`로 마운트된다
│   ├── config.yaml            # 기본 설정 (공개 가능)
│   ├── config.live.yaml       # 실전 오버레이 / config.paper.yaml 모의 오버레이
│   ├── universe.yaml          # 유니버스·슬리브 정의 (버전 관리, 승인 이력)
│   ├── targets.yaml           # 목표비중 **시드값**(최초 1회). 월간 산출물은 var/policy/ 로 간다
│   ├── goals.yaml             # 목표(goal)·glide path
│   ├── tax.yaml               # 세법 파라미터 (effective-date 버전)
│   ├── surveillance.yaml      # ★ 감시 등급 매핑 (risk_type → SV 등급) 외부화
│   ├── market_weights.yaml    # 시장 가중치 (상위 배분은 상수, 지역 비중만 월 1회 자동)
│   ├── external_schedules.yaml# ★ 자동이체·적립식 예약매수 → 대사 화이트리스트 입력(03 §1.3.1)
│   ├── external_income.yaml   # 외부 금융소득 계산식 {원금·이율·만기·지급주기} (00 §3.2 T2)
│   ├── secrets_registry.yaml  # ★ 시크릿 만료 대장 (발급일·만료일만, 값 없음)
│   └── tr_ids.kis.yaml        # KIS TR-ID 매핑 — 2섹션:
│                              #   rest: {live_prefix: T, paper_prefix: V}  (규칙 치환)
│                              #   ws:   {env별 tr_id 명시 테이블 + url + port}  ★ prefix 규칙 불성립
├── docs/
│   ├── plan/                  # 00~07 계획 문서 (이 문서 세트)
│   └── runbook/               # 운영 절차서
│       ├── secret-rotation.md # 앱키 갱신 15분 절차 (§6.2)
│       └── restore-drill.md
├── src/omra/
│   ├── __main__.py / cli/     # 엔트리포인트, Typer CLI (run/backtest/report/health/plan)
│   ├── core/                  # 도메인 모델·화폐·틱사이즈·Clock 추상화·예외
│   ├── config/                # 설정 로딩·계층 병합·스키마 검증
│   ├── calendar/              # 거래 캘린더·세션 상태머신 (KRX/US/크립토) + 결제일 계산
│   ├── brokers/               # BrokerGateway 추상화
│   │   ├── base.py            #   ABC + dry-run 분기(유일한 분기점)
│   │   ├── paper.py           #   dry-run 체결 시뮬레이터
│   │   ├── kis/               #   client, auth(토큰·approval_key), ratelimit, tr_map
│   │   │   └── ws/            #     session · registry · decoder · events
│   │   └── upbit/             #   client, auth, ratelimit, ws/(public·private)
│   ├── collectors/            # 범용 수집 프레임워크 (LLM 없음, 중립)
│   │   ├── http.py            #   조건부 요청(ETag/If-Modified-Since)·캐시·백오프
│   │   ├── robots.py          #   robots.txt Disallow 하드 차단
│   │   └── dedup.py           #   payload_hash 중복 제거
│   ├── surveillance/          # 시장 감시 (운영 큐, 하드 액션 유발). LLM 없음
│   │   ├── sources/           #   kis_master(.mst.zip) + kis_stock_info(CTPF1002R)
│   │   │                      #   + kis_ws_market(H0STMKO0 소비, T1 종속·조건부)
│   │   ├── flags.py           #   단일 테이블 surveillance_flags
│   │   └── gate.py            #   소비자 API 6종 (정본 06 §7.2): level_of · reasons ·
│   │                           #     partition_by_tradability · blocked_for_buy ·
│   │                           #     assert_tradable · frozen_nav_ratio
│   ├── realtime/              # 실시간 집행 가드 (T0 상시 / T1 조건부)
│   │   ├── verdict.py         #   Verdict / GuardOutput (frozen) — 축소 방향 전용
│   │   ├── guards.py          #   PriceGuard · MoveGuard · PremiumGate · KimchiGuard
│   │   │                      #   · CryptoDropGuard  (거래정지·VI 판정은 소유하지 않음)
│   │   ├── execution_hint.py  #   marketable limit 산정 (호가 나이 검사 포함)
│   │   └── fallback.py        #   WS↔REST 등가 전환 컨트롤러
│   ├── data/                  # TET Fetcher providers + Parquet 스토어 + DuckDB 뷰
│   ├── engine/                # 순수 함수 수치 엔진 (백테스트와 공유)
│   │   ├── expected_returns.py  # 역최적화 균형수익률 + Black-Litterman
│   │   ├── covariance.py        # Ledoit-Wolf shrinkage
│   │   ├── optimizer.py         # 제약 MVO + 턴오버 L1 + 정수 수량화
│   │   ├── sanity.py            # HRP 병렬 계산·괴리 판정
│   │   ├── rebalancer.py        # cash-flow first + 드리프트 밴드 → RebalancePlan
│   │   ├── montecarlo.py        # block bootstrap 경로 생성
│   │   └── overlay/             # 듀얼모멘텀 위성 (기본 OFF)
│   ├── tax/                   # asset location, 하베스팅 배치, 금소세·건보 임계 모니터,
│   │                          # ISA 비과세 한도 계약기간 누적 소진률 추적 (02 §5.2)
│   ├── execution/             # RebalancePlan → 주문 집행·재호가·체결 추적·대사
│   │   └── router.py          #   AccountMode(AUTO/BROKER_SCHEDULED/INSTRUCTION) 분기의 유일한 지점
│   ├── protections/           # 서킷브레이커 플러그인 P1~P15
│   ├── portfolio/             # 포지션·NAV, 원장 (라이브 DB / 백테스트 in-memory 로직 공유)
│   ├── persistence/           # SQLAlchemy 모델·리포지토리·마이그레이션
│   │   ├── ro.py              #   읽기 전용 세션 팩토리 (관측 4레이어의 유일한 읽기 경로)
│   │   └── repos/             #   쓰기 전용 리포지토리 — 테이블별로 분리해 화이트리스트 부여
│   │       ├── research_extractions.py   # research만 허용
│   │       ├── surveillance_flags.py     # surveillance만 허용
│   │       ├── pending_tax_events.py      # surveillance만 허용 (KR-04 → E7 트리거)
│   │       ├── experiments.py            # labs만 허용 (append-only, DB 트리거 보호)
│   │       └── budget.py                 # labs만 허용 (카나리 α·변경 예산 카운터)
│   ├── scheduler/             # APScheduler 래핑, 일일 세션 플래너, run ledger, 시간 예산
│   ├── rpc/                   # RPCManager + telegram / smtp / webhook 채널
│   ├── web/                   # FastAPI 라우터, Jinja 템플릿
│   ├── research/              # ★ LLM 레이어 — 산출물은 사람이 읽는 텍스트와
│   │                          #   KnowledgeItem 구조화 추출뿐. 어느 쪽도 주문·목표비중·
│   │                          #   파라미터를 만들지 않는다 (§8.1)
│   │   ├── sources/           #   수집 소스 어댑터 (07 §3.2)
│   │   ├── extract.py         #   LLM 구조화 추출 (KnowledgeItem 스키마 강제)
│   │   ├── citation.py        #   인용 검증기 — 월간 리포트와 코드 공유
│   │   ├── rules.py           #   ★ 룰 엔진 HR-1~HR-10 (결정론, LLM 없음) — 07 §4.4
│   │   └── digest.py          #   월간 다이제스트
│   ├── labs/                  # 자가 개선 오케스트레이션 (LLM 없음) (§8.2)
│   │   ├── experiments.py     #   사전등록(G0)·사양 해시·시도 수 N 집계 · append-only 원장
│   │   ├── challenger.py      #   G2 러너 (별도 프로세스 호출만)
│   │   ├── shadow.py          #   G3 섀도
│   │   ├── canary.py          #   카나리 α 블렌딩 (대상별 파라미터화 — 단일 코드)
│   │   ├── budget.py          #   변경 예산 (상위 캡 지배)
│   │   └── rollback.py        #   프로세스 지표 롤백 트리거 R1~R5 (정본은 07)
│   ├── backtest/              # 일 단위 시뮬, Walk-Forward 러너, lookahead 탐지
│   ├── audit/                 # append-only JSONL 감사로거
│   └── monitoring/            # healthcheck, heartbeat, dead-man's switch, loop lag,
│                              # 시크릿 만료 감시
├── tests/                     # 단위 + 계약 + 아키텍처 테스트, record-replay 카세트
└── scripts/                   # 프로비저닝, 복구 리허설(반자동), 키 로테이션
```

### 2.1 패키지 4종의 배치 근거

| 패키지 | 성격 | 배치 근거 |
|---|---|---|
| `collectors/` | **중립 수집 프레임워크**(LLM 없음) | `surveillance`(운영 큐, 하드 액션)와 `research`(연구 큐, LLM)가 **둘 다** 수집을 필요로 한다. `research/collectors/`에 두면 `surveillance → research` import가 발생해 prompt injection 격리가 깨진다. **중립 패키지가 유일한 정합 배치다.** |
| `surveillance/` | 운영 큐 — **거래정지·VI·관리종목·상폐의 유일한 소유자** | 산출이 하드 액션(신규매수 금지·거래 동결)이므로 LLM과 물리적으로 분리해야 한다. 소비자는 pull 방식으로만 접근(`gate.assert_tradable`) |
| `realtime/` | 집행 가드 — 축소 방향 전용 | 07:30 확정 계획을 **줄이거나 멈출 수만** 있다. `engine.optimizer/rebalancer` 접근이 물리적으로 불가능해야 "실시간이 목표비중을 흔든다"는 경로가 원천 차단된다 |
| `labs/` | 자가 개선 오케스트레이션(LLM 없음) | 섀도·카나리는 `engine`(순수함수)·`backtest`를 호출해야 하는데 `research`는 그걸 금지당한다. **두 격리의 목적이 다르므로**(LLM 격리 vs 실험 격리) `research`를 넓히지 않고 `labs`를 따로 둔다 |

`labs`와 `research`는 **import로 연결되지 않는다.** LLM이 추출한 후보는 `research_extractions` 테이블에 쓰이고 `labs`는 그것을 persistence를 통해 읽는다. 저장소를 통한 간접 연결이므로 두 격리가 서로를 오염시키지 않는다.

### 2.2 의존 방향 규율 — import-linter 계약 (정본, CI 강제)

**계약은 두 층으로 나뉜다.** import-linter는 **모듈 간선만** 검사하므로 "읽기 전용(RO)"을 강제할 수 없다 — 같은 모듈을 import하는 이상 SELECT인지 INSERT인지 구분할 방법이 없다. 그런데 `research`(추출 결과 적재)·`labs`(실험 원장·예산 카운터)는 **정의상 쓰기를 해야 한다.** 그래서 아래처럼 나눈다.

- **① 기계 강제(import-linter)** — 간선 목록. `(RO)` 표기를 쓰지 않는다.
- **② 쓰기 권한 강제(패키지 분할)** — 쓰기는 `persistence.repos.*`의 **테이블별 전용 리포지토리**로만 가능하고, 관측 4레이어는 `persistence.ro`와 **자신에게 허용된 repo 모듈**(`research` 1개 / `surveillance` 1~2개 / `labs` 2개 / `realtime` 0개)만 import할 수 있다. 즉 "RO"를 주석이 아니라 **import 가능한 모듈의 집합**으로 표현한다. **각 레이어의 허용 집합은 아래 목록이 완전열거이며, `persistence.repos.*` 중 열거되지 않은 모듈은 전부 금지줄로 명시한다** — default-allow 규칙 때문에 열거하지 않으면 조용히 허용되기 때문이다.

**계약 타입 표기**: 아래는 전부 `[forbidden]` 계약이다. **열거되지 않은 간선의 기본값은 허용**이며, 관측 4레이어(`research`·`surveillance`·`realtime`·`labs`)만 금지줄로 봉인한다. 코어 방향 규율 2줄도 동일하다.

```
# 코어 방향 규율
engine        →  brokers                                                          금지  (엔진은 브로커를 모른다)
brokers       →  engine · 전략                                                    금지  (브로커는 전략을 모른다)

# 수집 — 중립 프레임워크
collectors    →  core · audit                                                     허용  (그 외 전부 금지)

# research — LLM 격리
research      →  collectors · core · persistence.ro
                 · persistence.repos.research_extractions · data · audit          허용
research      →  execution · brokers · engine · tax                               금지
research      →  surveillance                                                     금지  ← prompt injection 격리
research      →  persistence.repos.experiments · persistence.repos.budget
                 · persistence.repos.surveillance_flags                           금지  ← LLM이 실험·예산·감시를 못 건드린다

# surveillance — 감시는 주문하지 않는다
surveillance  →  collectors · core · data · persistence.ro
                 · persistence.repos.surveillance_flags
                 · persistence.repos.pending_tax_events · audit                   허용
surveillance  →  persistence.repos.experiments · persistence.repos.budget
                 · persistence.repos.research_extractions                         금지
surveillance  →  brokers.kis.ws.events · brokers.upbit.*.events                   허용  (읽기 전용 이벤트)
surveillance  →  research                                                         금지  ← prompt injection 격리
surveillance  →  execution · brokers.*.client · engine.optimizer
                 · engine.rebalancer · tax                                        금지

# realtime — 축소 방향 전용
realtime      →  core · brokers.*.ws.events · surveillance.gate
                 · data.quote · audit · config                                    허용
realtime      →  execution · brokers.*.client                                     금지  ← 스스로 주문·조회하지 않는다
realtime      →  persistence.repos.*                                              금지  ← 어떤 상태도 쓰지 않는다
realtime      →  engine.optimizer · engine.rebalancer
                 · engine.expected_returns · tax                                  금지

# labs — 실험은 주문을 낼 수 없다
labs          →  engine · backtest · persistence.ro · data · audit
                 · protections · config
                 · persistence.repos.experiments · persistence.repos.budget       허용
labs          →  execution · brokers · rpc · research                             금지
labs          →  collectors                                                       금지  (labs는 수집하지 않는다)
labs          →  persistence.repos.research_extractions
                 · persistence.repos.surveillance_flags                           금지

# 소비 방향
execution · protections · engine.rebalancer  →  surveillance.gate                 허용  (소비자는 pull)
execution · protections                      →  tax                               허용  (매도 제약·오버레이)
execution                                    →  realtime                          허용  (역방향은 금지)
execution     →  persistence.repos.execution_state                                허용  (가드 예산 영속화 §3.5)
```

> **`realtime → data.quote` 허용이 새로 명시된 이유**: 06 §2.4의 가드 발동 조건 ②("가능한 경우 REST 스냅샷 1회 교차 확인")와 `realtime/fallback.py`(WS↔REST 등가 전환), `quote.max_age_ms` 초과 시 재조회는 **REST 접근 없이는 구현 불가능**하다. 그러나 브로커 클라이언트를 직접 잡게 하면 realtime이 주문 API에도 닿으므로, **`data`의 quote fetcher를 경유**하게 하고 `brokers.*.client`는 `surveillance`와 동일하게 금지한다.
>
> **이 계약 목록이 유일한 원문이다.** 06 §12·07 §12의 블록은 발췌 인용이며, 값이 다르면 이 절이 이긴다. 세 곳이 어긋나면 CI 계약 파일이 하나뿐이므로 어느 것을 등록할지 결정할 수 없게 된다.

### 2.3 거래정지·VI 이벤트의 단일 소유권 (충돌 해소)

같은 스트림의 같은 필드를 두 시스템이 각각 판정하면 감사로그가 둘로 갈리고 해제 조건이 달라진다. **소유권을 단일화한다.**

```
brokers/kis/ws/decoder.py     이벤트를 발행만 한다 (판정 없음)
   ├→ surveillance.sources.kis_ws_market   TRHT_YN / VI_CLS_CODE 소비
   │                                       → 감시 등급(SV0~SV3)의 유일한 소유자
   │                                       → 해제 조건·감사로그도 surveillance가 단독 관리
   └→ realtime.guards                      호가·체결가·NAV만 소비
                                           (장운영 필드 소비 금지 — CI 계약)

realtime / execution 은 주문 직전 surveillance.gate.assert_tradable(order) 를 호출한다 (pull).
```

`realtime`에는 `TradabilityGuard`·`ViHandler`가 **존재하지 않는다.** 거래 가능성은 감시가 판정하고 집행이 물어본다.

### 2.4 EventBus는 만들지 않는다

토픽당 구독자가 1~2개뿐인 in-process pub/sub은 간접층만 만든다(약 200줄 순비용). **`decoder.py`가 가드 함수를 직접 호출**하고, **Fill만 `asyncio.Queue`로 분리**한다 — 시세는 낡으면 버려도 되지만 체결은 절대 잃으면 안 되기 때문이다. 이 비대칭이 큐를 쓰는 유일한 이유이며, 그 외에는 직접 호출이다.

```python
# brokers/kis/ws/decoder.py (개념)
async def on_message(raw: str) -> None:
    ev = parse(raw)                                  # '|' '^' split + (체결통보만) AES256-CBC
    match ev:
        case Fill():         await fill_queue.put(ev)          # 유일한 큐 — drop 금지
        case MarketStatus(): surveillance.ingest_ws(ev)        # 감시가 단독 소유
        case BookTop() | QuoteTick() | NavTick():
            realtime.guards.on_market(ev)                      # 직접 호출, 예외는 여기서 격리
```

핸들러 예외는 호출부에서 격리한다(warning + 감사로그, 3회 연속 시 해당 가드 비활성 + critical). 핸들러에 blocking 연산·최적화·백테스트·LLM 호출을 두는 것은 규약 위반이며, import-linter가 대부분을 이미 막는다.

## 3. 핵심 인터페이스 (시그니처 초안)

### 3.1 도메인 모델 (`core/models.py`)

```python
class Market(StrEnum):
    KRX = "KRX"                      # KRX 정규장만 (NXT/SOR 미사용)
    NASD = "NASD"; NYSE = "NYSE"; AMEX = "AMEX"
    UPBIT = "UPBIT"

class Instrument(BaseModel, frozen=True):
    symbol: str                      # "069500", "VTI", "KRW-BTC"
    market: Market
    currency: str                    # "KRW" | "USD"
    asset_class: str                 # "kr_etf" | "us_etf" | "us_stock" | "crypto"
    lot_step: Decimal                # 정수 주식=1, 크립토=1e-8
    tick_rule: str                   # "krx_etf_5" | "krx7" | "usd_penny" | "upbit"

class OrderType(StrEnum): LIMIT; MARKET; LOO; MOO; LOC; MOC   # LOO/MOO/LOC는 개장 전 제출 전용

class Order(BaseModel):
    id: str                          # 내부 ULID
    account_id: str                  # ★ 내부 계좌 식별자 (계좌번호 아님 — §6.3 마스킹)
    broker_order_id: str | None
    broker_order_org_no: str | None  # ★ KIS 주문조직번호 — 정정/취소 TR 호출에 필수
    orig_broker_order_id: str | None # ★ 재호가로 대체된 원주문 (체인 추적)
    instrument: Instrument
    side: OrderSide; order_type: OrderType
    qty: Decimal; limit_price: Decimal | None
    status: OrderStatus              # PENDING…FILLED/CANCELLED/REJECTED/EXPIRED
    plan_id: str | None              # 어느 RebalancePlan에서 나왔는가 (감사 연결고리)
    reprice_count: int = 0           # 재호가 횟수 (02 §4.1.1 상한 3회)
    submitted_at_kst: datetime | None# net_buy 기간 귀속의 기준 (03 §2.2)
    dry_run: bool

class RebalancePlan(BaseModel):
    id: str; as_of: datetime
    reason: str                      # "drift_band" | "cashflow" | "harvest" | "manual"
    orders: list[Order]
    expected_turnover: Decimal
    sanity: SanityResult             # HRP 괴리 등
    approved: bool                   # grace period 내 거부 가능

class TargetWeights(BaseModel):
    as_of: date; sleeve: str
    weights: dict[str, Decimal]
    method: str                      # "bl_mvo_v1" — 감사로그용
    inputs_hash: str                 # 입력 데이터 지문(재현성)
```

종목 상태 플래그(`tr_stop_yn`·`admn_item_yn`·`etf_etn_ivst_heed_item_yn`·`lstg_abol_dt`·미국 `ptp_item_yn`)는 `Instrument`에 넣지 않는다 — 시점 의존 상태이므로 `surveillance_flags`(관측 시각 포함)에 둔다. 유니버스 hard 필터에서의 사용은 [02 §2.3](02-investment-engine.md)이 정본이다(**미국 PTP는 매도 대금 총액에 10% 원천징수이므로 `ptp_item_yn == 'N'`이 hard 조건**).

### 3.2 BrokerGateway — dry-run 분기의 유일한 위치

```python
class BrokerGateway(ABC):
    """상위 레이어는 dry-run 여부를 절대 모른다."""

    async def place_order(self, order: Order) -> Order:
        self._validate(order)                 # ★ '브로커 API 규격' 검증만 —
                                              #   호가단위·최소수량·필수 필드.
                                              #   감시·세금·브레이커·상태 게이트를 호출하지 않는다.
                                              #   pre-trade 체인의 소유자는 execution 이다(03 §1.6)
        if self.dry_run:
            return await self._paper.simulate_submit(order)   # ← 유일한 분기점
        return await self._submit_live(order)

    @abstractmethod
    async def replace_order(self, order: Order, new_limit_price: Decimal) -> Order:
        """재호가의 유일한 논리 단위. venue별 실체가 정반대이므로 추상으로 흡수한다.
           KIS   : 주식정정취소주문 TR 1회 (broker_order_org_no + broker_order_id 필요)
           업비트 : 정정 API 없음 → 취소 → 잔량 재조회 → 신규 주문 (3단계)
           규약  : ① 취소 확인 전 신규 호가 금지 ② 취소~재주문 사이 부분체결이 확정되면
                   재주문 수량은 '원수량 − 확정 체결수량'으로 재계산 후 제출
                   ③ 어느 단계에서 실패해도 원주문 상태를 REST로 재조회해 확정한 뒤 종료
           계수  : replace_order 1회 = 재호가 1회. P2(일일 주문 건수)에는
                   업비트의 신규 주문분도 가산하지 않는다(03 §1.2 P2 계수 정의)"""

    # get_balance / get_positions / get_quote / get_ohlcv / cancel_order /
    # stream_executions(체결통보 WS)를 추상 메서드로 정의
```

#### 주문 제출 프로토콜 — 멱등성과 고아 주문 (정본)

03 §3은 "주문 접수 후 상태 확인 실패(응답 유실) → 신규 주문 금지 + 강제 대사"만 정하고 **강제 대사가 유실 주문을 브로커 체결내역과 어떤 규칙으로 매칭하는지**를 정하지 않았다. 그 공백은 등급 A로 직결된다 — **제출 직후 크래시로 DB에 주문 레코드가 없으면 재기동 후 대사에서 고아 체결이 "수량 불일치 1주"로 관측되고(03 §1.2 P8 → 즉시 `HALTED`), 자가치유 조건 ②는 "CA 비율로 정확히 재현"을 요구하므로 고아 주문은 절대 재현되지 않아 자가치유가 실패하며, 등급 A는 자동 해제 영구 금지다.** 즉 **크래시 1회 = 사람이 올 때까지 무기한 정지**이며 03 §5.4의 "1개월 부재 중 강제 개입 0회"와 정면 충돌한다. 셋을 확정한다.

1. **쓰기 순서 고정(persist-then-submit)** — `orders` 레코드를 `status=SUBMITTING`으로 **트랜잭션 커밋 완료 후에** 브로커에 제출하고, 응답 수신 시 `broker_order_id`·`broker_order_org_no`를 갱신해 `PENDING`으로 전이한다. **커밋 없이 제출하는 경로를 코드 레벨로 금지하고 아키텍처 테스트로 강제**한다.
2. **고아 주문 판정 규칙** — 재기동·응답 유실 시 `status=SUBMITTING`인 레코드에 대해 브로커 주문체결조회를 `(account_id, instrument_key, side, qty, 제출 KST 시각 ±N분)` 튜플로 매칭한다(`N` 초기값 5분, M4 실측). 매칭 성공 시 `broker_order_id`를 흡수해 `SUBMITTING → PENDING`으로 확정하고, 실패 시 `EXPIRED_UNKNOWN`으로 두고 P8이 아니라 전용 경로로 보낸다.
3. **P8 예외 편입** — `SUBMITTING`/`EXPIRED_UNKNOWN` 레코드로 설명되는 수량 불일치는 03 §1.3.1 대사 화이트리스트에 **`kind=orphan_order`로 자동 등록**(1회 소비)해 등급 A `HALTED`로 가지 않게 한다.

> KIS 주문 TR에 내부 ULID를 실어 보낼 사용자 정의 필드가 있는지는 **미확인**이다. 있으면 2의 튜플 매칭 대신 그 필드를 쓰고, 없으면 튜플 매칭이 정본이다 — 어느 쪽이든 1(persist-then-submit)이 선행 조건이다. M4 장애주입에 **F21(제출 직후 SIGKILL → 재기동 → 고아 주문 흡수)**을 추가한다.

**`replace_order`를 추상 메서드로 올린 이유**: 02 §4.1.1은 국내와 크립토를 구분 없이 "재호가"로 기술하는데 두 브로커의 실체가 정반대다. 이것을 상위 레이어가 알게 되면 "업비트에서는 재호가가 취소+신규 2건"이라는 사실이 P2·P4 계수와 미체결 추적에 새어 들어가고, **T0 체결통보가 막으려던 "이미 체결됐는데 모르고 정정"이 업비트에서는 "취소 사이에 체결된 수량만큼 초과 주문"이라는 다른 형태로 되살아난다.** 규약 ②가 그 경로를 닫는다.

- 실행 모드 3종: `dry_run`(로컬 시뮬, 브로커 서버 없음) / `paper`(KIS 모의투자 서버 — live 코드 경로 그대로) / `live`. 모의투자 전환은 `env: paper` 스위치 하나로 도메인 URL·TR 매핑·rate limit 프로파일이 함께 바뀐다.
- **REST와 WebSocket의 env 분기 방식이 다르다.** REST TR-ID는 `T→V` prefix 치환 규칙이 성립하지만, **WebSocket은 접속 도메인·포트 자체가 다르고 체결통보 tr_id도 prefix 치환이 아니라 별도 ID**다. 따라서 `tr_ids.kis.yaml`은 `rest:`(규칙)와 `ws:`(env별 명시 테이블 + url + port) 2섹션으로 나눈다. **"prefix만 V"라는 단일 변환 규칙으로는 WS 경로를 매핑할 수 없다** — 이 구분이 없으면 M4(모의 도메인 E2E)에서 T0 체결통보를 한 번도 켜보지 못한 채 실전에 진입하게 된다.
- `PaperExecutionEngine`(dry-run 시뮬): 호가창 기반 보수적 체결 + 수수료/세금 반영. 지정가는 반대편 호가 도달 시에만 체결(낙관 편향 문서화 — freqtrade 교훈).

### 3.3 DataProvider — TET Fetcher (OpenBB 패턴 자체 구현)

```python
class Fetcher(Generic[Q, D], ABC):
    @staticmethod
    def transform_query(params: Q) -> dict: ...              # 표준 질의 → provider 파라미터
    @staticmethod
    async def extract_data(query, credentials) -> Any: ...   # 원천 호출 (I/O는 여기만)
    @staticmethod
    def transform_data(query, raw) -> list[D]: ...           # 표준 Pydantic 모델 검증

class ProviderRegistry:
    """시장 인지형 라우팅: (data_kind, market) → fetcher 우선순위.
    예: ("ohlcv_daily", KRX) → [FdrFetcher, PykrxFetcher]   (야간 배치)
        ("quote", KRX)       → [KisQuoteFetcher]            (장중, realtime의 교차확인 경로)
        ("fx_rate", "USDKRW")→ [KisFxFetcher, FdrFxFetcher] (★ 02 §4.7 환율 정본의 소스)
        ("quote_global_btc", -) → [BinanceFetcher, ...]     (김치프리미엄 산출용, M7 스파이크로 확정)"""

class FetchResult(BaseModel, Generic[D]):   # ★ 응답 봉투 (00 §4 OpenBB 채택 패턴의 실체)
    results: list[D]
    provider: str                            # 실제로 응답한 provider
    observed_at: datetime
    degraded: bool                           # 우선순위 리스트에서 폴백이 발생했는가
```

**응답 봉투를 두는 이유**: 우선순위 리스트를 순회하다 폴백이 발생하면 `degraded=True`와 **실제 응답 provider**를 함께 반환해야 "어느 소스의 값으로 그 판정을 했는가"가 사후 재구성된다. OpenBB `OBBject`의 `warnings`/`chart`/`extra`는 다사용자 CLI를 위한 것이므로 옮기지 않는다.

### 3.4 상태머신·Protections·RPC (freqtrade 이식 + SAFE_MODE)

```python
class BotState(StrEnum):          # 전역 상태 — DB 단일 행
    RUNNING
    SAFE_MODE             # 목표비중 동결, 하향 방향 매도 금지, 순매수 상한, 밴드 2배
    PAUSED                # 신규 매수 중단, 매도·모니터링·리포트는 계속
    STOPPED               # 전 집행 정지(미체결 취소), 데이터 적재만
    HALTED                # 브레이커 발동 — 신규 주문 전면 중단, 포지션 유지
    RELOAD_CONFIG         # 설정 재로딩 → 봇 객체 전체 재생성(핫스왑 아님, DB에서 복원)

class SleeveState(StrEnum):      # 슬리브별 오버레이 — sleeve_state 테이블
    ACTIVE
    PAUSED                # 신규 매수만 중단
    PAUSED_ALL            # 양방향 주문 정지 (시크릿 만료 D-7, P9-order 단일 venue)

class PresenceState(StrEnum):    # 부재 평면 — presence 단일 행 (03 §5.3.1)
    NORMAL                # 0~24h 무응답
    AWAY_SOFT             # 24~72h
    AWAY                  # 72h~7d
    AWAY_LONG             # 7d+  — SAFE_MODE 파라미터를 상태 전이 없이 적용한다

# 슬리브 = {kis_domestic, kis_overseas, upbit}  (브로커 × 시장. 계좌 단위가 아니다)
# ★ 결합 규칙: min()이 아니다 — 세 enum은 원소가 서로소라 단일 전순서가 없다.
#    각 상태를 5축 제약 벡터(신규매수 / 매도 / 목표비중 갱신 / 밴드 배수 / 순매수 상한)로
#    정의하고 축별로 더 제한적인 값을 취한다.
#      매수 축 = min(2값 격자)  /  매도 축 = min(3값 격자:
#        SELL_ALLOWED > SELL_DOWNWARD_BLOCKED > SELL_BLOCKED)
#      목표비중 축 = AND  /  밴드 배수 = max  /  순매수 상한 = min
#    ★ 세 평면이다: BotState(전역) ∪ SleeveState(슬리브) ∪ PresenceState(부재).
#      AWAY_LONG은 상태 전이 없이 SAFE_MODE 행과 같은 제약 벡터를 부과한다
#      (값을 중복 기재하지 않고 03 §2.2 SAFE_MODE 값을 참조한다).
#    5축 표와 전이의 정본은 03 §2.1, 부재 평면은 03 §5.3.

class Protection(ABC):
    def check(self, ctx: ProtectionContext) -> ProtectionResult: ...
    # action: block_plan | pause_bot | safe_mode | block_symbol | none
    # 체인은 config 선언 순서로 평가, 하나라도 block이면 집행 중단 + 알림
    # 파라미터·브레이커 정본(P1~P15)은 03 문서

class RPCManager:
    """멀티채널 브로드캐스트. 채널별 이벤트 on / muted / off 3단계.
    on    = 발송 + 주목(소리·푸시)
    muted = 발송하되 무음 (Telegram disable_notification, SMTP 정상)  ← 부재 중 브리핑
    off   = 미발송 (로그·대시보드만)                                   ← 03 §7.2의 silent
    채널 A: Telegram (알림 + 명령 수신, chat_id allowlist)
    채널 B: SMTP 이메일 (알림 전용 — 명령 수신 금지)
    채널 C: Webhook (dead-man's switch ping), Log (항상 on)
    집행 전제: A·B 중 하나라도 발송 성공. 양쪽 모두 실패해야 신규 집행 보류.
    Telegram 상태 변경 명령은 chat_id allowlist + 인라인 버튼 2단계 확인."""
```

**`SAFE_MODE`가 fail-safe의 기본 목적지다.** 무인 운용에서 전면 정지는 "리밸런싱하지 않겠다"는 능동적 포지션이며 하락장에서는 그 자체가 리스크다. `HALTED`는 **장부 무결성이 의심되는 경우(등급 A: P8 대사 불일치, P9-order 2개 venue 이상)와 등급 B\*(P1b −25%, P13 NAV 40% 초과, 순매수 상한 초과)에만** 쓴다. **상태 정의·5축 제약·전이 조건의 정본은 [03 §2.1](03-safety-operations.md), 노출 상한은 [03 §2.2·§2.4], fail-safe 목적지는 [03 §3]**이며, 요약하면:

- 금지되는 것은 **매도 전체가 아니라 "목표비중 하향 방향의 매도"**다. 밴드 복귀·cash-flow 방향 매도는 허용 — 이것을 막으면 SAFE_MODE 도입 명분(MDD −15% 국면이 곧 밴드 리밸런싱의 가치가 가장 큰 국면)이 자기모순이 된다.
- 노출 상한은 주문금액이 아니라 **순매수액**(일 NAV 3% / 월 NAV 10%)이다. 밴드 복귀는 매도+매수 쌍이라 순매수가 0에 가까워 상한을 소비하지 않고, "현금으로 하락 추격 매수"만 상한에 걸린다.
- 감시 동결(`SV3`)로 인한 **비대칭 재정규화(축소 방향)는 SAFE_MODE에서도 허용**한다 — 목표비중을 낮추는 것이 아니라 거래 불가능한 자산을 계산에서 제외하는 행위이기 때문이다.

### 3.5 실시간 가드 인터페이스 — 일방향 밸브(one-way valve)

```python
class Verdict(StrEnum):
    PROCEED   # 계획대로
    DEFER     # 이번 슬라이스 보류 (재평가 후 재개, 연기 예산 소진 시 당일 포기)
    SHRINK    # 이번 슬라이스 수량 축소 (계획 총량을 넘지 않는 방향으로만)
    ABORT     # 당일 해당 종목/시장 집행 중단

@dataclass(frozen=True)
class GuardOutput:
    verdict: Verdict
    scope: Literal["instrument", "venue"]        # ★ ABORT(종목) vs ABORT(시장, 당일)
    sides: frozenset[Literal["buy", "sell"]]     # ★ 판정이 적용되는 방향.
                                                 #   기본 {"buy","sell"}이며 가드는 이 집합을
                                                 #   **줄이기만** 할 수 있다(예: 급락 가드는
                                                 #   {"buy"}만 남긴다 = 매수만 차단).
                                                 #   CI 아키텍처 테스트 guard.oneway가 강제.
    limit_price_hint: Decimal | None   # 호가 기반 가격만. marketable limit을 넘을 수 없다
    reason: str
    source_event_id: str               # 감사로그 연결고리
    counterfactual: str                # "이 판정이 없었다면 무엇이 일어났을 것인가"
```

`create` / `expand` / `sell_more`는 **존재하지 않는다.** 액션 공간이 단조 축소적이므로 실시간 계층은 정의상 알파를 추구할 수 없고, 따라서 리밸런싱 빈도 실증과 충돌할 여지가 구조적으로 없다.

**`GuardOutput`은 순수 판정이며 예산 카운터를 소유하지 않는다.** `realtime`은 §2.2 계약상 **어떤 상태도 쓸 수 없는데**(`realtime -/-> persistence.repos.*`), 문서가 `realtime`에 **일 단위로 누적되는 값**을 여럿 부여했다 — `etf.premium_gate.max_defer_count`(연기 3회)·`max_total_defer_min`(당일 90분)·`ABORT`(시장, **당일**)·"가드 3회 연속 실패 시 비활성"(§2.4). 이 값들이 프로세스 메모리에만 있으면 **집행 창 도중 재시작(§6.4 자기복구 또는 03 §6.3 배포) 한 번에 상한이 조용히 무효화**된다. 따라서:

- 연기 횟수·당일 연기 누적 분·시장 단위 `ABORT`·가드 연속 실패 카운터는 **`execution`이 소유**하고 `persistence.repos.execution_state`(신설, `execution`만 허용)에 `(run_date, venue, instrument_key, counter_kind, value)`로 영속화한다.
- `realtime.guards`는 이 값을 **인자로 받아 판정만 반환**한다. `realtime -/-> persistence.repos.*` 금지는 그대로 유지된다.
- §2.2 계약에 `execution → persistence.repos.execution_state 허용`을 추가하고, 03 §3 재시작 행·§6.3 기동 셀프체크 목록에 **"당일 가드 예산·시장 ABORT 복원"**을 포함한다(03 §4.3 F22가 이를 검증한다).

`counterfactual` 필드는 선택이 아니라 **필수**다. 03 §4.6의 tracking error 분해가 5항목(비용 / 체결 시점 / **가드·감시 개입** / **SAFE_MODE 제약** / 잔차)으로 확장되었고, ③④를 계산하려면 **미집행 주문도 감사로그에 있어야** 하기 때문이다. 이것이 없으면 롤백 트리거 R1이 가드 개입을 잔차로 오인해 오탐한다.

**가드 발동 조건(모두 AND)**: ① 최소 지속 30초(단일 틱으로 발동 불가) ② 가능한 경우 REST 스냅샷 1회 교차 확인 ③ 마지막 정상 틱으로부터 5분 이내. 예외는 `Fill`과 거래정지 — 결정론적 사실이므로 즉시 반영한다. 근거: 2024-08-05 장중 VIX 65는 유동성 없는 프리마켓 SPX 옵션으로 계산된 아티팩트였다(동시점 VIX 선물 35 미만). **스트레스 국면의 실시간 지표는 그 자체가 오염된다.**

가드 목록에 **매도를 유발하는 것은 하나도 없다.** 급락 가드도 김치프리미엄 가드도 매수만 막는다. 코어의 가격 기반 자동 손절은 금지다(Kaminski-Lo: 랜덤워크 하 손절은 기대수익을 항상 감소). 2020-03과 2024-08-05 두 사례 모두 "그날 거래하지 않는다"가 옳았고 "청산한다"가 틀렸다.

### 3.6 감시 게이트 — 소비자 API

```python
class SurveillanceLevel(IntEnum):
    SV0_RECORD = 0     # 기록만
    SV1_NOTIFY = 1     # 알림
    SV2_NO_BUY = 2     # 신규매수 금지  ← unknown(판정 불가)의 fail-safe 기본값
    SV3_FREEZE = 3     # 거래 동결(양방향)

class EscalationKind(StrEnum):          # ★ enum을 의도적으로 분리한다
    ESC_REPLACE   = "replace"           # 대체 종목 교체 제안 (승인 필요)
    ESC_LIQUIDATE = "liquidate"         # 청산 제안 (승인 필요)

# 소비자 API(6개 메서드)의 정본은 06 §7.2다 —
#   level_of / reasons / partition_by_tradability / blocked_for_buy /
#   assert_tradable / frozen_nav_ratio
# 여기서 중복 정의하지 않는다.
```

**청산을 등급 enum 밖에 둔 것 자체가 설계다.** enum 안에 두면 "등급을 하나 올리면 청산"이라는 연속 스펙트럼으로 읽히고, 그러면 언젠가 자동화된다. 타입이 막는다 — 코드 리뷰가 아니라.

**`unknown`의 스냅샷 유예**: 소스가 STALE이어도 **전일 성공 스냅샷이 `max_age`(기본 2거래일) 이내면 그것을 사용**한다. `unknown`은 "한 번도 관측된 적 없거나 스냅샷이 `max_age` 초과"일 때만 부여한다. 즉 **소스 장애 하루는 아무것도 바꾸지 않는다.** 이 유예가 없으면 소스 장애 첫날에 전 종목이 SV2가 되어 자동이체 입금이 현금으로만 쌓인다.

## 4. 스케줄링

### 4.1 거래 캘린더

- **국내**: `exchange_calendars`(XKRX) 1차 + 장 시작 전 KIS 휴장일 조회 TR(CTCA0903R) 교차검증. **불일치 시 그날 국내 집행 중단 + critical 알림**(fail-safe).
- **미국**: XNYS 캘린더가 서머타임·조기폐장을 반영 → 미국 잡은 고정 cron이 아니라 **캘린더가 계산한 UTC 시각으로 매일 동적 등록**(DST 문제 원천 차단).
- **크립토**: 상시 개장. **업비트에는 점검 상태 API가 없다** — 점검은 06 §10의 **응답 기반 감지**(주문·조회 API의 연속 3회 점검성 응답 503/타임아웃 → 크립토 슬리브 당일 집행 보류, 정상 응답 3회 연속 시 자동 해제)로 판정하며, 그 구간을 CLOSED로 취급한다.
- 결제일 계산기: 국내 T+2 예수금, 미국 T+1(+국내 휴장일) — 세금 마감일·가용 현금 판정의 기반.

### 4.2 일일 파이프라인 시각표 (KST)

집행 창·주문 전략의 근거는 [02 §4 집행 스펙](02-investment-engine.md)이 정본이며, 이 표는 그것을 스케줄로 배열한 것이다.

| 시각 | 잡 | 내용 |
|---|---|---|
| 상시(24/7) | `realtime_t0` | **T0 WS 세션 유지**: KIS 체결통보 2건(`H0STCNI0`/`H0GSCNI0`) + 업비트 private(`myOrder`/`myAsset`) + 업비트 public `ticker`(BTC·ETH). 워치독·백오프 재연결 자체 관리. **장애 시 degrade only — HALT 유발 금지** |
| 02:00 | `nightly_data_batch` | pykrx/FDR 야간 배치(요청당 1초 지연): 일봉·시총 → Parquet. 마지막 **마스터 diff 분할/병합·코드 변경 감지 → 대사 화이트리스트 등록** 단계만 02:10 `surv_master_sync`를 최대 30분 기다리고, 미완료면 직전 2개 스냅샷으로 퇴화해 하루 지연과 warning을 남긴다(설계 12 [DD-12-19]). 실패해도 거래 차단 안 함(전일 캐시) |
| 02:10 | `surv_master_sync` | KIS 종목마스터 `.mst.zip` 다운로드·파싱 → 전종목 상태 플래그 갱신(`surveillance_flags`). 실패 시 전일 스냅샷 유지(§3.6 유예) |
| US 마감+20분 (동적) | `us_reconcile` | 미국 체결 확인·대사, 자동환전 결과 확인, 미국 일봉 적재 |
| **07:00 (하드 예산 10분)** | `daily_planner` | KIS 토큰 선제 갱신, **WS approval_key 재발급 + T0 세션 재수립**(§5.3), 휴장일 교차검증, 오늘 동적 잡 등록, **환율 스냅샷 취득**(02 §4.7), 헬스체크, **시크릿 만료 점검**, 부재 사다리 평가. 내부 서브스텝으로 `surv_daily_poll`(CTPF1002R 보유∪후보) + `surv_overseas_poll`(해외 search_info) + **`surv_ksdinfo`**(예탁원 합병/분할/감자 사전 캘린더 → KR-12) 실행 — **3개 합산 타임아웃 300초** |
| 07:30 | `signal_and_plan` | **업비트 슬리브 제외**(크립토는 09:00 `crypto_execute`가 슬리브 단일 판정으로 소유 — 02 §4.3.0-d). **전일 종가 기준** 드리프트 판정(밴드는 02 §4.3 계좌×모드 표) + cash-flow 반영 → RebalancePlan(정수 수량·호가단위) → HRP sanity → Protections 평가. **감시 폴 완료를 기다리지 않는다**(§4.3) |
| 08:30 | `morning_brief` | 브리핑 1건으로 통합: 전일 성과 + 오늘 계획 + 당일 확인코드 + "10:00 자동 집행 예정, /reject로 취소" + **전일 가드 개입 N건 1줄 집계**. **Telegram·이메일 중 하나라도 발송 성공이 당일 자동 집행의 전제조건** |
| 08:55 | `surv_upbit_poll` | 업비트 `/v1/market/all?isDetails=true`(**유의종목만** — 점검 상태는 06 §10의 응답 기반 감지가 담당). `crypto_execute`보다 앞 |
| 09:00 | `crypto_execute` | 암호화폐 위성 **일 1회 판정·집행**(업비트 일봉 경계 직후). **슬리브 밴드 판정의 유일한 소유자**(02 §7 의사코드). **판정 주기는 일 1회 고정**이며 WS는 집행 품질·급락·김치프리미엄 감시 전용. 집행 중에만 `orderbook` 추가 구독 |
| 10:00–14:30 | `krx_execute` | 국내 집행 창(개장·폐장 30분 회피): 지정가 marketable limit, 재호가 5분×3회(시장가 폴백 없음), 미체결 잔량 이월 없음. **오늘 국내 주문이 있을 때만 T1 구독 등록**(활성 종목 한정), 계획 소진 또는 14:30에 전량 해제 |
| 15:40 | `krx_eod` | 체결확인·대사, EOD 스냅샷, 세금 원장 갱신(결제일 기준), **전일 미국 자동환전의 익영업일 주간환율 재정산 확정분 반영 → 대사 화이트리스트(`kind=fx_resettle`) 등록**(03 §1.3.1). 이 서브스텝이 없으면 미국 결제가 도는 날마다 P8이 현금 불일치로 발동한다 |
| 22:20/23:20 (동적) | `us_submit_close` | 미국 기본 경로: **LOC 제출**(리밸런싱은 종가 판정이므로 종가 체결이 정합). LOO/MOO도 이 잡에서만 가능. **LOC 경로에서는 T1 WS를 구독하지 않는다** |
| US 개장+30분~마감−30분 (동적) | `us_execute_limit` | 대안 경로(config): 장중 지정가 + 재호가 5분×3회. Blue Ocean 주간거래는 코드 레벨 금지 |
| 매시 정각 | `guard_monitor` | 일중 모니터링 — **신규 주문 생성 없음.** 실시간 가드는 축소 방향 조치(DEFER/SHRINK/ABORT)를 발동할 수 있으나 **드리프트 밴드 재판정은 하지 않는다.** 집행 창 밖에서는 T0 채널(업비트 ticker)과 REST 스냅샷만 사용 |
| **매월 1일 03:30 (하드 예산 30분)** | `monthly_targets_batch` | ★ **목표비중 재추정의 유일한 잡**: BL 균형수익률 → LW 공분산(`Σ_strategic`) → 제약 MVO → HRP sanity(P7) → 조건수 게이트(P7-cond) → `market_weights` 지역 비중 갱신 → **계좌별 sub-target 재분해**(02 §4.3) → 카나리 α 등록 → **`var/policy/targets.yaml` 산출**(아래 주석 참조). **선행 조건: `nightly_data_batch` 성공 + `universe_reeval` 완료**(후자 실패 시 전월 `universe.yaml`로 진행하되 브리핑에 명시). 실패·게이트 미통과 시 **직전 `targets.yaml`을 그대로 유지**(운용 정지 아님) |
| **매월 1일 02:30** | `universe_reeval` | 02 §2.3 유니버스 필터 파이프라인 전체 재평가 → hard 필터 탈락 시 검토 플래그 → **`var/policy/universe.yaml` 산출**. 실패 시 전월 값 유지. **`monthly_targets_batch`보다 먼저 돈다** — 순서를 뒤집으면 목표비중이 전월 유니버스로 산출된다 |
| **매월 1일 02:20 + 기동 셀프체크 1회 + YAML 해시 변경 시** | `external_expectations_sync` | `external_schedules.yaml`(월정액 자동이체·적립식 예약매수)의 **당월 + 익월 30일분** 스케줄을 **`reconcile_expectations` 행으로 전개**(03 §1.3.1, `source=external_schedule`, `expires_at` 포함). **트리거가 셋인 이유**: 월 1일 단독이면 ① 15일에 처음 실전 투입하면 그 달 자동이체일에 기대값이 0건이고 ② 사용자가 10일에 YAML을 고쳐도 다음 달 1일까지 반영되지 않는다. `always` catch-up은 "오늘 예정이었던 잡"에만 걸리므로 구제하지 못한다. **멱등 키 `(source, account_id, kind, instrument_key, expected_date_from)`로 중복 전개를 막는다.** **이 잡이 없으면 매월 지정일마다 P8(등급 A `HALTED`, 자동 해제 영구 금지)이 발동한다**(03 §8) |
| 매월 1일 05:00 | `research_rank` | 수집 항목 LLM 구조화 추출 + 인용 검증 + 룰 엔진 → 다이제스트 (M10a) |
| 매월 1일 09:00 | `monthly_report` | LLM 월간 리포트 파이프라인(§8.1). 다이제스트를 섹션으로 포함 |
| **11월 1일 09:00 + 12/8·12/15·12/19 09:00** | `waterfall_gap_check` | 연금저축·IRP·ISA의 YTD 납입액 집계 → 공제 한도 잔여 산출 → 잔여 시 **critical**("12월 20일까지 X원 추가 이체 필요, 예상 세액공제 Y원") + D-12/D-5/D-1 재알림. 연금저축 600만 공제 = 연 79~99만원 확정 수익으로, 이 시스템 알파 추정(연 5~21bp)을 두 자릿수 배 압도한다 |
| 11/25~12월 평일 | `tax_harvest` | 하베스팅 후보 산출(**후보 선정·수량 산정 규칙의 정본은 02 §5.1.2**, T+1 결제일 역산 마감 D*−2), 첫 해는 지시서+수동 승인. **SAFE_MODE 중 자동 실행 금지** |
| 일요일 03:00 | `weekly_maintenance` | DB VACUUM·백업 검증, Parquet 무결성, 로그 로테이션, 카세트 스모크, 감시 소스 헬스 리뷰 |
| 일요일 04:00 | `research_collect` | 릴리스노트·문서·논문 수집기 실행(M10a). 실패해도 warning만 |
| **일요일 05:00** | `crypto_vol_scale_update` | 02 §7 크립토 슬리브 σ_realized(EWMA λ=0.94, 60일) 재계산 → 실효 비중 스케일 갱신. **주 1회 고정 — EX-4 판정 전까지 일중·일간 갱신 금지**(근거 강도 "중간", 02 §3.6). 06 §10에 따라 유의종목 지정 시 갱신 동결 |
| **분기 첫 영업일 04:00** | `mc_projection` | 02 §9 몬테카를로 목표 확률 재산출(block bootstrap 5,000경로). 월간 −10% 초과 급변 시 임시 실행. **매매 경로와 완전 분리 — 모니터링 전용** |

휴장일: 플래너가 해당 venue 잡을 등록하지 않고 브리핑에 "휴장" 명시. 반일장은 XNYS 세션 시각을 그대로 따름.

#### 4.2.1 잡별 catch-up 정책 (재시작 시 판정)

run ledger는 "오늘 해야 했는데 안 한 일"을 판정하지만, **그 판정 결과로 무엇을 할지**가 정의되어 있지 않으면 재시작이 이중 집행을 만든다. 잡을 3분류한다.

| 분류 | 잡 | 재시작 시 |
|---|---|---|
| **`none`** — 시각 자체가 의미인 잡 | `morning_brief`, `crypto_execute`, `us_submit_close`, `monthly_targets_batch`, `guard_monitor` | **재실행하지 않는다.** 미실행 사실을 기록하고 브리핑·다이제스트에 표기. 목표비중 배치는 익월로 미루지 않고 **다음 영업일 03:30에 1회 재시도**. `guard_monitor`는 다음 정각에 자연 회복 |
| **`until HH:MM`** — 창이 남아 있으면 실행 | `daily_planner`(→ 07:20 — 07:30 `signal_and_plan`을 침범하지 않는다. 그때는 예산 10분이 아니라 **잔여 시간만** 쓰고 미완료분은 `unknown` 처리), `signal_and_plan`(→ 08:00), `krx_execute`(→ 14:30), `us_execute_limit`(→ 마감−30분), `surv_upbit_poll`(→ 08:58), `tax_harvest`(→ D\*−2), **`waterfall_gap_check`(→ 12/19** — 재알림 3회가 12월에 있으므로 창을 11/30에서 늘린다. 79~99만원 확정 손실 경로다) | 창 안이면 catch-up, 창 밖이면 skip + 알림 |
| **`always`** — 언제 돌아도 결과가 같은(멱등) 잡 | `nightly_data_batch`, `surv_master_sync`, `surv_daily_poll`, `surv_overseas_poll`, `surv_ksdinfo`, `us_reconcile`, `krx_eod`, `universe_reeval`, `crypto_vol_scale_update`, `mc_projection`, `monthly_report`, `weekly_maintenance`, `research_collect`, `research_rank`, `external_expectations_sync` | 즉시 catch-up |
| **분류 대상 외** | `realtime_t0` | 상시 잡. 워치독·백오프가 자체 관리하며 run ledger 대상이 아니다 |

- **커버리지 불변식(CI 테스트)**: **§4.2의 모든 잡은 반드시 이 표의 한 행에 속한다.** 분류 없이 등록된 잡이 있으면 기동 셀프체크가 실패한다 — 분류를 잊은 잡은 재시작 시 이중 실행 여부가 미정의가 되기 때문이다.
- **불변식**: 동일 `run_date`(venue별 현지 거래일)에 `status=done`인 잡은 어떤 경우에도 재실행하지 않는다.
- 집행 계열 잡의 catch-up은 03 §3의 **"대사 통과 전 주문 금지"**를 그대로 따른다 — catch-up 판정이 대사를 앞지르지 않는다.

### 4.3 아침 창(07:00~07:30) 시간 예산 — 자기 유발 정지 방지

08:30 브리핑 발송 실패는 **당일 신규 집행 보류**를 뜻한다(03 §3). 따라서 07:30이 밀리면 그 자체가 정지 사유가 된다 — **감시 폴 실패가 운용 정지로 전이되는 경로를 구조적으로 끊어야 한다.**

| 항목 | 예산 | 초과 시 |
|---|---|---|
| `daily_planner` 창 전체 | **하드 10분** (07:00~07:10) | 초과분은 다음 잡으로 이월하지 않고 중단 |
| `surv_daily_poll` + `surv_overseas_poll` + `surv_ksdinfo` | **3개 합산 300초** | 미완료 종목을 `unknown`으로 표기(§3.6 유예 규칙 적용 후에도 미상이면 `SV2`). `surv_ksdinfo` 미완료 시 KR-12는 야간 마스터 diff 사후 감지로 퇴화 |
| `signal_and_plan`(07:30) | — | **감시 폴 완료를 기다리지 않는다.** 07:30 시점의 플래그 스냅샷을 그대로 사용 |

> **순서 불변식(완화형)**: `signal_and_plan`은 감시 폴의 **결과가 있으면 쓰고, 없으면 `unknown = SV2`(매수 계획에서 제외)로 처리하고 정시 진행**한다. 감시 폴 실패가 판정 자체를 지연시켜서는 안 된다.

## 5. KIS·업비트 제약 대응 컴포넌트

### 5.1 TokenManager — 캐시 + 락 + 선제 갱신

- 접근토큰 24h 유효 / 재발급 1분 1회(EGW00133) 대응: **SQLite `broker_tokens` 테이블**에 (env, token, issued_at, expires_at) 영속화 — 재시작에도 재발급하지 않음.
- **다중 프로세스 토큰 경합 방지**: 파일락 경로를 **`/app/var/db/.token.lock`**(= `omra-db` 볼륨)으로 고정한다. **`tools`는 이 락을 쓰지 않는다** — `omra-db`를 `:ro`로 마운트하고 브로커 자격증명도 없어 토큰을 요구하지 않기 때문이다(§1.6). 락의 실제 경합 상대는 `app` 안에서 사람이 돌리는 CLI(`omra config`·수동 조회)뿐이다. **락 획득 직후 반드시 캐시를 재조회**해 유효 토큰이 있으면 재발급하지 않는다(double-checked locking) — 그렇지 않으면 두 프로세스가 순차적으로 각각 재발급해 EGW00133을 자초한다. 다만 **근본 방어는 `tools` 컨테이너를 브로커 자격증명 없이(=오프라인 모드로) 기동시키는 것**이며(§1.6), 백테스트·챌린저 CLI는 토큰을 요구하지 않는다. 락은 `omra config`·수동 CLI 같은 예외 경로를 위한 2차 방어선이다.
- 만료 30분 전 백그라운드 선제 갱신(07:00 플래너 1차 보장). 401 수신 시 asyncio.Lock 안에서 1회만 재발급 후 재시도. EGW00133 수신 시 70초 대기 후 1회 재시도, 실패 시 주문 정지 + critical.
- **WebSocket `approval_key`**도 동일 저장소 관리하며, **07:00 플래너에서 만료 여부와 무관하게 선제 재발급**한다(유효기간이 미확인이므로 재발급 비용이 재연결 실패보다 싸다 — M1 W7에서 실측). **재발급은 T0 세션 재수립을 동반한다**(§5.3 세션 생명주기) — 재발급이 기존 세션의 승인을 무효화할 가능성이 있는데 24/7 상시 채널을 "연결 확인"만 하고 넘기면 **좀비 세션(연결은 살아 있으나 이벤트가 오지 않는 상태)**이 생겨 체결통보를 조용히 잃는다. **체결통보 등록에는 HTS ID 필요 — 시크릿 목록에 포함.** 구독 성공 응답의 AES key/iv는 세션 상태에 보관하고, 유실 시 재구독한다(복호화 실패를 조용히 넘기지 않는다).
- **앱키 만료는 토큰 문제가 아니라 운영 문제다** — §6.2 참조.

### 5.2 RateLimiter — 우선순위 token bucket

- 계좌/앱키 단위 단일 버킷 공유 → 시세가 주문을 굶기지 않도록 우선순위 큐: `ORDER(0) > FILL(1) > QUOTE(2) > BATCH(3)`.
- 실전 rate=15/s(문서상 20에 안전마진), 모의 프로파일 2/s — config 분리로 모의 테스트가 실전 코드 경로를 그대로 탄다. '초당 거래건수 초과'(EGW00201) 시 tenacity 지수 백오프(0.5s→8s) + 해당 버킷 일시 축소.
- 업비트는 응답 헤더 `remaining-req: group=…; min=…; sec=…`를 파싱해 버킷 잔량에 실시간 반영하고, `sec` 잔여 < 3이면 즉시 스로틀한다. 헤더가 없는 응답은 자체 카운터로 보수 추정.

**불변식 4개 (CI 아키텍처 테스트로 강제)**

```
1. ORDER 버킷은 어떤 경우에도 QUOTE/BATCH에 선점당하지 않는다.
2. 전체 소비가 '현재 rate limit 프로파일 상한의 80%'를 넘으면
   QUOTE → BATCH 순으로 자동 축소한다.
   (실전 15 rps → 12에서 발동 / 모의 2 rps → 1.6에서 발동)
   ★ 절대값 12로 두면 모의 프로파일에서는 영원히 발동하지 않아
     M4 모의 4주 동안 축소 경로가 단 한 번도 검증되지 않는다.
3. EGW00201 수신 시 지수 백오프 + 해당 버킷 축소. FILL/ORDER는 축소 대상에서 제외.
4. ★ 동적 조정은 QUOTE 버킷과 폴링 주기에만 적용된다.
   ORDER 버킷 상한, P2(일일 주문 건수), P3(일일 주문 금액),
   P11(회전율 일일 예산)은 변동성·이벤트와 무관하게 고정이다.
```

**이 4개 불변식의 정본은 이 절이며, 06 §3.2는 요약 참조다.**

불변식 4가 없으면 "변동성이 높으니 예산을 늘린다"가 뒷문으로 마켓타이밍을 들여온다. **동적 조정은 더 잘 보기 위한 것이지 더 많이 주문하기 위한 것이 아니다.**

```
동적 조정 트리거: 5분 실현변동성 > 20일 평균의 2.0배  OR  ETF 괴리율 |·| > 0.3%
                 OR  LP 스프레드 > 2틱  OR  VI 발동 이벤트 수신
조치           : 해당 시장 QUOTE 상한 2 → 4 rps, 비집행 스냅 주기 60s → 10s
해제           : 조건 해제 후 5분 유지 시 원복
```

### 5.3 실시간 채널 — T0/T1 2계층, 진실원은 언제나 REST

> **두 명제를 구분한다.** **목표비중·드리프트 판정을 위한 실시간은 불필요하다** — 이것은 강하게 유지된다. 그러나 **확정된 계획을 집행하고 이상을 차단하기 위한 채널은 필요하다**: 02 §4.4의 iNAV·스프레드 게이트는 정의상 준실시간 데이터 없이 작동하지 않는다. 실시간 채널이 하는 일은 새 판단을 만드는 것이 아니라 **이미 정의된 게이트를 실제로 작동시키는 것**이다.

#### 채널 등급

| Tier | 채널 | 생존 구간 | 41건 소비 | 채택 |
|---|---|---|---|---|
| **T0 상시** | KIS 체결통보 `H0STCNI0`·`H0GSCNI0` / 업비트 `myOrder`·`myAsset` / 업비트 public `ticker`(BTC·ETH) | 24/7 | **2건 고정** | **무조건 채택** |
| **T1 집행 창 한정** | KIS 국내 `H0STASP0`(호가)·`H0STMKO0`(장운영/VI)·`H0STCNT0`(체결가)·`H0STNAV0`(ETF NAV) / 해외 `HDFSASP0`·`HDFSCNT0` / 업비트 `orderbook` | 집행 창 진입 ~ 계획 소진 | 활성 종목당 4건 | **조건부 — M9 게이트 통과 시에만** |
| **T2 폴백** | 전 REST 경로 | 상시 | — | 진실원 |

**T0를 게이트 없이 채택하는 이유**: ① 이중 주문·이중 정정 위험 제거는 명백한 순이득이다(체결 확인 폴링이 사라지므로 **REST 소비를 오히려 줄인다**) ② 업비트는 24/7이라 사람이 자는 동안 사고가 나는데 WS 비용이 사실상 0이다 ③ T0는 **종목 무관 채널**이라 재구독 로직이 없고 장애 표면이 최소다.

#### 구독 예산 — 관리자를 만들지 않는다

41건 = **(tr_id × tr_key) 쌍** 단위이며 국내·해외 전 상품이 단일 세션의 공용 예산이다(체결통보 포함). 공식 샘플 라이브러리는 40에서 하드 캡한다. → **하드 41 / 운용 상한 38 / 예비 3.**

```
고정            : H0STCNI0 1 + H0GSCNI0 1                        =  2
활성 종목당 4건 : H0STASP0 + H0STMKO0 + H0STCNT0 + H0STNAV0      =  4n

n=6  →  2 + 24 = 26   ✓ 평시
n=9  →  2 + 36 = 38   ✓ 경계 = 하드캡
n=10 →  2 + 40 = 42   ✗ 초과 — 다음 슬라이스로 미룬다
```

**예산 초과 처리와 절단 우선순위의 정본은 [06 §1.3](06-realtime-and-surveillance.md)이다.** 요약하면 `assert`가 아니라 **명시적 분기**(등록 거부 + 해당 종목 REST 폴백 + warning)이며, 절단 순서는 `① 활성 주문 보유 → ② DEFER 유지 → ③ 다음 슬라이스 후보`의 결정론적 고정 순서다. 이 문서가 소유하는 것은 **세션·재연결·`approval_key` 관리**이지 예산 정책이 아니다.

**축약 사다리(L0/L1/L2)·LRU 강등·우선순위 스코어링·구독 예산 "관리자"는 만들지 않는다.** 예산의 60~70%만 쓰는데 3단 사다리가 필요 없다. 동시 구독 대상은 "당일 계획 전 종목"이 아니라 **"현재 활성 주문 ∪ 다음 슬라이스 후보"**(통상 2~5, 최악 10종목)이고, 02 §4.3이 "매도 먼저, 체결 확인 후 매수"를 규정하므로 실제 동시 활성은 더 작다. KRX(≤15:40)와 US(≥22:30) 세션은 KST 상 겹치지 않아 36건을 통째로 재사용한다. 미국은 종목당 2건(장운영·NAV TR 없음)이라 여유가 크다.

**다종목 상시 실시간 감시는 하지 않는다.** 우리 유니버스에서 거래정지·상장폐지의 base rate는 연 0~1회이며, 그마저 주문 직전 `assert_tradable`로 잡힌다. **우리가 주문을 내지 않는 시각에 거래정지를 몇 시간 빨리 아는 것의 가치는 0이다.**

#### 세션 생명주기

```
07:00 daily_planner    approval_key 선제 재발급
                       → KIS 소켓 graceful close → 재연결
                       → 체결통보 2건(H0STCNI0·H0GSCNI0) 재등록
                       → SUBSCRIBE SUCCESS(CONFIRMED) 확인까지가 1잡의 완료 조건
                       (업비트 소켓 2개는 approval_key와 무관하므로 연결 확인만)
10:00 krx_execute 진입 오늘 국내 주문이 있는가? 없으면 T1 구독 자체를 하지 않는다
                       (밴드 미도달일이 대부분이다)
                       첫 슬라이스 종목 등록(tr_type="1", 0.05초 간격 직렬)
                       SUBSCRIBE SUCCESS 확인 → CONFIRMED
                       구독 변경은 슬라이스 경계에서만 (틱마다 바꾸지 않는다 — 일 20회 미만)
14:30 또는 계획 소진    T1 전량 해제(tr_type="2"). DEFER 중인 종목은 구독 유지하되
                       당일 총 연기 상한 소진 시 해제
LOC 기본 경로          T1 구독 없음 (개장 전 제출이므로 실시간 호가가 무의미)
```

#### 재연결·복구

```
백오프  : 1 → 2 → 4 → 8 → 16 → 32 → 60s 상한, full jitter
          (업비트 WS 연결 5/s·100/min — 백오프 없는 즉시 재시도는 한도 자체를 깬다)
동시성  : 소켓 3개가 함께 끊기면 순차 재연결(3초 간격)
재구독  : 재연결 직후 ① 명시적 전체 해제 → ② 재등록(0.05초 간격 직렬)
          해제 실패 시 세션 완전 재수립 (서버 측 구독 누수로 41 초과 방지)
등록추적: REQUESTED / CONFIRMED / FAILED 상태머신.
          FAILED 종목은 자동 REST 폴백 + warning (조용히 누락되지 않게)
워치독  : KIS 장중 30초·업비트 60초 무메시지 → 강제 재연결. 업비트 자체 PING 30초
          (서버 120초 Idle Timeout 대응). KIS PINGPONG은 수신 원문 그대로 반향
포기    : 10회 연속 실패 → 당일 WS 영구 폴백 모드 + warning (HALT 아님)
```

#### 훼손 불가 불변식 2개

1. **WS는 진실원이 아니다.** 체결·잔고의 정본은 REST 대사(국내 15:40, 미국 마감+20분)다. WS는 "빨리 아는" 채널일 뿐이며, WS의 어떤 장애도 자산 정합성을 훼손하지 못한다 — 최악의 경우 반응이 30초 늦어질 뿐이다.
2. **폴백 등가성(fallback equivalence).** WS가 있을 때와 없을 때의 **판정 결과는 동일해야 하며 차이는 지연뿐이다.** 성능 차이는 허용, 정확성 차이는 불허. 03 §4.3 통합 테스트로 강제한다: 동일 카세트를 (a) WS 이벤트 주입 (b) REST 폴링만 두 경로로 재생해 `Verdict` 시퀀스 일치를 검증.

> **따라서 WS 전면 장애는 절대 HALT를 유발하지 않고 degrade만 한다.** 상시 채널이 많을수록 "WS가 죽으면 뭔가 잘못된다"는 결합이 생기고, 그 결합이 결국 HALT 경로를 만든다 — T1을 집행 창에 묶은 두 번째 이유다.

#### T1 진입 게이트

실시간의 평균 개선폭(연 1~5bp 추정)만으로는 T1이 정당화되지 않는다. 명분이 "보험"이면 게이트도 체결가가 아니라 **"게이트가 REST 근사 대비 실제로 다른 판정을 내리는 빈도"**여야 하므로 **OR 2조건**으로 판정한다. **게이트 정의와 조건의 정본은 [04 §2 M9](04-roadmap.md)**이며, 통과하지 못하면 T1을 짓지 않고 T0만 유지한다.

**측정해서 아니면 안 한다.** 이것이 이 절의 정직성 핵심이다.

#### iNAV 게이트의 2경로 (조건부)

| 경로 | 조건 | 정책 |
|---|---|---|
| **REST 스냅샷(기본)** | 항상 | 30분 연기 × 3회, 초과 시 당일 포기·익일 재판정 |
| **실시간 NAV** | SP-E2(`H0STNAV0` 실측) 통과 시에만 | 해제 = 게이트 해소 AND **최소 300초** 경과, 연기 3회 상한, **당일 총 90분 상한** |

**두 경로의 판정 결과는 동일해야 하며 차이는 지연뿐이다**(폴백 등가성). 정본은 [02 §4.4](02-investment-engine.md).

#### 만들지 않는 것

| 항목 | 이유 |
|---|---|
| `EventBus`(토픽별 큐 정책·핸들러 3회 실패 비활성) | 토픽당 구독자가 1~2개뿐인 in-process pub/sub은 간접층만 만든다. decoder 직접 호출 + Fill만 큐(§2.4) |
| 구독 축약 사다리 L0/L1/L2 + loop lag 자동 강등 | 예산의 60~70%만 쓴다. 어서션 + 종목 9개 하드캡으로 충분 |
| 호가 잔량 기반 슬라이싱(`max_slice_vs_topbook`) | 개인 규모에서 마켓 임팩트가 사실상 0이면 효익도 0인데, 주문 건수를 늘려 P2(일일 건수)·P4(종목 쿨다운)를 압박한다. **과매매 방지를 표방하는 설계가 주문 건수를 늘릴 수는 없다.** 금액 기준 분할만 유지 |
| 실시간 신호에 의한 목표비중·밴드 재판정, 자동 손절·자동 청산 | **영구 금지** |

### 5.4 API 한도 예산표

#### 대원칙 — "최대 활용"의 올바른 해석

**[R2]의 "한도 내 최대 활용"을 REST 호출 수 극대화로 해석하면 안 된다.** KIS 국내 시세는 `intstock-multprice`(FHKST11300006)가 **1콜에 최대 30종목**을 반환하므로, 보유 14종목을 5초마다 폴링해도 0.2 rps다. 일일 총량 제한은 공식·커뮤니티 어디에도 근거가 없다. **REST 총량은 병목이 아니다.** 병목은 셋뿐이다:

1. KIS WS **41건** 구독 상한
2. 업비트 WS 메시지 **5/s · 100/min**
3. KIS REST **순간 버스트 20/s**

> **따라서 진짜 "최대 활용"은 상시 스트림을 WS로 옮겨 REST 예산을 집행 순간 버스트에 몰아주고, 나머지 헤드룸을 의도적으로 비워두는 것이다.** 헤드룸은 낭비가 아니라 **장애 복구 용량**이다 — 재시작 catch-up(전 종목 재조회 + 대사), 대사 불일치 시 3회 재조회, 카세트 스모크, WS 전면 폴백 전환이 동시에 일어나면 평시의 수십 배가 필요하다. 목표 소비율: 평시 각 그룹 **<10%**, 집행 버스트 시 **<50%**.

#### KIS REST — 시간대 × 용도 (모두 추정, M1 실측 대상)

| 시간대 (KST) | 주 소비처 | 버킷 | 평시 목표 | 상한 | 비고 |
|---|---|---|---|---|---|
| 02:00–05:00 | 야간 배치(일봉·마스터·유니버스 필터) | BATCH | ≤2 rps | 3 | pykrx 요청당 1초 지연이 실질 제약 |
| 07:00–08:30 | 플래너·휴장일 TR·토큰·approval_key·환율 스냅샷·감시 폴 | BATCH/QUOTE | ≤3 rps | 5 | 감시 폴 **약 45콜/일**(국내 `CTPF1002R` ~22 + 해외 `search_info` ~20 + `ksdinfo` ~1 + 업비트 2 — M6·M7 이후 기준. M1~M5 국내 단독 구간은 **~23콜**). 15 rps 예산의 3초 분량 — 무시 가능 |
| 09:00–15:30 (비집행) | 국내 멀티시세 스냅 60초 + 잔고 60초 | QUOTE | **0.03 rps** | 2 | 급변 감시는 T0/T1이 담당 |
| **10:00–14:30 (집행 활성)** | 주문·정정·취소·체결확인 | ORDER/FILL | 버스트 ≤12 rps | **15** | 체결확인 폴링이 T0 체결통보로 이전 → ORDER 버스트 여유 확대 |
| 15:40–16:10 | EOD 대사·스냅샷·세금 원장 | FILL/BATCH | ≤3 rps | 5 | |
| 미국 장중(비집행) | 미국 시세 60초 | QUOTE | 0.18 rps | 2 | 멀티조회 TR 미발견 — 종목당 1콜 |
| 미국 LOC 제출 / 대안 경로 | 주문·체결 | ORDER/FILL | 버스트 | 15 | |
| 상시 | 토큰·헬스체크 | BATCH | <0.05 rps | 1 | |

**평시 총 소비 추정: WS 도입 전 약 0.8 rps(안전예산 15의 5.3%) → 도입 후 약 0.25 rps(1.7%).** **실시간 도입이 한도 압박을 늘린다는 직관은 틀렸다** — 체결확인·크립토 ticker 폴링이 WS로 이전하므로 REST 소비는 오히려 줄어든다.

#### 업비트

| 그룹 | 한도 | 우리 소비 | 비율(추정) |
|---|---|---|---|
| Exchange 주문(생성·취소) | 8/s · 200/min | 09:00 집행 시 BTC/ETH 각 1~3주문 + 3분 재호가 → 분당 최대 6 | **3%** |
| Exchange 주문 외(잔고·주문조회) | 30/s · 900/min | 잔고 60초 + WS 끊김 시 폴백 | **<2%** |
| Quotation(ticker/orderbook/candles) | 10/s · 600/min, 엔드포인트 그룹별 | **WS로 대체하여 평시 0.** 일봉 배치만 | **<1%** |
| WS 연결 요청 | 5/s · 100/min | 일 3~5회(재연결 포함) | 극소 |
| WS 메시지(구독 변경) | 5/s · 100/min | 일 ≤20회(슬라이스 경계에만) | 극소 |

## 6. 설정·시크릿·감사로그·모니터링·백업

### 6.1 설정 계층 (정본: `.env` + YAML)

```
우선순위: CLI 인자 > OMRA__섹션__키 환경변수 > config.{env}.yaml > config.yaml > 코드 기본값
```

- `pydantic-settings` fail-fast 검증, `omra config show`(시크릿 마스킹)로 실효 설정 덤프.
- **시크릿은 YAML에 절대 넣지 않고 `.env`(chmod 600, git 제외)만**: `KIS_APP_KEY/SECRET`, **`KIS_PAPER_APP_KEY/SECRET`**(모의 도메인 — 실전 키와 다른 경로 보관), `KIS_ACCOUNT_NO`, `KIS_HTS_ID`, `UPBIT_ACCESS/SECRET`, `TELEGRAM_BOT_TOKEN/CHAT_ID`, **`SMTP_HOST/PORT/USER/PASS`**, `ANTHROPIC_API_KEY`, `WEB_SESSION_SECRET`, **`WEB_ADMIN_PASSWORD_HASH`**(argon2), **`DEADMAN_WEBHOOK_URL`**, Litestream 스토리지 키, **`RESTIC_REPOSITORY`/`RESTIC_PASSWORD` + 오브젝트 스토리지 키**.
- **`.env.tools`는 별도 파일**이며 브로커·Telegram·SMTP 자격증명을 **포함하지 않는다**(§1.6). 백테스트·리서치 CLI에 주문 능력을 주지 않는 것이 `labs`/`research` 격리의 프로세스 경계 쪽 절반이다.
- **입력물과 산출물을 분리한다.** `config/`는 사람이 편집하는 **입력물**이며 컨테이너에 `:ro`로 마운트된다. `monthly_targets_batch`·`universe_reeval`이 만드는 **산출물은 `var/policy/`**(rw 볼륨)에 쓰고, 유효 버전은 `policy_versions(kind, version, as_of, inputs_hash, path)` 테이블이 가리킨다. **CI 게이트 대상은 입력물 `config/*.yaml`뿐이며 `var/policy/` 산출물은 대상이 아니다** — 그렇지 않으면 매월 CI가 자기 산출물에 대해 회귀 게이트를 도는 모순이 생긴다.
- **병합 규칙**: 계층 병합에서 **매핑은 키 단위 재귀 병합, 리스트는 치환**(merge 아님)이다. `approved_substitutes`·`external_schedules` 같은 리스트를 오버레이에서 부분 수정할 수 없다는 뜻이며, 이 규칙이 없으면 "오버레이에 한 항목만 적었는데 전체가 사라졌다"가 발생한다.
- **effective-date 선택 기준 시각**: `tax.yaml` 등 버전 파일은 **주문 제출 시각의 KST 날짜**로 유효 버전을 고른다(03 §2.2의 기간 귀속 규칙과 동일 — 체결일·결제일이 아니다).

#### 구조화 설정 파일 스키마 (정본)

02 부록 A 서문이 "전체 스키마는 4개 블록의 합집합"이라고 선언하지만 그 4블록은 전부 **스칼라 키의 기본값 표**이고, 아래 파일들은 **레코드**를 담는데 어느 블록에도 없다. 그런데 잡의 직접 입력이므로 필드가 없으면 잡을 구현할 수 없다.

```yaml
# config/external_schedules.yaml — external_expectations_sync 의 입력(03 §1.3.1)
- id: pension_monthly_transfer
  account_id: pension_savings
  kind: cash_in                  # cash_in | scheduled_fill
  instrument_key: null           # scheduled_fill 만 필수
  day_of_month: 25
  holiday_shift: next_business_day   # ★ next_business_day | prev_business_day | skip
                                     #   → expected_date_from/to 폭을 결정한다
  amount_krw: 500000
  amount_tolerance_krw: 1000     # 사용자가 쓴다(시스템 산출 아님). 0 금지(03 §1.3.1)
  start_date: 2026-09-01
  end_date: null
```

```yaml
# config/universe.yaml
version: 7
approved_at: 2026-08-01
instruments:
  - symbol: "360750"
    market: KRX
    currency: KRW
    asset_class: kr_etf_equity   # 02 §4.3 EQUITY_ASSETS 판정의 입력
    sleeve: core
    tax_inefficiency_score: 4    # 02 §1.2 표1
    risk_asset: true             # 02 §1.2 IRP 70% 제약의 입력
    lot_step: 1
    tick_rule: krx_etf_5
approved_substitutes:            # 02 §2.2 — 1:1 페어, 교체 시 §2.3 필터 재통과 필수
  - ["VOO", "IVV"]
```

```yaml
# config/secrets_registry.yaml — 값은 없고 날짜만(§6.2)
- name: KIS_APP_KEY
  issued_at: 2026-08-01
  expires_at: 2027-08-01
  tier: 1
  auto_action: pause_all_d7_safe_mode_d3
```

- **config 변경도 CI 게이트를 탄다**: 스키마 검증 + 상호 제약(**`band.abs` ≤ `band.class_abs`** — 총자산 차원 비교이며 `band.isa_abs`·`band.pension_scheduled_abs`·`band.crypto_abs`는 계좌·슬리브 차원이라 제외, 예산 상위 캡 ≥ 하위 예산 실사용 등) + 백테스트 스냅샷 회귀. 코드만 CI를 타고 config는 안 타는 구멍을 메운다.

### 6.2 시크릿 만료 대장 — 1급 운영 항목

**무인 운용의 최대 단일 실패점은 시장이 아니라 시크릿 만료다.** KIS 앱키도 연 1회 강제 만료되며 **갱신 시 키가 재발급**된다(갱신 버튼은 만료 30일 전부터만 활성화). 대책이 알림뿐이면 부재 중 만료 = 전면 정지다.

| 시크릿 | 만료 정책 | 등급 | 자동 조치 |
|---|---|---|---|
| **KIS 실전 앱키/시크릿** | 신청일 +1년. 갱신은 D-30부터만 가능, **갱신 시 키 재발급** | **1급** | D-7 KIS 슬리브 **`PAUSED_ALL`** / D-3 전체 `SAFE_MODE` |
| **업비트 Access/Secret** | 발급 +1년 강제 만료(자동 갱신 없음) | **1급** | D-7 업비트 슬리브 **`PAUSED_ALL`** / D-3 전체 `SAFE_MODE` |
| KIS 모의투자 참가 기간 | 신청 단위 | 2급 | 만료 시 `paper` 환경만 비활성(실전 영향 없음) |
| KIS HTS ID / `approval_key` | approval_key 유효기간 미확인(M1 W7) | 2급 | 07:00 무조건 선제 재발급 |
| `TELEGRAM_BOT_TOKEN` | 무기한(수동 폐기 시) | 2급 | 발송 실패 3회 연속 → SMTP 단독 운용 + warning |
| **SMTP 자격증명** | 앱 비밀번호 정책에 종속 | 2급 | 발송 실패 3회 연속 → warning(Telegram 단독) |
| Litestream 스토리지 키 | 무기한 | 2급 | 백업 실패 시 critical |
| **restic 저장소 자격증명** | 무기한(오브젝트 스토리지 키 정책 종속) | 2급 | 스냅샷 실패 3회 연속 → warning, 7일 연속 → critical |
| **대시보드 관리자 계정**(`WEB_ADMIN_PASSWORD_HASH`) | 무기한 | 3급 | — (연 1회 로테이션 권고) |
| `ANTHROPIC_API_KEY` | 무기한 | 3급 | 실패 시 리포트만 skip(운용 무관) |
| `WEB_SESSION_SECRET` | 연 1회 로테이션 권고 | 3급 | — |

- **알림 사다리**: **D-45**(예고 — "갱신 버튼이 아직 열리지 않았다") / **D-30**(갱신 가능, critical) / **D-14** / **D-7** / **D-3** / **D-1**. D-30부터는 매일 critical.
- **발급일 분산 규칙**: KIS와 업비트의 최초 발급을 **6개월 이상 간격**으로 배치한다. 같은 달 만료는 그 달 부재가 곧 전면 정지다. **알림보다 배치가 효과적인 방어다.**
- **`/away` 선언 시** 부재 기간과 겹치는 만료 시크릿이 있으면 즉시 경고한다(4~5월 양도세 기간과 겹치는 경우도 동일).
- **갱신 절차는 `docs/runbook/secret-rotation.md`가 정본**: 포털 갱신 → 새 키 검증 호출 → `.env` 교체 → `docker compose up -d --force-recreate app` → 기동 셀프체크 통과 확인 → 만료 대장(`config/secrets_registry.yaml`) 갱신. **소요 15분, 장 마감 후 수행.**
- 대장의 **발급일·만료일은 config에, 값은 `.env`에** 둔다. `monitoring/`이 매일 07:00에 대장을 읽어 사다리를 평가한다.

### 6.3 감사로그

- 운영 로그: structlog JSON → stdout + `var/logs/app-{date}.jsonl`(14일 로테이션).
- **감사 이벤트 공통 봉투(정본)** — 원칙 4("모든 결정을 1년 뒤에도 재구성")와 03 §4.6 TE 5항목 분해·07 R1~R5가 이 로그를 **입력으로 소비**하므로 레코드 형태를 고정한다.

```json
{ "schema_version": 1,
  "event_id":  "01J...",                      // ULID
  "ts_kst":    "2026-08-02T10:03:11+09:00",
  "event_type": "order_submitted",            // 아래 열거
  "actor":     "scheduler",                   // scheduler | user | guard | surveillance | labs
  "correlation": { "plan_id": "...", "order_id": "...", "change_id": null,
                   "run_id": "...", "source_event_id": null },
  "payload":   { }                            // event_type별 스키마
}
```

`event_type` 열거(최소): `targets_computed` · `plan_created` · `plan_approved` · `plan_rejected` · `order_submitted` · `order_filled` · `order_cancelled` · `order_rejected` · `guard_verdict`(≠PROCEED만) · `surveillance_transition` · `protection_tripped` · `state_transition` · `config_changed` · `token_issued` · `llm_call` · `reconcile_whitelisted` · `fx_snapshot_applied` · `canary_step` · `budget_consumed` · `rollback_fired`.

**스키마 진화 규칙**: `schema_version`을 올리는 변경만 허용하고 **기존 필드의 의미를 바꾸지 않는다**(append-only 로그를 소급 재해석하면 1년 뒤 재구성이 깨진다). 필드 추가는 버전을 올리지 않고, 삭제·의미 변경은 올린다. 리더는 알 수 없는 필드를 무시한다.

- **감사로그**: `var/logs/audit/{yyyy-mm}.jsonl`, append-only·로테이션 없음·백업 대상. 기록: 신호 입력 지문(`inputs_hash`)·산출 가중치, RebalancePlan 생성/승인/거부, Protections 발동, 모든 주문·체결·취소(요청/응답 원문), 상태 전이, 설정 변경, 토큰 발급, LLM 호출(프롬프트 해시+모델+토큰 사용량), **대사 화이트리스트 통과 건**(03 §1.3.1), **적용된 환율 스냅샷**(02 §4.7).
- **마스킹(필수)**: 주문 요청/응답 원문을 저장할 때 `CANO`·`ACNT_PRDT_CD`·`HTS_ID`·`appkey`·`appsecret`·접근토큰은 마스킹하고, 계좌 식별은 내부 `account_id`로 대체한다. **03 §4.2 카세트 녹화의 마스킹 필터와 같은 코드를 재사용**한다 — 두 벌을 만들면 한쪽만 갱신되는 순간 실계좌번호가 로그에 남는다.
- **신규 필수 기록 3종**:
  - `Verdict != PROCEED`인 모든 `GuardOutput`(§3.5) — `plan_id`·`order_id`·`verdict`·**`scope`**·**`sides`**·`reason`·`source_event_id`·**`counterfactual`**. 이것이 없으면 실시간 도입이 과매매로 새는지 사후 판정 자체가 불가능하고, 03 §4.6 TE 분해 ③④를 계산할 수 없다.
  - 감시 등급 전이(SV0~SV3 진입·해소)와 그 근거 원문 발췌.
  - 카나리 α 단계 전이·롤백 발동·변경 예산 소비.
- **WS 원문은 전량 저장하지 않는다.** 체결통보 원문만 기존 주문 감사 정책(요청/응답 원문)을 따른다.
- 대시보드에 **look / breach / trade 3분 계측**(관찰 횟수 / 밴드 breach 감지 / 실제 체결)을 별도 패널로 노출하고 `trade/look` 비율 상승을 경보 대상으로 둔다.
- 백테스트도 동일 스키마로 기록해 라이브와 비교 가능.

### 6.4 모니터링

- 내부 healthcheck(`/healthz` + CLI): heartbeat 나이, DB 쓰기, 토큰 유효, 마지막 적재 시각, 디스크, **이벤트 루프 지연(loop lag)**, **WS 세션 상태·구독 등록 수**, **감시 소스 신선도**.
- **자발적 종료 워치독 = 1차 자기복구.** ★ **Docker의 restart policy는 컨테이너 프로세스의 종료(exit)에만 반응하며 healthcheck가 산출하는 `unhealthy` 상태에는 반응하지 않는다**(Docker Engine/Compose의 문서화된 동작이며, `autoheal` 같은 사이드카가 존재하는 이유다). 따라서 §1.6의 healthcheck는 컨테이너를 `unhealthy`로 표시할 뿐 재시작을 유발하지 않는다. **이 구멍이 치명적인 이유는 §9.2가 최대 실질 위험으로 지목한 "단일 asyncio 루프 점유"와 loop lag가 정확히 "프로세스가 죽지 않고 응답만 멈추는" 실패이기 때문**이다 — exit이 없으므로 restart policy는 영원히 발동하지 않는다.
  - **채택**: 봇 프로세스 내부에 워치독 태스크를 두고 **heartbeat 갱신 실패 또는 loop lag 임계 초과가 연속 N회면 `os._exit(1)`로 자발적 종료**해 `restart: unless-stopped`를 발동시킨다. 사이드카에 `/var/run/docker.sock`을 주지 않으므로 §7 보안 원칙과 충돌하지 않는다.
  - 트리거 초기값: `heartbeat_max_age_sec: 180` / `loop_lag_exit_ms: 5000` / `consecutive: 3`(전부 M4 실측 재캘리브레이션). **크래시 루프 방지**: 10분 내 자발적 종료 3회 초과 시 재기동 후 기동 셀프체크가 `STOPPED`로 고정하고 critical.
- **알림 채널 이중화가 필수다**(무인 장기 운용에서 Telegram 단일 의존은 고/치명 리스크): 채널 A Telegram(알림+명령), 채널 B SMTP(**알림 전용, 명령 수신 금지** — 메일 계정 탈취가 곧 주문 경로 탈취가 되는 것을 막는다). **집행 전제는 "둘 중 하나라도 발송 성공"**으로 완화한다. 발송 성공했으나 읽지 않은 것은 집행을 막지 않는다(negative-option의 본질) — 다만 `last_seen`이 갱신되지 않아 부재 사다리가 작동한다.
- **Dead-man's switch** ping 조건(확장): 브리핑 **산출물 생성 성공**(발송 성공이 아니다 — 부재 등급에 따라 푸시가 주 1회로 감축되므로 발송을 AND 조건으로 두면 DMS가 가장 필요한 구간에서 상시 오탐한다) + **드리프트 판정 실행 성공**(밴드 미달이어도 판정 자체는 매일 실행된다) + 대사 성공 + 감시 소스 신선도 + **venue별 계획 대비 체결률**(미국 LOC가 매일 조용히 전량 미체결되는 상태를 관측하기 위함). **"30일간 주문 0건"이 정상(밴드 미도달)인지 판정 로직이 죽어 조용한 것인지 구분 가능해야 한다.**
- **자기복구 사다리**(사람 없이 시도되는 순서): (a) Docker restart → (b) 기동 셀프체크(토큰·대사·캘린더·스키마·**진행 중 카나리 복원**·**당월 외부 스케줄 기대값 재전개**) → (c) 대사 자가치유 3회 → (d) `SAFE_MODE` 강등 → (e) `HALTED` + 일 1회 재시도(주 1회만 알림).
- 대사(reconciliation)를 모니터링의 일부로: 불일치 → 등급 A 경로(03 §1 P8).

### 6.5 백업

**`config/litestream.yml`** (RPO≈초 주장의 근거 — 이 파일이 없으면 §1.6 서비스가 아무것도 복제하지 않는다):

```yaml
dbs:
  - path: /app/var/db/omra.sqlite
    replicas:
      - type: s3
        bucket: ${LITESTREAM_BUCKET}          # .env.litestream
        path: omra-db
        sync-interval: 1s                     # ★ RPO≈초의 실체
        snapshot-interval: 24h
        retention: 720h                       # 30일
```

> **`weekly_maintenance`의 `VACUUM`과 Litestream의 충돌**: `VACUUM`은 DB를 재작성하므로 Litestream이 **전체 스냅샷을 재전송**한다. 단일 사용자 DB 크기(수십~수백 MB)에서 주 1회 재전송은 허용 가능하므로 그대로 둔다. 단 **`VACUUM` 직후 다음 스냅샷 완료 전까지는 복원 지점이 직전 스냅샷**이므로, `weekly_maintenance`는 `VACUUM` 후 Litestream 스냅샷 1회 성공을 확인하고 종료한다.

| 대상 | 방법 | 주기 |
|---|---|---|
| SQLite | Litestream → S3 호환 스토리지 (`config/litestream.yml`, `sync-interval: 1s`) | 실시간(RPO≈초) |
| Parquet | restic 스냅샷 | 일 1회 |
| **감사로그** | restic 증분 스냅샷 | **당일분 5분 증분 + 확정 월파일 일 1회** — 원칙 4("모든 결정을 1년 뒤에도 재구성")를 지키려면 RPO가 SQLite(초 단위)와 크게 벌어져서는 안 된다 |
| 설정 | git (시크릿 제외) | 커밋 시 |
| 시크릿 | 서버 외부 패스워드 매니저 사본 + **만료 대장 사본** | 변경 시 |
| 복구 리허설 | `scripts/restore_drill.sh` — **복원+대사+리포트까지 반자동, 사람은 결과 확인만** | 분기 1회 |

원장(정본)은 증권사/거래소에 있으므로 복구 후 대사 배치가 로컬 상태를 재동기화한다 — 백업이 다소 낡아도 자산 정합성은 회복된다.

## 7. 보안

1. **네트워크 노출 제로 — Tailscale**: 대시보드(8080)는 Tailscale 인터페이스에만 바인딩, 공인망에 어떤 포트도 열지 않음(SSH 포함). UFW 기본 deny.
2. **대시보드 인증**: Tailscale이 1차 방벽 + 심층방어로 세션 로그인(argon2) 유지, 상태 변경 엔드포인트는 CSRF 토큰.
3. **API 키**: `.env` → 컨테이너 env 주입, 이미지에 굽지 않음, 로그 마스킹 필터. 유출 대응 절차(즉시 폐기·재발급)를 runbook에. KIS 앱키는 출금 불가지만 주문은 가능 — 유출 시 피해 가능성 인지.
4. **업비트 키**: VPS 고정 IP 화이트리스트로 발급, 출금 권한 제외.
5. **Telegram**: chat_id allowlist 하드체크, 파괴적 명령은 인라인 버튼 2단계 확인. **SMTP 채널은 수신 전용**(명령 파싱 코드가 존재하지 않는다).
6. **컨테이너**: non-root 유저, read-only 루트 FS + 명시적 쓰기 볼륨.
7. **공급망**: uv.lock 고정, pip-audit CI, 자동 업데이트 금지(수동 승인 배포).
8. **Prompt injection 방어**: 외부 텍스트(뉴스/공시/릴리스노트/논문)는 `research` 레이어에서만 소비하고 산출물은 사람이 읽는 텍스트로만. **감시 파이프라인 안에서는 LLM 파싱을 하지 않는다** — 감시는 하드 액션(거래 동결)을 유발하므로, LLM을 넣는 순간 prompt injection이 집행 경로에 직결된다. 주문 경로 파라미터가 LLM 산출물에서 파생되지 않음을 import-linter + 리뷰 체크리스트로 강제.
9. **스크래핑 규율**: `collectors/robots.py`가 `robots.txt` Disallow를 하드 차단한다. 현재 스크래핑 소스를 쓰지 않지만 차단기는 먼저 만든다 — 소스를 붙이면서 차단기를 만들면 그때는 이미 늦다.
10. **WebSocket 평문 채널(잔여 리스크)**: KIS 실전 WS가 `ws://ops.koreainvestment.com:21000`(평문)일 경우 **시세와 구독 종목 목록이 노출**된다. **T0(체결통보)는 AES256-CBC로 보호되므로 평문 리스크는 실질적으로 T1(시세·호가·구독 종목 목록) 고유 문제**이며, 따라서 `wss://` 지원 여부 확인은 **M9 착수 시점**에 수행한다(04 §5.2, 06 §13.2와 동일). 미지원이면 "포지션 추론 가능 / 주문·자금 이동 불가" 등급의 잔여 리스크로 등재한다. **M9를 짓지 않으면 이 문제는 발생하지 않는다.**

## 8. 판단하지 않는 레이어 — `research` · `labs` · `surveillance` · `realtime`

> **원칙 9(00 §5): 관측 계층은 결정을 만들 수 없다.** 네 레이어는 확정된 계획을 **줄이거나 멈추거나 제안**할 수만 있고, 수량·방향·목표비중을 **생성**할 수 없다. 넷 다 import-linter로 동일한 방식으로 봉인된다 — 새 개념이 아니라 기존 LLM 격리 원칙의 네 번째 적용 사례다.

| 레이어 | 산출물 | 생성 불가 | 봉인 방법 |
|---|---|---|---|
| `research` | 사람이 읽는 텍스트 + `KnowledgeItem` 구조화 추출 | 가중치·주문·파라미터 | `execution`/`brokers`/`engine` import 금지 |
| `surveillance` | 감시 등급 SV0~SV3 (축소 방향) + `ESC_*` 제안 | 주문·목표비중 | `execution`/`brokers.*.client`/`engine.optimizer` import 금지 |
| `realtime` | `{PROCEED, DEFER, SHRINK, ABORT}` + 가격 힌트 | 수량·방향·계획 | `engine.optimizer/rebalancer/expected_returns`/`tax` import 금지 |
| `labs` | 챌린저 제안·카나리 α·롤백 트리거 | 주문 | `execution`/`brokers`/`rpc` import 금지 |

### 8.1 LLM 리서치 레이어 (`research/`)

- **격리 원칙**: 허용 의존성은 §2.2 계약과 문자 단위로 동일하다 — `collectors`·`core`·`persistence.ro`·`persistence.repos.research_extractions`·`data`·`audit`. `execution`/`brokers`/`engine`(전체)/`tax`/`surveillance`/`persistence.repos.experiments`/`persistence.repos.budget` import는 CI 실패. **`labs`는 계약에 넣지 않는다** — `labs -/-> research`가 이미 단방향을 보장하고, 역방향 간선은 발생 경로 자체가 없다. 데이터 흐름은 단방향: 시스템 → research → 사람.
- **역할 한정**: ① 월간 리포트 서술 ② 뉴스/공시 요약 ③ 포트폴리오 설명 Q&A(읽기 전용) ④ **지식 수집 항목의 구조화 추출**(§8.2 M10a). 가중치·주문·파라미터 생성 금지.
- **숫자는 코드, 글은 LLM**: 모든 수치는 QuantStats/엔진이 계산해 provenance로 주입, LLM 산출물에서 수치 불변 검증 후 템플릿이 숫자를 직접 삽입.

```python
class ReportNumber(BaseModel, frozen=True):        # ★ 수치 provenance (05 §1.4가 참조하는 실체)
    key: str
    value: Decimal
    unit: str
    source: Literal["computed_by_code_v1"]         # LLM 생성 수치는 이 타입을 가질 수 없다
    computed_at: datetime
    inputs_hash: str                               # §3.1 TargetWeights.inputs_hash와 같은 규약

ReportNumbers = dict[str, ReportNumber]
```

**`verify_numbers_unchanged()`의 판정 규칙**(07 §4.3 인용 검증기와 **코드 공유** — `research/citation.py`): LLM 산출 텍스트에서 정규식으로 추출한 수치 토큰이 `nums`의 값 집합(표시 형식 정규화 후)에 **정확 일치**하지 않으면 그 문장을 제거하고 `UNVERIFIED_NUMBER`로 기록한다. 한 리포트에서 **2건 이상 실패하면 해당 섹션을 서술 없이 표만 렌더**한다(숫자는 4단계에서 템플릿이 직접 삽입하므로 정보 손실이 없다). 월간 실패율이 **10%를 초과하면 사람이 개입**한다(07 §4.3과 동일 임계). **"하나라도 불일치하면 리포트 전체 폐기"는 채택하지 않는다** — 07 §4.3의 단계적 규율과 충돌한다.

```python
async def build_monthly_report(month: str) -> ReportArtifact:
    nums = compute_numbers(month)                       # 1) 코드가 수치 산출
    data_cot    = await llm_step("data_cot", nums)      # 2) 고정 DAG (자유 대화 금지)
    concept_cot = await llm_step("concept_cot", data_cot, market_context())
    thesis_cot  = await llm_step("thesis_cot", concept_cot)
    verify_numbers_unchanged(nums, [...])               # 3) 수치 불변 검증
    return render_markdown(nums, thesis_cot)            # 4) 숫자는 템플릿이 직접 삽입
```

- **Claude API 규격**: 기본 모델 `claude-opus-5`(config 교체 가능). 긴 출력은 `client.messages.stream()` + `get_final_message()`. 지연 무관 배치(뉴스 요약·지식 추출)는 Message Batches API(50% 할인). 고정 시스템 프롬프트(수치 재생성 금지·투자권유 표현 금지)는 prompt caching 대상으로 앞쪽 고정. 장문 공시는 shadow 요약 후 주입 + "신뢰할 수 없는 외부 문서" 래핑 표준화. 모든 호출은 감사로그 기록, **월 예산 상한 초과 시 자동 skip + warning**(지식 추출 배치가 리포트 예산을 잠식하지 않도록 용도별 하위 예산 분리).

### 8.2 자가 개선 레이어 (`labs/`)

`research`를 넓히지 않고 `labs`를 따로 두는 이유는 **두 격리의 목적이 다르기 때문**이다. `research`는 "LLM 산출물이 주문 경로에 닿지 않게", `labs`는 "실험이 평가 인프라·주문 경로를 건드리지 않게" 격리한다. `labs`는 `engine`의 순수 함수와 `backtest`를 호출할 수 있어야 하는데 `research`는 그것이 금지된다.

- **허용**: `engine`·`backtest`·`persistence.ro`·`persistence.repos.experiments`·`persistence.repos.budget`·`data`·`audit`·`protections`·`config`(§2.2 정본).
- **금지**: `execution`·`brokers`·`rpc`·`research`·**`collectors`**·`persistence.repos.research_extractions`. `labs -/-> execution·brokers`가 **"실험은 절대 주문을 낼 수 없다"**를 구조로 보장하고, `labs -/-> collectors`가 **"labs는 수집하지 않는다"**(수집은 `research`/`surveillance`의 일)를 보장한다. **쓰기는 `persistence.repos`의 테이블별 전용 리포지토리로만 가능**하므로 "RO"가 주석이 아니라 import 가능 모듈 집합으로 강제된다.
- **`labs` ⟷ `research`는 import로 연결되지 않는다.** LLM 추출 결과는 `research_extractions` 테이블에 쓰이고 `labs`는 persistence를 통해 읽는다.
- **범위는 M10a(수집기 + 룰 엔진 + 다이제스트, 2주)다.** 섀도(`G3`)·챔피언-챌린저·카나리 실사격은 **첫 챌린저 후보가 실제로 나왔을 때** 착수한다 — 자가 개선의 성공 지표는 채택한 개선의 수가 아니라 **놓친 부패의 수 = 0**이고, 착수를 늦추는 것이 최대 위험 완화이기 때문이다. **M10a 이전에 필요한 것은 M0의 GitHub watch 30분 설정이 전부다.**
- **카나리는 단일 코드(`labs/canary.py`)를 대상별로 파라미터화**한다: 목표비중 정기 재계산은 `α: 1/3 → 2/3 → 1 × 5거래일`, 방법론 교체는 `α: 0.25 → 0.50 → 1.00 × 20거래일`. 롤백 트리거 R1~R5의 정본은 **07 문서**다.
- **변경 예산은 상위 캡이 지배**한다: `total_per_year: 6`이 하위(targets 4 / params 4 / logic 2)를 지배하며, 어떤 하위 예산도 total 잔량을 초과 소비할 수 없다. 소진 시 모든 자동 변경이 APPROVE로 강등되고 연 1회(1/1)에만 리셋된다. **개별 변경은 전부 합리적인데 누적하면 다른 시스템이 되는 것**이 자동화 표류의 실제 형태이므로, 상위 캡(6)은 하위 합(10)보다 작아야 의미가 있다.

## 9. VPS 리소스·안정성 영향 평가

### 9.1 리소스 (추정 — M1 W10에서 1주 실측)

| 항목 | 평가 |
|---|---|
| 소켓 수 | **3개** (KIS 1 + 업비트 public 1 + 업비트 private 1). T0는 상시, T1은 동일 KIS 소켓에 구독 추가 |
| 메시지량 | T0 상시: 체결통보는 주문 시에만, 업비트 ticker BTC/ETH는 초당 수~수십 건 → **평시 부하 무시 가능.** T1 집행 창: 국내 4~6종목 × (체결가+호가+장운영+NAV) → **추정 초당 수십~수백 건**, 하루 4.5시간 중 실제 활성은 통상 30~60분 |
| CPU | 파싱은 `\|`·`^` 문자열 split + AES 복호화(체결통보만). **추정 <5%(1 vCPU).** 호가 10단계는 1건당 필드 40+로 메시지량이 급증 — "호가는 활성 주문 종목만" 규칙이 리소스 측면에서도 정당화된다 |
| 메모리 | Fill 큐만 유지, 시세는 최신값 슬롯. **추정 수십 MB 증가** |
| 디스크 | WS 원문 전량 저장 안 함. 감사로그는 `Verdict != PROCEED` 판정과 근거 요약만 append |
| **백테스트** | **봇 프로세스에서 실행 금지**(§1.6). 별도 컨테이너 일회성 실행. **M2 DoD에 10년 백테스트 1회 실행 시간 VPS 실측 추가**, 30분 초과 시 런타임 백테스트 게이트 축소·삭제 |

### 9.2 단일 asyncio 루프에서의 안정성 — 가장 실질적인 위험

**위험**: WS 수신·디코딩이 이벤트 루프를 점유하면 APScheduler 잡·FastAPI 응답·Telegram 폴링이 밀린다. 단일 프로세스 설계(00 §5.1)의 대가다.

**완화 5종**

1. **T1은 집행 창에만 존재한다.** 하루 대부분의 시간에 루프는 현행과 동일한 부하다.
2. **호가 구독은 활성 주문 종목만**(9개 하드캡). 메시지량의 지배적 원천을 최소 집합으로 묶는다.
3. **큐 정책의 비대칭**: 시세는 최신값만 유지(낡으면 버려도 된다), Fill은 절대 drop 금지. **루프가 밀려도 잃어서는 안 되는 것만 살아남는다.**
4. **핸들러에 blocking 연산 금지**를 규약화. 최적화·백테스트·LLM은 실시간 경로에 두지 않는다(import-linter가 대부분 강제).
5. **핸들러 예외 격리**: 가드 하나의 예외가 디코더를 죽이지 않는다. 3회 연속 실패 시 해당 가드 비활성 + critical.

**관측**: `monitoring/`에 **loop lag**(asyncio 타이머 오차) 지표를 추가한다. 집행 창 중 lag이 임계(예: 500ms)를 넘으면 **알림만** 발생시킨다 — 자동 강등 사다리는 만들지 않았으므로(§5.3), 반복되면 종목 하드캡을 낮추는 설정 변경으로 대응한다.

### 9.3 나빠지는 것과 좋아지는 것 — 정직한 회계

| 나빠지는 것 | 좋아지는 것 |
|---|---|
| 코드 표면 증가(session/registry/decoder/guards — 순증 추정 400~600줄) | **REST 소비 감소**: 평시 추정 0.8 → 0.25 rps |
| 새 장애 유형 5종(좀비 연결, 구독 누수, 부분 등록 실패, AES key/iv 유실, approval_key 만료) | 02 §4.4 게이트가 **실제로 작동**한다(현재는 주문 직전 스냅샷 1회로 근사) |
| asyncio 루프 부하 증가(집행 창 한정) | **이중 체결·이중 정정 위험 원천 제거**(체결통보·`myOrder`) |
| 테스트 표면 증가(폴백 등가성 검증 필수) | 크립토 24/7 감시가 사실상 무료로 확보 |
| **사용자 개입 빈도 상승 유인**(attention-induced trading) | (조건부) VI·거래정지 제외가 추정 → 실측 |

마지막 행이 가장 큰 위험이며, 대응은 §1.2의 UI 격리다. **실시간 데이터를 넣는 결정과 그것을 사람에게 보여주는 결정은 별개이며, 후자는 하지 않는다.**

## 10. M1 스파이크 — 아키텍처 관련 항목

M1 스파이크는 **로드맵을 바꾸는 것만 8개로 하드 캡**한다(04 정본). 그중 이 문서가 소유하는 항목은 셋이다.

| ID | 항목 | 무엇을 뒤집는가 | 실패 시 폴백 |
|---|---|---|---|
| **SP-C5** | 앱키 1개로 복수 CANO(계좌) 운용이 가능한가 | §5.1 TokenManager·§5.2 RateLimiter 구조(버킷이 앱키 단위인가 계좌 단위인가) | 계좌별 앱키 분리 + 버킷 분할 |
| **SP-B14** | KIS 앱키 만료일을 API로 조회 가능한가 | §6.2 만료 대장의 자동화 가능 범위 | 수동 기입 + 캘린더 이중 등록 |
| **SP-E2** | `H0STNAV0` 실시간 NAV가 KRX 공시값·`nav_comparison_trend`와 일치하는가 | **M9 착수 여부** + 02 §4.4 iNAV 게이트 경로 확정 | REST 스냅샷 경로 확정, 실시간 NAV 경로 폐기 |

**WS 검증 항목은 "T0가 의존하는가"로 나뉜다.** T0(체결통보 + 업비트 WS)는 게이트 없이 M4·M7에서 채택되고 24/7 상시 연결이므로, T0가 반드시 쓰는 항목을 "M9 착수 시에만"으로 미루면 **기본 시나리오(M9 취소)에서 상시 채널의 전제가 영구 미검증**으로 남는다.

| 구분 | 항목 | 시점 |
|---|---|---|
| **T0 의존 — 필수** | `approval_key` 유효기간 **및 재발급이 기존 세션에 미치는 영향**, **SP-B3**(앱키당 동시 세션 수 = 1인가), **모의 도메인 WS 지원·접속 URL·체결통보 tr_id**(SP-C3b) | **M1 W7 / M4**(§5.1·§6.2 표기가 정본) |
| **미국 확장 의존 — 필수** | `HDFSCNT0`·`HDFSASP0` 실지연 실측(미국 장중 대안 경로의 가격 산정 전제 — 02 §4.1) | **M6** |
| **T1 전용 — 조건부** | SP-B1(등록 상한 41 vs 40), SP-B2(체결통보가 예산에 포함되는가), 구독 해제 `tr_type`, `wss://` 지원, EGW00201 차단 지속시간, `intstock-multprice` 사전 등록 요구, WS 상시 연결 시 loop lag 1주 실측 | **M9 착수 시** |

**M9는 취소 가능한 마일스톤이므로 아래 행의 검증만 조건부**다 — 게이트를 통과하지 못하면 수행하지 않는다. 위 행은 M9와 무관하게 수행한다.
