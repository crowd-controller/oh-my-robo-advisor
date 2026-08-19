# 04. 설정 · 시크릿

> **범위**: `src/omra/config/` 패키지 전체 — `config/` 디렉터리에 놓이는 모든 YAML 파일의 스키마(필드·타입·검증 규칙·기본값·effective-date 버전 규칙), `pydantic-settings` 계층 병합과 `OMRA__` env 오버라이드, `.env` 3종 분리와 시크릿 카탈로그, 시크릿 만료 대장·알림 사다리·로테이션 절차와의 배선, config 변경 CI 게이트.
> **계획 정본**: 01 §6.1(설정 계층)·§6.2(시크릿 만료 대장)·§7(보안)·§2(config/ 트리)·§1.6(compose env_file)·§6.5(litestream.yml) / 02 부록 A(파라미터 총괄표)·§5.5 / 03 부록 A(안전장치 키)·§5.1(전환 절차)·§6.3(배포)·§6.4(시크릿 갱신) / 06 부록 C(관측 계층 키)·§5.1(리스크 카탈로그)·§8.1(등급→행동) / 07 §9(변경 예산)·부록 D(자가 개선 키) / 00 §3.2(자동화 등급표)·§5 원칙 6.
> **선행 문서**: [02-domain-model.md](02-domain-model.md)(`Account`·`AccountMode`·`Instrument`·`instrument_key`·Decimal 규약), [03-data-and-persistence.md](03-data-and-persistence.md)(`policy_versions`·`reconcile_expectations` DDL), [01-system-architecture.md](01-system-architecture.md)(기동 시퀀스 phase A·SC-1·SC-13·`RELOAD_CONFIG`).
> **이 문서가 소유하는 정의**: config/YAML 스키마·키 정의(브리프 §2.1). 시크릿 값 관리·만료 대장·`.env` 키 목록([05-broker-gateway.md](05-broker-gateway.md) §2 소유권 표가 본 문서를 지목).

---

## 1. 개요 — 설계 대상과 책임

### 1.1 이 문서가 책임지는 것

00 §5 원칙 6("파라미터는 코드가 아닌 설정 — 세법·밴드·임계값은 versioned YAML, 하드코딩 금지")이 이 문서의 존재 이유다. 그 원칙을 구현 수준으로 내리면 네 가지 책임이 된다.

1. **키 하나하나에 타입과 검증을 붙인다.** 02 부록 A·03 부록 A·06 부록 C·07 부록 D는 "키 이름 + 기본값 + 근거"의 표이지 스키마가 아니다. 이 문서는 그 4블록 합집합을 pydantic v2 모델 트리로 확정하고, 단일 키 검증(범위·enum)과 **키 사이의 상호 제약**(§4.5)을 코드가 실행 가능한 형태로 정의한다.
2. **레코드형 파일의 스키마를 만든다.** 01 §6.1이 이미 지적했듯 4블록은 전부 스칼라 키 표이고, `universe.yaml`·`external_schedules.yaml`·`secrets_registry.yaml`처럼 **레코드**를 담는 파일은 어느 블록에도 없다. 잡의 직접 입력이므로 필드가 없으면 잡을 구현할 수 없다(§5).
3. **시크릿이 코드·이미지·git·감사로그 어디에도 남지 않게 한다.** `.env` 3종 분리(§7), 마스킹 배선(§7.4), 자격증명 배치 검증(§7.5).
4. **무인 운용의 최대 단일 실패점인 시크릿 만료를 1급 운영 항목으로 배선한다**(01 §6.2). 만료 대장 스키마·알림 사다리 평가기·자동 조치 전이·로테이션 절차 연계(§8).

### 1.2 이 문서가 정의하지 않는 것 (소유권 경계)

| 주제 | 소유 |
|---|---|
| `Account`·`AccountMode`·`AccountType`·`Broker`·`Instrument`·`instrument_key`·Decimal 직렬화 | [02-domain-model.md](02-domain-model.md) §3.3·§4·§5 |
| `policy_versions`·`reconcile_expectations` 등 **DDL** | [03-data-and-persistence.md](03-data-and-persistence.md) §3.2 |
| `tr_ids.kis.yaml`의 **TR 목록·TR ID 값·`TrMap` 로더** | [05-broker-gateway.md](05-broker-gateway.md) §7.1 (본 문서는 §5.10에서 **검증 배선과 표기 규약만** 소유) |
| 브로커 payload 마스킹 필터(`brokers/masking.py`) | [05-broker-gateway.md](05-broker-gateway.md) §3.7 [DD-05-4] |
| config 로드 실패의 기동 처리(FATAL_EXIT)·`RELOAD_CONFIG` 재생성 시퀀스 | [01-system-architecture.md](01-system-architecture.md) §5.1·§5.4·§6.3 |
| 각 키를 **소비하는 로직**(밴드 판정·P1~P15 발동·가드 판정·세금 계산) | 07·09·11·10 각 문서 |
| 시크릿 만료 **감시 잡의 스케줄 등록·`monitoring/` 배치** | [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §(모니터링) — 본 문서는 평가 함수와 자동 조치 계약만 |
| 만료 알림의 **채널 라우팅·문구** | [13-web-and-telegram.md](13-web-and-telegram.md) §(알림 등급 라우팅) |

### 1.3 입력물과 산출물의 분리 (정본: 01 §6.1)

```
config/          사람이 편집하는 입력물. 컨테이너에 :ro 마운트. git 추적. CI 게이트 대상.
var/policy/      잡(monthly_targets_batch·universe_reeval)이 만드는 산출물. rw 볼륨.
                 유효 버전 포인터 = policy_versions(kind, version, as_of, inputs_hash, path)
                 ★ CI 게이트 대상이 아니다 — 매월 CI가 자기 산출물에 회귀 게이트를 도는 모순 방지
```

이 분리가 스키마 설계에 주는 함의는 하나다: **`targets.yaml`과 `universe.yaml`은 두 위치에 같은 스키마로 존재한다.** `config/`의 것은 사람이 준 시드·승인본이고 `var/policy/`의 것은 잡 산출물이며, 로더는 §6.3의 우선순위로 하나를 고른다. 스키마를 두 벌 만들면 잡 산출물이 사람이 편집한 파일과 호환되지 않는 순간이 온다.

### 1.4 파일 카탈로그 (정본: 01 §2 저장소 구조)

| 파일 | 종류 | 자동 갱신 주체 | HR(00 §3.2 P7) | CI 게이트 | 본 문서 절 |
|---|---|---|---|---|---|
| `config.yaml` | 스칼라 계층 | — (사람) | 부분(`risk.level`·`core.min_weight`·`satellite.total_cap`·`crypto.cap`·`max_account_value`·kill switch 임계·`band.*`) | ✓ | §4 |
| `config.live.yaml` / `config.paper.yaml` | 오버레이 | — | 〃 | ✓ | §4.6 |
| `universe.yaml` | 레코드 | `universe_reeval`(월 1회, 산출물은 `var/policy/`) | 계좌별 금지자산 | ✓ | §5.1 |
| `targets.yaml` | 레코드(시드) | `monthly_targets_batch`(산출물은 `var/policy/`) | — | ✓ | §5.2 |
| `goals.yaml` | 레코드 | 없음 | **전체 HR** | ✓ | §5.3 |
| `market_weights.yaml` | 레코드 | 지역 비중만 월 1회(P6) | 상위 배분 상수 | ✓ | §5.4 |
| `external_schedules.yaml` | 레코드 | 없음 | — | ✓ | §5.5 |
| `external_income.yaml` | 레코드 | 없음 | — | ✓ | §5.6 |
| `surveillance.yaml` | 레코드 | 없음 | — | ✓ | §5.7 |
| `tax.yaml` | **버전(effective-date)** | 없음(T7 = A5) | 세법 해석 = `T3` HR | ✓ | §5.8 |
| `secrets_registry.yaml` | 레코드 | 없음(로테이션 후 사람이 갱신) | — | ✓ | §5.9 |
| `tr_ids.kis.yaml` | 레코드 | 없음 | — | ✓ | §5.10 |
| `research_open_questions.yaml` | 레코드 | 없음(사람이 관리 — 14 §10.3) | — | ✓ | §5.12 |
| `litestream.yml` | 외부 도구 설정 | 없음 | — | 스키마 검증 제외(§5.11) | §5.11 |

---

## 2. 모듈 구조 (`src/omra/config/`)

```
src/omra/config/
├── __init__.py           # 공개 API 4개: load_and_validate_config / load_secrets /
│                         #   effective_dump / config_fingerprint
├── settings.py           # AppConfig 루트 모델 + pydantic-settings 소스 조립 (§3.4)
├── layers.py             # YAML 로드 · deep_merge · OMRA__ env 파서 · CLI 오버레이 (§3.2·§3.3)
├── errors.py             # ConfigError 계층 (§10.1)
├── constraints.py        # 상호 제약 검증 — 런타임과 CI가 같은 함수를 호출 (§4.5)
├── fingerprint.py        # 파일 해시·실효 설정 해시 (§3.7)
├── redact.py             # `omra config show` 마스킹 (§7.4) — 브로커 payload 마스킹과 별개
├── schema/               # config.yaml 블록별 모델 (§4.2)
│   ├── run.py            #   env · live_confirmation · manual_approve · max_account_value
│   ├── accounts.py       #   계좌 등록부 (§4.3)
│   ├── engine.py         #   risk core satellite cash bl mvo cov sanity band rebalance
│   │                     #   universe trade momentum crypto mc gk backtest
│   ├── execution.py      #   order execution etf.premium_gate
│   ├── taxcfg.py         #   tax.* waterfall.*
│   ├── protections.py    #   protections safe_mode presence tracking_error alerts
│   ├── observe.py        #   ws quote fx guard realtime surveillance data
│   ├── policy.py         #   policy.change_budget canary
│   ├── improve.py        #   research labs
│   └── ops.py            #   watchdog runtime tools monitoring web
├── files/                # 레코드형 YAML 로더 (§5) — 계층 병합 대상이 아니다
│   ├── base.py           #   RecordFile[T] 공통 로더 (경로·해시·오류 위치 보고)
│   ├── universe.py  targets.py  goals.py  market_weights.py
│   ├── schedules.py income.py  surveillance_map.py
│   ├── taxlaw.py         #   tax.yaml — VersionedFile[TaxParams]
│   ├── open_questions.py #   research_open_questions.yaml (§5.12)
│   ├── secrets_registry.py
│   └── trids.py          #   tr_ids.kis.yaml 스키마 검증 (로더 본체는 brokers/kis/tr_map.py)
├── versioned.py          # VersionedFile[T] — effective-date 선택 (§6.2)
├── policy_output.py      # var/policy/ 산출물 해석 (§6.3)
└── secrets.py            # Secrets 모델 + SecretSpec 카탈로그 (§7.2·§7.3)
```

> **[DD-04-1] `config/` 패키지 내부 분해와 단일 루트 모델 `AppConfig`**
> - 결정: 01 §2 트리가 `config/`에 부여한 책임("설정 로딩·계층 병합·스키마 검증")을 위 11개 모듈로 분해하고, `config.yaml` 계층의 유일한 루트 모델을 `AppConfig`로 둔다. 레코드형 파일은 `AppConfig`의 필드가 아니라 `ConfigBundle`이 병렬로 보유한다(§3.4).
> - 근거: 계층 병합(스칼라 오버레이 + env 오버라이드)과 레코드 파일 로딩은 **병합 규칙이 다르다**(01 §6.1: 매핑은 재귀 병합, 리스트는 치환). 레코드 파일은 통째로 리스트이므로 오버레이 병합의 의미가 없고, 오히려 오버레이에 한 줄 적으면 전체가 사라지는 사고를 부른다. 물리적으로 다른 로더로 분리해 그 사고 경로 자체를 없앤다.
> - 계획 문서와의 관계: 01 §2·§6.1의 여백(모듈 내부 구조 미정) 채움. 충돌 없음.

### 2.1 의존 규율

`config`는 관측 4레이어(`realtime`·`labs`)가 import를 **허용받은** 패키지다(01 §2.2 `realtime → … · config` 허용, `labs → … · config` 허용). 따라서 `config`는 **`core` 외의 어떤 상위 패키지도 import하지 않는다** — 그렇지 않으면 허용 간선을 타고 금지 간선이 되살아난다.

```
config → core            허용 (Decimal·Account·Instrument 타입 재사용)
config → 그 외 전부       금지 (아키텍처 테스트 AT-C1, 16이 수거)
```

`Secrets`는 `config` 안에 있지만 브로커 자격증명의 **값**만 담고 브로커 타입을 모른다 — `AccountResolver`(정의: [05-broker-gateway.md](05-broker-gateway.md) §3.2)의 구현이 `brokers` 쪽에서 `Secrets`를 읽어 `KisAccountRef`를 만든다.

---

## 3. 계층 병합과 env 오버라이드

### 3.1 우선순위 (정본: 01 §6.1)

```
CLI 인자  >  OMRA__섹션__키 환경변수  >  config.{env}.yaml  >  config.yaml  >  코드 기본값
```

`env` 자체(`live`|`paper`|`dry_run`)는 **부트스트랩 값**이라 이 사슬 안에서 순환한다 — 오버레이 파일을 고르려면 `env`를 먼저 알아야 하는데 `env`도 오버라이드 대상이다. 2패스로 끊는다.

```
pass 1: config.yaml 만 로드 → env 후보 결정
        env 후보 = CLI --env  >  OMRA__RUN__ENV  >  config.yaml 의 run.env  >  "dry_run"
pass 2: 결정된 env 로 오버레이 파일을 고르고 4계층 병합 → AppConfig 검증
        ★ 오버레이 파일이 run.env 를 다른 값으로 적으면 ConfigConflictError (기동 거부)
          — config.live.yaml 이 env: paper 를 적는 것은 언제나 사고다
```

> **[DD-04-2] `dry_run`에는 오버레이 파일이 없다**
> - 결정: 오버레이 파일은 `config.live.yaml`·`config.paper.yaml` 둘뿐이며(01 §2 트리에 그 둘만 있다), `env: dry_run`은 `config.yaml` 단독으로 동작한다. `config.dry_run.yaml`이 존재하면 `ConfigError`로 기동 거부한다(조용히 무시하지 않는다).
> - 근거: 01 §3.2의 실행 모드 3종 중 `dry_run`은 브로커 서버가 없어 도메인·TR·rate limit 프로파일 교체가 필요 없다. 존재하지 않는 오버레이를 "선택적으로 없으면 넘어감"으로 두면 오타(`config.papper.yaml`)가 조용히 무시된다.
> - 계획 문서와의 관계: 01 §2·§6.1의 여백 채움. 충돌 없음.

### 3.2 병합 규칙 (정본: 01 §6.1)

```python
# config/layers.py
def deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any], *, path: str = "") -> dict[str, Any]:
    """01 §6.1 정본: **매핑은 키 단위 재귀 병합, 리스트는 치환**(merge 아님).

    - dict × dict            → 재귀
    - list × 아무거나         → overlay 로 **통째 치환**
    - scalar × scalar        → overlay
    - dict × scalar (타입 충돌) → ConfigTypeConflict(path) — 조용한 승리 금지
    """
```

**리스트 치환 규칙의 실제 함의를 스키마가 강제한다.** 01 §6.1은 "`approved_substitutes`·`external_schedules` 같은 리스트를 오버레이에서 부분 수정할 수 없다"고 못박았다. 본 설계는 그 규칙을 다르게 지킨다 — **그 두 대상은 애초에 `config.yaml` 계층에 있지 않고 별도 레코드 파일이며(§5), 레코드 파일은 오버레이 대상이 아니다.** 따라서 "오버레이에 한 항목만 적었는데 전체가 사라졌다"가 물리적으로 발생할 수 없다. `config.yaml` 계층에 남는 리스트형 값은 스칼라 목록(`alerts.critical_channels`·`data.master.files`·`labs.tuning_space`·`labs.canary.*.alphas`)뿐이고, 이들은 치환이 자연스러운 의미다.

### 3.3 `OMRA__` env 오버라이드

```
문법: OMRA__<SECTION>__<KEY>[__<SUBKEY>...]   구분자는 이중 언더스코어
매핑: 대문자 → 소문자, __ → 중첩 경로
      OMRA__SAFE_MODE__NET_BUY_DAILY_CAP_PCT=2     → safe_mode.net_buy_daily_cap_pct = 2
      OMRA__QUOTE__MAX_AGE_MS__KRX=1500            → quote.max_age_ms.krx = 1500
값 파싱: ① JSON 파싱을 먼저 시도(리스트·불리언·숫자·null) ② 실패하면 문자열
      OMRA__ALERTS__CRITICAL_CHANNELS='["telegram"]'   → 리스트
      OMRA__RUN__MANUAL_APPROVE=true                   → bool
```

> **[DD-04-3] env 오버라이드의 구분자·파싱·경계 규칙**
> - 결정: ① 구분자는 `__`, 접두사는 `OMRA__` ② 값은 JSON 우선 파싱 후 문자열 폴백 ③ **레코드 파일(§5)의 내용은 env로 오버라이드할 수 없다** — `OMRA__UNIVERSE__…`는 `config.yaml`의 `universe.shrink_below_krw` 등 스칼라 블록에만 닿고 `universe.yaml`에는 닿지 않는다 ④ 존재하지 않는 경로를 가리키는 `OMRA__*` 변수는 **무시가 아니라 기동 거부**(`UnknownOverrideError`).
> - 근거: 계획(01 §6.1, 04 §2 M1)은 `OMRA__섹션__키` 형태만 명시하고 파싱·미지 키 처리를 정의하지 않았다. 미지 키를 무시하면 `OMRA__SAFEMODE__…`(접두사 오타 — 02 부록 A가 경고한 `safemode` vs `safe_mode` 혼동)가 조용히 아무 효과 없이 지나가며, 그것은 "설정했다고 믿는데 안 된 상태"로 무인 운용에서 가장 나쁜 실패다.
> - 계획 문서와의 관계: 01 §6.1 여백 채움. 02 부록 A 서문의 "이름이 갈리면 로더가 어느 쪽을 구현할지 결정할 수 없다"는 문제의식과 정합.

`.env` 파일도 컨테이너 env로 주입되므로(01 §1.6 `env_file: [.env]`) `OMRA__*` 변수를 `.env`에 적는 것도 동작한다. **시크릿과 오버라이드는 접두사로 구분된다** — `Secrets`는 고정 필드명(접두사 없음), `AppConfig`는 `OMRA__` 접두사만 읽으므로 두 네임스페이스는 충돌하지 않는다.

### 3.4 진입점 시그니처

```python
# config/__init__.py
@dataclass(frozen=True)
class ConfigBundle:
    app:        AppConfig                 # config.yaml 계층 병합 결과 (§4)
    universe:   UniverseFile              # §5.1  (config/ 또는 var/policy/ — §6.3)
    targets:    TargetsFile | None        # §5.2  None = 콜드스타트 (02 §3.3)
    goals:      GoalsFile                 # §5.3
    weights:    MarketWeightsFile         # §5.4
    schedules:  ExternalSchedulesFile     # §5.5
    income:     ExternalIncomeFile        # §5.6
    surv_map:   SurveillanceMapFile       # §5.7
    tax:        VersionedFile[TaxParams]  # §5.8
    registry:   SecretsRegistryFile       # §5.9
    trids:      TrIdsRaw                  # §5.10 — 검증만, 해석은 brokers.kis.tr_map
    questions:  OpenQuestionsFile         # §5.12 — 소비는 research 다이제스트 D4 (14 §10.3)
    sources:    tuple[LoadedSource, ...]  # 어느 파일·어느 계층에서 왔는지 (감사·config show)
    fingerprint: ConfigFingerprint        # §3.7

def load_and_validate_config(
    config_dir: Path = Path("/app/config"),
    policy_dir: Path = Path("/app/var/policy"),
    *,
    cli_overrides: Mapping[str, Any] | None = None,
    policy_pointer: PolicyPointer | None = None,   # policy_versions 조회 결과 (§6.3)
    clock: Clock,                                   # effective-date 선택 기준 (02-domain-model.md §7)
) -> ConfigBundle:
    """fail-fast. 첫 오류에서 멈추지 않고 **전 파일의 오류를 모아** ConfigValidationError로 던진다.
    호출 지점: 기동 phase A2 (01-design §5.1) / RELOAD_CONFIG 3단계 (01-design §6.3) /
              CI 게이트 (§9) / `omra config show`."""

def load_secrets(env_files: Sequence[Path]) -> Secrets:      # §7.3
def effective_dump(bundle: ConfigBundle, secrets: Secrets) -> str:   # §7.4 `omra config show`
def config_fingerprint(config_dir: Path) -> ConfigFingerprint:       # §3.7
```

`policy_pointer`가 `None`이면(= DB 열기 전) `config/`만 읽는다. 기동 phase A2는 DB보다 앞서므로(01-design §5.1) **최초 로드는 언제나 `config/` 기준**이고, DB 오픈 후 `Bot` 조립 단계에서 `bundle.with_policy(pointer)`로 산출물 버전을 덮어쓴다(§6.3).

### 3.5 fail-fast와 오류 보고

```
1. 각 파일을 개별적으로 YAML 파싱 → 구문 오류는 (파일, 줄, 열)로 보고
2. deep_merge (config.yaml 계층만)
3. OMRA__ 오버라이드 적용 → 미지 경로는 UnknownOverrideError 로 수집
4. AppConfig 모델 검증 (pydantic v2) → ValidationError 를 (키 경로, 입력값, 사유)로 평탄화
5. 레코드 파일 각각 모델 검증 → (파일, 인덱스, 필드) 경로로 평탄화
6. 상호 제약 검증 constraints.check_all(bundle) (§4.5)
7. 수집된 오류가 1건이라도 있으면 ConfigValidationError(전체 목록) — 부분 기동 없음
```

**전 오류를 모으는 이유**: 기동 거부는 `FATAL_EXIT`이고(01-design §5.4) Docker가 즉시 재시작하므로, 오류 하나씩 고치게 하면 사람이 재시작 루프를 N번 본다. 한 번에 전부 보여주는 것이 15분 로테이션 절차(01 §6.2)의 실효성을 결정한다.

### 3.6 실행 모드가 바꾸는 것 / 바꾸지 않는 것

| 바뀌는 것 | 근거 |
|---|---|
| KIS REST·WS 도메인·포트, TR ID prefix 치환 | `tr_ids.kis.yaml`의 `rest.base_url.{live,paper}` / `ws.{live,paper}` ([05-broker-gateway.md](05-broker-gateway.md) §7.1) |
| rate limit 프로파일 | 01 §3.2 "모의투자 전환은 `env: paper` 스위치 하나로 … rate limit 프로파일이 함께 바뀐다" |
| 사용하는 시크릿 세트 | `live` → `KIS_APP_KEY/SECRET`, `paper` → `KIS_PAPER_APP_KEY/SECRET`(01 §6.1 "실전 키와 다른 경로 보관") |
| `run.manual_approve` 기본값 | `live` 전환 첫 1주 `true`(03 §5.1-4) |

| 바뀌지 않는 것 | 근거 |
|---|---|
| 프로세스 구조·태스크 토폴로지·셀프체크 목록 | [01-system-architecture.md](01-system-architecture.md) §3.3 |
| 엔진·밴드·세금·안전장치 파라미터 | dry-run 분기는 브로커 어댑터 최하단에만(00 §5 원칙 2) |

### 3.7 실효 설정 지문과 감사

```python
@dataclass(frozen=True)
class ConfigFingerprint:
    files: Mapping[str, str]     # 파일명 → sha256 (config/ 의 모든 *.yaml)
    effective: str               # 병합·오버라이드 적용 후 AppConfig.model_dump(mode="json") 의 정규화 sha256
```

- `effective`는 **키 정렬 + Decimal→문자열 정규화** 후 해싱한다. 같은 설정이 다른 표기(`0.5` vs `.5`)로 적혀도 지문이 같아야 "설정이 바뀌었는가"를 판정할 수 있다.
- 기동·`RELOAD_CONFIG` 때 `config_changed` 감사 이벤트(열거는 01 §6.3)를 남긴다. payload:

```json
{ "trigger": "startup | reload | ci",
  "effective_before": "sha256:…", "effective_after": "sha256:…",
  "files_changed": ["config/tax.yaml"],
  "key_diff": [{"path": "tax.income_alerts.warn_krw", "from": "16000000", "to": "18000000"}] }
```

- `key_diff`에는 **값이 그대로 들어간다**. config 계층에는 시크릿이 없으므로(§7.1 불변식) 마스킹이 필요 없고, 필요해지는 순간이 곧 불변식 위반이다 — 그래서 `redact.py`가 diff 생성 시 `SecretSpec` 이름과 겹치는 키가 있으면 **예외를 던진다**(§7.4).
- `external_schedules.yaml`의 파일 해시는 별도 소비자가 있다: `external_expectations_sync`가 해시 변경을 감지해 기대값을 재전개한다(03 §6.3, 01 §4.2). `fingerprint.files["config/external_schedules.yaml"]`이 그 입력이다.

---

## 4. `config.yaml` 스키마 — 4블록 합집합

### 4.1 키 이름 정본 규칙 (02 부록 A 서문 그대로)

1. 전체 스키마 = **4개 블록의 config-key 합집합**: 02 부록 A(엔진·집행·세금, 첫 열이 `tax.yaml params.*`인 법령값 행 제외) + 03 부록 A(`protections.*`·`safe_mode.*`·`presence.*`·`alerts.*`·`execution.*`) + 06 부록 C(`ws.*`·`quote.*`·`fx.*`·`guard.*`·`realtime.*`·`etf.premium_gate.*`·`surveillance.*`) + 07 부록 D(`research.*`·`labs.*`). 자기 블록에만 있는 키는 그 문서가 이름까지 정본.
2. 두 곳 이상에 나타나는 키는 **02 부록 A의 이름**을 따른다(`safe_mode.*`가 정본 접두사, `safemode.*`는 존재하지 않는다).
3. CI 화이트리스트의 생성원은 이 4블록의 config-key 행이며 CI가 ⓐ 블록 간 키 중복·불일치 0건 ⓑ 07 §7.1 `tuning_space` 표의 키 ⊆ 4블록 합집합을 단정한다(§9.2). `tax.yaml params.*` 행은 별도로 `TaxParams`와 대조한다.

**본 설계는 여기에 규칙 4를 더한다.**

> **[DD-04-4] 규칙 4 — `AppConfig` 모델의 키 집합 == 4블록 합집합 ∪ 등재된 신규 키**
> - 결정: CI가 (ⓒ **4블록에서 추출한 config 키 집합 ⊆ `AppConfig` 필드 경로 집합**) (ⓓ **`AppConfig`에만 있고 등재처가 없는 키 = 0건**)을 추가로 단정한다. 02 부록 A에서 `tax.yaml params.*`로 명시한 법령값은 ⓒ의 입력이 아니며 `TaxParams` 필드와 별도로 대조한다. ⓓ의 "등재처"는 넷이다 — 4블록 / §4.3(`run.*`·`accounts[]`) / §4.4 신규 키 표 / **4블록이 구조값으로만 준 키의 하위 필드**(`order.reprice.{interval_min,max_count}`·`cov.monitor.{lam,days}`·`guard.move_guard.*`·`crypto.mix`·`tax.income_alerts.*` 등 — 부모 키가 4블록에 있으면 하위 필드명은 §4.2 모델이 이름 정본).
> - 근거: 02 부록 A 규칙 3은 "문서 ↔ 문서" 정합만 검사한다. 문서에 있는데 모델에 없으면 그 키는 YAML에 적어도 무시되고(pydantic `extra="forbid"`면 기동 거부지만, 그 전에 아무도 그 키를 쓸 수 없다), 모델에만 있으면 문서화되지 않은 숨은 파라미터다. 무인 운용에서 후자가 더 위험하다.
> - 계획 문서와의 관계: 02 부록 A 규칙 3의 확장. 충돌 없음.

> **[DD-04-21] 세법 법령값은 `tax.yaml` 단일 정본**
> - 결정: [DD-10-16]을 수용해 `TaxCfg`의 `deduction`·`isa_free_limit`·`crypto_tax_enabled`와 `WaterfallCfg`의 `pension_deduct_cap_total`·`pension_deduct_cap_savings`를 제거한다. 법령값은 Clock으로 선택한 `TaxParams`에서만 읽고, 과거 config·`OMRA__` 경로는 strict unknown/extra 입력으로 거부한다.
> - C-29는 비교할 교집합이 사라져 폐기하며 번호를 다른 규칙에 재사용하지 않는다. `ConfigConflictError`는 계층 간 `run.env` 충돌 등 기존 용도로 유지한다.
> - 근거: 02 §5.5는 세율·공제·한도를 effective-date `tax.yaml`로 관리하라고 명시한다. 복제값을 비교하는 것보다 두 번째 입력 경로를 없애야 한쪽만 갱신되는 실패가 구조적으로 불가능하다.
> - 계획 문서와의 관계: 02 부록 A의 과거 별칭을 실제 `tax.yaml params.*` 좌표로 명시한 규칙 4를 구현한다. 충돌 없음.

### 4.2 루트 모델과 블록 트리

```python
# config/settings.py
class AppConfig(BaseSettings, frozen=True):
    model_config = SettingsConfigDict(extra="forbid", env_prefix="OMRA__",
                                      env_nested_delimiter="__", frozen=True)

    run:           RunCfg              # §4.3
    accounts:      tuple[AccountCfg, ...]   # §4.3
    # ── 02 부록 A: 엔진 ────────────────────────────────────────────
    risk:          RiskCfg;        core:      CoreCfg;      satellite: SatelliteCfg
    cash:          CashCfg;        bl:        BlCfg;        mvo:       MvoCfg
    cov:           CovCfg;         sanity:    SanityCfg;    band:      BandCfg
    rebalance:     RebalanceCfg;   universe:  UniverseCfg;  trade:     TradeCfg
    momentum:      MomentumCfg;    crypto:    CryptoCfg
    mc:            McCfg;          gk:        GkCfg;        backtest:  BacktestCfg
    # ── 02 부록 A + 03 부록 A: 집행 ────────────────────────────────
    order:         OrderCfg;       execution: ExecutionCfg;  etf:      EtfCfg
    # ── 02 부록 A: 세금 ───────────────────────────────────────────
    tax:           TaxCfg;         waterfall: WaterfallCfg
    # ── 03 부록 A: 안전장치 ───────────────────────────────────────
    protections:   ProtectionsCfg; safe_mode: SafeModeCfg;   presence: PresenceCfg
    tracking_error: TrackingErrorCfg;  alerts: AlertsCfg
    # ── 06 부록 C: 관측 계층 ──────────────────────────────────────
    ws:            WsCfg;          quote:     QuoteCfg;      fx:       FxCfg
    guard:         GuardCfg;       realtime:  RealtimeCfg;   surveillance: SurveillanceCfg
    # ── 07 부록 D: 자가 개선 ─────────────────────────────────────
    research:      ResearchCfg;    labs:      LabsCfg
    # ── 정책 ─────────────────────────────────────────────────────
    policy:        PolicyCfg;      canary:    CanaryCfg
    # ── 설계서 등재 신규 블록 (§4.4) ──────────────────────────────
    data:          DataCfg;        watchdog:  WatchdogCfg
    runtime:       RuntimeCfg;     tools:     ToolsCfg;      web: WebCfg
    secrets:       SecretsPolicyCfg                # 만료 사다리·발급일 분산 (§8)
    jobs:          JobsCfg;        monitoring: MonitoringCfg  # 값 제안: 12 §19
```

`extra="forbid"`가 오타 키를 기동 거부로 만든다 — 이것이 §3.3 규칙 ④(미지 오버라이드 거부)의 YAML 쪽 짝이다.

**블록 모델 (값·근거는 전부 4블록에서 온다. 표기 `[→ 문서 §절]`)**

> **단위 규약**: 03 부록 A·06 부록 C·07 부록 D는 값을 **YAML 리터럴**로 주므로 그 표기를 그대로 옮긴다 — `_pct`·`_pp` 접미 키는 퍼센트 수치다(`mdd_safe_mode_pct: -15`, `etf.premium_gate.threshold_pct: 0.5`). 02 부록 A는 표에서 백분율 문장으로만 서술하므로, 그 블록에서 오는 비율 키(`core.min_weight`·`cash.*`·`mvo.asset_cap`·`crypto.*`·`bl.view_shift_cap` 등)는 **소수 비율**로 싣는다. 두 규약이 섞이는 지점은 이 문장이 유일한 판정 근거이며, 키별 실제 표기는 아래 모델이 정본이다.

```python
# schema/engine.py
class RiskCfg(BaseModel, frozen=True):
    level: int = Field(6, ge=1, le=10)                        # [→ 02 부록 A, §1.1]  HR

class CoreCfg(BaseModel, frozen=True):
    min_weight: Decimal = Dec("0.80")                         # [→ 02 부록 A] 기본 90%, 하한 80%  HR

class SatelliteCfg(BaseModel, frozen=True):
    total_cap: Decimal = Dec("0.20")                          # [→ 02 부록 A]  HR
    momentum: MomentumSleeveCfg                               # §6 위성

class MomentumSleeveCfg(BaseModel, frozen=True):
    enabled: bool = False                                     # 옵트인 [→ 02 §1]
    cap: Decimal = Dec("0.10")                                # 상한 10% [→ 02 §1]
    pair: tuple[str, str] = ("VOO", "VXUS")                   # [→ 02 부록 A satellite.momentum.pair]
    return_basis: Literal["usd_total_return"] = "usd_total_return"
    dd_basis: Literal["sleeve_krw_peak_to_trough"] = "sleeve_krw_peak_to_trough"
    turnover_cap_annual: Decimal = Dec("2.00")                # 200% [→ 02 부록 A]

class CashCfg(BaseModel, frozen=True):
    buffer: Decimal = Dec("0.01")                             # 1% [→ 02 부록 A, §4.2]
    frozen_reserve_alert_pct: Decimal = Dec("0.05")           # 5% [→ 02 부록 A]

class BlCfg(BaseModel, frozen=True):
    tau: Decimal = Field(Dec("0.025"), ge=Dec("0.02"), le=Dec("0.05"))   # 허용 0.02~0.05
    delta_mkt: Decimal = Field(Dec("3.0"), ge=Dec("2"), le=Dec("4"))     # BL 역최적화 전용 상수
    max_views: int = 3
    view_shift_cap: Decimal = Dec("0.015")                    # ±1.5%p                [→ 02 부록 A]

class MvoCfg(BaseModel, frozen=True):
    lambda_risk_bounds: tuple[Decimal, Decimal] = (Dec("0.5"), Dec("30"))
    turnover_gamma: Decimal = Dec("0.01")                     # 1.0%
    asset_cap: Decimal = Dec("0.40")                          # 단일 ETF ≤40%
    asset_cap_overrides: Mapping[str, Decimal] = {"nasdaq": Dec("0.10"), "reits": Dec("0.05")}
                                                              # 나스닥 10%, 리츠 5%   [→ 02 부록 A]

class CovCfg(BaseModel, frozen=True):
    strategic: Literal["lw_constant_correlation"] = "lw_constant_correlation"
    lookback_days: int = 756
    monitor: EwmaCfg = EwmaCfg(lam=Dec("0.94"), days=60)      # 모니터링 전용
    condition_number_max: int = 1000                          # 초과 시 P7-cond      [→ 02 부록 A]

class SanityCfg(BaseModel, frozen=True):
    hrp_divergence: Decimal = Dec("0.20")                     # 20%p, 자산군 내부 배분 max 괴리

class BandCfg(BaseModel, frozen=True):                        # 전부 HR (00 §3.2 P7)
    abs: Decimal = Dec("0.05");            rel: Decimal = Dec("0.25")
    pension_scheduled_abs: Decimal = Dec("0.07");  pension_scheduled_rel: Decimal = Dec("0.35")
    isa_abs: Decimal = Dec("0.07");        isa_rel: Decimal = Dec("0.35")
    crypto_abs: Decimal = Dec("0.01");     crypto_rel: Decimal = Dec("0.30")
    class_abs: Decimal = Dec("0.05")
    restore_fraction: Decimal = Dec("0.5")                    # 잠정 — M2 EX-1에서 확정
    restore_mode: Literal["fraction", "destination"] = "fraction"   # [→ 07 [DD-07-11]] §4.4
    restore_rho: Decimal | None = None                        # destination 경로 전용 ρ (C-31)

class RebalanceCfg(BaseModel, frozen=True):
    cooldown_days: int = 5                                    # 드리프트 2×밴드 초과 시 무시

class UniverseCfg(BaseModel, frozen=True):                    # ※ universe.yaml 과 다른 블록
    shrink_below_krw: int = 30_000_000
    restore_above_krw: int = 40_000_000

class TradeCfg(BaseModel, frozen=True):
    min_amount: Mapping[Literal["kr", "us", "upbit"], Decimal] = {
        "kr": Dec("50000"), "us": Dec("100"), "upbit": Dec("10000")}   # T_min, us 는 USD

class CryptoCfg(BaseModel, frozen=True):
    enabled: bool = False                                     # 옵트인
    target: Decimal = Field(Dec("0.03"), ge=Dec("0.01"), le=Dec("0.10"))
    cap: Decimal = Dec("0.10")                                # HR
    mix: Mapping[str, Decimal] = {"KRW-BTC": Dec("0.70"), "KRW-ETH": Dec("0.30")}  # 고정
    vol_target: Decimal = Dec("0.40")                         # 연 40%
    vol_scale_floor: Decimal = Dec("0.33")                    # 스케일 하한 [→ 02 §7]
    kimchi_halt: Decimal = Dec("0.08")                        # 8% 신규 매수 정지
    kimchi_alert: Decimal = Dec("0.05")                       # 5% 알림      [→ 02 §7]
    drop_guard_24h_pct: Decimal = Dec("-0.15")                # BTC 24h −15% → 당일 매수 정지
    vol_scale_max_age_days: int = 10                          # [→ 07 §11.2 [DD-07-12]] §4.4

class McCfg(BaseModel, frozen=True):                          # 값 정본 02 부록 A · 02 §9
    paths: int = 5_000                                        # [→ 02 부록 A `mc.paths`]
    block: int = 6                                            # 평균 6개월 stationary block bootstrap
                                                              # (L ~ Geometric(p=1/block) — 07 §14.2)
    success_bands: SuccessBands = SuccessBands(green=Dec("0.75"), amber=Dec("0.60"))
                                                              # 녹/황/적 [→ 02 부록 A `mc.success_bands`]
    cost_annual: Decimal = Dec("0.0035")                      # 실효 비용 연 0.35% [→ 02 §9] — 이름 §4.4
    inflation_annual: Decimal = Dec("0.02")                   # 인플레 2.0%       [→ 02 §9] — 이름 §4.4
    # ★ 소비 타입 McParams 의 정의 정본은 07-portfolio-engine.md §14.1. 여기는 값을 담는 config 키뿐이다.

class GkCfg(BaseModel, frozen=True):                          # Guyton-Klinger [→ 02 부록 A · 02 §9]
    guardrail: Decimal = Dec("0.20")                          # ±20% 이탈 판정
    adjust: Decimal = Dec("0.10")                             # ±10% 인출액 조정
    # 초기 인출률 4.0%는 goals.yaml 의 withdrawal.initial_rate (§5.3) — 여기서 중복 정의하지 않는다

class BacktestCfg(BaseModel, frozen=True):
    # ── 02 부록 A(계획 정본) ────────────────────────────────────────
    account_model: Literal["single", "multi"] = "single"      # [→ 02 부록 A] multi 는 M8 이후
    gates: BacktestGatesCfg = BacktestGatesCfg()              # core / satellite / challenger_years
    # ── 15-backtest-and-validation.md [DD-15-4]가 이름을 정하고 본 문서가 등재 ──
    sim_mode: Literal["clean", "with_guards"] = "clean"       # [→ 02 §8.1.1]
    costs: BacktestCostsCfg = BacktestCostsCfg()              # 8항, 값 정본 02 §8.1 (C-32)
    data: BacktestDataCfg = BacktestDataCfg(max_gap_pct=Dec("0.5"))    # 0.5% — `_pct` 접미 = 퍼센트
                                                                       #   수치(§4.2 단위 규약). 15 §18-16
                                                                       #   임의 초기값, M2 재설정
    lookahead: LookaheadCfg = LookaheadCfg(samples=10, weight_tolerance=Dec("1e-9"))  # 02 §8.3
    snapshot: SnapshotCfg                                     # ★ 기본값 없음 — 필수 키 (C-33)
    benchmark: BenchmarkCfg = BenchmarkCfg(                   # [→ 02 §8.2 게이트 C1]
        composition={"equity": Dec("0.60"), "bond": Dec("0.40")}, rebalance="annual",
        apply_costs=True, track="pretax")
    tax: BacktestTaxCfg = BacktestTaxCfg(harvest_enabled=True)   # A-B 산출 스위치 (15 [DD-15-9])
    seed: int = 20260101                                      # bootstrap·표본 추출의 유일한 난수 원천
    us_fill_basis: Literal["close", "intraday_limit"] = "close"  # SP-C3 양경로 (15 §15-1)

class BacktestGatesCfg(BaseModel, frozen=True):
    core: str = "WF(5+1y) + lookahead 0건 + 스냅샷 회귀(config 포함)"        # [→ 02 부록 A]
    satellite: str = "CPCV(21/5) + 이웃 ±25% + DSR>0.95 + 부트스트랩"        # [→ 02 부록 A]
    challenger_years: int = 10                                # 30분 초과 시 5 (15 §10.6 분기 B)

class BacktestCostsCfg(BaseModel, frozen=True):               # 값 전량 [→ 02 §8.1], 이름 15 §5.2
    fee_kr: Decimal = Dec("0.00015");        fee_us: Decimal = Dec("0.0009")
    fee_crypto: Decimal = Dec("0.0005");     tax_sell_kr_stock: Decimal = Dec("0.0015")
    slip_kr_etf_bp: Decimal = Dec("5");      slip_us_bp: Decimal = Dec("3")
    slip_crypto_bp: Decimal = Dec("10");     fx_spread_roundtrip: Decimal = Dec("0.002")

class SnapshotCfg(BaseModel, frozen=True):                    # 15 [DD-15-10] — 값은 M2 실측
    tolerance_pct: Decimal | None = None                      # None 이면 CI 실패 (C-33)
    absolute_floor: AbsoluteFloorCfg | None = None            # {sharpe, max_mdd} — 〃
```

`BacktestCfg.snapshot`에 기본값을 주지 않은 것이 의도다 — 15 [DD-15-10]이 "필수 키·값 미정(비면 CI 실패)"으로 요청했고, 임의 기본값을 넣으면 "임계가 없는 상태"와 "임계를 정했는데 그 값이 우연히 임의값인 상태"가 구별되지 않는다.

```python
# schema/execution.py
class OrderCfg(BaseModel, frozen=True):
    max_amount_krw: int = 5_000_000                            # 1회 주문 상한
    reprice: RepriceCfg = RepriceCfg(interval_min=5, max_count=3)   # 5분 × 최대 3회
    us_strategy: Literal["loc", "intraday_limit"] = "loc"      # LOC 기본 (SP-C3 종속)

class ExecutionCfg(BaseModel, frozen=True):
    max_open_orders: Mapping[SleeveId, int] = {                # 03 부록 A — (계좌 × 시장)별
        "kis_domestic": 6, "kis_overseas": 6, "upbit": 4}

class PremiumGateCfg(BaseModel, frozen=True):                  # 두 경로 공통 임계
    threshold_pct: Decimal = Dec("0.5");     threshold_ticks: int = 3   # 0.5% [→ 06 부록 C 리터럴]
    rest_defer_minutes: int = 30;            max_defer_count: int = 3
    min_wait_sec: int = 300;                 max_total_defer_min: int = 90
```

```python
# schema/protections.py — 값 정본 03 부록 A
class ProtectionsCfg(BaseModel, frozen=True):
    mdd_safe_mode_pct: Decimal = Dec("-15");   mdd_halt_pct: Decimal = Dec("-25")
    mdd_recover_pct: Decimal = Dec("-10");     mdd_recover_days: int = 5
    daily_order_count: int = 30;               daily_order_amount_pct: Decimal = Dec("30")
    daily_order_amount_abs_krw: int | None = None   # P3 절대 상한. None = 미적용 (§4.4 [DD-04-17])
    symbol_cooldown_hits: int = 3;             symbol_cooldown_hours: int = 24
    symbol_cooldown_window_min: int = 60       # P4 계수 창 "1시간 내" (03 §1.2 P4 행) — §4.4
    price_outlier_pct: Decimal = Dec("15");    price_outlier_pct_crypto: Decimal = Dec("30")
    quote_stale_min: int = 5;                  spread_max_pct: Decimal = Dec("1.0")
    reconcile_tolerance_shares: int = 0        # 1주라도 불일치 → HALTED
    reconcile_tolerance_cash_krw: int | None = None   # ~ (M4 실측 캘리브레이션 — null 허용)
    error_streak_order: int = 5;               error_streak_quote: int = 5
    turnover_monthly_mult_warn: Decimal = Dec("2");  turnover_monthly_mult_halt: Decimal = Dec("3")
    turnover_annual_assumption: Decimal = Dec("0.30")   # 일일 예산 = /250
    turnover_carryover_cap_days: int = 60
    turnover_streak_safe_mode: int = 3
    surveillance_stale_hours: int = 24
    frozen_nav_safe_mode_pct: Decimal = Dec("20");   frozen_nav_halt_pct: Decimal = Dec("40")
    deadline_pause_days: int = 3
    event_burst_abs: int = 4;                  event_burst_ratio: Decimal = Dec("0.30")
    # ★ P7·P7-cond 임계는 여기에 두지 않는다 — sanity.hrp_divergence / cov.condition_number_max
    #   (03 부록 A 주석: 엔진 파라미터이므로 02 부록 A가 이름·값 정본)

class SafeModeCfg(BaseModel, frozen=True):
    net_buy_daily_cap_pct: Decimal = Dec("3");   net_buy_monthly_cap_pct: Decimal = Dec("10")
    net_buy_monthly_window_days: int = 30        # 역월 아님 — rolling 30일
    order_size_divisor: int = 3;                 band_multiplier: Decimal = Dec("2")

class PresenceCfg(BaseModel, frozen=True):
    away_soft_h: int = 24; away_h: int = 72; away_long_d: int = 7
    grace_normal_min: int = 30; grace_away_soft_h: int = 4; grace_away_h: int = 12
    halt_downgrade_no_response_h: int = 24
    grace_cap_kst: GraceCapCfg = GraceCapCfg(crypto="08:55", krx="09:45", us_loc="-PT30M")

class AlertsCfg(BaseModel, frozen=True):
    guard_verdict_default: Literal["silent", "info"] = "silent"
    surveillance_state_entry: Literal["info", "warning"] = "info"
    critical_channels: tuple[Literal["telegram", "smtp", "webhook"], ...] = ("telegram", "smtp")
    both_channels_fail_safe_mode_days: int = 2
    info_immediate_max_per_day: int = 5        # [→ 13 [DD-13-4]] 즉시 발송 상한. §4.4
                                               # ★ DAILY_BRIEF 는 이 상한의 적용 대상이 아니다(13 §3.4)

class TrackingErrorCfg(BaseModel, frozen=True):               # 값 정본 03 부록 A
    residual_monthly_threshold_pp: Decimal = Dec("0.3")       # ⑤ 잔차에만 적용 — 03 §4.6·07 §10 R1
```

`GraceCapCfg.us_loc`은 `"-PT30M"`(ISO-8601 duration, 음수 = LOC 제출 시각 기준 상대 오프셋)이고 나머지 둘은 `"HH:MM"` KST 절대 시각이다(03 부록 A). 파서는 두 형식을 모두 받아 `GraceCap` union으로 정규화한다 — 소비자([09-safety-protections.md](09-safety-protections.md) 부재 사다리)는 `resolve(run_date, venue) -> datetime`만 호출한다.

```python
# schema/observe.py — 값 정본 06 부록 C
class WsCfg(BaseModel, frozen=True):
    tier1_execution_window_only: bool = True
    tier1_enabled: bool = False         # ★ T1 등록 경로 on/off — [→ 05 §7.6·§11 C1] §4.4
                                        #   `_execution_window_only` 는 "집행 창 한정"이지 스위치가 아니다
    subscription_cap: int = 38          # 하드 41, 공식 샘플 40 캡
    reserve: int = 3
    max_active_symbols: int = 9         # 종목 상한 하드캡 (축약 사다리 없음)

class QuoteCfg(BaseModel, frozen=True):
    max_age_ms: Mapping[Literal["krx", "upbit", "us"], int | None] = {
        "krx": 2000, "upbit": 2000, "us": None}     # us=null → 나이 검사 비적용

class FxCfg(BaseModel, frozen=True):
    max_age_hours: int = 72             # 초과 시 KimchiGuard 무판정(= PROCEED)

class GuardCfg(BaseModel, frozen=True):
    oneway: Literal[True] = True        # ★ 일방향 밸브 — false 를 표현할 수 없는 타입 (§4.5-불변)
    min_duration_sec: int = 30
    move_guard: MoveGuardCfg = MoveGuardCfg(
        window_sec=300, nav_weighted_move_pct=Dec("3.0"), min_symbols=2, min_samples=5)

class RealtimeCfg(BaseModel, frozen=True):
    rest_fallback_poll_sec: int = 30           # 동적 조정 시 10
    upbit_maintenance_fail_streak: int = 3

class SurveillanceCfg(BaseModel, frozen=True):
    max_age_trading_days: int = 2
    unknown_default_level: Literal["SV0","SV1","SV2","SV3"] = "SV2"
    override_max_days: int = 90                # /riskflag override
    override_clear_max_days: int = 30          # /riskflag clear TTL
    daily_poll_timeout_sec: int = 300          # 3개 폴 합산 하드 예산
    sources: Mapping[str, SurvSourceCfg]       # 아래 기본값 6개

class SurvSourceCfg(BaseModel, frozen=True):
    enabled: bool
    grade: Literal["official"] = "official"    # ★ 값이 하나뿐인 것이 의도 — 아래
    max_auto_level: Literal["SV0","SV1","SV2","SV3"] = "SV3"
    max_age_trading_days: int | None = None    # None → surveillance.max_age_trading_days 상속
    max_age_hours: int | None = None           # ★ 24/7 소스 전용 — [→ 11 §9.2 요청] §4.4
                                               #   설정 시 max_age_trading_days 보다 우선한다
```

`grade`를 `Literal["official"]`로 좁힌 것은 `guard.oneway`·`esc_proposal`과 같은 계열의 조치다 — 00 §6.1(뉴스·SNS·커뮤니티 감시 배제)·00 §6.3(공식 API가 있는 데이터의 스크래핑 금지, 하드 규칙)·06 §6.1(KIND·업비트 공지 비공식 API 배제)이 비공식 소스를 **영구 배제**했으므로, `grade: unofficial`을 config로 적을 수 있게 두면 배제된 경로가 설정 한 줄로 되살아난다. 06 부록 C도 6개 소스를 전부 `official`로 적고 "전부 official"이라고 못박았다.

`sources` 기본값(06 부록 C 그대로): `kis_master`·`kis_stock_info`·`kis_ksdinfo` = `enabled: true` / `kis_overseas`(M6)·`upbit_market`(M7)·`kis_ws_market`(M9 조건부) = `enabled: false`. 전부 `grade: official`, `max_auto_level: SV3`. **`upbit_market`만 `max_age_hours: 12`를 갖는다** — 06 §6.1 소스 표가 이 소스의 `max_age`를 12시간으로 규정하는데 크립토는 상시 개장이라 "거래일" 단위 키로 표현되지 않기 때문이다([11-realtime-and-surveillance.md](11-realtime-and-surveillance.md) §9.2가 요청, 값 정본 06 §6.1).

```python
# schema/policy.py
class ChangeBudgetCfg(BaseModel, frozen=True):
    total_per_year: int = 6            # ★ 상위 캡
    targets_per_year: int = 4; params_per_year: int = 4; logic_per_year: int = 2

class PolicyCfg(BaseModel, frozen=True):
    change_budget: ChangeBudgetCfg = ChangeBudgetCfg()
    auto_threshold_pp: Decimal = Dec("8")      # 목표비중 자동 승인 상한
    reject_threshold_pp: Decimal = Dec("20")   # 자동 REJECT
    auto_nocanary_threshold_pp: Decimal = Dec("3")   # ≤3%p = 카나리 없음·예산 미소비 (07 §9 규칙 6)

class CanaryCfg(BaseModel, frozen=True):
    targets: CanaryStepCfg = CanaryStepCfg(alphas=(Dec("0.333"), Dec("0.667"), Dec("1.0")),
                                           days_per_step=5)
    methodology: CanaryStepCfg = CanaryStepCfg(alphas=(Dec("0.25"), Dec("0.50"), Dec("1.0")),
                                               days_per_step=20)
```

> `canary.targets`/`canary.methodology`(02 부록 A)와 `labs.canary.{targets_recalc, method_swap, universe_swap}`(07 부록 D)은 **같은 대상의 두 표기**다. 02 부록 A 규칙 2(두 곳에 나타나면 02의 이름을 따른다)에 따라 `canary.*`가 정본 경로이고, `labs.canary.*`는 07 부록 D에만 있는 세 번째 항목(`universe_swap`)과 `veto_window_hours`를 위해 유지한다. 상호 제약(§4.5 C-14)이 `canary.targets == labs.canary.targets_recalc`, `canary.methodology == labs.canary.method_swap`을 단정해 두 표기의 이탈을 CI에서 잡는다.

```python
# schema/improve.py — 값 정본 07 부록 D
class ResearchCfg(BaseModel, frozen=True):
    enabled: bool = False                       # M10a 착수 시 true
    collect_cron: str = "0 4 * * 0";  digest_cron: str = "0 5 1 * *"
    max_items_per_digest: int = 40;   max_chars_per_item: int = 8000
    source_fail_streak_warn: int = 3
    citation_fail_rate_alert: Decimal = Dec("0.10")
    sources: Mapping[str, ResearchSourceCfg]    # 8개, 전부 공식 채널
    # ── 14-research-and-labs.md §2.3이 이름을 제안하고 본 문서가 등재 (§4.4) ──
    llm: ResearchLlmCfg = ResearchLlmCfg()
    user_agent: str = "omra-research/1.0 (+self-hosted; contact via operator)"   # collectors 주입
    inbox_root: Path = Path("/app/var/data/research/inbox")     # [→ 14 [DD-14-4]]
    report_root: Path = Path("/app/var/reports/research")       # 〃

class ResearchLlmCfg(BaseModel, frozen=True):   # 값 정본 01 §8.1, 타입 정본 14 §2.3 `LlmSettings`
    model: str = "claude-opus-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_output_tokens: int = 4096
    use_batch: bool = True                      # 야간 대량 처리 = Message Batches
    monthly_budget_usd: Mapping[Literal["research_extract"], Decimal] = {
        "research_extract": Dec("0")}           # 용도별 하위 예산. 0 = 미설정(호출 금지)
                                                # ★ [확인 필요] 예산 금액은 01 §8.1 확인 후 채운다

class LabsCfg(BaseModel, frozen=True):
    enabled: bool = False
    challenger_enabled: bool = False            # [→ 12 §4.3·§19] `experiment_ingest` enabled_when
                                                #   의미 정의는 14 소유, 키 등재만 본 문서
    tuning_space: tuple[str, ...] = ()          # 착수 시 07 §7.1 표의 4키
    shadow_min_days: int = 126
    g2: LabsG2Cfg = LabsG2Cfg(mode="full")      # [→ 14 §1.4 C4] full(10년) | short(5년) | disabled
    canary: LabsCanaryCfg                       # + veto_window_hours: 72
    rollback: RollbackCfg                       # r1_te_residual_pp .3 / r1_breach_count 2 /
                                                # r2_guard_multiple 2.0 / r3_turnover_multiple 1.3 /
                                                # r3_budget_consumption .8 / r4_exec_failure_multiple 2.0 /
                                                # freeze_days_after_2_rollbacks 90 / annual_rollback_alarm 3

class LabsG2Cfg(BaseModel, frozen=True):
    mode: Literal["full", "short", "disabled"] = "full"   # `disabled` → G2 = SKIPPED_BY_CONFIG (14 §1.4)
```

`labs.rollback.r1_te_residual_pp`(07 부록 D)와 `tracking_error.residual_monthly_threshold_pp`(03 부록 A)는 **같은 0.3%p의 두 표기**다 — 전자는 롤백 트리거 R1의 입력, 후자는 조사 임계이며 계획이 두 곳에 같은 값을 실었다(03 §4.6 = 07 §10.2 R1). C-14와 같은 계열의 상호 제약(C-36)이 두 값의 이탈을 CI에서 잡는다.

`labs.tuning_space`의 원소는 **`AppConfig` 필드 경로 문자열**이며 모델 검증 시 실재 경로인지 확인한다. 07 §7.1 제외 목록(`band.*` 전체·`safe_mode.*`·`protections.*`·`execution.max_open_orders`·`crypto.*`·`satellite.*`·`bl.delta_mkt`·`mvo.lambda_risk_bounds`)은 **런타임 검증으로도 거부**한다 — CI가 문서 대조만 하면 사람이 YAML에 직접 적은 순간을 못 잡는다.

```python
# schema/taxcfg.py — TaxParams 법령값은 10 §3.1·tax.yaml만 소유. 여기는 운영 키·사용자 입력.
class TaxCfg(BaseModel, frozen=True):
    # 법령값 별칭은 두지 않는다([DD-04-21]).
    harvest_start: str = "11-25"                       # MM-DD
    income_alerts: IncomeAlertSets                     # api / fallback 두 집합 (mapping)
    basis_price_source: Literal["api", "fallback"] = "fallback"   # SP-C1 종속
    isa_usage_alert: Decimal = Dec("0.70")
    isa_contract_start_date: date | None = None
    isa_usage_opening_amount: int | None = None        # null → 소진률 unknown (02 §5.2)
    isa_usage_opening_as_of: date | None = None
    harvest_rebuy_buffer_pct: Decimal = Dec("0.005")
    health_insurance_status: Literal["employee","regional","dependent"] = "regional"  # [DD-10-10]
    user_marginal_credit_rate: Decimal = Dec("0.132")  # [DD-10-7] 보수적 하한
    harvest_auto_enabled: bool = False                 # [→ 10 [DD-10-14]] 하베스팅 자동 실행 승격
                                                       #   false = 제안·승인 경로만 (00 §3.2 T3)

class WaterfallCfg(BaseModel, frozen=True):
    fill_pension_to_limit: bool = False
    gap_check_date: str = "11-01"
    reminders: tuple[str, ...] = ("12-08", "12-15", "12-19")   # D-12 / D-5 / D-1
    transfer_reserve_expiry_days: int = 7
```

`tax.deduction`·`tax.isa_free_limit`·`tax.crypto_tax_enabled`·`waterfall.pension_deduct_cap_*`는 config 키가 아니다. 각각 `tax.yaml`의 `overseas_cg_deduction_krw`·`isa_free_limit_krw`·`crypto_tax_enabled`·`pension_deduct_cap_*_krw`를 가리키며, 유효 버전 선택은 §6.2의 Clock 경계를 따른다.

`tax.income_alerts`는 **스칼라 목록이 아니라 mapping**이다(02 부록 A 명시). 두 집합의 값은 02 §5.3 표 그대로: `api = {health: 1000만, info: 1200만, warn: 1600만, soft_stop: 1800만}`, `fallback = {health: 1000만, info: 1400만, warn: 1800만, soft_stop: 1900만}`.

### 4.3 실행·계좌 블록

```python
# schema/run.py
class ExecEnv(StrEnum):
    DRY_RUN = "dry_run"; PAPER = "paper"; LIVE = "live"     # 01 §3.2

class RunCfg(BaseModel, frozen=True):
    env: ExecEnv = ExecEnv.DRY_RUN
    live_confirmation: str | None = None      # "<계좌 뒤 4자리>-I-UNDERSTAND" (03 §5.1-2)
    manual_approve: bool = False              # live 전환 첫 1주 true (03 §5.1-4)
    max_account_value: int | None = None      # KRW. 초과분 신규 매수 불가 (03 §5.2). HR
                                              # ★ 키 이름 정본은 00 §3.2 P7·03 §5.2 (`_krw` 접미 없음)
    kill_file: Path = Path("/app/var/db/KILL")   # 01-design §5.1 A1
```

**live 3중 일치 검사**(03 §5.1-2, 01-design §5.1 A2)는 config 계층이 소유한다:

```python
def assert_live_confirmation(run: RunCfg, accounts: Sequence[AccountCfg], secrets: Secrets) -> None:
    """env == LIVE 일 때만 실행. 세 값이 일치해야 통과:
       ① run.env == "live"
       ② 실계좌번호(secrets.kis_account(account_id).cano)의 뒤 4자리
       ③ run.live_confirmation == f"{뒤 4자리}-I-UNDERSTAND"
    불일치 → LiveConfirmationMismatch (기동 거부, 상태 기록 없음 — 01-design §5.4 FATAL_EXIT).
    ★ 대조 대상 계좌는 type == GENERAL 이며 enabled 인 계좌. 복수면 ConfigError."""
```

```python
# schema/accounts.py
class AccountCfg(BaseModel, frozen=True):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")   # 정본: 02-domain-model.md §3.3 [DD-02-3]
    type: AccountType                                     # general | isa | pension | irp | upbit
    broker: Broker                                        # KIS | UPBIT
    mode: AccountMode                                     # AUTO | BROKER_SCHEDULED | INSTRUCTION
    enabled: bool = True
    forbidden_asset_classes: tuple[str, ...] = ()         # 계좌별 금지자산 — HR (00 §3.2 P7)

    def to_domain(self) -> Account: ...                   # core.accounts.Account (02-domain-model.md)
```

- `mode`가 **SP-C4 분기를 값으로 흡수**한다(00 §3.2 E2). 분기 A(절세계좌 API 주문 성공) → ISA·연금·IRP를 `AUTO`로 적는다. 분기 B → 연금·IRP는 `BROKER_SCHEDULED`, ISA는 `INSTRUCTION`. **어느 쪽이든 config 스키마·상위 코드는 동일**하고 바뀌는 것은 YAML 한 줄이다. `band_for(account, mode)` 조회 키 매핑(02 §4.3)이 이 값을 그대로 읽는다.
- 계좌 유형별 허용 자산(02 §1.2 표)은 `AccountCfg`가 아니라 **`universe.yaml`의 종목별 `allowed_accounts`**(§5.1)가 표현한다 — 자산 쪽에 두면 종목 추가 시 한 곳만 고치면 되고, 계좌 쪽에 두면 두 곳이 어긋난다.

### 4.4 설계서가 등재하는 신규 블록 (4블록 밖)

이웃 설계서가 도입하고 **키 등재를 본 문서에 위임**한 것과, 계획 본문에 값이 있으나 4블록에 실리지 않은 것을 여기서 정식 키로 확정한다.

| 키 | 기본값 | 출처 |
|---|---|---|
| `watchdog.heartbeat_max_age_sec` | 180 | 01 §6.4 트리거 초기값 (M4 실측 재캘리브레이션) |
| `watchdog.loop_lag_exit_ms` | 5000 | 〃 |
| `watchdog.consecutive` | 3 | 〃 |
| `watchdog.interval_sec` | 10 | **[DD-04-5]** — 01-design §4.5 `cfg.watchdog.interval_sec` 참조에 값이 없음 |
| `watchdog.crashloop_window_min` / `.crashloop_max` | 10 / 3 | 01 §6.4 "10분 내 자발적 종료 3회 초과" |
| `runtime.fill_queue_warn` | 1000 | 01-design §4.4 [DD-01-*] — 체결 큐 수위 경고 |
| `tools.snapshot_max_age_h` | 168 | 01-design §7.3 (weekly_maintenance 주기) |
| `data.quality.max_abs_daily_return` | 0.3 (크립토 0.5) | 06-design §7.2 [DD-06-*] 수정주가 점프 탐지 |
| `data.master.files` | `["kospi_code.mst.zip", "kosdaq_code.mst.zip"]` | 06-design §8.1 [DD-06-7] |
| `web.session_idle_hours` / `.session_max_days` | 12 / 30 | **[DD-04-6]** — [13-web-and-telegram.md](13-web-and-telegram.md) §(대시보드 인증)이 값을 확정, 본 문서는 키 등재 |
| `web.https` | false | 〃 (쿠키 `Secure` 종속) |
| `secrets.ladder_days` | `[45, 30, 14, 7, 3, 1]` | 01 §6.2 알림 사다리 (§8.2 `LADDER`의 `days_before` 정본) |
| `secrets.issue_spacing_days` | 180 | 01 §6.2 "6개월 이상 간격" 발급일 분산 규칙 |
| `jobs.*` · `monitoring.*` | [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §19 표 | 12가 값을 제안하고 본 문서가 블록을 등재(§4.2 루트 모델). **`watchdog.interval_sec`은 본 문서 [DD-04-5]가 정본**(§14-13) |
| `satellite.momentum.enabled` / `.cap` | false / 0.10 | 02 §1 구조 트리(옵트인 위성, 모멘텀 슬리브 상한 10%)·02 §6 |
| `crypto.enabled` | false | 02 §1·§7 옵트인(기본 0%). 활성화는 설정 + Telegram 확인(02 §1) |
| `crypto.vol_scale_floor` | 0.33 | 02 §7 "스케일 하한 0.33" |
| `crypto.kimchi_alert` | 0.05 | 02 §7 "김치프리미엄 >5% 알림". 차단 임계 `crypto.kimchi_halt`(8%)는 02 부록 A |
| `crypto.drop_guard_24h_pct` | −0.15 | 02 §7 "BTC 24h −15% 초과 → 당일 매수 정지" |
| `protections.price_outlier_pct_crypto` | 30 | 03 부록 A `price_outlier_pct` 행 주석 "크립토 30" — 값은 정본, **키 이름만 본 문서가 확정** |
| `mvo.asset_cap_overrides` | `{nasdaq: 0.10, reits: 0.05}` | 02 부록 A `mvo.asset_cap` 행의 괄호값(나스닥 10%, 리츠 5%) — 키 이름만 본 문서가 확정 |
| `policy.auto_nocanary_threshold_pp` | 3 | 07 §9 규칙 6 · 02 §3.3 승인 사다리의 "≤3%p" — 키 이름만 본 문서가 확정 |
| **── 이웃 설계서가 등재를 위임한 키 (이 판본에서 추가) ──** | | |
| `protections.symbol_cooldown_window_min` | 60 | 03 §1.2 P4 "1시간 내"(부록 A에 키 없음) — [09-safety-protections.md](09-safety-protections.md) §17-13 요청. **[DD-04-17]** |
| `protections.daily_order_amount_abs_krw` | `null`(미적용) | 03 §1.2 P3 "또는 절대 상한"(부록 A에 키·값 없음) — 〃. **[DD-04-17]** |
| `alerts.info_immediate_max_per_day` | 5 | [13-web-and-telegram.md](13-web-and-telegram.md) §3.4 [DD-13-4]·§12-8 위임 |
| `tracking_error.residual_monthly_threshold_pp` | 0.3 | 03 부록 A(4블록 안이나 본 문서 §4.2에 모델이 없었다 — 이 판본에서 정의). **[DD-04-15]** |
| `band.restore_mode` / `band.restore_rho` | fraction / `null` | [07-portfolio-engine.md](07-portfolio-engine.md) [DD-07-11] 위임 (C-31) |
| `crypto.vol_scale_max_age_days` | 10 | 〃 [DD-07-12] 위임 |
| `mc.paths` / `mc.block` / `mc.success_bands` | 5000 / 6 / `{green: .75, amber: .60}` | 02 부록 A(모델 미정의였음). **[DD-04-15]** |
| `mc.cost_annual` / `mc.inflation_annual` | 0.0035 / 0.02 | 02 §9 "실효 비용 연 0.35%, 인플레이션 2.0%" — 값은 계획, **키 이름만 본 문서**. **[DD-04-15]** |
| `gk.guardrail` / `gk.adjust` | 0.20 / 0.10 | 02 부록 A(모델 미정의였음). **[DD-04-15]** |
| `backtest.account_model` / `backtest.gates.core` / `.satellite` | single / 02 부록 A 문자열 | 02 부록 A(모델 미정의였음). **[DD-04-15]** |
| `backtest.sim_mode` · `backtest.costs.*`(8) · `backtest.data.max_gap_pct` · `backtest.lookahead.{samples,weight_tolerance}` · `backtest.snapshot.{tolerance_pct,absolute_floor.*}` · `backtest.benchmark.*` · `backtest.tax.harvest_enabled` · `backtest.seed` · `backtest.gates.challenger_years` · `backtest.us_fill_basis` | §4.2 `BacktestCfg` | [15-backtest-and-validation.md](15-backtest-and-validation.md) [DD-15-4] 위임. `snapshot.*`는 **값 미정 필수 키**(C-33) |
| `ws.tier1_enabled` | false | [05-broker-gateway.md](05-broker-gateway.md) §7.6·§11 C1 위임 (M9 미통과 시 T1 등록 경로 차단) |
| `surveillance.sources.<name>.max_age_hours` | `null`(단 `upbit_market` = 12) | [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md) §9.2 위임, 값 정본 06 §6.1 |
| `labs.challenger_enabled` | false | [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §4.3·§19 위임(의미 정의는 14) |
| `labs.g2.mode` | full | [14-research-and-labs.md](14-research-and-labs.md) §1.4 C4 위임 |
| `research.llm.*`(model·effort·max_output_tokens·use_batch·monthly_budget_usd) | 01 §8.1 값 | [14-research-and-labs.md](14-research-and-labs.md) §2.3 위임. 월 예산은 **[확인 필요]** |
| `research.user_agent` / `research.inbox_root` / `research.report_root` | §4.2 참조 | 〃 (경로 정본 14 [DD-14-4]) |
| `tax.harvest_auto_enabled` | false | [10-tax-engine.md](10-tax-engine.md) [DD-10-14] 위임 |
| `data.providers.<name>.enabled` | true | [06-market-data-and-calendar.md](06-market-data-and-calendar.md) §4.1 위임([DD-06-5]와 동일 취급) |
| `runtime.role` | `app` (`app`\|`tools`) | [01-system-architecture.md](01-system-architecture.md) §7.1 compose(`OMRA__RUNTIME__ROLE`)·SC-13 입력. **[DD-04-16]** |
| `web.bind_host` / `.bind_port` | `0.0.0.0` / 8080 | [13-web-and-telegram.md](13-web-and-telegram.md) §7.4 [DD-13-14] — 호스트 노출은 compose가 Tailscale IP에 바인딩 |
| `web.public_exposed` | false | 〃 (`env=live`에서 true면 기동 거부 — C-37) |
| `web.request_budget_ms` | 2000 | 〃 §7.5 [DD-13-15] |
| `web.shutdown_grace_sec` | 5 | 13 §7.1이 소비하고 값이 없다. 01-design [DD-01-5] 종료 예산 30초의 4단계(web·telegram 정지) 몫. **[DD-04-16]** |
| `jobs.*` · `monitoring.*` · `watchdog.*` | 아래 `schema/ops.py` | 12 §19 표를 필드로 확정. **[DD-04-16]** |

`market_weights.region_shift_approve_pp`(기본 5, 근거 00 §3.2 P6)는 **`AppConfig` 키가 아니라 레코드 파일 `market_weights.yaml`의 필드**다(§5.4) — 갱신 대상 값과 그 승인 임계를 같은 파일에 두어 버전이 함께 움직이게 한다. 따라서 CI ⓒⓓ의 대상이 아니며 `OMRA__MARKET_WEIGHTS__…` 오버라이드도 닿지 않는다([DD-04-3] ③). **같은 처분을 받는 항목이 셋 더 있다**: `glide.floor_level`([07-portfolio-engine.md](07-portfolio-engine.md) [DD-07-14])은 `goals.yaml`의 `glide_path.floor_level`로 통일하고([DD-04-18]), `universe.proxy_index_key`([DD-07-5])와 `fx_hedged`(15 §12.2)는 `universe.yaml`의 **종목 필드**다(§5.1).

**운영 블록 모델** — 12 §19 표가 값을 제안하고 본 문서가 필드로 확정한다(값 정본은 12, 단 `watchdog.interval_sec`은 [DD-04-5]):

```python
# schema/ops.py
class RuntimeCfg(BaseModel, frozen=True):
    role: Literal["app", "tools"] = "app"      # SC-13 자격증명 배치 검사의 입력 (§7.5)
    fill_queue_warn: int = 1000                # 01-design §4.4

class ToolsCfg(BaseModel, frozen=True):
    snapshot_max_age_h: int = 168              # 01-design §7.3

class WatchdogCfg(BaseModel, frozen=True):
    interval_sec: int = 10                     # ★ [DD-04-5] — 값 정본(12 §19 반영 완료, §14-13)
    heartbeat_max_age_sec: int = 180;  loop_lag_exit_ms: int = 5000;  consecutive: int = 3
    crashloop_window_min: int = 10;    crashloop_max: int = 3

class WebCfg(BaseModel, frozen=True):
    bind_host: str = "0.0.0.0";        bind_port: int = 8080
    public_exposed: bool = False;      https: bool = False
    session_idle_hours: int = 12;      session_max_days: int = 30      # [DD-04-6]
    request_budget_ms: int = 2000;     shutdown_grace_sec: int = 5

class JobsCfg(BaseModel, frozen=True):
    # ★ 12 §19가 `jobs.<name>.budget_sec`로 적은 것을 `jobs.overrides.<name>.budget_sec`로 확정한다 —
    #   `extra="forbid"` 아래에서 임의 잡 이름과 고정 필드(planner·catchup…)를 같은 레벨에 둘 수 없고,
    #   같은 레벨이면 `jobs.planner`가 잡 이름인지 예약어인지 스키마가 구별하지 못한다. (§14-16)
    overrides: Mapping[str, JobOverrideCfg] = {}   # `<name>.{budget_sec, enabled}` (12 §4.1)
    planner: PlannerStepsCfg                       # `jobs.planner.steps.<step>_sec` (12 §5.2, C-30)
    us_submit_lead: int = 10                       # 분. 12 §4.2 (개장−10분 역산 — 40분 아님)
    catchup: CatchupCfg = CatchupCfg(serial=True)  # 12 §8.2
    dep_wait: DepWaitCfg = DepWaitCfg(universe_reeval_min=30)          # 12 [DD-12-6]

class JobOverrideCfg(BaseModel, frozen=True):
    budget_sec: int | None = None;     enabled: bool = True

class MonitoringCfg(BaseModel, frozen=True):
    heartbeat_interval_sec: int = 30                                   # 12 [DD-12-7]
    disk:   DiskCfg  = DiskCfg(warn_pct=80, block_pct=90, release_pct=85)   # 12 [DD-12-14] (C-35)
    logs:   LogsCfg  = LogsCfg(retention_days=14, retention_days_pressure=7)  # 12 [DD-12-15]
    dms:    DmsCfg                                                     # ping_url [확인 필요] / 15분
    health: HealthCfg                                                  # thresholds.* — 12 §11.1 표

class DataCfg(BaseModel, frozen=True):
    quality: DataQualityCfg = DataQualityCfg(max_abs_daily_return=Dec("0.3"),
                                             max_abs_daily_return_crypto=Dec("0.5"))
    master:  DataMasterCfg                     # files: ["kospi_code.mst.zip", "kosdaq_code.mst.zip"]
    providers: Mapping[str, ProviderCfg] = {}  # `<name>.enabled` — 06 §4.1

class SecretsPolicyCfg(BaseModel, frozen=True):
    ladder_days: tuple[int, ...] = (45, 30, 14, 7, 3, 1)   # 01 §6.2 (§8.2 LADDER 의 days_before 정본)
    issue_spacing_days: int = 180                          # 01 §6.2 발급일 분산 (C-27)
```

> **[DD-04-5] `watchdog.interval_sec` 기본 10초**
> - 결정: 워치독 샘플링 주기를 10초로 둔다. 임의값이며 M4 실측 재캘리브레이션 대상(01 §6.4의 나머지 워치독 값과 동일 취급).
> - 근거: `loop_lag_exit_ms: 5000` × `consecutive: 3`이 의미를 가지려면 샘플 간격이 lag 임계와 같은 자릿수여야 한다. 60초면 자발적 종료까지 3분이 걸려 "응답만 멈춘" 구간이 길어지고, 1초면 정상 GC 지연을 연속 3회로 오탐한다.
> - 계획 문서와의 관계: 01 §6.4가 나머지 3개 값만 제시했다. 충돌 없음(여백 채움).

> **[DD-04-6] 대시보드 세션 수명 키 — `web.session_idle_hours` 12 / `web.session_max_days` 30**
> - 결정: 유휴 만료 12시간 + 절대 만료 30일 **두 키**를 등재한다. 값과 쿠키 속성의 소비 설계는 [13-web-and-telegram.md](13-web-and-telegram.md)가 소유하고 본 문서는 키·타입·기본값만 등재한다.
> - 근거: 01 §7-2가 세션 로그인(argon2)을 요구하나 유효기간을 정하지 않았다. Tailscale이 1차 방벽이므로(01 §7-1) 공격면이 좁고, 짧은 타임아웃은 부재 중 대시보드 확인을 방해한다. 다만 `last_seen` 갱신은 부재 감지의 입력이므로(03 §5.3.1) 무제한으로 두지도 않는다 — 절대 만료가 그 상한이다. 이전 판본의 단일 키 `web.session_idle_min: 60`은 13의 설계와 이름·값이 모두 어긋나 폐기했다. **[13-web-and-telegram.md](13-web-and-telegram.md) §7.3 [DD-13-13]이 12h/30d와 `web.https` 종속 `Secure` 속성을 확정했으므로 양방향 정합이 확인됐다**(검증자 미해결 항목 해소).
> - 계획 문서와의 관계: 여백 채움. 충돌 없음.

> **[DD-04-15] 루트 모델이 선언만 하고 필드가 없던 4블록 소속 블록의 정의 — `McCfg`·`GkCfg`·`TrackingErrorCfg`·`BacktestCfg`**
> - 결정: 네 블록의 필드를 §4.2에 정의한다. 값은 전부 계획 정본에서 온다 — `mc.paths`(5,000)·`mc.block`(평균 6개월 block bootstrap)·`mc.success_bands`(75%/60%)·`gk.guardrail`(±20%)·`gk.adjust`(±10%)·`backtest.account_model`(single)·`backtest.gates.{core,satellite}`는 **02 부록 A**, `tracking_error.residual_monthly_threshold_pp`(0.3)는 **03 부록 A**, `mc.cost_annual`(0.35%)·`mc.inflation_annual`(2.0%)는 **02 §9**(값은 계획, 키 이름만 본 문서). `backtest.*`의 나머지 키는 [15-backtest-and-validation.md](15-backtest-and-validation.md) [DD-15-4]가 이름을 정하고 본 문서가 스키마로 등재한다.
> - 근거: 이 넷은 §4.2 루트 모델에 필드로 선언되어 있는데 문서 어디에도 하위 필드가 없었다. [DD-04-4] 검사 ⓒ("4블록에서 추출한 키 집합 ⊆ `AppConfig` 필드 경로 집합")를 그대로 적용하면 본 문서가 자기 CI 게이트를 통과하지 못하고, 소비처는 실재하므로([07-portfolio-engine.md](07-portfolio-engine.md) §14.1 `McParams`, [15-backtest-and-validation.md](15-backtest-and-validation.md) §13.2·§5.2, [14-research-and-labs.md](14-research-and-labs.md) R1 잔차 임계) CI가 아니라 런타임 `AttributeError`로 드러난다.
> - 계획 문서와의 관계: 02 부록 A·02 §9·03 부록 A의 값을 스키마로 옮긴 것이며 새 값을 만들지 않았다. 충돌 없음.

> **[DD-04-16] 운영 블록(`runtime`·`tools`·`watchdog`·`web`·`jobs`·`monitoring`·`data`·`secrets`)의 필드 확정**
> - 결정: §4.4의 `schema/ops.py` 코드블록대로 필드를 확정한다. 값은 [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §19 표와 [01-system-architecture.md](01-system-architecture.md) §7.1·§4.4·§7.3, [13-web-and-telegram.md](13-web-and-telegram.md) §7.3~§7.5, [06-market-data-and-calendar.md](06-market-data-and-calendar.md) §4.1이 제안한 것을 그대로 받는다. 본 문서가 새로 정한 값은 둘뿐이다 — `runtime.role`의 기본값 `app`(compose가 tools 컨테이너에만 `OMRA__RUNTIME__ROLE=tools`를 주므로 기본은 app이어야 한다)과 `web.shutdown_grace_sec: 5`(01-design [DD-01-5]의 종료 예산 30초 중 4단계 몫).
> - 근거: 이 블록들은 루트 모델에 이름만 있고 하위 필드가 없어 소비 문서가 참조하는 키 경로를 검증할 수단이 없었다. [DD-04-4] 검사 ⓓ의 "등재처"가 §4.4 표뿐이면 표의 한 행(`jobs.* · monitoring.*`)이 수십 개 키를 가리키게 되어 오타를 잡지 못한다.
> - 계획 문서와의 관계: 01 §6.4(워치독 값)·01 §1.6(compose env)의 여백 채움. `watchdog.interval_sec`은 [DD-04-5] 10초를 유지한다(§14-13). 충돌 없음.

> **[DD-04-17] P3·P4의 계획 여백 키 신설 — `protections.symbol_cooldown_window_min`(60) / `protections.daily_order_amount_abs_krw`(`null`)**
> - 결정: 03 §1.2 본문에만 있고 03 부록 A에 키가 없는 두 파라미터를 정식 키로 등재한다. P4의 계수 창은 `symbol_cooldown_window_min: 60`(본문 "1시간 내"의 값 전재), P3의 절대 상한은 `daily_order_amount_abs_krw: null`이며 **`null`은 "미적용"을 뜻한다**(비율 상한 `daily_order_amount_pct: 30`만 강제).
> - 근거: [09-safety-protections.md](09-safety-protections.md) §17-13이 키 부재 때문에 60분을 코드 상수로, 절대 상한을 미적용으로 두었다고 기록했다. 60분은 계획 본문의 값이므로 하드코딩할 이유가 없고(00 §5 원칙 6), 절대 상한은 계획이 값을 주지 않았으므로 임의값을 만드는 대신 `null`로 두어 "미설정"과 "0원 상한"을 구별한다.
> - 계획 문서와의 관계: 03 §1.2 P3·P4 행의 여백을 키로 채운다. 값을 창작하지 않았다. 충돌 없음.

> **[DD-04-18] glide path 파라미터는 `goals.yaml` 한 곳에 둔다 — `glide.*` AppConfig 블록을 만들지 않는다**
> - 결정: [07-portfolio-engine.md](07-portfolio-engine.md) [DD-07-14]가 `glide.floor_level`(기본 3)로 지칭한 값을 **`goals.yaml`의 `glide_path.floor_level`**로 등재하고, `AppConfig`에 `glide` 블록을 만들지 않는다. 07 §13.1 `glide_level(goal, as_of, params: GlideParams)`의 `params`는 `bundle.goals.glide_path`에서 조립한다. 구간 경계(15년·5년)와 규칙명도 같은 블록의 `bands`가 정본이며 07의 알고리즘은 그 값을 읽는다(코드 상수 아님).
> - 근거: 04 §5.3의 `goals.yaml`은 이미 `glide_path.{mode, bands, transition_months}`를 갖는다. 여기에 `floor_level`만 `config.yaml` 쪽으로 빼면 **하나의 규칙이 두 파일에 갈리고**, 더 나쁘게는 `goals.*` 전체가 hard rail(00 §3.2 P7)인데 `glide.floor_level`만 HR 밖에 놓여 `labs.tuning_space` 사정거리에 들어온다. 리스크 레벨 하한은 정확히 자동 조정하면 안 되는 값이다.
> - 계획 문서와의 관계: 02 §3.5(glide path)·00 §3.2 P7(`goals.*` HR)과 정합. 07 [DD-07-14]의 **값(3)과 알고리즘은 그대로 수용**하고 키 경로만 확정한다 — 07 쪽 표기 정정이 필요하다(§14-18).

### 4.5 상호 제약 검증 (`constraints.py`)

01 §6.1이 요구한 "스키마 검증 + 상호 제약"의 구현. **런타임(기동 SC-1)과 CI(§9)가 같은 함수를 호출한다** — 03 §8 리스크 등록부의 "게이트는 CI 게이트 코드를 런타임 재사용(새 코드 최소화)" 규율이다.

```python
def check_all(bundle: ConfigBundle) -> list[ConstraintViolation]:
    """위반을 모아 반환(예외 아님). 호출자가 fail-fast 여부를 정한다."""
```

| ID | 제약 | 근거 |
|---|---|---|
| C-1 | `band.abs ≤ band.class_abs` | 01 §6.1 명시. **총자산 차원 비교이며 `band.isa_abs`·`band.pension_scheduled_abs`·`band.crypto_abs`는 계좌·슬리브 차원이라 제외** |
| C-2 | `policy.change_budget.total_per_year < targets + params + logic` | 02 부록 A "상위 캡 6이 하위 합 10보다 작아야 의미가 있다" |
| C-3 | 하위 예산 각각 ≥ 해당 카테고리의 **실사용 카운터**(DB) | 01 §6.1 "예산 상위 캡 ≥ 하위 예산 실사용" — 런타임 전용(CI는 스킵) |
| C-4 | `policy.auto_nocanary_threshold_pp < auto_threshold_pp < reject_threshold_pp` (3 < 8 < 20) | 02 §3.3 승인 사다리 |
| C-5 | `core.min_weight ≥ 1 − satellite.total_cap` | 02 §1 구조 트리(코어 하한 80% / 위성 하드캡 20%) |
| C-6 | `satellite.momentum.cap + crypto.cap ≤ satellite.total_cap` | 02 §1 트리(10% + 10% ≤ 20%) |
| C-7 | `crypto.target ≤ crypto.cap` | 02 §7 (기본 3%, 설정 1~10%, 하드캡 10%) |
| C-8 | `sum(crypto.mix.values()) == 1` 이고 키가 정확히 `{KRW-BTC, KRW-ETH}` | 02 §7 "BTC 70 : ETH 30 고정(알트 없음)" |
| C-9 | `protections.mdd_halt_pct < mdd_safe_mode_pct < mdd_recover_pct < 0` | 03 부록 A (−25 < −15 < −10) |
| C-10 | `protections.frozen_nav_safe_mode_pct < frozen_nav_halt_pct`, `turnover_monthly_mult_warn < _halt` | 03 부록 A |
| C-11 | `safe_mode.net_buy_daily_cap_pct ≤ net_buy_monthly_cap_pct` | 03 부록 A |
| C-12 | `presence.away_soft_h < away_h < away_long_d × 24` 이고 `grace_normal_min ≤ grace_away_soft_h×60 ≤ grace_away_h×60` | 03 부록 A |
| C-13 | `ws.subscription_cap + ws.reserve ≤ 41` | 06 부록 C ("하드 41") |
| C-14 | `canary.targets == labs.canary.targets_recalc`, `canary.methodology == labs.canary.method_swap` | §4.2 주석(두 표기의 이탈 방지) |
| C-15 | 모든 `canary.*.alphas`가 **단조증가**이고 마지막 원소 == 1.0 | 07 §8 (α는 혼합 비율, 최종은 완전 적용) |
| C-16 | `tax.income_alerts.{api,fallback}` 각각 `health ≤ info ≤ warn ≤ soft_stop` 이고 `soft_stop < 20,000,000` | 02 §5.3 표 + 금소세 2,000만 방어선 |
| C-17 | `universe.shrink_below_krw < universe.restore_above_krw` | 02 §3.3.1 히스테리시스 |
| C-18 | `mvo.lambda_risk_bounds[0] < [1]`, `bl.tau ∈ [0.02, 0.05]`, `bl.delta_mkt ∈ [2, 4]` | 02 부록 A 허용 범위 |
| C-19 | `etf.premium_gate.min_wait_sec ≤ max_total_defer_min × 60` | 06 부록 C |
| C-20 | `labs.tuning_space ⊆ AppConfig 실재 경로` 이고 07 §7.1 **제외 목록과 교집합 0** | 07 §7.1 |
| C-21 | `run.env == LIVE` → `live_confirmation` 3중 일치(§4.3), `crypto.enabled` → `upbit` 브로커 계좌 1개 이상 존재 | 03 §5.1, 02 §7 |
| C-22 | `accounts[].id` 유일, `broker == UPBIT ⇔ type == UPBIT`, `type == GENERAL`인 enabled 계좌 정확히 1개 | 02 §1.2 표(업비트는 암호화폐 전용, 일반위탁이 잔량 흡수 계좌 — 02 §4.3.0-b 4단계) |
| C-23 | `universe.yaml`의 모든 `approved_substitutes` 페어의 양쪽이 `instruments`에 존재하고 **같은 `asset_class`** | 02 §2.2("§2.3 hard 필터를 1순위와 동일하게 통과") |
| C-24 | `targets` 합 + `cash.buffer` == 1 (±1e-9) | 02 §3.3 1단계 제약 `1ᵀw + w_cash = 1` |
| C-25 | `market_weights.top_level` 합 == 1, `equity_regions` 합 == 1 | 02 §3.1 |
| C-26 | `external_schedules[].amount_tolerance_krw > 0` | 03 §1.3.1 "0 금지" |
| C-27 | `secrets_registry`의 tier-1 항목 2건(KIS 실전·업비트)의 `issued_at` 간격 ≥ `secrets.issue_spacing_days`(180) | 01 §6.2 발급일 분산 규칙 — **위반은 warning**(§8.5) |
| C-28 | `surveillance.yaml`의 `risk_type` 집합 ⊇ 06 §5.1 카탈로그 7종(M9 조건부 2종은 선택) | 06 §5.1 |
| C-29 | **폐기 — ID 재사용 금지.** [DD-04-21]이 법령값의 config 별칭을 제거해 비교할 교집합 자체가 없다 | 02 §5.5, 10 [DD-10-16]. 이전의 `ConfigConflictError` 비교안보다 단일 출처가 강한 불변식 |
| C-30 | `sum(jobs.planner.steps.*) ≤ 600` | 12 §5.2 [DD-12-3] 소프트 예산 합 ≤ `daily_planner` 하드 예산 |
| C-31 | `band.restore_mode == "destination"` → `band.restore_rho is not None`이고 `∈ (0, 1]` / `== "fraction"` → `restore_rho is None` | 07 [DD-07-11] (두 경로의 파라미터가 섞이면 어느 규칙이 돌았는지 사후에 알 수 없다) |
| C-32 | `backtest.costs.*`가 **전부 0이면 거부** | 15 §5.2 `_reject_zero`("거래비용 0 백테스트는 증거가 아니다" — 05 §10.3, 07 §4.4 HR-2) |
| C-33 | `backtest.snapshot.tolerance_pct`와 `absolute_floor.{sharpe,max_mdd}`가 **모두 설정**되어 있어야 한다(`None`이면 위반) | 15 [DD-15-10] "필수 키·값 미정(비면 CI 실패)" — 누락과 "임계 없음"을 구별한다 |
| C-34 | `mc.success_bands.green > mc.success_bands.amber` 이고 둘 다 `∈ (0, 1)` | 02 부록 A 녹/황/적 3분할 |
| C-35 | `monitoring.disk.warn_pct < release_pct < block_pct` | 12 [DD-12-14] 5%p 히스테리시스(80 < 85 < 90) |
| C-36 | `labs.rollback.r1_te_residual_pp == tracking_error.residual_monthly_threshold_pp` | 03 §4.6 = 07 §10.2 R1의 같은 0.3%p가 두 블록에 실렸다(C-14와 동형) |
| C-37 | `run.env == LIVE` → `web.public_exposed is False` 이고 `web.bind_host == "0.0.0.0"` | 13 [DD-13-14] ③(노출 통제는 호스트 바인딩·방화벽이 담당하며 앱은 그 전제가 깨졌는지만 검증) |

**불변 제약(타입으로 강제)**: `guard.oneway`는 `Literal[True]`다 — 일방향 밸브를 config로 끌 수 있으면 00 §5 원칙 9가 설정 한 줄로 무너진다. 06 부록 C가 "CI 아키텍처 테스트로 강제"라고 적은 것을 **타입 레벨로 한 겹 더** 올린다.

---

## 5. 레코드형 YAML 파일 스키마

공통 로더:

```python
# config/files/base.py
T = TypeVar("T", bound=BaseModel)

class RecordFile(Generic[T]):
    path: Path; sha256: str; model: type[T]; data: T
    @classmethod
    def load(cls, path: Path, model: type[T], *, required: bool = True) -> "RecordFile[T] | None":
        """YAML → model 검증. 오류는 (파일, YAML 경로, 사유)로 평탄화해 수집한다.
        required=False 이고 파일이 없으면 None (targets.yaml 콜드스타트 — 02 §3.3)."""
```

### 5.1 `universe.yaml` (정본 예시: 01 §6.1)

```yaml
version: 7
approved_at: 2026-08-01
instruments:
  - symbol: "360750"
    market: KRX                    # core.Market (02-domain-model.md §4)
    currency: KRW
    asset_class: kr_etf_equity     # 02 §4.3 EQUITY_ASSETS 판정의 입력
    sleeve: core                   # core | momentum | crypto
    tax_inefficiency_score: 4      # 02 §1.2 표1 (0~5 정수 랭크)
    risk_asset: true               # 02 §1.2 IRP 70% 제약의 입력
    lot_step: 1
    tick_rule: krx_etf_5
    allowed_accounts: [general, isa, pension, irp]     # 02 §1.2 표 (허용 자산 hard 제약)
    account_preference: {pension: 3, irp: 4, isa: 1, general: 2}   # 02 §1.2 표2 [DD-10-4]
    qualified_tdf: false           # 02 §1.2 "적격 TDF는 예외 처리(별도 플래그)"
    proxy_index_key: null          # 2년 미만 자산의 대리지수 백필 키 [DD-07-5] — null = 백필 없음
    fx_hedged: false               # 실효 환헤지비율 지표의 입력 (02 §8.4, 15 §12.2)
approved_substitutes:              # 02 §2.2 — 1:1 페어
  - ["VOO", "IVV"]
```

```python
class UniverseInstrument(BaseModel, frozen=True):
    symbol: str; market: Market; currency: Literal["KRW", "USD"]
    asset_class: str                                  # 어휘 검증은 아래
    sleeve: Literal["core", "momentum", "crypto"]
    tax_inefficiency_score: int = Field(ge=0, le=5)
    risk_asset: bool
    lot_step: Decimal; tick_rule: TickRuleId
    allowed_accounts: tuple[AccountType, ...]
    account_preference: Mapping[AccountType, int]     # 1 = 최우선
    qualified_tdf: bool = False
    proxy_index_key: str | None = None                # [→ 07 [DD-07-5]] 대리지수 백필 선언
    fx_hedged: bool = False                           # [→ 15 §12.2·§18-15] 실효 환헤지비율 입력

    def to_instrument(self) -> Instrument: ...        # core.Instrument (02-domain-model.md §4)

class UniverseFile(BaseModel, frozen=True):
    version: int = Field(ge=1)
    approved_at: date
    instruments: tuple[UniverseInstrument, ...]
    approved_substitutes: tuple[tuple[str, str], ...] = ()
```

- **`asset_class` 어휘의 정본은 이 파일이다**([02-domain-model.md](02-domain-model.md) [DD-02-4]가 "허용 어휘는 universe.yaml 스키마(04)가 검증한다"고 위임). 초기 어휘:

> **[DD-04-7] `asset_class` 허용 어휘 확정**
> - 결정: `{kr_etf_equity, kr_etf_bond, kr_etf_bond_ultrashort, kr_etf_reit, kr_etf_gold, kr_etf_us_equity, kr_etf_us_dividend, us_etf_equity, us_etf_bond, us_etf_reit, us_etf_gold, us_etf_tips, us_stock, crypto}` 14종을 초기 어휘로 고정하고, 어휘 추가는 config 변경(P5 = A3 승인 — 00 §3.2)으로만 가능하다.
> - 근거: 02 §1.2 표1의 자산군 구분(국내상장 채권 종합·리츠 / 국내상장 해외주식 ETF / 미국배당(국내상장) / 국내상장 초단기·금 / 국내주식형 ETF / 해외상장 ETF 전부)과 02 §2.1·§2.2 코어 후보 표의 자산군, 그리고 `EQUITY_CLASSES = {kr_etf_equity, us_etf_equity, us_stock}`(02 §4.3)을 하나의 어휘로 합친 결과다. 표1의 6행이 `tax_inefficiency_score` 5→0에 그대로 대응한다.
> - 계획 문서와의 관계: 02 §1.2 표1·02 §4.3 `EQUITY_ASSETS`와 정합. 02-domain-model.md [DD-02-4]가 위임한 여백을 채운다.

- **모델 검증**: `to_instrument()`가 [02-domain-model.md](02-domain-model.md) §4의 교차 검증표(market × currency × tick_rule × lot_step)를 통과해야 한다 — universe.yaml 로딩 시점에 즉시 실행하므로 잘못된 조합이 런타임까지 살아남지 않는다.
- **`account_preference`의 키는 `allowed_accounts`와 정확히 일치**해야 한다(부분 집합·초과 집합 모두 거부). 그렇지 않으면 02 §4.3.0-b 2단계의 "선호 순서 오름차순 순회"가 미정의가 된다.
- **`proxy_index_key`**([07-portfolio-engine.md](07-portfolio-engine.md) [DD-07-5]): 상장 2년 미만 자산의 기본 처분은 **제외**이고, 이 필드가 선언된 종목만 해당 지수 수익률로 앞부분을 백필한다. `null`이 기본이므로 **명시적 선언 없이는 백필이 일어나지 않는다** — 백필을 옵트인으로 두는 것이 07의 결정이며 스키마가 그것을 강제한다. 키 어휘(어떤 지수 식별자가 유효한가)는 [06-market-data-and-calendar.md](06-market-data-and-calendar.md)의 지수 카탈로그에 존재해야 하며 로딩 시 교차 검증한다.
- **`fx_hedged`**([15-backtest-and-validation.md](15-backtest-and-validation.md) §12.2·§18-15): 02 §8.4의 신규 지표 "실효 환헤지비율"의 유일한 입력이다. 계획이 지표는 요구했으나 속성 필드를 명시하지 않아 15가 등재를 요청했다. **필드가 없거나 전 종목이 기본값이면 지표를 추정하지 않고 `null`로 보고한다**(15 §12.2) — 추정치를 만들어 넣는 경로를 두지 않는다.
- **종목 상태 플래그는 이 파일에 없다**(`tr_stop_yn`·`admn_item_yn`·`lstg_abol_dt` 등) — 시점 의존 상태이므로 `surveillance_flags` 소관(02-domain-model.md §4 "넣지 않는 것", 06 §7.1).
- `universe_reeval`(월 1회, 01 §4.2)이 만드는 `var/policy/universe.yaml`도 **같은 모델**이며 `version`을 올린다. 교체는 자동 집행하지 않고 검토 플래그 + 승인 후 반영(02 §2.3-5).

### 5.2 `targets.yaml`

```yaml
version: 12
as_of: 2026-08-01
risk_level: 6                 # 산출 시점의 risk.level — 레벨 변경 감지용
weights:                      # instrument_key → 총자산 대비 목표비중
  "KRX:360750": 0.28
  "NASD:VTI":   0.17
cash: 0.01                    # cash.buffer 와 일치해야 한다 (C-24)
inputs_hash: "sha256:…"       # policy_versions.inputs_hash 와 동일 값
```

```python
class TargetsFile(BaseModel, frozen=True):
    version: int; as_of: date; risk_level: int
    weights: Mapping[str, Decimal]      # 키는 instrument_key (02-domain-model.md §3.2)
    cash: Decimal
    inputs_hash: str | None = None      # config/ 시드에는 없을 수 있다
```

- `config/targets.yaml`은 **시드값(최초 1회)**이다(01 §2). 유효 목표 선택 순서는 §6.3.
- **콜드스타트 정의**: `var/policy`에 targets 산출물이 없고 `config/targets.yaml`도 없으면 `bundle.targets is None`이며, 02 §3.3이 규정한 대로 **턴오버 항을 제거(γ=0)**한다. `w_prev = w_mkt` 같은 대체값을 만들지 않는다.
- `weights`의 모든 키는 `universe.yaml`의 종목이어야 한다(교차 검증). 유니버스에 없는데 보유 중인 자산은 `legacy` 집합이며 targets에 등장하지 않는다(02 §4.3.0-b 5단계).

### 5.3 `goals.yaml` — 전체 HR (00 §3.2 P7 `goals.*`)

```yaml
goals:
  - id: retirement
    kind: accumulate            # accumulate | withdraw    (02 §3.5 적립/인출)
    target_amount_krw: 1500000000
    target_date: 2050-12-31
    risk_level: 6
glide_path:                     # 02 §3.5 "잔여기간 기반 구간 규칙" — 예시 규칙이 기본값
  mode: remaining_years_bands
  bands:
    - {min_years: 15, rule: cap_at_level}          # 잔여 15년+ → 레벨 상한
    - {min_years: 5,  rule: linear_down}           # 5~15년 → 선형 하향
    - {min_years: 0,  rule: quarterly_step_down}   # 5년 미만 → 분기별 하향
  floor_level: 3                # 레벨 하한 (07 [DD-07-14] ④, 연변동성 6%) — [DD-04-18]
  transition_months: 3          # 하향 전환도 3개월 점진 집행 (02 §1.1·§3.5)
withdrawal:                     # 인출기 (02 §9, 00 §3.2 T8)
  initial_rate: 0.04
  inflation_link: true
```

```python
class Goal(BaseModel, frozen=True):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    kind: Literal["accumulate", "withdraw"]
    target_amount_krw: int; target_date: date
    risk_level: int = Field(ge=1, le=10)

class GoalsFile(BaseModel, frozen=True):
    goals: tuple[Goal, ...]
    glide_path: GlidePathCfg
    withdrawal: WithdrawalCfg | None = None
```

> **[DD-04-8] `goals.yaml` 스키마와 glide path의 구간 표현**
> - 결정: goal 레코드는 02 §3.5의 4요소(목표금액·목표일·유형·리스크 레벨)를 필드로 갖고, glide path는 `remaining_years_bands` 모드의 `bands` 리스트 + `floor_level`로 표현한다. 02 §3.5가 "예"로 든 3구간을 **기본값**으로 싣되 사용자가 변경할 수 있다(HR 영역이므로 사람만 바꾼다). `withdrawal.initial_rate: 0.04`는 02 §9의 초기 인출률 4.0%이며 Guyton-Klinger 가드레일 값 자체는 `gk.*`(02 부록 A, §4.2 `GkCfg`)에 남긴다. **`floor_level`을 이 블록에 둔 근거는 [DD-04-18]**이다.
> - 근거: 02 §3.5는 goal의 구성 요소만 확정하고 파일 형식을 정하지 않았다. 구간 규칙을 코드 상수로 두면 원칙 6(하드코딩 금지) 위반이고, `gk.*`와 중복 정의하면 인출 규칙이 두 곳으로 갈린다.
> - 계획 문서와의 관계: 02 §3.5·§9의 여백 채움. `gk.guardrail`/`gk.adjust`(02 부록 A)와 중복하지 않는다. 충돌 없음.

### 5.4 `market_weights.yaml`

```yaml
version: 4
as_of: 2026-07-31
top_level:                     # ★ 상수 — 자동 갱신 대상 아님 (02 §3.1, 03 §6.1 연 1회 사람 재검토)
  equity: 0.45
  bond: 0.45
  alternative: 0.10
equity_regions:                # ★ 월 1회 자동 갱신 (P6). 소스: MSCI ACWI IMI factsheet
  source: msci_acwi_imi
  weights:
    kr:  ~        # [확인 필요 — factsheet 실측값. M2 최초 적재 시 채워진다]
    us:  ~
    dev_ex_us: ~
```

```python
class MarketWeightsFile(BaseModel, frozen=True):
    version: int; as_of: date
    top_level: Mapping[Literal["equity","bond","alternative"], Decimal]
    equity_regions: EquityRegions
    region_shift_approve_pp: Decimal = Dec("5")   # 00 §3.2 P6. ★ AppConfig 키가 아니라
                                                  #   이 레코드 파일의 필드다(§4.4 말미)
```

- `top_level`은 **상수로 확정**되어 있고 갱신 자체가 폐지되었다(00 §3.2 P6, 02 §3.1). 스키마는 `auto_update` 플래그를 두지 않는다 — 플래그가 있으면 켤 수 있다는 뜻이 되고, 계획은 그 경로를 폐지했다.
- `equity_regions.weights`의 값은 **계획 문서에 수치가 없다**. `[확인 필요 — MSCI ACWI IMI factsheet 월 1회 갱신값. 확인 방법: 02 §3.1이 지정한 factsheet 파싱 잡의 최초 실행 결과]`로 두고 `None`을 허용하되, `None`이 하나라도 있으면 `monthly_targets_batch`는 **직전 유효 버전을 유지**한다(01 §4.2 "실패 시 전월 값 유지"와 같은 처분).
- 자산군당 5%p 초과 이동 시 A3 승인(00 §3.2 P6). 판정 로직은 [07-portfolio-engine.md](07-portfolio-engine.md) 소유이며 본 파일은 임계값만 제공한다.

### 5.5 `external_schedules.yaml` (정본 예시: 01 §6.1)

```yaml
- id: pension_monthly_transfer
  account_id: pension_savings
  kind: cash_in                       # cash_in | scheduled_fill
  instrument_key: null                # scheduled_fill 만 필수
  day_of_month: 25
  holiday_shift: next_business_day    # next_business_day | prev_business_day | skip
  amount_krw: 500000
  amount_tolerance_krw: 1000          # 사용자가 쓴다(시스템 산출 아님). 0 금지
  start_date: 2026-09-01
  end_date: null
```

```python
class ExternalSchedule(BaseModel, frozen=True):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    account_id: str
    kind: Literal["cash_in", "scheduled_fill"]
    instrument_key: str | None = None
    day_of_month: int = Field(ge=1, le=31)
    holiday_shift: Literal["next_business_day", "prev_business_day", "skip"]
    amount_krw: int = Field(gt=0)
    amount_tolerance_krw: int = Field(gt=0)      # 0 금지 (03 §1.3.1)
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def _check(self):
        # kind == scheduled_fill 이면 instrument_key 필수, cash_in 이면 반드시 null
        # end_date 가 있으면 start_date 이하 금지
        # account_id 는 accounts 등록부에 존재해야 한다 (번들 레벨 교차 검증)
```

- `holiday_shift`가 **`expected_date_from`/`expected_date_to` 폭을 결정한다**(01 §6.1). 전개 규칙(멱등 키 `(source, account_id, kind, instrument_key, expected_date_from)`)과 `reconcile_expectations` 행 생성은 `external_expectations_sync` 잡의 일이며 DDL은 [03-data-and-persistence.md](03-data-and-persistence.md) §3.2.2, 절차 정본은 03 §1.3.1이다.
- `day_of_month: 29~31`은 짧은 달에 존재하지 않는다. 스키마는 값을 허용하되 **전개기가 "그 달의 마지막 영업일"로 클램프**하는 것을 계약으로 명시한다 — 이 규칙이 없으면 2월에 기대값이 생성되지 않아 P8이 발동한다.
- 파일 해시 변경이 재전개 트리거다(03 §6.3, §3.7).

### 5.6 `external_income.yaml`

```yaml
- id: bank_deposit_1
  kind: deposit            # deposit | bond | other
  principal_krw: 50000000
  annual_rate: 0.035
  maturity: 2027-03-31
  payout: at_maturity      # monthly | quarterly | annual | at_maturity
```

필드는 [10-tax-engine.md](10-tax-engine.md) §8.3의 소비 형태와 문자 단위로 일치한다(계획 근거: 02 §5.2·00 §3.2 T2의 `{원금·이율·만기·지급주기}`). 연간 귀속 계산·70% 확인 질의·타임아웃 처분은 10이 소유한다.

```python
class ExternalIncome(BaseModel, frozen=True):
    id: str; kind: Literal["deposit", "bond", "other"]
    principal_krw: int = Field(gt=0)
    annual_rate: Decimal = Field(ge=0)
    maturity: date
    payout: Literal["monthly", "quarterly", "annual", "at_maturity"]
```

### 5.7 `surveillance.yaml` — 등급 매핑 외부화 (06 부록 C 말미)

```yaml
version: 1
map:
  - risk_type: KR-01          # 매매거래정지            [→ 06 §5.1]
    level: SV3
  - risk_type: KR-02          # 관리종목 지정
    level: SV2
    esc_proposal: ESC_REPLACE
  - risk_type: KR-03          # ETF/ETN 투자유의종목
    level: SV2
    notify: SV1
  - risk_type: KR-04          # 상장폐지일자 확정
    level: SV2
    esc_proposal: ESC_REPLACE
    deadline_from: lstg_abol_dt        # deadline_at 을 채우는 소스 필드 → P14 입력
  - risk_type: KR-12          # CA 매매거래정지 예정
    level: SV3
    notify: SV1
    effective_from: td_stop_dt         # ★ 사전 예약 (06 §7.1)
  - risk_type: US-01          # 미국 거래정지 (M6)
    level: SV3
  - risk_type: US-02          # 미국 상장폐지 확정 (M6)
    level: SV2
    esc_proposal: ESC_REPLACE
  # ── M9 조건부 2행 (06 §5.2). kis_ws_market 비활성 시 로드되지만 소스가 없어 사문화된다
  - risk_type: KR-09          # VI 발동/해제
    level: SV0
    hold_orders: true
    p9_exempt: true                    # P9 카운트 제외 (06 §5.2)
    requires_source: kis_ws_market
  - risk_type: KR-01P         # 거래정지 실시간 승격 (06 §5.2 KR-01′)
    level: SV3
    requires_source: kis_ws_market
```

```python
class SurvMapEntry(BaseModel, frozen=True):
    risk_type: str                                   # 06 §5.1 카탈로그 ID
    level: Literal["SV0","SV1","SV2","SV3"]
    notify: Literal["SV1"] | None = None             # 등급과 별도로 info 1회 동반
    esc_proposal: Literal["ESC_REPLACE"] | None = None   # ★ ESC_LIQUIDATE 는 표현 불가
    deadline_from: str | None = None                 # 소스 필드명 → surveillance_flags.deadline_at
    effective_from: str | None = None                # 소스 필드명 → surveillance_flags.effective_from
    hold_orders: bool = False
    p9_exempt: bool = False
    requires_source: str | None = None               # surveillance.sources 의 키

class SurveillanceMapFile(BaseModel, frozen=True):
    version: int
    map: tuple[SurvMapEntry, ...]                    # risk_type 유일
```

> **[DD-04-9] `esc_proposal`의 타입에서 `ESC_LIQUIDATE`를 제거한다**
> - 결정: `esc_proposal` 필드의 타입을 `Literal["ESC_REPLACE"] | None`으로 두어 `ESC_LIQUIDATE`를 **config로 표현할 수 없게** 한다. `ESC_LIQUIDATE`는 사람이 명시적으로 만드는 승인 큐 항목으로만 존재한다([11-realtime-and-surveillance.md](11-realtime-and-surveillance.md) 소유).
> - 근거: 00 §3.2 S5와 06 §8.1이 `ESC_LIQUIDATE`를 "A3 승인 전용 — 자동 금지, **영구**"로 못박았다. 자동 제안조차 매핑 테이블에 값으로 존재하면 "등급을 하나 더 올리면 청산"이라는 연속 스펙트럼 오독이 config 파일에 물리적으로 새겨진다 — 06 §5.1이 `ESC_*`를 등급 enum에서 분리한 의도의 정면 위반이다.
> - 계획 문서와의 관계: 06 §8.1 세 줄 원칙("어떤 소스도, 어떤 오버라이드도 `ESC_*`를 자동 실행할 수 없다")을 타입으로 승격. 충돌 없음.

> **[DD-04-14] 06 §5.2 `KR-01′`의 config 표기를 `KR-01P`로 고정**
> - 결정: 06 §5.2가 프라임 기호로 표기한 `KR-01′`을 config·DB 값으로는 `KR-01P`로 쓴다. 06의 표기는 문서상의 명칭이고, `risk_type`은 `surveillance_flags` 복합 PK의 일부이자 exact match 판정 키다(06 §7.1·02-domain-model.md §3.2의 exact-match 규율).
> - 근거: `′`(U+2032)는 프라임이고 아포스트로피(U+0027)·억음부호와 육안 구별이 되지 않는다. 사람이 손으로 쓰는 `surveillance.yaml`에 그 문자를 요구하면 "보기에 같은데 매칭되지 않는 행"이 생기고, 그 실패는 M9 착수 시점에야 드러난다. ASCII 토큰으로 고정하는 것이 exact-match 규율의 전제다.
> - 계획 문서와의 관계: 06 §5.2의 **명칭은 그대로 두고 값 표기만 확정**한다(06 §5.1 7종의 ID는 이미 전부 ASCII라 영향 없음). 충돌 없음. 단 [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md)가 같은 토큰을 써야 한다(§14-17).

- **M9 조건부 처리(양쪽 경로)**: `requires_source`가 가리키는 소스가 `surveillance.sources[...].enabled == false`이면 그 엔트리는 **로드되되 비활성**으로 표시된다(`SurvMapEntry.active == False`). M9 미착수 경로에서는 KR-09·KR-01′ 행이 생성되지 않고 06 §5.2대로 사후 추정·일 1회 배치가 담당한다. M9 착수 시 `kis_ws_market.enabled: true` 한 줄로 활성화되며 **스키마 변경이 없다** — 조건부 요소를 조건부 스키마로 만들지 않는 것이 요점이다.
- `map`은 `enabled`가 아니라 `requires_source`로 조건을 표현한다. 소스 활성 여부는 이미 `surveillance.sources`에 있으므로 두 곳에 켜고 끄는 스위치를 두면 어긋난다.

### 5.8 `tax.yaml` — effective-date 버전 파일

```yaml
schema_version: 1
versions:
  - effective_from: 2026-01-01
    note: "2026 세제 기준"
    params:
      overseas_cg_rate: 0.22
      overseas_cg_deduction_krw: 2500000
      dividend_wht_rate: 0.154
      fin_income_aggregate_threshold_krw: 20000000
      isa_free_limit_krw: 2000000
      isa_excess_rate: 0.099
      isa_annual_contrib_cap_krw: 20000000
      pension_deduct_cap_savings_krw: 6000000
      pension_deduct_cap_total_krw: 9000000
      pension_contrib_cap_total_krw: 18000000
      harvest_cost_gate_factor: 0.5      # 왕복비용 < 절세액 × 0.5   [→ 00 §3.2 T3]
      harvest_annual_nav_cap: 0.20       # 연 하베스팅 주문금액 ≤ NAV 20%  〃
      crypto_tax_enabled: false
```

```python
class TaxVersion(BaseModel, frozen=True):
    effective_from: date
    note: str = ""
    params: TaxParams              # 소비 모델 정본: 10-tax-engine.md §3.1

class TaxLawFile(BaseModel, frozen=True):
    schema_version: int = 1
    versions: tuple[TaxVersion, ...]

    @model_validator(mode="after")
    def _check(self):
        # ① effective_from 중복 금지 ② 최소 1개 ③ 정렬은 로더가 내림차순으로 재정렬
        # ④ 배당 분리과세 세율표·분기 키가 존재하면 거부 (02 §5.5 "만들지 않는다")
```

> **[DD-04-10] 버전 파일의 물리 형식 — `versions:` 리스트 단일 파일**
> - 결정: effective-date 버전은 파일을 여러 개 두지 않고 하나의 `tax.yaml` 안에 `versions:` 리스트로 담는다. 검증기가 `effective_from` 중복을 거부하고 로더가 내림차순으로 정렬해 보관한다.
> - 근거: [10-tax-engine.md](10-tax-engine.md) §3.2 `TaxParamStore`가 "`tax.yaml`의 `versions: [...]` 목록을 보유"를 전제로 이미 작성되어 있다. 파일 분할(`tax.2026.yaml`)은 디렉터리 스캔 규칙과 파일명 파싱을 추가로 요구하고, T7 diff 초안(00 §3.2, 10 §3.3)이 "현행 vs 제안"을 한 파일 안에서 보여주기 어려워진다.
> - 계획 문서와의 관계: 02 §5.5·01 §6.1의 "effective-date 버전으로 관리" 여백 채움. 충돌 없음.

- **④ 배당 분리과세 키 금지 검증**: 02 §5.5가 "배당 분리과세 세율표·분기 키는 `tax.yaml`에 만들지 않는다"고 명시했으므로, `TaxParams`에 해당 필드가 없는 것(= `extra="forbid"`로 거부)만으로 이미 강제된다. 검증기는 오류 메시지에 그 근거 문장을 실어 사람이 "왜 거부됐는가"를 즉시 알게 한다.
- 유효 버전 선택 기준 시각은 §6.2.

### 5.9 `secrets_registry.yaml` — 값 없이 날짜만 (정본 예시: 01 §6.1·§6.2)

```yaml
- name: KIS_APP_KEY
  issued_at: 2026-08-01
  expires_at: 2027-08-01
  tier: 1
  auto_action: pause_all_d7_safe_mode_d3
```

```python
class SecretTier(IntEnum):
    TIER1 = 1     # 만료 = 전면 정지 위험 (KIS 실전 앱키 / 업비트)
    TIER2 = 2
    TIER3 = 3

class AutoAction(StrEnum):
    NONE = "none"
    PAUSE_ALL_D7_SAFE_MODE_D3 = "pause_all_d7_safe_mode_d3"   # 01 §6.1 예시 문자열 그대로
    DISABLE_PAPER_ON_EXPIRY   = "disable_paper_on_expiry"     # KIS 모의투자 참가 기간 (2급)
    PREEMPTIVE_REISSUE_DAILY  = "preemptive_reissue_daily"    # approval_key 07:00 무조건 재발급
    WARN_ON_SEND_FAIL_STREAK  = "warn_on_send_fail_streak"    # Telegram/SMTP 3회 연속 실패
    CRITICAL_ON_BACKUP_FAIL   = "critical_on_backup_fail"     # Litestream
    WARN3_CRITICAL7_ON_FAIL   = "warn3_critical7_on_fail"     # restic 3회 warning / 7일 critical

class SecretRegistryEntry(BaseModel, frozen=True):
    name: str                         # SecretSpec 카탈로그의 이름과 일치해야 한다 (§7.2)
    issued_at: date
    expires_at: date | None           # None = 무기한 (01 §6.2 "무기한" 행)
    tier: SecretTier
    auto_action: AutoAction = AutoAction.NONE
    sleeves: tuple[SleeveId, ...] = ()   # tier1 자동 조치의 대상 슬리브(복수 — 아래)

class SecretsRegistryFile(BaseModel, frozen=True):
    entries: tuple[SecretRegistryEntry, ...]     # name 유일
```

> **[DD-04-11] `auto_action`을 자유 문자열이 아니라 닫힌 enum으로 둔다**
> - 결정: 01 §6.1 예시의 `pause_all_d7_safe_mode_d3` 문자열을 포함해 01 §6.2 표의 "자동 조치" 열 7종을 `AutoAction` enum으로 확정하고, tier-1 항목은 `PAUSE_ALL_D7_SAFE_MODE_D3` 외의 값을 가질 수 없다.
> - 근거: 자동 조치는 봇 상태를 바꾸는 행동(`PAUSED_ALL`·`SAFE_MODE`)이다. 자유 문자열이면 오타가 "조치 없음"으로 조용히 퇴화하고, 그 실패는 만료 당일에야 드러난다 — 01 §6.2가 "대책이 알림뿐이면 부재 중 만료 = 전면 정지"라고 경고한 바로 그 상황이다.
> - 계획 문서와의 관계: 01 §6.2 표의 자동 조치 열을 값 어휘로 코드화. 충돌 없음.

- **`sleeves` 필드**: tier-1 자동 조치는 "해당 슬리브 `PAUSED_ALL`"인데(01 §6.2) 어느 슬리브인지가 시크릿마다 다르다(KIS 앱키 → `kis_domestic`+`kis_overseas`, 업비트 → `upbit`). `SleeveId`는 [02-domain-model.md](02-domain-model.md) §3.4가 소유하며, KIS 항목은 **두 슬리브**를 가리키므로 필드는 단수 `SleeveId`가 아니라 `tuple[SleeveId, ...]`다(§8.3 `AutoActionEffect.sleeves`가 그대로 받는다).
- **값은 절대 이 파일에 없다**(01 §6.2 "발급일·만료일은 config에, 값은 `.env`에"). 검증기는 엔트리에 `value`·`secret`·`key` 같은 필드가 있으면 즉시 거부한다(`extra="forbid"`가 이미 처리하지만, 오류 메시지로 이유를 명시한다).

### 5.10 `tr_ids.kis.yaml` — 참조 + 검증 배선

**파일의 내용 정본(2섹션 구조·TR 목록·TR ID 값·`TrMap` 로더)은 [05-broker-gateway.md](05-broker-gateway.md) §7.1이 소유한다.** 본 문서는 config 계층으로서의 세 가지만 소유한다.

1. **표기 규약**: `rest.trs[].name`은 `^[a-z][a-z0-9_]{1,31}$`, `tr_id`는 대문자·숫자, 값이 `"<확인 필요…>"`로 시작하면 **미확정 마커**로 취급한다.
2. **검증 배선**: 기동 셀프체크 SC-1(01-design §5.2)이 이 파일을 로드해 필수 키(`rest.live_prefix`·`rest.paper_prefix`·`rest.base_url.{env}`·`ws.{env}.url`)의 존재를 확인한다. **미확정 마커가 남은 채 `env: live`로 기동하면 기동 거부**, `env: paper`·`dry_run`이면 warning 후 진행한다 — 실전 주문 경로에 확정되지 않은 TR ID가 실리는 것만 막고 개발은 막지 않는다.
3. **CI 게이트**: config 변경 CI(§9)가 이 파일의 스키마 검증을 수행한다. TR ID 값 자체의 정확성은 CI가 알 수 없으므로 카세트 계약 테스트(16 소유)에 맡긴다.

```python
# config/files/trids.py — 스키마 검증 전용. 해석은 brokers/kis/tr_map.py (05 §7.1)
class TrIdsRaw(BaseModel, frozen=True):
    rest: RestSection; ws: WsSection
    def unresolved(self) -> tuple[str, ...]:
        """"<확인 필요" 로 시작하는 값의 YAML 경로 목록. live 기동 거부 판정의 입력."""
```

### 5.11 `config/litestream.yml`

01 §6.5가 파일 내용의 정본이고, `${LITESTREAM_BUCKET}`은 `.env.litestream`에서 온다. **이 파일은 외부 도구(litestream 컨테이너)가 소비하므로 `AppConfig` 스키마 검증 대상이 아니다.** config CI 게이트는 두 가지만 확인한다: ① YAML 구문 유효 ② `dbs[].path`가 `/app/var/db/omra.sqlite`([03-data-and-persistence.md](03-data-and-persistence.md)의 DB 경로)와 일치. 경로 불일치는 "복제되고 있다고 믿는데 아무것도 복제되지 않는" 실패이며 01 §6.5가 그것을 우려해 파일 자체를 정본으로 실었다.

### 5.12 `research_open_questions.yaml` — "재확인 필요" 항목 레지스트리

[14-research-and-labs.md](14-research-and-labs.md) §10.3이 다이제스트 섹션 `D4`의 입력으로 요구하고 **스키마 소유를 본 문서에 위임**한 레코드 파일이다. 소비 모델 `OpenQuestion`의 필드 구성은 14 §10.3이 정본이며, 본 절은 파일 형식·검증 규칙만 정의한다.

```yaml
version: 1
questions:
  - id: "05 §4.5.3"                 # 계획 문서의 절 참조 — 사람이 읽는 식별자
    text: "한국 세제 보정(추론)"
    status: OPEN                    # OPEN | RESOLVED
    spike: SP-E3                    # 종속 스파이크. 없으면 null
    opened_at: 2026-08-01
    resolved_at: null               # status == RESOLVED 일 때만 필수
    note: ""
```

```python
class OpenQuestion(BaseModel, frozen=True):     # 소비 타입 정본: 14 §10.3
    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    status: Literal["OPEN", "RESOLVED"]
    spike: str | None = None                     # "SP-E3" 등
    opened_at: date
    resolved_at: date | None = None
    note: str = ""

class OpenQuestionsFile(BaseModel, frozen=True):
    version: int = Field(ge=1)
    questions: tuple[OpenQuestion, ...]          # id 유일
```

> **[DD-04-20] `research_open_questions.yaml` 스키마 — `related_count_this_month`는 파일에 두지 않는다**
> - 결정: 파일에는 **사람이 관리하는 사실만** 담는다(`id`·`text`·`status`·`spike`·`opened_at`·`resolved_at`·`note`). 14 §10.3 `OpenQuestion`이 갖는 `related_count_this_month`는 **다이제스트 생성 시 그 달의 추출 결과에서 계산되는 파생값**이므로 config 파일 필드가 아니다 — `RecordFile` 로더는 파생값을 만들지 않는다.
> - 근거: 이 파일은 `config/` 하위이므로 :ro 마운트이고 잡이 쓸 수 없다(§1.3). 월별 카운트를 파일에 두면 매월 사람이 편집해야 하거나 잡이 입력물을 수정해야 하며, 후자는 입력물·산출물 분리(01 §6.1)의 정면 위반이다. 14가 "자동으로 `RESOLVED`로 바꾸지 않는다"고 못박은 것과 같은 방향이다.
> - 계획 문서와의 관계: 07 §1.1(재확인 필요 항목의 가시화)의 여백 채움. 충돌 없음.

- **검증 규칙**: ① `id` 유일 ② `status == RESOLVED` ⇔ `resolved_at is not None` ③ `resolved_at >= opened_at` ④ `spike` 값이 있으면 `^SP-[A-Z]\d$` 패턴.
- 파일이 없으면 빈 레지스트리로 취급한다(`required=False`) — `research.enabled: false`(M10a 이전)에서 존재를 강제할 이유가 없다.

---

## 6. effective-date 버전 규칙과 정책 산출물

### 6.1 두 종류의 "버전"을 구분한다

| 종류 | 대상 | 선택 기준 | 소유 |
|---|---|---|---|
| **effective-date 버전** | `tax.yaml` — 한 파일 안에 시점별 파라미터 집합이 공존 | **주문 제출 시각의 KST 날짜**(01 §6.1) | §6.2 |
| **산출물 버전** | `targets`·`universe` — 잡이 만드는 파일이 `var/policy/`에 누적 | `policy_versions`의 최신 행(kind별) | §6.3 |

두 개를 섞으면 "이번 달 targets"가 "작년 세법"으로 계산되는 식의 사고가 난다. 타입으로 분리한다 — `VersionedFile[T]`(시점 질의)와 `PolicyOutput[T]`(포인터 조회)는 다른 클래스다.

### 6.2 `VersionedFile[T]`

```python
# config/versioned.py
class VersionedFile(Generic[T]):
    versions: tuple[tuple[date, T], ...]        # effective_from 내림차순, 중복 없음

    def at(self, kst_date: date) -> T:
        """effective_from <= kst_date 인 것 중 가장 최신.
        ★ 기준 시각은 **주문 제출 시각의 KST 날짜**다 (정본: 01 §6.1 —
          체결일·결제일이 아니며, 03 §2.2 기간 귀속 규칙과 동일).
        해당 버전이 없으면(모든 effective_from 이 미래) EffectiveVersionMissing."""

    def at_or_none(self, kst_date: date) -> T | None: ...
    def latest(self) -> T: ...
```

- `Clock`(정의 정본: [02-domain-model.md](02-domain-model.md) §7)을 주입받아 KST 날짜를 얻는다. 백테스트는 같은 `Clock` 추상으로 과거 날짜를 넣어 **당시 유효 세법**으로 시뮬레이션한다 — 현재 세법을 과거에 적용하는 것은 lookahead이며(02 §8.3), `at()`이 그 경로를 막는 구조적 장치다.
- 집계 경로(YTD 누적·연말 판정)는 **결제일 기준 버전**을 쓴다([10-tax-engine.md](10-tax-engine.md) §3.2). 본 클래스는 날짜를 받는 순수 함수이므로 두 경로를 모두 지원하며, 어느 날짜를 넣을지는 소비자(10)가 정한다.
- **경계 케이스**: 세법 개정 `effective_from`이 연중이면, 같은 과세연도 안에서 `at()`이 두 버전을 반환한다. 이는 정상이며 10이 "개정 이후 발생분에 신 버전"으로 처리한다.

### 6.3 정책 산출물 로딩

```python
# config/policy_output.py
@dataclass(frozen=True)
class PolicyPointer:
    targets:  PolicyRow | None      # policy_versions(kind='targets')  의 최신 행
    universe: PolicyRow | None      # policy_versions(kind='universe') 의 최신 행

def resolve_targets(config_dir: Path, policy_dir: Path, ptr: PolicyPointer) -> TargetsFile | None:
    """선택 순서:
       1. ptr.targets 가 있고 그 path 파일이 존재·해시 일치 → 그것을 쓴다 (잡 산출물)
       2. 없으면 config/targets.yaml (사람이 준 시드 — 01 §2)
       3. 그것도 없으면 None → 콜드스타트(γ=0, 02 §3.3)
    ★ 1에서 path 는 있는데 파일이 없거나 해시가 다르면 → PolicyArtifactMissing(critical) 후 2로
      폴백한다. DB 포인터가 깨진 참조가 되는 경우(03-design [DD-03-23])의 처리."""
```

- `universe`도 동일 구조다. `policy_versions.inputs_hash`는 산출 입력의 지문이며(01 §1.3) 재현성 검증에 쓰인다.
- **`var/policy/` 산출물은 CI 게이트 대상이 아니다**(01 §6.1). `config/` 하위만 §9의 스키마 검증·스냅샷 회귀를 탄다.
- `RELOAD_CONFIG`(01-design §6.3)는 `config/`만 다시 읽고 산출물 포인터는 DB에서 재조회한다 — 사람이 `/reload_config`를 했다고 진행 중인 월간 목표가 바뀌면 안 된다.

---

## 7. 시크릿 관리

### 7.1 불변식 세 개

1. **시크릿은 YAML에 절대 넣지 않는다**(01 §6.1). `AppConfig` 모델에는 시크릿을 담을 수 있는 필드가 **하나도 없다** — `redact.py`가 `SecretSpec` 이름과 겹치는 `AppConfig` 경로를 발견하면 예외를 던지므로(§7.4), 실수로 필드를 추가하면 테스트가 즉시 깨진다.
2. **`.env`는 chmod 600, git 제외**(01 §6.1, 01 §1.6).
3. **`account_id → 실계좌번호` 매핑은 시크릿 계층과 브로커 어댑터만 안다**([02-domain-model.md](02-domain-model.md) [DD-02-3]). core 도메인 타입·config 트리·감사로그 어디에도 `CANO`가 없다.

### 7.2 `.env` 3종 분리 (정본: 01 §1.6·§6.1·§6.5)

| 파일 | 소비 컨테이너 | 내용 | 절대 넣지 않는 것 |
|---|---|---|---|
| `.env` | `app` | 아래 전체 카탈로그 | — |
| `.env.litestream` | `litestream` | `LITESTREAM_BUCKET` + 오브젝트 스토리지 키 | 브로커·Telegram·SMTP 자격증명 |
| `.env.tools` | `tools`(profile) | Parquet·DuckDB 경로류 + `ANTHROPIC_API_KEY` | **브로커·Telegram·SMTP 자격증명 전부** |

`.env.tools`의 최소권한이 `labs`/`research` 격리의 **프로세스 경계 쪽 절반**이다(01 §6.1) — import는 막았는데 같은 이미지·같은 자격증명으로 도는 별도 프로세스가 주문을 낼 수 있으면 계약이 무효화된다(01 §1.6). 검증은 SC-13(§7.5).

**시크릿 카탈로그** (`SecretSpec`, 코드 상수 — 01 §6.1 목록 + §6.2 표):

```python
@dataclass(frozen=True)
class SecretSpec:
    name: str
    required_in: frozenset[ExecEnv]        # 어느 실행 모드에서 필수인가
    surface: Literal["app", "litestream", "tools"]
    tier: SecretTier
    registry_tracked: bool                 # secrets_registry.yaml 에 만료 행이 있어야 하는가

CATALOG: Final[tuple[SecretSpec, ...]] = (
    # ── 브로커 (01 §6.1) ────────────────────────────────────────────
    SecretSpec("KIS_APP_KEY",           {LIVE},        "app", TIER1, True),
    SecretSpec("KIS_APP_SECRET",        {LIVE},        "app", TIER1, True),
    SecretSpec("KIS_PAPER_APP_KEY",     {PAPER},       "app", TIER2, True),
    SecretSpec("KIS_PAPER_APP_SECRET",  {PAPER},       "app", TIER2, True),
    SecretSpec("KIS_ACCOUNT_NO",        {LIVE, PAPER}, "app", TIER1, False),
    SecretSpec("KIS_HTS_ID",            {LIVE, PAPER}, "app", TIER2, True),
    SecretSpec("UPBIT_ACCESS",          {LIVE},        "app", TIER1, True),
    SecretSpec("UPBIT_SECRET",          {LIVE},        "app", TIER1, True),
    # ── 알림 (01 §6.1·§6.4 — 이중화 필수) ───────────────────────────
    SecretSpec("TELEGRAM_BOT_TOKEN",    {LIVE, PAPER}, "app", TIER2, True),
    SecretSpec("TELEGRAM_CHAT_ID",      {LIVE, PAPER}, "app", TIER2, False),
    SecretSpec("SMTP_HOST",             {LIVE},        "app", TIER2, False),
    SecretSpec("SMTP_PORT",             {LIVE},        "app", TIER2, False),
    SecretSpec("SMTP_USER",             {LIVE},        "app", TIER2, False),
    SecretSpec("SMTP_PASS",             {LIVE},        "app", TIER2, True),   # 앱 비밀번호
    SecretSpec("DEADMAN_WEBHOOK_URL",   {LIVE},        "app", TIER2, False),
    # ── 웹 (01 §6.1·§7) ────────────────────────────────────────────
    SecretSpec("WEB_SESSION_SECRET",      {LIVE, PAPER}, "app", TIER3, True),
    SecretSpec("WEB_ADMIN_PASSWORD_HASH", {LIVE, PAPER}, "app", TIER3, True),   # argon2
    # ── 안전장치 확인코드 (09 [DD-09-14] 요청 — [DD-04-19]) ──────────
    SecretSpec("SAFETY_CODE_SECRET",      {LIVE, PAPER}, "app", TIER3, True),   # 당일 코드 HMAC 파생
    # ── 백업 (01 §6.1·§6.5) ────────────────────────────────────────
    SecretSpec("LITESTREAM_BUCKET",       {LIVE}, "litestream", TIER2, False),
    SecretSpec("LITESTREAM_ACCESS_KEY_ID",     {LIVE}, "litestream", TIER2, True),
    SecretSpec("LITESTREAM_SECRET_ACCESS_KEY", {LIVE}, "litestream", TIER2, True),
    SecretSpec("RESTIC_REPOSITORY",       {LIVE}, "app",        TIER2, False),
    SecretSpec("RESTIC_PASSWORD",         {LIVE}, "app",        TIER2, True),
    SecretSpec("RESTIC_ACCESS_KEY_ID",     {LIVE}, "app",       TIER2, True),
    SecretSpec("RESTIC_SECRET_ACCESS_KEY", {LIVE}, "app",       TIER2, True),
    # ── LLM (01 §6.1 `.env` 목록 + §1.6 `.env.tools`) ───────────────
    # ★ 유일하게 app·tools 양쪽 서페이스에 존재한다: research 파이프라인은 봇 프로세스가
    #   인-프로세스로 돌리고(01 §1.6), 백테스트·리서치 CLI도 같은 키를 쓴다.
    #   surface="app" 이므로 §7.5 tools 역방향 검사가 이 이름만 예외 처리한다.
    SecretSpec("ANTHROPIC_API_KEY",     set(),         "app", TIER3, True),
)
```

> 백업 계열의 개별 변수명(`LITESTREAM_ACCESS_KEY_ID` 등)은 계획이 "Litestream 스토리지 키"·"오브젝트 스토리지 키"로만 지칭한 것을 구체화한 것이다 — **[확인 필요]**: litestream·restic이 요구하는 정확한 env 변수명은 각 도구의 공식 문서로 확인해 확정한다(M1 백업 배선 시점). 카탈로그는 이름만 바꾸면 되는 구조이므로 스키마 변경은 발생하지 않는다.

> **[DD-04-12] 다계좌 브로커 식별자 — `KIS_ACCOUNT__<ACCOUNT_ID>` 시크릿 맵**
> - 결정: 01 §6.1의 단일 `KIS_ACCOUNT_NO`를 다계좌로 일반화해 `KIS_ACCOUNT__<ACCOUNT_ID>="<CANO>-<ACNT_PRDT_CD>"` 형식의 env 변수 집합으로 둔다(예: `KIS_ACCOUNT__GENERAL_KIS="12345678-01"`). `KIS_ACCOUNT_NO`가 단독으로 존재하면 `type == GENERAL` 계좌의 값으로 해석해 하위 호환한다. `AccountResolver`([05-broker-gateway.md](05-broker-gateway.md) §3.2)의 구현이 이 맵을 읽어 `KisAccountRef(cano, acnt_prdt_cd)`를 만든다.
> - 근거: `ACNT_PRDT_CD`는 계좌마다 다르고(01/22/29, ISA는 SP-C4 미확인 — 05 §3.2), 01 §6.3이 `CANO`·`ACNT_PRDT_CD`를 함께 마스킹 대상으로 지정했으므로 둘 다 시크릿 계층에 두는 것이 일관된다. config에 `ACNT_PRDT_CD`만 남기면 마스킹 대상 값이 git 추적 파일에 존재하게 되어 규칙이 반쪽이 된다.
> - 계획 문서와의 관계: 01 §6.1의 `.env` 목록을 다계좌로 확장. 02-domain-model.md [DD-02-3]("`account_id → 실계좌번호` 매핑은 시크릿 계층(04)과 브로커 어댑터(05)만 안다")를 구현한 형태. 충돌 없음.

**[05-broker-gateway.md](05-broker-gateway.md) §11 C2 요청("KIS 계좌상품코드를 상수 하드코딩이 아니라 설정 값으로 노출")은 이 결정으로 이미 충족된다** — `ACNT_PRDT_CD`는 코드 상수가 아니라 `KIS_ACCOUNT__<ACCOUNT_ID>` 값의 뒷부분이며, 계좌마다 다른 값을 계좌별 env 변수 하나로 준다. 계획이 확정한 22(개인연금)·29(퇴직연금) 역시 어댑터가 아니라 이 시크릿 맵에서 온다. **별도의 `accounts[].acnt_prdt_cd` config 키는 만들지 않는다** — 01 §6.3이 `ACNT_PRDT_CD`를 마스킹 대상으로 지정했으므로 git 추적 파일에 그 값을 남기면 마스킹 규칙이 반쪽이 된다(위 근거와 동일). ISA 상품코드는 SP-C4 확정 후 같은 형식으로 채운다(§14-1).

### 7.3 `Secrets` 모델

```python
# config/secrets.py
class Secrets(BaseSettings, frozen=True):
    model_config = SettingsConfigDict(env_file=(".env",), extra="ignore",
                                      case_sensitive=True, frozen=True)
    # 값은 전부 pydantic.SecretStr — repr/로그/직렬화에 원문이 나가지 않는다
    kis_app_key: SecretStr | None = None
    ...
    kis_accounts: Mapping[str, SecretStr] = {}     # account_id → "CANO-ACNT_PRDT_CD" ([DD-04-12])

    def require(self, env: ExecEnv, surface: Literal["app","litestream","tools"]) -> None:
        """CATALOG 를 돌며 required_in 에 env 가 포함된 항목의 존재를 확인.
        누락 → MissingSecrets(list[str]) — 기동 거부(FATAL_EXIT, SC-13)."""

    def assert_absent(self, names: Iterable[str]) -> None:
        """tools 컨테이너용 역방향 검사 — 있으면 즉시 종료 (§7.5)."""

    def all_values(self) -> frozenset[str]:
        """마스킹의 '값 패턴 기반' 치환 입력.
        소비자: brokers/masking.py (05-broker-gateway.md §3.7) — 값 전수 치환용."""
```

- `extra="ignore"`인 이유: `.env`에는 `OMRA__*` 오버라이드도 함께 있을 수 있으므로(§3.3) 미지 필드를 거부하면 안 된다. 반대로 `AppConfig`는 `extra="forbid"`다 — 두 모델의 정책이 다른 것이 의도다.
- **파일 권한 검증**: 로드 시 `.env` 계열 파일의 mode가 `0o600`이 아니면 warning(리눅스 한정). 01 §6.1이 chmod 600을 명시했으나 강제 수단을 정하지 않았고, 기동 거부로 만들면 개발 환경(Windows 등 권한 모델이 다른 곳)에서 기동 자체가 불가능해진다.

### 7.4 마스킹 — 두 층위를 분리한다

| 층위 | 대상 | 구현 | 소유 |
|---|---|---|---|
| **브로커 payload** | 주문 요청/응답 원문·카세트 (`CANO`·`ACNT_PRDT_CD`·`HTS_ID`·`appkey`·`appsecret`·토큰·`approval_key`) | `brokers/masking.py` — 키 이름 기반 + **값 패턴 기반**(`Secrets.all_values()` 전수 치환) | [05-broker-gateway.md](05-broker-gateway.md) §3.7 [DD-05-4] |
| **설정 덤프** | `omra config show` 출력 | `config/redact.py` | 본 문서 |

```python
# config/redact.py
def effective_dump(bundle: ConfigBundle, secrets: Secrets) -> str:
    """① AppConfig + 레코드 파일을 YAML로 덤프 (시크릿이 없으므로 원문 그대로)
       ② 'secrets' 섹션을 부가: 이름 · 존재 여부 · 앞 4자 지문 · 만료일(레지스트리) 만
       ③ 불변식 검사: SecretSpec 이름과 겹치는 AppConfig 경로가 있으면 SecretInConfigError
          — '시크릿은 YAML에 절대 넣지 않는다'(01 §6.1)를 코드가 매번 재확인한다."""
```

`omra config show` 출력 예:

```
run.env: live
band.abs: 0.05
…
secrets:
  KIS_APP_KEY:      present  fp=a3f1…  expires=2027-08-01  (tier 1, D-364)
  UPBIT_ACCESS:     present  fp=9c02…  expires=2027-02-10  (tier 1, D-192)
  SMTP_PASS:        MISSING  (required_in={live}) ← 기동 시 SC-13 실패 항목
```

지문(`fp`)은 값의 sha256 앞 4자다 — 로테이션 후 "새 키가 반영됐는가"를 값 노출 없이 확인하는 유일한 수단이며, 15분 절차(01 §6.2)의 6단계("기동 셀프체크 통과 확인")에서 쓴다.

### 7.5 자격증명 배치 검증 (SC-13 계약)

기동 셀프체크 SC-13(01-design §5.2, 분류 `FATAL_EXIT`)이 호출하는 함수를 본 문서가 제공한다.

```python
def check_credential_placement(surface: Literal["app", "tools"],
                               env: ExecEnv, secrets: Secrets) -> None:
    if surface == "app":
        secrets.require(env, "app")
        # 알림 이중화(01 §6.4): Telegram 또는 SMTP 중 최소 한 채널이 완비돼야 한다
        if not (has_telegram(secrets) or has_smtp(secrets)):
            raise MissingSecrets(["TELEGRAM_BOT_TOKEN|SMTP_*"])
    else:  # tools — 01 §1.6 "브로커 키 없음, 최소권한"
        secrets.assert_absent([s.name for s in CATALOG if s.surface == "app"
                               and s.name != "ANTHROPIC_API_KEY"])
```

**`tools`의 역방향 검사가 이 절의 핵심이다.** `app`의 `.env`를 그대로 상속하면 `labs -/-> brokers` import 계약이 프로세스 경계에서 무효화된다(01 §1.6). 검사는 "없어야 할 것이 없음"을 단정하며 실패 시 즉시 종료한다.

---

## 8. 시크릿 만료 대장과 로테이션

> **무인 운용의 최대 단일 실패점은 시장이 아니라 시크릿 만료다**(01 §6.2). 대책이 알림뿐이면 부재 중 만료 = 전면 정지이므로, **알림 사다리 + 자동 조치 + 발급일 분산** 세 겹으로 설계한다.

### 8.1 대장 내용 (정본: 01 §6.2 표)

| 시크릿 | 만료 정책 | 등급 | 자동 조치 |
|---|---|---|---|
| KIS 실전 앱키/시크릿 | 신청일 +1년, 갱신은 D-30부터만, **갱신 시 재발급** | **1급** | D-7 KIS 슬리브 `PAUSED_ALL` / D-3 전체 `SAFE_MODE` |
| 업비트 Access/Secret | 발급 +1년 강제 만료 | **1급** | D-7 업비트 슬리브 `PAUSED_ALL` / D-3 전체 `SAFE_MODE` |
| KIS 모의투자 참가 기간 | 신청 단위 | 2급 | 만료 시 `paper` 환경만 비활성(실전 무영향) |
| KIS HTS ID / `approval_key` | 유효기간 미확인(M1 W7) | 2급 | 07:00 무조건 선제 재발급 |
| `TELEGRAM_BOT_TOKEN` | 무기한 | 2급 | 발송 3회 연속 실패 → SMTP 단독 + warning |
| SMTP 자격증명 | 앱 비밀번호 정책 종속 | 2급 | 발송 3회 연속 실패 → warning |
| Litestream 스토리지 키 | 무기한 | 2급 | 백업 실패 시 critical |
| restic 저장소 자격증명 | 무기한 | 2급 | 3회 연속 실패 warning / 7일 연속 critical |
| `WEB_ADMIN_PASSWORD_HASH` | 무기한 | 3급 | — (연 1회 로테이션 권고) |
| `ANTHROPIC_API_KEY` | 무기한 | 3급 | 실패 시 리포트만 skip |
| `WEB_SESSION_SECRET` | 연 1회 로테이션 권고 | 3급 | — |
| `SAFETY_CODE_SECRET` | 무기한, 연 1회 로테이션 권고 | 3급 | — (본 문서가 추가 — [DD-04-19]) |

> **[DD-04-19] `SAFETY_CODE_SECRET`을 전용 3급 시크릿으로 등재한다**
> - 결정: [09-safety-protections.md](09-safety-protections.md) [DD-09-14]의 당일 확인코드 파생키 `SAFETY_CODE_SECRET`을 `SecretSpec` 카탈로그(§7.2)와 `secrets_registry.yaml`(§5.9)에 **3급·`expires_at: null`(무기한)·`auto_action: none`**으로 등재한다. `required_in = {live, paper}`이며 `dry_run`에서는 요구하지 않는다.
> - 근거: 09가 요청한 대로 `WEB_SESSION_SECRET` 재사용은 **채널 분리 원칙과 충돌**한다 — 웹 세션 서명키가 유출되면 Telegram 확인코드까지 동시에 위조되고, 로테이션 주기도 서로 다른 사유로 움직인다. 3급인 이유는 만료가 없고(자동 조치 대상 아님) 유실 시 영향이 "확인코드 재발급"에 그치기 때문이다. `paper`에서도 필수인 것은 `/resume`·`/kill` 계열 명령이 모드와 무관하게 코드를 요구하기 때문이다(09 §17-8).
> - 계획 문서와의 관계: 01 §6.1의 `.env` 목록에 없는 신규 시크릿이며 01 §7-2(웹 인증)와 01 §6.2(만료 대장) 양쪽의 여백을 채운다. 값이 `.env`에만 존재하고 레지스트리에는 날짜만 남는 규율은 그대로다. 충돌 없음.

### 8.2 알림 사다리 평가기

```python
# config/files/secrets_registry.py
class LadderStep(NamedTuple):
    days_before: int              # 45 / 30 / 14 / 7 / 3 / 1
    level: Literal["info", "warning", "critical"]
    daily: bool                   # D-30 부터는 매일 critical (01 §6.2)

#  days_before 값의 정본은 config `secrets.ladder_days`(§4.4)이고 아래는 그 기본값이다.
#  level·daily 열은 코드가 소유한다 — 01 §6.2·03 §7.2가 "D-30부터 매일 critical"로 고정했으므로
#  등급을 config로 낮출 수 있게 두면 사다리의 목적이 설정 한 줄로 무너진다.
LADDER: Final = (LadderStep(45, "info",     False),   # "갱신 버튼이 아직 열리지 않았다"
                 LadderStep(30, "critical", True),    # 갱신 가능
                 LadderStep(14, "critical", True),
                 LadderStep( 7, "critical", True),
                 LadderStep( 3, "critical", True),
                 LadderStep( 1, "critical", True))

@dataclass(frozen=True)
class ExpiryAssessment:
    name: str; tier: SecretTier; days_left: int
    step: LadderStep | None            # 오늘 발송해야 할 단계 (없으면 None)
    due_actions: tuple[AutoActionEffect, ...]   # 오늘 적용해야 할 자동 조치

def assess(registry: SecretsRegistryFile, today_kst: date,
           already_notified: Mapping[tuple[str, int], date]) -> list[ExpiryAssessment]:
    """1. entry.expires_at is None → 평가 대상 아님(무기한). days_left = ∞
       2. days_left = (expires_at − today_kst).days
       3. 발동 단계 = LADDER 중 days_left <= days_before 인 것의 **최소 days_before**
       4. 멱등: daily=False 단계는 (name, days_before) 조합당 1회만 발송한다.
          daily=True 단계는 하루 1회(같은 날 중복 금지 — already_notified 로 판정).
          ★ already_notified 의 복원 출처는 run_ledger 의 SYS 행이다 ([DD-04-13]).
       5. days_left < 0 (이미 만료) → critical 매일 + tier1 이면 자동 조치 유지
       6. 자동 조치: entry.auto_action 을 days_left 로 해석 (§8.3)
    """
```

**멱등 규칙이 필요한 이유**: `monitoring/`이 매일 07:00에 대장을 읽는데(01 §6.2) 재기동이 잦은 날이면 같은 알림이 여러 번 나간다. 알림 피로가 쌓이면 D-3의 critical이 무시되고, 그것이 정확히 이 사다리가 막으려는 실패다.

> **[DD-04-13] 사다리 발송 멱등 상태는 `run_ledger`의 `SYS` 네임스페이스 행으로 보관한다**
> - 결정: `(secret_name, days_before)` 조합의 발송 사실을 **`run_ledger` 한 행**으로 표현한다 — `(run_date='YYYY-MM-DD', venue='SYS', task_name='secret_expiry_alert:<secret_name>:<days_before>')`, `status='done'`, `note={"level": …, "days_left": …}`. 판정은 두 질의뿐이다:
>   - `daily=True` 단계 → **오늘의 `run_date` 행이 있는가**(하루 1회 보장)
>   - `daily=False` 단계(D-45 info) → **`run_date` 무관하게 그 `task_name` 행이 하나라도 있는가**(영구 1회 보장)
>
>   `already_notified` 맵(§8.2 `assess`의 인자)은 기동 시 이 조회로 복원한다. **03에 새 테이블을 만들지 않고, 알림 억제 테이블에도 의존하지 않는다.**
> - 근거: 시크릿 만료 알림은 일반 억제 창과 성격이 다르다 — [13-web-and-telegram.md](13-web-and-telegram.md) [DD-13-5] ①이 `SECRET_EXPIRY`의 `dedup_window`를 `None`(억제 없음)으로 둔 것은 "D-30부터 매일"이 정본이기 때문이고, 여기서 필요한 것은 억제가 아니라 **일자별·단계별 멱등**이다. 억제 상태 테이블([03-data-and-persistence.md](03-data-and-persistence.md) §3.3.17 `notification_suppression`, 정책 소유 13 [DD-13-5])은 `(subject_key, reason_key)`당 **마지막 발송 1행**만 유지하므로 "D-45 영구 1회 + D-3 매일"을 얹으려면 단계를 `reason_key`에 인코딩해야 하고, 그러면 억제 정책(13 소유)과 사다리 멱등 판정(본 문서 소유)이 같은 행을 두고 경합한다. 13 [DD-13-5]도 사다리 멱등의 소유를 본 DD로 명시했다. [12-scheduling-and-operations.md](12-scheduling-and-operations.md) [DD-12-9]가 정확히 그 요구(재시작을 견디는 일자별 카운터)를 새 DDL 없이 `run_ledger`의 `venue='SYS'`로 해결하는 패턴을 이미 확립했고, PK가 `(run_date, venue, task_name)`이므로 위 두 질의가 그대로 성립한다.
> - 계획 문서와의 관계: 01 §6.2가 사다리를 정의하고 상태 보관을 정하지 않은 여백을 채운다. 본 DD 때문에 03 DDL을 신설하지 않으며, 13 [DD-13-5]·03 [DD-03-31]의 `notification_suppression`(억제 상태 **영속**)과도 무충돌 — 억제(창)와 사다리 멱등(단계별 1회)은 다른 메커니즘이고 13 [DD-13-5]가 그 분리를 명시했다. **12에 `secret_expiry_alert:*` `task_name` 접두사의 `SYS` 예약을 요청한다**(§14-19). `JobRegistry`에 등록되지 않은 `task_name`은 catch-up 판정 대상이 아니라는 [DD-12-9]의 규칙이 그대로 적용된다.

### 8.3 자동 조치 전이

```python
@dataclass(frozen=True)
class AutoActionEffect:
    kind: Literal["sleeve_pause_all", "bot_safe_mode", "disable_paper_env",
                  "preemptive_reissue", "notify_only"]
    sleeves: tuple[SleeveId, ...] = ()
    reason: str = ""                # 상태 전이 사유 문자열 — 감사로그 state_transition 에 실린다

def effects_for(entry: SecretRegistryEntry, days_left: int) -> tuple[AutoActionEffect, ...]:
    match entry.auto_action:
        case AutoAction.PAUSE_ALL_D7_SAFE_MODE_D3:
            out = []
            if days_left <= 7: out.append(AutoActionEffect("sleeve_pause_all", entry.sleeves,
                                                           f"secret_expiry:{entry.name}"))
            if days_left <= 3: out.append(AutoActionEffect("bot_safe_mode", (),
                                                           f"secret_expiry:{entry.name}"))
            return tuple(out)
        ...
```

**계약(본 문서가 소유하는 것은 여기까지)**: 이 함수는 **효과를 계산할 뿐 상태를 바꾸지 않는다**. 실제 전이는 상태머신([09-safety-protections.md](09-safety-protections.md))이 수행하고, 잡 스케줄은 [12-scheduling-and-operations.md](12-scheduling-and-operations.md)가 등록한다. 00 §5 원칙 9(관측 계층은 결정을 만들 수 없다)의 정신을 config 계층에도 적용한 것 — 설정 모듈이 봇 상태를 직접 바꾸면 그 경로는 감사·테스트 대상 밖에 놓인다.

**해소 조건**: `secrets_registry.yaml`의 `issued_at`/`expires_at`이 갱신되어 `days_left > 7`이 되면 `sleeve_pause_all` 사유가 사라진다. `SAFE_MODE` 이탈은 03 §2.1대로 `/resume`이며 자동 복귀하지 않는다 — 로테이션 절차 8단계가 그것이다(§8.4).

**PAUSED_ALL이어야 하는 이유(계획 근거 보존)**: 03 §6.4가 "`PAUSED`(신규 매수만 중단)만으로는 매도·취소 경로가 그대로 실패해 P9-order 연속 5회에 즉시 도달했다"고 기록한다. `PAUSED_ALL`(양방향 정지) + 인증 계열 오류의 P9 카운트 면제(03 §1.4) + P9-order의 venue별 격리, 세 겹이 함께 있어야 안전망이 성립한다.

### 8.4 로테이션 절차와의 연계 (정본: 03 §6.4 / 01 §6.2)

```
소요 15분 · 장 마감 후 · 대상: KIS 실전 앱키(연 1회) / 업비트 키(연 1회)
1. 포털 로그인 → 갱신 버튼 (KIS는 D-30부터만 활성, 갱신 시 구 키 즉시 무효)
2. 새 키로 검증 호출 1건 (KIS: 잔고조회 / 업비트: 계좌조회)
3. 업비트는 VPS 고정 IP 화이트리스트 재등록 + 출금 권한 제외 재확인
4. `.env` 교체 (chmod 600 유지)                     ← §7.3 파일 권한 검증이 확인
5. docker compose up -d --force-recreate app
6. 기동 셀프체크 통과 확인 (토큰·대사·캘린더·스키마)  ← `omra config show` 의 fp 로 반영 확인(§7.4)
7. config/secrets_registry.yaml 의 발급일·만료일 갱신 → 알림 사다리 재계산 (§8.2)
8. 슬리브가 PAUSED_ALL / 전체가 SAFE_MODE 였다면 /resume <당일 확인코드>
```

7단계는 **config 변경이므로 §9의 CI 게이트를 탄다**. 다만 로테이션은 장 마감 후 긴급 작업일 수 있으므로, `secrets_registry.yaml`만 바뀐 변경은 §9.4의 **경량 경로**(스키마 + 상호 제약만, 백테스트 스냅샷 회귀 생략)를 탄다 — 만료 대장은 백테스트 산출물에 영향을 주지 않는다.

### 8.5 발급일 분산 규칙 (C-27)

01 §6.2: "KIS와 업비트의 최초 발급을 **6개월 이상 간격**으로 배치한다. 같은 달 만료는 그 달 부재가 곧 전면 정지다. **알림보다 배치가 효과적인 방어다.**"

```python
def check_issue_spacing(registry: SecretsRegistryFile, min_days: int) -> ConstraintViolation | None:
    """tier==TIER1 이고 expires_at 이 있는 항목들의 issued_at 간 최소 간격 < min_days(기본 180)
    → warning 수준 위반. **기동 거부가 아니다** — 이미 발급된 키의 날짜는 되돌릴 수 없고,
    거부하면 사용자가 대장 자체를 비워 버려 사다리 전체가 죽는다.
    산출물: '다음 로테이션 때 KIS를 N개월 뒤로 미루라'는 권고 문구."""
```

- **`/away` 겹침 경고**(01 §6.2): 부재 선언 기간과 겹치는 만료 시크릿이 있으면 즉시 경고한다. 4~5월 양도세 기간(00 §3.2 T5·T6)과 겹치는 경우도 동일. 판정 함수는 본 문서가 제공하고 호출 지점은 `/away` 명령 처리([13-web-and-telegram.md](13-web-and-telegram.md))다.

```python
def overlapping_expiries(registry: SecretsRegistryFile,
                         window: tuple[date, date]) -> tuple[SecretRegistryEntry, ...]: ...
```

---

## 9. config 변경 CI 게이트

### 9.1 트리거와 범위 (정본: 01 §6.1, 03 §4.4·§6.3, 02 §8.2)

```
트리거: config/*.yaml 변경을 포함한 PR (03 §4.4 "config 변경도 이 CI를 트리거한다")
대상  : 사람이 편집하는 입력물 config/ 하위만.
        var/policy/ 산출물은 대상이 아니다 (01 §6.1 — 매월 CI가 자기 산출물에 회귀 게이트를
        도는 모순 방지)
단계  : ① 스키마 검증        load_and_validate_config(config_dir, policy_pointer=None)
        ② 상호 제약          constraints.check_all(bundle)  ← 런타임과 동일 함수 (03 §8)
        ③ 4블록 키 화이트리스트 단정 (§9.2)
        ④ 백테스트 스냅샷 회귀 (config 포함 — 02 §8.2 backtest.gates.core)
```

### 9.2 4블록 키 화이트리스트 단정 (02 부록 A 규칙 3 + [DD-04-4])

```python
# tests/arch/test_config_keys.py (구현 소유: 16-testing-and-quality.md, 추출기는 config 패키지)
def extract_doc_keys() -> dict[str, set[str]]:
    """docs/plan 의 4블록에서 키 경로를 추출한다:
       02 부록 A  — 표의 첫 열 `키` 중 config-key 행
                     (`tax.yaml params.*` 법령값 행은 TaxParams 대조 집합으로 분리)
       03 부록 A  — YAML 코드블록의 리프 경로
       06 부록 C  — 〃
       07 부록 D  — 〃
    """

def test_no_cross_block_conflict():   ...   # ⓐ 블록 간 키 중복·불일치 0건
def test_tuning_space_subset():       ...   # ⓑ 07 §7.1 표의 키 ⊆ 합집합
def test_docs_subset_of_model():      ...   # ⓒ config-key 합집합 ⊆ AppConfig 필드 경로
def test_tax_law_docs_match_model():  ...   # tax.yaml 법령 키 == TaxParams 필드
def test_model_subset_of_docs_plus_registry(): ...  # ⓓ 모델 전용 키 = §4.4 표에 등재된 것뿐
```

**값이 아니라 키 목록을 검사한다**(02 부록 A 규칙 3). config-key 집합은 `AppConfig`에, `tax.yaml params.*` 집합은 `TaxParams`에 각각 대조한다. `labs.tuning_space`의 런타임 값은 챌린저층 착수 전까지 `[]`이므로 값 대조는 성립하지 않는다.

### 9.3 HR 키 변경의 취급

00 §3.2 P7이 hard rail로 지정한 키(`risk.level`·`goals.*`·`core.min_weight`·`satellite.total_cap`·`crypto.cap`·`max_account_value`·kill switch 임계·`band.*`·계좌별 금지자산)는 **시스템이 자동 변경할 수 없다**.

- **런타임 강제**: `AppConfig`에 HR 키를 쓰는 API가 존재하지 않는다(모델 전체가 `frozen=True`이고 config 파일 쓰기 함수가 `config/` 패키지에 없다). `labs`가 만드는 챌린저는 `tuning_space` 화이트리스트를 통과해야 하고 HR 키는 07 §7.1 제외 목록에 있다(C-20).
- **CI 강제**: PR diff에 HR 키 변경이 포함되면 라벨 `hard-rail-change`를 붙이고 리뷰 체크리스트를 요구한다. 자동 승인 파이프라인이 config를 바꾸는 이상 이 구멍은 자가 개선과 무관하게 지금 필요하다(03 §4.4).

### 9.4 경량 경로

`secrets_registry.yaml`·`external_schedules.yaml`·`external_income.yaml`·`research_open_questions.yaml`만 바뀐 PR은 ①②③만 돌고 ④(백테스트 스냅샷 회귀)를 생략한다. 네 파일은 백테스트 입력이 아니기 때문이다. 이 분기가 없으면 15분 로테이션 절차(§8.4)가 CI 대기로 30분이 된다.

---

## 10. 오류 처리 · 엣지 케이스

### 10.1 예외 계층

```python
# config/errors.py — 모두 core.exceptions.OmraError 하위 (계층 정본: 02-domain-model.md §9)
class ConfigError(OmraError): ...                 # 최상위
class ConfigSyntaxError(ConfigError): ...         # YAML 구문 — (file, line, col)
class ConfigTypeConflict(ConfigError): ...        # deep_merge 중 dict × scalar
class ConfigValidationError(ConfigError):         # 수집된 전체 오류
    violations: tuple[Violation, ...]
class ConstraintViolationError(ConfigError): ...  # §4.5 상호 제약
class UnknownOverrideError(ConfigError): ...      # OMRA__ 미지 경로
class ConfigConflictError(ConfigError): ...       # 오버레이가 run.env 를 뒤집음
class LiveConfirmationMismatch(ConfigError): ...  # 03 §5.1-2 3중 일치 실패
class MissingSecrets(ConfigError): ...            # SC-13
class SecretInConfigError(ConfigError): ...       # §7.4 불변식 위반 (개발 시점 오류)
class EffectiveVersionMissing(ConfigError): ...   # §6.2 at() 실패
class PolicyArtifactMissing(ConfigError): ...     # §6.3 DB 포인터 깨진 참조
class UnsupportedInEnvError(ConfigError): ...     # 미확정 TR ID로 live 기동 시도 (§5.10)
```

### 10.2 실패 시 안전 방향

| 상황 | 처분 | 근거 |
|---|---|---|
| 기동 시 config 스키마·상호 제약 실패 | **`FATAL_EXIT`**(프로세스 종료, 상태 기록 없음) | 01-design §5.2 SC-1 / 03 §5.1 "기동 거부". 사람이 고쳐야 하는 오류를 상태 기계로 흡수하지 않는다 |
| `RELOAD_CONFIG` 중 새 config 검증 실패 | 새 config 폐기 → **직전 유효 config로 Bot 재생성 + critical** | 01-design §6.3 [DD-01-6] |
| 직전 config마저 로드 불가(파일 훼손) | `FATAL_EXIT` | 〃 |
| `env: live`인데 `live_confirmation` 불일치 | 기동 거부 | 03 §5.1-2 |
| `env: live`인데 `tr_ids.kis.yaml`에 미확정 마커 | 기동 거부 | §5.10 (paper·dry_run은 warning) |
| `var/policy` 산출물 파일 유실(포인터는 존재) | critical + `config/` 시드로 폴백 | §6.3, 03-design [DD-03-23] |
| `targets` 없음(시드도 없음) | 콜드스타트 — γ=0 | 02 §3.3 |
| `market_weights.equity_regions`에 `null` | 직전 유효 버전 유지 | 01 §4.2 "실패 시 전월 값 유지"와 동형 |
| `tax.yaml`의 유효 버전 없음(모든 `effective_from`이 미래) | 기동 거부 | 세금 파라미터 없이 주문을 내는 경로를 만들지 않는다(02 §5.5 하드코딩 금지의 귀결) |
| `secrets_registry`에 `expires_at`이 이미 과거 | critical 매일 + tier1이면 자동 조치 유지 | 01 §6.2 |
| 발급일 분산 위반(C-27) | **warning만**, 기동 계속 | §8.5 |
| `.env` 권한 ≠ 600 | warning | §7.3 |
| `config.dry_run.yaml` 존재 | 기동 거부 | [DD-04-2] |

### 10.3 엣지 케이스

- **`day_of_month: 31` × 2월**: 전개기가 그 달 마지막 영업일로 클램프(§5.5).
- **`effective_from`이 오늘인 세법 버전 + 07:30 판정**: `at()`은 KST 날짜 비교이므로 당일부터 신 버전이 적용된다. 전일 밤 배치가 만든 계획이 당일 아침에 신 버전으로 검증되는 경우가 생기며, 이는 정상이다(01 §6.1이 "주문 제출 시각"을 기준으로 못박은 이유).
- **오버레이가 리스트를 빈 리스트로 치환**: 허용된다(리스트 치환 규칙). 다만 `alerts.critical_channels: []`는 C-21 계열 제약이 아니라 별도 검증으로 거부한다 — critical 알림 채널이 0개면 03 부록 A의 `both_channels_fail_safe_mode_days`가 의미를 잃는다.
- **`accounts`가 비어 있음**: `dry_run`에서는 허용(백테스트·스모크), `paper`·`live`에서는 C-22 위반.
- **크립토 슬리브 opt-out인데 `universe.yaml`에 crypto 종목이 있음**: 허용. `crypto.enabled: false`면 슬리브 목표가 0이고 종목은 legacy 처분 경로를 탄다(02 §4.3.0-b 5단계).

---

## 11. 검증 항목 (16이 수거)

| ID | 항목 | 방법 |
|---|---|---|
| V4-1 | 우선순위 4계층: 같은 키를 4곳에 다르게 두고 CLI > env > 오버레이 > base > 기본값 순으로 이김 | 단위 |
| V4-2 | `deep_merge`: 매핑 재귀 / **리스트는 치환** / dict × scalar → `ConfigTypeConflict` | property-based |
| V4-3 | `OMRA__` 미지 경로 → `UnknownOverrideError`(무시 아님). `OMRA__SAFEMODE__…` 오타가 잡힌다 | 단위 |
| V4-4 | env 값 JSON 파싱: `true`/`3`/`["a"]`/`null`/`"문자열"` 5형 왕복 | 단위 |
| V4-5 | 2패스 env 결정: 오버레이가 `run.env`를 뒤집으면 `ConfigConflictError` | 단위 |
| V4-6 | `extra="forbid"`: `config.yaml`에 오타 키 1개 → 기동 거부 + 오류 메시지에 키 경로 | 단위 |
| V4-7 | bundle-resident 상호 제약(C-1·C-2·C-4~C-28·C-30~C-37) 각각에 대해 위반 케이스 1개씩 → 정확히 그 ID만 보고. C-3은 DB 런타임, C-21의 시크릿 대조는 별도 경계, C-29는 폐기 | 표 기반 |
| V4-8 | `guard.oneway: false`를 YAML에 적으면 타입 오류(`Literal[True]`) | 단위 |
| V4-9 | 4블록 키 화이트리스트 ⓐⓑⓒⓓ 전부 green | 아키텍처 |
| V4-10 | `AppConfig` 모델에 `SecretSpec` 이름과 겹치는 경로 0건(`SecretInConfigError` 미발생) | 아키텍처 |
| V4-11 | `config` 패키지가 `core` 외 상위 패키지를 import하지 않음 | 아키텍처(AT-C1) |
| V4-12 | `universe.yaml` → `to_instrument()`가 02-domain-model.md §4 교차검증표 위반 조합을 전부 거부 | 표 기반 |
| V4-13 | `account_preference` 키 집합 ≠ `allowed_accounts` → 거부 | 단위 |
| V4-14 | `esc_proposal: ESC_LIQUIDATE`를 `surveillance.yaml`에 적으면 파싱 실패 | 단위 |
| V4-15 | M9 조건부: `kis_ws_market.enabled` false ↔ true 전환에서 **스키마 변경 없이** KR-09·KR-01′ 엔트리의 `active`만 뒤집힘 | 단위 |
| V4-16 | SP-C4 분기: 같은 `config.yaml`에서 `accounts[].mode`만 A/B로 바꿔 로드 → `band_for` 조회 키가 표(02 §4.3)대로 바뀜 | 스냅샷 |
| V4-17 | `VersionedFile.at()`: 경계일(effective_from 당일·전일), 미래 버전만 존재 → `EffectiveVersionMissing` | 단위 |
| V4-18 | `resolve_targets` 3분기(산출물 / 시드 / 콜드스타트) + 포인터 깨진 참조 → critical 후 시드 폴백 | 단위 |
| V4-19 | `Secrets.require`: `env=live`에서 `SMTP_PASS`·`TELEGRAM_BOT_TOKEN` 동시 부재 → `MissingSecrets` | 단위 |
| V4-20 | `tools` 서페이스: 브로커 키가 하나라도 있으면 `assert_absent` 실패(= 즉시 종료) | 통합(compose) |
| V4-21 | `effective_dump`에 시크릿 원문이 0회 등장(전 시크릿 값을 출력 문자열에서 검색) | 단위 |
| V4-22 | 사다리 `assess`: D-46/45/31/30/29/14/7/3/1/0/−1 각 날짜의 단계·멱등 판정 | 표 기반 |
| V4-23 | `effects_for`: D-8 → 효과 0건 / D-7 → `sleeve_pause_all` / D-3 → +`bot_safe_mode` / 대장 갱신 후 → 0건 | 단위 |
| V4-24 | C-27 위반은 warning이며 기동이 계속됨(거부 아님) | 단위 |
| V4-25 | `config_fingerprint`: 의미가 같고 표기가 다른 두 파일(`0.5` vs `.5`)의 `effective` 해시 동일 | 단위 |
| V4-26 | `external_schedules.yaml` 해시 변경 감지 → 재전개 트리거 신호 1회 | 통합(12와 결합) |
| V4-27 | `RELOAD_CONFIG`에 깨진 YAML 주입 → 직전 config로 운용 계속 + critical([DD-01-6]) | 통합(01과 결합) |
| V4-28 | CI 경량 경로: `secrets_registry.yaml`만 변경한 PR에서 백테스트 스냅샷 회귀가 실행되지 않음 | CI |
| V4-29 | 사다리 멱등 복원: `run_ledger` SYS 행이 있는 상태로 재기동 → 같은 날 재발송 0건, D-45 info는 `run_date`가 달라도 재발송 0건([DD-04-13]) | 통합(12와 결합) |
| V4-30 | `backtest.snapshot.*` 미설정(`None`) → C-33 위반 1건. `backtest.costs.*` 전부 0 → C-32 위반 1건 | 단위 |
| V4-31 | `band.restore_mode: destination` + `restore_rho: null` → C-31 위반. `fraction` + `restore_rho: 0.9` → 동일 ID 위반 | 단위 |
| V4-32 | `surveillance.sources.upbit_market.max_age_hours: 12`가 `max_age_trading_days` 상속보다 우선 적용됨 | 단위 |
| V4-33 | `AppConfig`에 `glide` 블록이 **존재하지 않음**이고 `goals.glide_path.floor_level`이 로드됨([DD-04-18]) | 아키텍처 |
| V4-34 | `run.env=live` + `web.public_exposed: true` → C-37 위반(기동 거부) | 단위 |
| V4-35 | `research_open_questions.yaml`: `status: RESOLVED` + `resolved_at: null` → 거부, 파일 부재 → 빈 레지스트리 | 단위 |
| V4-36 | 법령값 legacy config 경로 5개는 필드 집합에 없고 YAML은 `extra_forbidden`, `OMRA__`는 `unknown_override` exact path로 거부. `TaxParams`·seed `tax.yaml` 계약은 유지 | 표 기반 단위 |

---

## 12. 계획 문서 추적표

| 계획 조항 | 이 문서의 반영 위치 | 비고 |
|---|---|---|
| 01 §6.1 우선순위 5계층 | §3.1 | `env` 순환은 2패스로 해소 |
| 01 §6.1 pydantic-settings fail-fast·`omra config show` | §3.4·§3.5·§7.4 | |
| 01 §6.1 시크릿은 YAML 금지·`.env` 키 목록 | §7.1·§7.2 | `KIS_ACCOUNT_NO` 다계좌 확장은 [DD-04-12] |
| 01 §6.1 `.env.tools` 최소권한 | §7.2·§7.5 | SC-13 역방향 검사 |
| 01 §6.1 입력물·산출물 분리·`policy_versions` | §1.3·§6.3 | DDL은 03 소유 |
| 01 §6.1 병합 규칙(매핑 재귀·리스트 치환) | §3.2 | 레코드 파일 분리로 사고 경로 제거 |
| 01 §6.1 effective-date 기준 시각 | §6.2 | 주문 제출 시각의 KST 날짜 |
| 01 §6.1 구조화 설정 파일 3종 예시 | §5.5·§5.1·§5.9 | 예시 필드 전량 반영 |
| 01 §6.1 config CI 게이트(스키마·상호제약·스냅샷 회귀) | §9 | |
| 01 §6.2 만료 대장 표·사다리·분산 규칙·갱신 절차 | §8 전체 | |
| 01 §6.3 `config_changed` 감사 이벤트 | §3.7 | 열거는 01 §6.3 |
| 01 §6.4 워치독 트리거 초기값 | §4.4 `watchdog.*` | `interval_sec`는 [DD-04-5] |
| 01 §6.5 `litestream.yml` | §5.11 | 경로 일치만 검증 |
| 01 §7 보안(키 주입·마스킹·Telegram allowlist·업비트 출금 제외) | §7.1·§7.4·§8.4 | 채널 정책은 13 |
| 01 §2 config/ 트리 13파일 | §1.4 카탈로그 | |
| 01 §1.6 compose `env_file` 3종 | §7.2 | |
| 02 부록 A 전체(키·기본값·근거) | §4.2 블록 모델 | 규칙 1~3 준수 + [DD-04-4] 규칙 4 |
| 02 §5.5 `tax.yaml` 외부화·분리과세 키 금지 | §5.8 | 소비 모델은 10 |
| 02 §1.2 표1·표2·허용 자산 | §5.1 `universe.yaml` | 표2 승격은 [DD-10-4] |
| 02 §3.1 `market_weights` 상수/자동 분리 | §5.4 | |
| 02 §3.5 goal 4요소·glide path 구간 | §5.3 | [DD-04-8] |
| 02 §4.3 `band_for(account, mode)` 조회 키 | §4.3 `AccountCfg.mode` | 판정은 07 |
| 02 §7 크립토 고정 유니버스·vol targeting | §4.2 `CryptoCfg` + C-8 | |
| 02 §8.1 비용·체결 가정 / §8.2 게이트 | §4.2 `BacktestCfg` | [DD-04-15]. 시뮬 구현은 15 |
| 02 §9 몬테카를로·Guyton-Klinger 값 | §4.2 `McCfg`·`GkCfg` | 소비 타입 `McParams`는 07 §14.1 |
| 03 부록 A 전체 | §4.2 `protections/safe_mode/presence/tracking_error/alerts` | 접두사 `safe_mode` 정본 |
| 03 §1.2 P3 절대 상한 · P4 "1시간 내" | §4.2 `ProtectionsCfg` + §4.4 | 03 부록 A에 키가 없던 두 값 — [DD-04-17] |
| 03 §4.6 TE ⑤ 잔차 월 0.3%p | §4.2 `TrackingErrorCfg` + C-36 | R1 입력의 값 정본 |
| 03 §5.1 전환 절차(3중 일치·manual_approve) | §4.3 | |
| 03 §5.2 `max_account_value` HR | §4.3·§9.3 | |
| 03 §6.3 배포·`/reload_config`·YAML 해시 재전개 | §3.7·§6.3 | 시퀀스는 01 |
| 03 §6.4 시크릿 갱신 8단계 | §8.4 | |
| 03 §4.4 config 변경이 CI 트리거 | §9.1 | |
| 03 §8 "게이트는 CI 코드를 런타임 재사용" | §4.5 `constraints.check_all` | |
| 06 부록 C 전체 | §4.2 `ws/quote/fx/guard/realtime/surveillance` + `etf.premium_gate` | |
| 06 부록 C 말미 "등급 매핑 외부화" | §5.7 `surveillance.yaml` | [DD-04-9] |
| 06 §5.1 리스크 카탈로그 7종 / §5.2 조건부 2행 | §5.7 기본 매핑 | M9 양쪽 경로 |
| 06 §7.1 `effective_from`·`deadline_at`·소스별 `max_age` | §5.7·§4.2 `SurvSourceCfg` | |
| 06 §8.1 `ESC_*` 자동 금지 | §5.7 [DD-04-9] | |
| 07 §9 변경 예산 소비 규칙 | §4.2 `PolicyCfg` + C-2·C-4 | 소비 로직은 14 |
| 07 부록 D `research.*`·`labs.*` | §4.2 `improve.py` | |
| 07 §7.1 `tuning_space` 허용·제외 목록 | C-20·§9.2 | 런타임 + CI 이중 강제 |
| 00 §5 원칙 6(versioned YAML·하드코딩 금지) | 문서 전체 | |
| 00 §3.2 P7 hard rail 목록 | §9.3·§1.4 HR 열 | |
| 00 §3.2 E2 SP-C4 분기 | §4.3 `AccountCfg.mode` | 양쪽 경로 동일 스키마 |
| 00 §3.2 P6 `market_weights` 5%p → A3 | §5.4 `region_shift_approve_pp` | |
| 00 §3.2 O1 앱키 로테이션 | §8 전체 | |
| 00 §3.2 T2 `external_income.yaml` | §5.6 | |
| 00 §3.2 T7 세법 개정 A5 | §5.8 | diff 렌더링은 10 |

---

## 13. 설계 결정(DD) 목록

| ID | 요지 | 위치 |
|---|---|---|
| DD-04-1 | `config/` 패키지 11모듈 분해 + 단일 루트 `AppConfig`, 레코드 파일은 별도 로더 | §2 |
| DD-04-2 | `dry_run`에는 오버레이 파일이 없다. `config.dry_run.yaml` 존재 시 기동 거부 | §3.1 |
| DD-04-3 | `OMRA__` 구분자·JSON 우선 파싱·레코드 파일 비적용·**미지 경로는 기동 거부** | §3.3 |
| DD-04-4 | 키 정본 규칙 4 — `AppConfig` 필드 경로 집합 == 4블록 합집합 ∪ 등재 신규 키 (CI ⓒⓓ) | §4.1 |
| DD-04-5 | `watchdog.interval_sec` 기본 10초(임의값, M4 재캘리브레이션) | §4.4 |
| DD-04-6 | `web.session_idle_hours` 12 / `web.session_max_days` 30 (값 확정은 13, 키 등재는 본 문서) | §4.4 |
| DD-04-7 | `asset_class` 허용 어휘 14종 확정(02-domain-model.md [DD-02-4] 위임 수용) | §5.1 |
| DD-04-8 | `goals.yaml` 스키마 — goal 4요소 + `remaining_years_bands` glide path + `withdrawal` | §5.3 |
| DD-04-9 | `surveillance.yaml`의 `esc_proposal` 타입에서 `ESC_LIQUIDATE` 제거(표현 불가) | §5.7 |
| DD-04-10 | effective-date 버전은 단일 파일의 `versions:` 리스트(파일 분할 안 함) | §5.8 |
| DD-04-11 | `auto_action`을 닫힌 enum으로. tier-1은 `PAUSE_ALL_D7_SAFE_MODE_D3` 강제 | §5.9 |
| DD-04-12 | 다계좌 브로커 식별자 `KIS_ACCOUNT__<ACCOUNT_ID>="<CANO>-<ACNT_PRDT_CD>"` | §7.2 |
| DD-04-13 | 사다리 발송 멱등 상태 = `run_ledger`의 `venue='SYS'` 행(03 DDL 무변경. 억제(13/03 영속)와 사다리 멱등은 다른 메커니즘) | §8.2 |
| DD-04-14 | 06 §5.2 `KR-01′`의 config·DB 값 표기를 ASCII 토큰 `KR-01P`로 고정 | §5.7 |
| DD-04-15 | 루트 모델이 선언만 하던 `McCfg`·`GkCfg`·`TrackingErrorCfg`·`BacktestCfg`의 필드 정의 | §4.2·§4.4 |
| DD-04-16 | 운영 블록(`runtime`·`tools`·`watchdog`·`web`·`jobs`·`monitoring`·`data`·`secrets`) 필드 확정 | §4.4 |
| DD-04-17 | P3·P4 계획 여백 키 신설 — `symbol_cooldown_window_min` 60 / `daily_order_amount_abs_krw` null | §4.4 |
| DD-04-18 | glide path 파라미터는 `goals.yaml` 한 곳 — `glide.*` AppConfig 블록을 만들지 않는다 | §4.4·§5.3 |
| DD-04-19 | `SAFETY_CODE_SECRET`을 전용 3급 시크릿으로 등재(웹 세션키 재사용 배제) | §7.2·§8.1 |
| DD-04-20 | `research_open_questions.yaml` 스키마 — 파생값(`related_count_this_month`)은 파일에 두지 않는다 | §5.12 |
| DD-04-21 | [DD-10-16] 수용 — 세법 법령값은 `tax.yaml` 단일 정본, config 별칭 5개와 C-29 폐기 | §4.1·§4.2·§4.5 |

**수용한 타 문서 DD**(재정의 아님, 키 등재만): [DD-02-3](계좌 슬러그·`Account` 타입) → §4.3 / [DD-02-4](`asset_class` str + config 어휘) → §5.1 / [DD-10-4](`account_preference` 컬럼) → §5.1 / [DD-10-7](`tax.user_marginal_credit_rate`) → §4.2 / [DD-10-10](`tax.health_insurance_status`) → §4.2 / [DD-10-14](`tax.harvest_auto_enabled`) → §4.2 / [DD-06-5]·[DD-06-7](`data.providers.*`·`data.master.files`) → §4.4 / [DD-01-6](RELOAD 검증 실패 처리) → §10.2 / [DD-07-5](`universe.proxy_index_key`) → §5.1 / [DD-07-11](`band.restore_mode`·`restore_rho`) → §4.2 / [DD-07-12](`crypto.vol_scale_max_age_days`) → §4.2 / [DD-07-14](glide `floor_level` 값 3) → §5.3 / [DD-09-14](`SAFETY_CODE_SECRET`) → §7.2 / [DD-13-4](`alerts.info_immediate_max_per_day`) → §4.2 / [DD-13-13]·[DD-13-14]·[DD-13-15](`web.*`) → §4.4 / [DD-15-4](`backtest.*`) → §4.2 / [DD-12-3]·[DD-12-4]·[DD-12-6]·[DD-12-7]·[DD-12-14]·[DD-12-15](`jobs.*`·`monitoring.*`) → §4.4 / [DD-14-4](`research.inbox_root`·`report_root`) → §4.2.

특히 [DD-10-16]의 법령값/운영값 분리는 [DD-04-21]로 수용했다.

---

## 14. 미해결 항목 · 스파이크 종속

| # | 항목 | 해소 시점 | 그때까지의 처분 |
|---|---|---|---|
| 1 | **SP-C4** — 절세계좌(ISA/연금/IRP) API 주문·잔고조회 가능 여부 | M1 | `accounts[].mode`가 분기를 흡수한다. 스키마·상위 코드는 양쪽 경로에서 동일하며 바뀌는 것은 YAML 한 줄. ISA의 `ACNT_PRDT_CD`도 미확인이므로 `KIS_ACCOUNT__ISA_*` 값은 SP-C4 후 채운다 |
| 2 | **SP-C1** — 과표기준가 자동 수집 가능성 | M1 | `tax.basis_price_source: fallback`이 기본값. 성공 시 `api` 한 줄 전환 + `income_alerts.api` 집합으로 자동 교체(02 §5.3) |
| 3 | **SP-C3(b)** — 모의 도메인 WS 지원·URL·체결통보 tr_id | M1 | `tr_ids.kis.yaml`의 `ws.paper` 미확정 마커. `env: paper` 기동은 warning으로 허용, `live`는 거부(§5.10) |
| 4 | **M9 T1 계층 착수 여부**(조건부 마일스톤) | M9 게이트 | `surveillance.sources.kis_ws_market.enabled: false` + `ws.tier1_execution_window_only: true`로 비활성. 착수 시 스키마 변경 없이 플래그만 전환(V4-15) |
| 5 | `market_weights.equity_regions.weights` 실측값 | M2 최초 factsheet 적재 | `null` 허용 + 직전 유효 버전 유지(§5.4). **[확인 필요 — MSCI ACWI IMI factsheet]** |
| 6 | `protections.reconcile_tolerance_cash_krw` | M4 모의 기간 실측 | `None`(= 미설정). 03 부록 A가 `~`로 남긴 값이며 스키마도 `None`을 허용한다. 미설정 상태의 P8 판정 처분은 [09-safety-protections.md](09-safety-protections.md) 소관 |
| 7 | `band.restore_fraction` 확정값 | M2 EX-1 | 0.5(잠정). 후보 ρ ∈ {0.75, 0.875, 1.0} — 확정 시 config 1줄, HR이므로 사람이 바꾼다 |
| 8 | `guard.move_guard.*`·`guard.min_duration_sec` 임의값 | 06 §14 등재 항목 | 06 부록 C 값 그대로. 재캘리브레이션 시 config 변경 |
| 9 | KIS `approval_key` 유효기간 | M1 W7 | `secrets_registry.yaml`에 tier 2 · `PREEMPTIVE_REISSUE_DAILY`로 등재(01 §6.2 "07:00 무조건 선제 재발급") |
| 10 | KIS 실전 WS `wss://` 지원 여부 | M9 착수 시 | `tr_ids.kis.yaml`의 `ws.live.url`이 `ws://`면 잔여 리스크 등재(01 §7-10). M9 미착수 시 발생하지 않는 문제 |
| 11 | `execution.max_open_orders`·`protections.daily_order_count` 재캘리브레이션 | M4 실측 | 03 부록 A 초기값 사용 |
| 12 | ~~알림 억제 테이블의 물리 스키마~~ **해소** | — | [DD-04-13]을 재작성해 `run_ledger`의 `venue='SYS'` 행([12-scheduling-and-operations.md](12-scheduling-and-operations.md) [DD-12-9] 패턴)으로 전환했다. **본 문서 때문에 03 DDL을 신설할 필요가 없고**, 13 [DD-13-5]·03 [DD-03-31]의 `notification_suppression`(억제 상태 영속)과도 충돌하지 않는다 — 억제(창)와 사다리 멱등(단계별 1회)은 다른 메커니즘이기 때문이다. 잔여 조율은 항목 19 |
| 13 | ~~`watchdog.interval_sec` 값 충돌~~ **해소** | — | **config 키의 값 정본은 본 문서**이므로 [DD-04-5]의 **10**을 유지한다(§4.4 `WatchdogCfg`). [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §19 표의 `watchdog.*` 행이 `180 / 5000 / 3 / **10**` + "(값 정본: 04 [DD-04-5])"로 정정되어 양방향 정합이 확인됐다 |
| 14 | ~~`crypto` 김프 알림 임계의 키 이름~~ **해소** | — | **키 이름 정본은 본 문서**의 `crypto.kimchi_alert`(§4.4)이며, [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md)가 [DD-11-7]로 `kimchi_alert`(소수 비율 0.05)로 정정을 마쳤다 — 11에 `crypto.kimchi_warn`은 더 이상 존재하지 않는다 |
| 15 | ~~`tax.*`·`waterfall.*` 법령값의 `config.yaml`/`tax.yaml` 이중 정의~~ **해소** | — | [DD-10-16]과 [DD-04-21]로 법령값을 `tax.yaml TaxParams`에만 남겼다. 과거 별칭 5개는 strict 입력 거부되고 C-29는 ID 재사용 없이 폐기됐다 |
| 16 | `jobs.*`·`monitoring.*` 블록의 필드 확정 | **부분 해소** | §4.4 `schema/ops.py`에 필드를 확정했다([DD-04-16]). 잔여 ①**(해소)**: 잡별 오버라이드의 키 경로를 **`jobs.overrides.<name>.{budget_sec,enabled}`**로 확정했고(고정 필드 `planner`·`catchup`·`dep_wait`·`us_submit_lead`와 임의 잡 이름을 같은 레벨에 두면 `extra="forbid"` 스키마가 성립하지 않는다), [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §4.1 [DD-12-4]·§19 표가 그 표기로 정정을 마쳤다. 잔여 ②: `jobs.overrides.*` 기본값 표(12 §4.1)와 `monitoring.health.thresholds.*`(12 §11.1 표)는 **12가 값 정본**이라 본 문서는 매핑 타입만 갖는다. `monitoring.dms.ping_url`은 12 §13.2 **[확인 필요]** 그대로 |
| 17 | `KR-01′` vs `KR-01P` 토큰 | 11 설계서와 조율 | [DD-04-14]가 config·DB 값을 `KR-01P`로 고정했다. [11-realtime-and-surveillance.md](11-realtime-and-surveillance.md)가 프라임 표기를 그대로 쓰면 `surveillance.yaml`의 행이 매칭되지 않는다 |
| 18 | ~~`glide.floor_level` 키 경로~~ **해소** | — | [DD-04-18]이 `goals.yaml`의 `glide_path.floor_level`로 통일했고(값 3은 07 [DD-07-14] 그대로), [07-portfolio-engine.md](07-portfolio-engine.md) §13.1이 "config 키의 최종 좌표는 `goals.glide_path.floor_level`"로 정정을 마쳤다(07 §21 조율 표도 해소 표기) |
| 19 | ~~`secret_expiry_alert:*` `task_name`의 `SYS` 네임스페이스 예약~~ **해소** | — | [DD-04-13]이 `(run_date, venue='SYS', task_name='secret_expiry_alert:<secret_name>:<days_before>')`를 쓰며, [12-scheduling-and-operations.md](12-scheduling-and-operations.md) §7.4 [DD-12-9]의 `SYS` `task_name` 표에 **접두사 형태** 행이 등재되어 예약이 완료됐다(고정 이름 5개와 달리 가변 접미가 붙는 유일한 항목) |
| 20 | `research.llm.monthly_budget_usd` 금액 | 01 §8.1 확인 | **[확인 필요]** — 14 §2.3이 "용도별 월 예산"을 요구하고 01 §8.1을 값 정본으로 지목했으나 금액이 확정되지 않았다. 기본값 `0`(= 미설정, LLM 호출 금지)으로 두어 "예산을 안 정했는데 돌고 있는" 상태를 만들지 않는다. 확인 방법: 계획 01 §8.1의 LLM 비용 항목 재확인, 없으면 M10a 착수 시 사용자가 값을 넣는다 |
| 21 | `research.user_agent` 기본 문자열 | M10a 착수 | 본 문서가 둔 `omra-research/1.0 (+self-hosted; contact via operator)`는 형식만 갖춘 자리표시자다. robots.txt 게이트(14 §3)가 요구하는 연락처 표기 규약은 14 소유이며, 실제 배포 시 사용자가 교체한다 |

### 계획 문서에 대한 이견 (브리프 §1.4 — 설계로 되살리지 않고 기록만)

- 01 §6.1의 `.env` 목록은 `KIS_ACCOUNT_NO` **단수**인데, 같은 문서 §2·02 §1.2가 계좌를 5종(일반위탁·ISA·연금저축·IRP·업비트)으로 전제한다. 본 설계는 [DD-04-12]로 다계좌 확장을 선언했으나, **계획 쪽에서 단일 계좌를 의도한 것이라면(예: 실계좌번호 8자리 CANO는 하나이고 상품코드만 다름) `KIS_ACCOUNT_NO` + config의 상품코드 조합이 더 단순하다.** 다만 그 경우 `ACNT_PRDT_CD`가 git 추적 파일에 남아 01 §6.3 마스킹 대상과 어긋나므로, 본 설계는 시크릿 쪽으로 통일했다. 재판정이 필요하면 이 항목이다.
- 02 부록 A는 `canary.targets`/`canary.methodology`를, 07 부록 D는 `labs.canary.{targets_recalc, method_swap, universe_swap}`를 각각 정의해 **같은 대상이 두 경로로 존재**한다. 규칙 2에 따라 02를 정본으로 삼고 C-14로 정합성을 단정했으나, 장기적으로는 한쪽을 폐기하는 것이 옳다 — 두 표기가 남아 있는 한 CI 단정이 계속 필요하다.
