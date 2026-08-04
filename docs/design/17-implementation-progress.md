# 17. 구현 진행 관리 — 단위 분해 · 착수 순서 · 진행 상태

> **이 문서는 설계서가 아니다.** 설계 정본은 [00~16](00-design-overview.md)이고 상위 정본은 계획 [00~07](../plan/00-overview.md)이다. 이 문서가 소유하는 것은 **"무엇을 어떤 순서로 짓고, 지금 어디까지 지었는가"** 하나뿐이며, 설계 결정을 새로 내리지 않는다. 설계서와 이 문서가 어긋나면 **언제나 설계서가 이긴다**.
>
> **마일스톤 순서의 정본은 계획 [04-roadmap.md](../plan/04-roadmap.md)**다(M0 → M1 → M2 → M3 → M4 → M5 → M6 → **M9** → M7 → M8 → M10a — M9가 M7보다 먼저임에 주의). 이 문서는 그 순서 안에서 **의존성 위상정렬로 단위를 배열**한 것이다.

---

## 1. 이 문서의 규약

### 1.1 단위(unit)의 정의

| 요건 | 내용 |
|---|---|
| **크기** | 반나절~2일. 3일을 넘으면 쪼갠다 |
| **완결성** | 코드 + 테스트가 함께 완성되어야 한다. "테스트는 나중에"인 단위는 존재하지 않는다 |
| **독립 커밋 가능** | 단위 하나 = 커밋 하나. 단위가 끝나면 CI가 green이어야 한다 |
| **근거 명시** | 모든 단위는 근거 설계서 절을 갖는다. 근거 없는 단위는 만들지 않는다 |
| **DoD** | "구현했다"가 아니라 **기계로 판정 가능한 완료 조건**을 적는다 |

### 1.2 상태 기호

| 기호 | 의미 |
|---|---|
| `☐` | 미착수 |
| `◐` | 진행 중 (커밋되지 않은 작업이 있음) |
| `☑` | 완료 (코드 + 테스트 커밋됨, CI green) |
| `⊘` | 조건부 취소 (게이트 미통과로 짓지 않음 — 사유를 비고에 적는다) |
| `⏸` | 보류 (선행 스파이크·외부 확인 대기 — 사유를 비고에 적는다) |

### 1.3 단위 완료 절차 (매 단위마다 반드시 수행)

```
1. 코드 작성 + 테스트 작성
2. 로컬 게이트 통과 확인
     ruff check . && ruff format --check .
     mypy
     lint-imports
     pytest -m "unit or property or arch"          # 해당 단위가 건드린 계층까지
3. 이 문서의 해당 단위 상태를 ☐ → ☑ 로 갱신하고 "커밋" 열에 커밋 제목을 적는다
     (해시가 아니라 제목인 이유: 진행 문서와 코드가 같은 커밋에 들어가므로
      해시는 커밋 시점에 알 수 없다)
     §2.1 진행 요약표의 완료 수치도 함께 갱신한다
4. 코드 + 이 문서를 **하나의 커밋**으로 묶어 커밋 → push
     (진행 문서를 별도 커밋으로 분리하지 않는다 — 어느 커밋이 무엇을 완성했는지가 흐려진다)
```

### 1.4 커밋 메시지 규약

기존 리모트 이력(`docs: 로보어드바이저 애플리케이션 설계서 추가`)과 Conventional Commits를 결합한다.

```
<type>(<scope>): <제목 — 한국어 명령형, 50자 이내, 마침표 없음>

<본문 — 한국어, 72자 줄바꿈. 무엇을·왜를 적고 어떻게는 코드에 맡긴다>

구현 단위: <단위 ID> (<단위 제목>)
근거: <설계서 절 목록>

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

| type | 사용처 |
|---|---|
| `feat` | 새 기능·모듈 구현 |
| `fix` | 버그 수정 |
| `test` | 테스트만 추가·수정 |
| `build` | pyproject·uv.lock·Dockerfile·의존성 |
| `ci` | GitHub Actions·CI 게이트 |
| `refactor` | 동작 변경 없는 구조 개선 |
| `docs` | 문서 (이 문서 단독 갱신 포함) |
| `chore` | 그 외 잡무 |

`<scope>`는 **패키지명**을 쓴다: `core` · `config` · `persistence` · `audit` · `runtime` · `cli` · `brokers` · `data` · `calendar` · `engine` · `backtest` · `execution` · `protections` · `surveillance` · `realtime` · `scheduler` · `rpc` · `web` · `tax` · `portfolio` · `labs` · `research` · `monitoring` · `collectors` · `tests` · `docker` · `ci`.

여러 패키지에 걸치면 대표 스코프 하나만 적거나 생략한다.

### 1.5 게이트 — 단위가 아닌 것

로드맵의 마일스톤 게이트(`모의 4주 무사고`, `실전 4주 무사고` 등)는 **코드가 아니라 시간과 무사고 운용**이므로 이 문서에서 단위로 취급하지 않는다. 대신 각 마일스톤 절 머리에 **진입 게이트**와 **DoD**를 적어 두고, 코드 단위가 전부 `☑`가 되어도 게이트를 통과하기 전에는 다음 마일스톤으로 넘어가지 않는다.

### 1.6 조건부 마일스톤

- **M9(T1 실시간 집행 계층)** — 계획 04 §2 M9의 OR 2조건 중 하나도 통과하지 못하면 **짓지 않는다**. 해당 단위는 `⊘`로 마감하고 사유를 적는다. 기본 시나리오는 "짓지 않음"이다(계획 04 부록 B).
- **M8** — SP-C4 결과에 따라 범위가 3주/6주로 갈린다. 분기 확정 전까지 두 경로의 단위를 모두 등재해 두고, 확정 시 한쪽을 `⊘` 처리한다.
- **`[확인 필요]` 종속 단위** — 설계서가 외부 사실 확인으로 미룬 값에 의존하는 단위는 폴백 경로로 먼저 구현하고, 확인 후 값만 교체한다. 스캐폴드·`xfail` 테스트를 미리 두는 것이 원칙이다.

---

## 2. 진행 요약

### 2.1 마일스톤별 진행

| 마일스톤 | 스테이지 | 단위 수 | 완료 | 진행률 | 상태 |
|---|---|---:|---:|---:|---|
| **M0** 스캐폴드 (기반 계층) | S01~S08 | 54 | 8 | 15% | ◐ |
| **M1** 데이터·브로커 read-only·감시 데이터층 | S09~S17 | 47 | 0 | 0% | ☐ |
| **M2** 엔진·백테스트 | S18~S25 | 37 | 0 | 0% | ☐ |
| **M3** dry-run 라이브 루프·감시 정책층 | S26~S32 | 43 | 0 | 0% | ☐ |
| **M4** 모의 E2E·안전장치·무인성 | S33~S40 | 54 | 0 | 0% | ☐ |
| **M5** 실전 소액 | S41 | 5 | 0 | 0% | ☐ |
| **M6** 미국 확장·세금 엔진 | S42~S45 | 23 | 0 | 0% | ☐ |
| **M9** T1 실시간 집행 계층 (조건부) | S46 | 6 | 0 | 0% | ☐ |
| **M7** 암호화폐·모멘텀 위성 | S47~S48 | 11 | 0 | 0% | ☐ |
| **M8** 목표기반·리포팅·계좌 자동화 | S49~S51 | 14 | 0 | 0% | ☐ |
| **M10a** 자가 개선 — 지식 수집 | S52 | 7 | 0 | 0% | ☐ |
| *(보류)* labs 챌린저층 | S53 | 6 | 0 | — | ⏸ |
| **합계** | **53** | **307** | **8** | **2.6%** | |

> **M0의 범위에 관한 주의**: 계획 04 §2 M0이 명시적으로 열거한 것은 저장소 구조·설정 계층·TR-ID 매핑·Docker·CI·감사 로거다. 여기에 `core`·`persistence`·`runtime`을 함께 넣은 근거는 **설계 03 §4.4가 "초기 리비전 = M0에서 §3 전 테이블 + 트리거 + 전 인덱스 생성"으로 확정**했고, 설계 01 §2.4가 "전 패키지는 M0부터 빈 패키지로라도 존재해야 한다"를 요구하며, 감사 로거가 `core.ids`(ULID)·`core.money`(KST 직렬화)에 의존하기 때문이다. 즉 M0는 **"M1이 착수 가능해지는 최소 기반"**이며 로드맵의 M0 열거를 줄이거나 늘린 것이 아니다.

### 2.2 현재 작업 위치

```
▶ 현재 단위 : S02-2 (Decimal·화폐 규약 core.money)
  직전 완료 : S02-1 (예외 계층 core.errors)
  다음 단위 : S02-3 (식별자 체계 core.ids)
```

---

## 3. 착수 순서 원칙 (계획 04 §1.1 우선순위 규칙의 적용)

일정이 미끄러지면 **위에서부터 지키고 아래에서부터 자른다**. 이 문서의 단위 배열은 그 순위를 그대로 반영한다.

1. **집행 가능성 필터** (`partition_by_tradability` + 감시 최소판 2소스) — S15·S27. 자기 유발 전면 HALT 제거.
2. **`SAFE_MODE` + 브레이커 3분류 + P9 분리 + 알림 이중화** — S34~S36·S38. 상태 모델 변경은 실전 이후에 하면 훨씬 비싸다.
3. **T0 실시간 채널** — S33·S47. 게이트 없이 채택 가능한 유일한 실시간 항목.
4. **EX-1 밴드 복귀 실험 + config CI 게이트** — S25·S05-9.
5. **절세계좌 자동화** — S50 (M8, SP-C4 분기).
6. **시크릿 만료 대응** — S17. 비용 거의 0, 무인 운용 최대 단일 실패점.
7. **M10a 지식 수집** — S52. M5 실전 6개월 이후.

**전 마일스톤 공통 불변식** (순서를 틀리면 소급이 불가능한 것들):

- `partition_by_tradability`(S27)·미집행 주문 감사로그(S30)·SAFE_MODE(S35)·대사(S37)는 **전부 M5(실전 전환) 앞에 완성**한다.
- 정수 수량 변환기(S20)는 최적화와 분리된 **순수 함수**여야 한다 — 백테스트·dry-run·실전이 공유하는 것이 시뮬-실전 괴리 측정의 전제다.
- 세금 원장 **스키마**는 M4(S06)에 선반영하고 **엔진**은 M6(S43)에 짓는다.
- `experiments` 원장 테이블은 M2(S25)에 짓는다 — M7 위성 게이트 S3(DSR)의 `N` 산출에 필요해 챌린저층을 기다릴 수 없다.

---

## M0 — 스캐폴드

> **진입 게이트**: 없음 (기점)
> **DoD** (계획 04 §2 M0): `docker compose up` → 헬스체크 응답 · CI green(import-linter 포함) · 모의 앱키 토큰 발급 1회 성공 · 시크릿 만료 대장에 KIS 실전 앱키를 1급 항목으로 초기 등록

### S01 — 저장소 골격과 정적 품질 게이트

> 계약이 참조하는 모듈은 **존재해야** import-linter가 통과하므로, 전 패키지를 빈 패키지로라도 M0에서 만든다(01 §2.4).

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S01-1** | 저장소 스캐폴드·패키지 배치 | `pyproject.toml`(프로젝트·의존성·pytest 최소 부트스트랩), `uv.lock`, `.gitignore`, `README.md`, `src/omra/**/__init__.py`(45개), `tests/arch/test_scaffold.py` | `uv sync` 성공 · `import omra` 성공 · 1차 패키지 24종 + 하위 패키지 20종이 **정확히** 설계 01 §2.1 트리와 일치(누락·초과 양방향 단정) · 전 패키지가 소유 설계서를 docstring에 명시 · 최상위 잡 모듈 0건 · **90 passed** | 01 §2.1·§2.3·§2.4, 계획 01 §1.5·§2 | ☑ | `feat: 저장소 스캐폴드와 패키지 골격 구성` |
| **S01-2** | ruff·mypy 정적 게이트 구성 | `pyproject.toml`(`[tool.ruff]`·`[tool.mypy]`), `tests/arch/test_static_gates.py` | `ruff check .`·`ruff format --check .`·`mypy` green · strict 섬 15개 모듈이 16 §3.1 표와 집합 일치(V16-07) · banned-api 4종 등록 + **위반 픽스처로 TID251 실차단 실증**(V16-06) · `disallow_any_explicit`·`disallow_any_unimported` 확인 · **마크다운을 ruff 대상에서 제외**(설계서 코드 펜스가 포매터에 재작성되는 것을 차단) · **98 passed** | 16 §3.1 [DD-16-2]·§3.3 [DD-16-3]·§3.4 | ☑ | `build: ruff·mypy 정적 게이트 구성` |
| **S01-3** | import-linter 계약 C01~C15 전량 등록 | `pyproject.toml`(`[tool.importlinter]`), `src/omra/**` 스텁 33종(engine 4·brokers 2·surveillance 3·data 3·persistence 2·repos 25), `tests/arch/test_at_contract_sync.py` | **계약 19종 KEPT, 0 broken** · 계약이 참조하는 전 모듈 실재(01 §2.4) · `allow_indirect_imports`를 C04b·C05b·C07b에 적용(정당한 체인 오탐 방지 — 01 §11-1 실측 결과) · **AT-1 양방향 대조**(repos 파일 집합 ↔ 금지 열거) · **AT-7 실차단 12건 실증**(C03·C04a·C05a·C06a·C07a·C08·C09·C11~C15) · **128 passed** | 01 §8.1.1 [DD-01-7]·§8.2 [DD-01-8·15]·§8.3·§2.4, 계획 01 §2.2 | ☑ | `feat: import-linter 의존 방향 계약 전량 등록` |
| **S01-4** | pytest 하네스·결정론 픽스처 | `pyproject.toml`(`[tool.pytest.ini_options]`), `tests/conftest.py`, `tests/marks.py`, `tests/unit/test_harness.py`, `tests/**/__init__.py` | **마커 없는 테스트 0건**을 수집 후 집계로 단정(V16-02) · **디렉터리↔마커 불일치가 수집 단계 실패**(V16-01, 위반 픽스처로 실증) · 소켓 차단 + `allow_socket`는 `record`와만 조합(V16-03) · 시드 = 노드 ID blake2b 해시(순서·병렬화 무관 재현) · hypothesis 3종(`dev`/`ci` derandomize/`nightly`) · `--golden-update`가 CI에서 거부됨 · `verifies()` ID 형식 검증 · **139 passed** | 16 §2.1 [DD-16-1]·§2.3·§4.3·§11.1~§11.4 [DD-16-11] | ☑ | `test: pytest 하네스와 결정론 픽스처 구성` |
| **S01-5** | Docker 3서비스 토폴로지 | `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `config/litestream.yml`, `.env{,.litestream,.tools}.example`, `tests/arch/test_compose_topology.py` | **토폴로지 불변식 19종 스냅샷 테스트** — tools에 `omra-db` 미마운트 / litestream이 `.env.litestream`만 로드 / tools에 브로커 자격증명 부재 / 세 서비스 non-root·read_only / docker.sock 미마운트 / 배제 스택 부재 / `stop_grace_period: 40s`·`init: true` / config `:ro` / 볼륨 4종 / `latest` 태그 금지 / stdout 로테이션 50m×3 / `.env.example`에 실값 0건 · **158 passed** · `docker compose config`는 CI(J1)에서 검증 | 01 §7.1~§7.5 [DD-01-5·10·13], 계획 01 §1.6·§6.1·§6.5·§7-6 | ☑ | `build: Docker 3서비스 배포 토폴로지 구성` |
| **S01-6** | GitHub Actions CI 골격 (J1~J4·J10) | `.github/workflows/ci.yml`, `tests/arch/test_ci_workflow.py` | J1(ruff check+format+`docker compose config`)·J2(mypy)·J3(lint-imports+`-m arch`)·J4(`-m "unit or property"`, J1~J3 선행)·J10(`uv lock --check`+pip-audit) 등록 · **브로커 자격증명·`OMRA_TEST_LIVE`·`secrets.` 참조 0건**을 파싱 트리 스캔으로 단정(V16-29) · `UV_FROZEN=1`·`HYPOTHESIS_PROFILE=ci`(derandomize)·`OMRA_TEST_NETWORK=blocked` · 전 잡 타임아웃 · **미활성 J5~J9·J11의 활성화 시점 문서화 단정** · **176 passed** | 16 §10.1~§10.3 [DD-16-9]·§1.3, 계획 01 §7-7 | ☑ | `ci: GitHub Actions 파이프라인 J1~J4·J10 구성` |
| **S01-7** | 아키텍처 테스트 AST 유틸 | `tests/arch/astutil.py`, `tests/arch/test_astutil.py` | `source_modules()`(캐시)·`modules_in/except` · `find_calls`(접미사 매칭, 부분 문자열 오탐 없음) · `find_imports`(**`TYPE_CHECKING` 구분** — 타입 전용 참조는 런타임 간선이 아니다) · `public_annotations`(미어노테이션을 `""`로 기록) · `find_string_literals`(**주석·docstring 제외** — 설계 근거 주석을 위반으로 잡지 않는다) · 유틸 자체 검증 20종 · **196 passed**. AT-1·AT-7은 S01-3에서 선행 완료 | 16 §6.1·§6.3, 01 §8.3 | ☑ | `test: 아키텍처 테스트 AST 유틸 구현` |

### S02 — `core/` 기반 4종 (L0~L1 계층)

> core 내부 의존은 비순환이며 `errors` → `money`·`clock`·`tick`·`ids` → `models`·`states` → `accounts` 4단이다([DD-02-1]). 이 스테이지는 L0·L1까지다.

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S02-1** | 예외 계층 `core.errors` | `src/omra/core/errors.py`, `tests/unit/core/test_errors.py` | `OmraError`(`code`·`retryable`·`context`·`to_audit_payload`) + 트리 21종 전량 · **트리 구조 21쌍 파라미터 검증** · `code` 고유성 + 점표기 형식 · **retryable 기본값 11종 표 일치**(`BrokerUnavailable`/`BrokerRateLimited`만 True) · tenacity 술어가 **타입만으로** 판정 가능함을 계약 테스트로 고정 · `OmraError` 밖을 직접 상속한 클래스 0건(§10.2 규칙 5 기계 검사) · `PretradeRejection`의 `step`·`order_id`·`reason`·`retry_today` payload · `__all__` ↔ 실제 클래스 집합 일치 · core 내부 import 유출 0 · **248 passed**. 마스킹 필터 테스트는 `audit.masking` 구현 후 S04-1에서 결선 | 02 §10 [DD-02-12·20] | ☑ | `feat(core): 예외 계층과 retryable 규약 구현` |
| **S02-2** | Decimal·화폐 규약 `core.money` | `src/omra/core/money.py`, `tests/unit/core/test_money.py`, `tests/property/test_inv_money.py` | `Dec`가 float 입력 거부(0.1 포함) · `to_text`/`from_text` 왕복 항등 + 스케일 보존 + 지수 표기 부재(property) · `krw_floor` ROUND_DOWN 고정(음수 포함) · `qty_floor` lot_step 1·1e-8 격자 · `usd_budget`이 `V/(rate×1.005)`와 수치 일치 · `to_kst_text`/`from_kst_text` naive 거부 | 02 §5 [DD-02-9·10·15] | ☐ | |
| **S02-3** | 식별자 체계 `core.ids` | `src/omra/core/ids.py`, `tests/unit/core/test_ids.py` | `new_id()` 10⁶회 유일 + 단조(발급 순서 == 사전식 정렬) · `Market` enum 5값 · `instrument_key`/`parse_instrument_key` 왕복 항등(`KRW-BTC` 하이픈 보존, 첫 콜론 분리) · 실패 5형이 전부 `IdentifierError` | 02 §3.1~§3.2 [DD-02-1·2] | ☐ | |
| **S02-4** | 시각 추상 `core.clock` | `src/omra/core/clock.py`, `tests/unit/core/test_clock.py` | `Clock` ABC(`now_utc`·`now_kst`·`sleep_until`·`sleep_for`) · `SystemClock` 오프셋 +09:00 고정 · `SimClock` 후퇴 거부·naive 거부·벽시계 경과 ≈ 0 · `sleep_until` 과거 시각 즉시 반환 | 02 §8 [DD-02-11·21] | ☐ | |
| **S02-5** | 틱사이즈 규칙 `core.tick` | `src/omra/core/tick.py`, `tests/unit/core/test_tick.py`, `tests/property/test_inv_tick.py` | `TickRuleId` 4값 · `krx_etf_5`(5원)·`usd_penny`($0.01, <$1 거부) 확정 구현 · `krx7`·`upbit` 사다리는 **[확인 필요] 표 자리 + xfail 경계 테스트 스캐폴드** · `snap_buy(p) ≤ p ≤ snap_sell(p)` / `is_aligned(snap_*(p))` / `next_up(p) > p` / `next_down(next_up(p)) == snap_buy(p)` property · `next_up` 구간 경계 과점프 방지 · `ticks_between` 비격자 입력 거부 | 02 §6 [DD-02-7·8] | ☐ | |

### S03 — `core/` 모델·상태·계좌 (L2~L3 계층)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S03-1** | 상태 enum·제약 벡터 `core.states` | `src/omra/core/states.py`, `tests/unit/core/test_states.py` | `BotState` 6값·`SleeveState` 3값·`PresenceState` 4값이 계획 01 §3.4와 문자 단위 일치(스냅샷) · `BuyAxis` 2값 / `SellAxis` 3값 `IntEnum` 격자 순서 6조합 · `NetBuyCap`·`ConstraintVector` frozen + 항등원(None cap) 직렬화 왕복 | 02 §9 [DD-02-13] | ☐ | |
| **S03-2** | `Instrument`·주문 enum | `src/omra/core/models.py`(1차), `tests/unit/core/test_instrument.py` | `Instrument` frozen + market×currency×tick_rule×lot_step 교차 검증표 위반 조합 전수 거부 · `EQUITY_CLASSES` 상수 스냅샷 · `OrderSide` 2값·`OrderType` 6값·`OrderStatus` 8값·`OrderIntent` 11값·`PlanReason` 5값 스냅샷 · core 소스에 `CANO`·`ACNT_PRDT_CD` 문자열 부재(아키텍처 테스트) | 02 §4·§7.1~§7.2 [DD-02-4·5·6·17·19] | ☐ | |
| **S03-3** | 주문 상태 전이표·`assert_transition` | `src/omra/core/models.py`(2차), `tests/unit/core/test_transition.py` | 8×8 전이 행렬에서 02 §7.1 표의 합법 전이만 통과 · `EXPIRED_UNKNOWN → CANCELLED` 허용·`→ FILLED` 거부 · 동일 상태 갱신(멱등) 허용 · `_TERMINAL` 4값 | 02 §7.1 [DD-02-5·18] | ☐ | |
| **S03-4** | `Order`·`Fill` 모델 | `src/omra/core/models.py`(3차), `tests/unit/core/test_order_fill.py` | `Order` validator 4종(qty>0 + lot_step 격자 / limit_price 필수·금지 조합 / `is_aligned` / aware datetime) · `transition_to()` 외 status 대입 금지 아키텍처 테스트 · `filled_qty`를 필드로 두지 않음(fills 합산 파생) · `Fill` frozen·qty>0·price>0 | 02 §7.3 [DD-02-5] | ☐ | |
| **S03-5** | 계획 모델 `RebalancePlan`·`TargetWeights`·`SanityResult` | `src/omra/core/models.py`(4차), `tests/unit/core/test_plan.py` | `SanityResult` 4필드(`hrp_gap_max`·`threshold`·`passed`·`by_group`) · `TargetWeights.weights` 키가 `instrument_key` · `RebalancePlan` 불변식(모든 order의 `plan_id == self.id`) · 내용 검증은 core가 하지 않음 | 02 §7.4 [DD-02-14·16·19] | ☐ | |
| **S03-6** | 계좌·슬리브 `core.accounts` | `src/omra/core/accounts.py`, `tests/unit/core/test_accounts.py` | `Broker` 2값·`AccountType` 5값·`AccountMode` 3값·`SleeveId` 3값 · `Account.id` 슬러그 정규식 `^[a-z][a-z0-9_]{1,31}$` 검증 · `sleeve_of` (Broker 2 × Market 5) 전수 조합 표 테스트, 미정의 조합은 `IdentifierError` · 실계좌번호 필드 부재 | 02 §3.3~§3.4 [DD-02-3] | ☐ | |
| **S03-7** | core 아키텍처 테스트 (AT-8~AT-10) | `tests/arch/test_code_rules.py` | `datetime.now(`·`date.today(` 호출이 `core/clock.py` 밖에 0건 · `asyncio.sleep(` 직접 호출이 `core/clock.py`·테스트·05 제외목록 밖에 0건 · strict 섬 공개 시그니처에 `Any`·`float` 0건 · core의 옴라 내부 import 유출 0건 | 02 §8.2·§10.4, 16 §6.3 | ☐ | |

### S04 — `audit/` append-only 감사로그

> 계획 04 §2 M0이 "append-only JSONL 감사 로거 유틸(전 마일스톤 공용)"을 M0 항목으로 명시한다. 봉투·payload 스키마 정본은 03 §7이다.

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S04-1** | 마스킹 필터 `audit.masking` | `src/omra/audit/masking.py`, `tests/unit/core/test_masking.py` | `CANO`·`ACNT_PRDT_CD`·`HTS_ID`·`appkey`·`appsecret`·접근토큰 → `"***"` · 중첩 dict·list 재귀 적용 · 카세트 녹화 필터와 **같은 코드**임을 계약 테스트로 고정(두 벌 금지) | 03 §7.3, 계획 01 §6.3 | ☐ | |
| **S04-2** | 감사 봉투·payload 모델 `audit.events` | `src/omra/audit/events.py`, `tests/unit/core/test_audit_events.py` | 봉투 7필드(`schema_version`·`event_id`·`ts_kst`·`event_type`·`actor`·`correlation`·`payload`) · `event_type` 23종 레지스트리(01 §6.3의 20종 + [DD-03-35] 3종) · `GuardVerdictPayload`(`blocked_by` 8값·`counterfactual` 필수)·`CounterfactualOrder`·`OrderIoPayload`·`ReconcileWhitelistedPayload` 등 핵심 payload 모델 · `actor` 5값 | 03 §7.1~§7.2 [DD-03-25·34·35] | ☐ | |
| **S04-3** | 감사 라이터 `audit.logger` | `src/omra/audit/logger.py`, `tests/unit/core/test_audit_logger.py` | `emit()`이 ULID 반환 · 봉투 검증 → 마스킹 → write+flush+fsync 순서 · payload 타입이 `event_type` 레지스트리와 불일치 시 거부 · 월 롤오버(`{yyyy-mm}.jsonl`) 경계에서 유실 0 · 백테스트 경로 `audit/backtest/<run_id>.jsonl` 분리 · 기록 실패가 `AuditWriteError`로 전파(삼키지 않음) | 03 §7.3~§7.4 [DD-03-22·35] | ☐ | |

### S05 — `config/` 설정 로딩·시크릿

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S05-1** | 계층 병합·env 오버라이드 | `src/omra/config/errors.py`, `src/omra/config/layers.py`, `tests/unit/config/test_layers.py` | `deep_merge`(dict 재귀 / list 치환 / 타입 충돌 시 `ConfigTypeConflict`) · `OMRA__` 파서(이중 언더스코어, JSON 우선 파싱 후 문자열 폴백) · 미지 경로가 `UnknownOverrideError`로 **기동 거부** · 2패스 env 결정(오버레이가 다른 `run.env`를 적으면 `ConfigConflictError`) · `config.dry_run.yaml` 존재 시 거부 | 04 §3.1~§3.3 [DD-04-2·3] | ☐ | |
| **S05-2** | `AppConfig` 루트·실행/계좌 블록 | `src/omra/config/settings.py`, `src/omra/config/schema/run.py`, `src/omra/config/schema/accounts.py`, `tests/unit/config/test_schema_run.py` | `run.{env,live_confirmation,manual_approve,max_account_value}` · `accounts[]` 등록부(`id`·`type`·`broker`·`mode`·금지자산) · `extra="forbid"` · `env` 3값 검증 | 04 §4.3, 02 §3.3 | ☐ | |
| **S05-3** | `AppConfig` 엔진·집행·세금 블록 | `src/omra/config/schema/engine.py`, `.../execution.py`, `.../taxcfg.py`, `tests/unit/config/test_schema_engine.py` | 계획 02 부록 A의 키 전량(`risk`·`core`·`satellite`·`cash`·`bl`·`mvo`·`cov`·`sanity`·`band`·`rebalance`·`universe`·`trade`·`momentum`·`crypto`·`mc`·`gk`·`backtest`·`order`·`execution`·`etf.premium_gate`·`tax`·`waterfall`)이 모델 필드 경로로 존재 | 04 §4.2, 계획 02 부록 A | ☐ | |
| **S05-4** | `AppConfig` 안전·관측·정책·개선·운영 블록 | `src/omra/config/schema/protections.py`, `.../observe.py`, `.../policy.py`, `.../improve.py`, `.../ops.py`, `tests/unit/config/test_schema_rest.py` | 계획 03 부록 A(`protections`·`safe_mode`·`presence`·`alerts`·`tracking_error`) + 06 부록 C(`ws`·`quote`·`fx`·`guard`·`realtime`·`surveillance`·`data`) + 07 부록 D(`research`·`labs`·`policy.change_budget`·`canary`) + 01 신규 키(`watchdog.*`·`runtime.{role,fill_queue_warn}`·`tools.snapshot_max_age_h`·`monitoring`·`web`) | 04 §4.2·§4.4, 01 §11-13 | ☐ | |
| **S05-5** | 레코드형 YAML 로더 11종 | `src/omra/config/files/base.py`, `.../universe.py`, `.../targets.py`, `.../goals.py`, `.../market_weights.py`, `.../schedules.py`, `.../income.py`, `.../surveillance_map.py`, `.../trids.py`, `.../open_questions.py`, `.../secrets_registry.py`, `tests/unit/config/test_files.py` | 11종 로더가 (파일, 인덱스, 필드) 경로로 오류 보고 · **레코드 파일은 오버레이·env 오버라이드 대상이 아님**을 테스트로 고정 · `universe.yaml`의 `approved_substitutes` 1:1 페어 검증 | 04 §5.1~§5.10 [DD-04-1] | ☐ | |
| **S05-6** | effective-date 버전 파일·정책 산출물 | `src/omra/config/versioned.py`, `src/omra/config/files/taxlaw.py`, `src/omra/config/policy_output.py`, `tests/unit/config/test_versioned.py` | `VersionedFile[TaxParams]`가 `as_of` 기준 유효 버전 선택 · `config/` 시드 vs `var/policy/` 산출물 우선순위 · `bundle.with_policy(pointer)` 경로 | 04 §6.1~§6.3 | ☐ | |
| **S05-7** | 상호 제약 검증 `constraints` | `src/omra/config/constraints.py`, `tests/unit/config/test_constraints.py` | `band.abs ≤ band.class_abs` · 변경 예산 상위 캡 ≥ 하위 예산 합 · 계좌 등록부와 `universe.yaml` 금지자산 정합 등 · **런타임과 CI가 같은 함수를 호출**함을 계약 테스트로 고정 | 04 §4.5, 계획 01 §6.1 | ☐ | |
| **S05-8** | 시크릿 3분할·마스킹·SC-13 계약 | `src/omra/config/secrets.py`, `src/omra/config/redact.py`, `tests/unit/config/test_secrets.py` | `Secrets` 모델 + `SecretSpec` 카탈로그 · `.env`/`.env.litestream`/`.env.tools` 3분할 · `role=tools`에서 브로커·Telegram·SMTP 자격증명 **존재 시 실패** · `redact`가 `SecretSpec` 이름과 겹치는 config 키 발견 시 예외 | 04 §7.1~§7.5 | ☐ | |
| **S05-9** | 진입점·지문·`config validate`·J9 게이트 | `src/omra/config/__init__.py`, `src/omra/config/fingerprint.py`, `.github/workflows/ci.yml`(J9), `tests/arch/test_config_keys.py` | `load_and_validate_config`가 **전 오류를 모아** `ConfigValidationError`로 던짐(부분 기동 없음) · `ConfigFingerprint`(파일별 sha256 + 정규화 실효 해시) · J9 단정 ⓐ~ⓓ(4블록 키 중복 0 / `tuning_space` ⊆ 합집합 / 합집합 ⊆ `AppConfig` 경로 / 등재처 없는 모델 전용 키 0) · `config/**` 변경이 CI를 트리거 | 04 §3.4~§3.7·§9, 01 §2.3 [DD-01-16], 16 §10.2 | ☐ | |
| **S05-10** | `config/` 초기 YAML 세트 13종 | `config/config.yaml`, `config.live.yaml`, `config.paper.yaml`, `universe.yaml`, `targets.yaml`, `goals.yaml`, `tax.yaml`, `surveillance.yaml`, `market_weights.yaml`, `external_schedules.yaml`, `external_income.yaml`, `secrets_registry.yaml`, `tr_ids.kis.yaml`, `research_open_questions.yaml` | 13종 파일이 스키마 검증 통과 · `omra config validate` exit 0 · 잡 산출물(`var/policy/`)을 `config/`에 커밋하면 J9 실패(V16-31) | 04 §1.4·§5, 계획 01 §2·§6.1 | ☐ | |

### S06 — `persistence/` 영속 계층

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S06-1** | Decimal·시각 TypeDecorator | `src/omra/persistence/types.py`, `tests/unit/persistence/test_types.py` | `core.money`의 `to_text`/`from_text`·`to_kst_text`/`from_kst_text`를 **그대로 호출**(별도 구현 금지 계약 테스트) · `NaN`/`Inf`/지수 표기 거부 · 스케일 보존 왕복 | 03 §3.1·§4, 02 §5.2 [DD-02-10] | ☐ | |
| **S06-2** | 모델 — 핵심 6종 + 계획 확정 3종 | `src/omra/persistence/models.py`(1차), `tests/unit/persistence/test_models_core.py` | `orders`(+`intent` 컬럼)·`fills`·`positions`·`run_ledger`·`bot_state`(+`prev_state`)·`sleeve_state`·`policy_versions`·`reconcile_expectations`·`surveillance_flags`·`pending_transfers` · 계획 전재분의 컬럼 이름·타입·PK·UNIQUE·NULL 허용을 한 글자도 바꾸지 않음(대조 테스트) | 03 §3.2 [DD-03-1·2·3·26·27] | ☐ | |
| **S06-3** | 모델 — 브로커·계획·집행 상태·캘린더 | `src/omra/persistence/models.py`(2차), `tests/unit/persistence/test_models_ops.py` | `broker_tokens`·`pending_tax_events`·`rebalance_plans`·`execution_state`·`presence`·`market_holidays`·`nav_snapshots` | 03 §3.3.1~§3.3.7 | ☐ | |
| **S06-4** | 모델 — 세금 원장·승인·카나리·실험·리서치 | `src/omra/persistence/models.py`(3차), `tests/unit/persistence/test_models_ledger.py` | `tax_events`·`taxbase_snapshots`·`contribution_ledger`·`harvest_ledger`·`approval_requests`·`canary_state`·`change_budget`·`experiments`·`experiment_events`·`research_extractions` | 03 §3.3.8~§3.3.12 | ☐ | |
| **S06-5** | 모델 — 브레이커·분해·위성·미매칭·알림억제 + 트리거 | `src/omra/persistence/models.py`(4차), `tests/unit/persistence/test_models_rest.py` | `protection_state`·`protection_counters`·`portfolio_decomposition`(+`_meta`)·`satellite_state`·`unmatched_fills`·`notification_suppression` · append-only 트리거 4종이 `experiments`·`experiment_events`의 UPDATE/DELETE 차단 · 전 인덱스 생성 | 03 §3.3.13~§3.3.17·§3.4 | ☐ | |
| **S06-6** | rw 세션 `session.py` | `src/omra/persistence/session.py`, `tests/unit/persistence/test_session.py` | PRAGMA 4종(WAL·`busy_timeout=5000`·`synchronous=NORMAL`·`foreign_keys=ON`) · `write_session` 컨텍스트가 예외 시 rollback 후 재던짐 · `SQLITE_BUSY` tenacity 3회 · **모듈 좌표 `omra.persistence.session` 고정**(계약 초크포인트) | 03 §4.1, 01 §8.1 | ☐ | |
| **S06-7** | ro 세션 `ro.py` 3중 방어 | `src/omra/persistence/ro.py`, `tests/unit/persistence/test_ro.py` | URI `mode=ro` + `PRAGMA query_only=ON` + `before_flush` 훅 `RuntimeError` · ro 세션에서 INSERT 시도 시 3중 방어 각각이 독립적으로 차단됨을 실증 | 03 §4.2 [DD-03-17] | ☐ | |
| **S06-8** | repos 규약·관측 레이어 repo 5종 | `src/omra/persistence/repos/base.py`, `.../surveillance_flags.py`, `.../pending_tax_events.py`, `.../experiments.py`, `.../budget.py`, `.../research_extractions.py`, `tests/unit/persistence/test_repos_obs.py` | `TABLES: Final[frozenset[str]]` 선언 규약 · `upsert_from_poll`이 `override_*` 4컬럼을 절대 건드리지 않음 · `budget.consume`이 total·bucket 동시 증가, cap 도달 시 아무것도 소비하지 않고 `BudgetExhausted` · `research_extractions.insert_items`가 `payload_hash` UNIQUE로 INSERT OR IGNORE | 03 §4.3 | ☐ | |
| **S06-9** | 코어 repos 19종 | `src/omra/persistence/repos/{orders,fills,positions,plans,reconcile,tax_events,pending_transfers,approvals,state,tokens,run_ledger,holidays,nav_snapshots,policy_versions,decomposition,satellite,notifications,execution_state,protections}.py`, `tests/unit/persistence/test_repos_core.py` | 19개 모듈 전부 `TABLES` 선언 · §4.3 표의 다중 테이블 매핑(`state`·`tax_events`·`fills`·`budget`·`experiments`·`protections`·`decomposition`) 반영 · 함수 시그니처 첫 인자가 `Session` | 03 §4.3 [DD-03-18·37] | ☐ | |
| **S06-10** | alembic 초기 리비전·KILL 가드 | `src/omra/persistence/migrations/env.py`, `.../versions/0001_initial.py`, `alembic.ini`, `tests/unit/persistence/test_migrations.py` | `alembic upgrade head`가 §3 전 테이블 + 트리거 + 인덱스 생성 · `alembic heads` 1줄 · 모든 `downgrade()`가 `NotImplementedError` · `data/KILL` 존재 또는 `bot_state.state='STOPPED'`이면 마이그레이션 거부(테이블 부재 = 최초 기동은 허용) · `naming_convention` 고정 | 03 §4.4 [DD-03-24], 계획 01 §1.3 | ☐ | |
| **S06-11** | repo 계약 아키텍처 테스트 (검사 1~4) | `tests/arch/test_repo_contract.py` | 검사1 전 repo가 `TABLES` 선언 · 검사2 `TABLES` 서로소 · 검사3 합집합 = `models.py` 전 테이블 · 검사4 모듈 내 insert/update/delete 대상 ⊆ `TABLES`(AST) | 03 §4.3 [DD-03-18], 16 §6.2 | ☐ | |
| **S06-12** | Parquet 레이아웃·DuckDB 뷰 정의 | `src/omra/data/store.py`(레이아웃 상수), `src/omra/data/duck.py`(뷰 SQL), `tests/unit/data/test_duck_views.py` | 파티션 규약(연도·시장) 구현 · 뷰 4종 스키마 스냅샷 테스트(컬럼·타입 고정) · `v_master_asof`가 `as_of` 이후 스냅샷 미반환 · `read_only=True` 연결에서 `COPY TO`·`CREATE TABLE` 거부 | 03 §5~§6 | ☐ | |

### S07 — `runtime/`·`cli/` 조립과 기동

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S07-1** | Typer CLI 카탈로그 | `src/omra/cli/__init__.py`, `src/omra/cli/__main__.py`, `src/omra/__main__.py`, `tests/unit/core/test_cli.py` | 명령 9종(`run`·`health`·`backtest`·`report`·`plan --dry`·`config show`·`config validate`·`experiment ingest`·`research probe`) 등록 · `python -m omra.cli <cmd>` 호출 형식 · `backtest`가 app 컨테이너에서 호출되면 즉시 거부 · `--set 섹션.키=값` 오버라이드가 최상위 계층 | 01 §2.3 [DD-01-16], 계획 01 §1.6 | ☐ | |
| **S07-2** | 태스크 감독 `runtime/tasks.py` | `src/omra/runtime/tasks.py`, `tests/unit/core/test_tasks.py` | `RestartPolicy` 3값·`TaskSpec`·`TaskSupervisor`(`start_all`·`stop_all`·`snapshot`) · 모든 상시 태스크가 `start_in_states=None`(전 상태 기동) · `ALWAYS` 지수 백오프(1→2→4→…→60s) 3연속 실패 시 warning · `ESCALATE`가 Worker 종료 · WS 태스크에 `start_delay = 3.0 × 인덱스` 부여 · 태스크 카탈로그 스냅샷(9종 고정) | 01 §4.1~§4.2·§4.6 [DD-01-17] | ☐ | |
| **S07-3** | 기동 셀프체크 프레임 `runtime/selfcheck.py` | `src/omra/runtime/selfcheck.py`, `tests/unit/core/test_selfcheck.py` | `CheckClass` 4값·`SelfCheckItem`·`BootResult`·`run_selfcheck` · SC-1~SC-13 등록(미구현 항목은 명시적 스텁) · **셀프체크는 상태를 악화만 시킨다**는 원칙을 부팅 매트릭스 property 테스트로 고정 · 자기복구 사다리 (a)~(e) 배선 | 01 §5.1~§5.6 [DD-01-11] | ☐ | |
| **S07-4** | 종료 시퀀스 `runtime/shutdown.py` | `src/omra/runtime/shutdown.py`, `tests/unit/core/test_shutdown.py` | `ShutdownBudget`(30s = jobs 10 + ws 5 + drain 5) · 6단계 순서(스케줄러 pause → 잡 대기 → WS 해제·close → telegram·web 정지 → fill_queue 드레인 → audit fsync·DB close) · **상태 저장 단계 없음** · SIGTERM 수신 30초 내 exit 0 | 01 §6.1·§6.5 [DD-01-5] | ☐ | |
| **S07-5** | composition root `runtime/bot.py`·`worker.py` | `src/omra/runtime/bot.py`, `src/omra/runtime/worker.py`, `tests/unit/core/test_bot.py` | phase A~H 순서 구현 · **phase C까지 네트워크 I/O 0건**(httpx transport mock 단정) · `RELOAD_CONFIG` 20회 반복에서 태스크·소켓·파일핸들 누수 0 · 모드 3종에서 조립 그래프 동일(스냅샷) · config 검증 실패 시 직전 유효 config로 재생성 + critical · `fill_queue` 무제한 + 1,000건 초과 warning · `order_lock` → `token_lock` 순서 단정 | 01 §3.1~§3.2·§4.3·§6.3 [DD-01-1·3·6] | ☐ | |
| **S07-6** | 워치독·자발적 종료·크래시 루프 | `src/omra/monitoring/heartbeat.py`, `tests/unit/core/test_watchdog.py` | loop lag 실측 · `lag > 5000ms` 또는 `hb_age > 180s`가 3연속이면 `restart_marks.jsonl` append(fsync) 후 `os._exit(1)` · SC-3이 최근 10분 창 자발적 종료 3회 초과 시 `STOPPED` 고정 + critical | 01 §4.5 [DD-01-14]·§5.2 SC-3 | ☐ | |
| **S07-7** | 최소 `/healthz`·`health` CLI (M0 DoD) | `src/omra/web/app.py`(최소), `src/omra/web/server.py`, `src/omra/web/routers/health.py`, `src/omra/monitoring/health.py`, `tests/integration/test_healthz.py` | `docker compose up` → `python -m omra.cli health` exit 0 · `/healthz` 인증 면제 · **healthcheck는 관측 전용**(unhealthy가 재시작을 유발하지 않음)임을 compose 주석·테스트로 고정 · 항목은 heartbeat 나이·DB 쓰기까지(나머지는 M3~M4에 확장) | 01 §7.4, 12 §11, 계획 01 §6.4 | ☐ | |

### S08 — 운영 준비 (코드 외 산출물)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S08-1** | 저장소 문서·런북 자리 | `README.md`, `docs/runbook/README.md` | 기동·개발·테스트 절차가 README에 있고 실제로 재현됨 | 계획 04 §2 M0 | ☐ | |
| **S08-2** | GitHub watch 설정 (30분, 코드 불필요) | — (설정 작업, 결과를 `docs/runbook/`에 기록) | skfolio·pandas·QuantStats·KIS 공식 레포의 release 알림 수동 설정 완료 기록 | 계획 04 §2 M0, 계획 07 | ☐ | |
| **S08-3** | KIS 계좌·앱키 발급 (수동) | `config/secrets_registry.yaml`(초기 등록) | KIS 실전/모의 계좌 개설 · Open API 신청 · **통합증거금 신청** · 앱키 2세트 발급(발급일 6개월 이상 분산 규칙 적용) · 시크릿 만료 대장에 KIS 실전 앱키를 1급 항목으로 등록 · 모의 앱키 토큰 발급 1회 성공 | 계획 04 §2 M0 DoD, 계획 01 §6.2 | ☐ | |

---

## M1 — 데이터 + 브로커 read-only + 감시 데이터층 + 스파이크 8종

> **진입 게이트**: M0 DoD
> **DoD** (계획 04 §2 M1): 배치 7일 연속 무인 성공 · 실계좌 잔고 read-only 적재 · 카세트 세트 녹화 · 마스터파일 7일 연속 파싱 성공 · import-linter 계약 green · 스파이크 8종 결과 문서화(설계 반영 포함) · SP-C4 결과로 M8 범위 확정 · M1 W7 T0 의존 검증 2건 결과 문서화

### S09 — `brokers/` 게이트웨이 기반

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S09-1** | 게이트웨이 ABC·공통 이벤트 타입 | `src/omra/brokers/base.py`, `src/omra/brokers/events.py`, `tests/unit/brokers/test_base.py` | `BrokerGateway` ABC 전 메서드 시그니처 · `ExecEnv` · **dry-run 분기가 어댑터 최하단 한 곳뿐**임을 아키텍처 테스트로 고정 · venue 공통 WS 이벤트 dataclass(frozen) | 05 §2~§3, 계획 01 §3.2 | ☐ | |
| **S09-2** | 브로커 규격 검증 `_validate` | `src/omra/brokers/base.py`(2차), `tests/unit/brokers/test_validate.py` | 수량 lot_step·호가단위 `is_aligned`·주문유형×시장 조합·최소 주문금액 검증 · 위반 시 제출 전 거부(브로커 왕복 없음) | 05 §3.4, 계획 01 §3.2 | ☐ | |
| **S09-3** | 브로커 오류 분류·P9 태깅 | `src/omra/brokers/errors.py`, `tests/unit/brokers/test_errors.py` | `BrokerError` 하위 분류가 `core.errors` 계층 아래 · `BrokerAuthError`(retryable=False)·`BrokerRateLimited`(True)·`BrokerUnavailable`(True)·`OrderRejectedError`(False)·`AmbiguousOrderState`(False) · **VI·거래정지 유래 거부는 P9 카운트 제외** 태그 · tenacity 술어 계약 테스트 | 05 §3.6, 02 §10.1 | ☐ | |
| **S09-4** | 브로커 마스킹 필터 | `src/omra/brokers/masking.py`, `tests/unit/brokers/test_masking.py` | `audit/masking.py`와 **같은 코드**를 쓰는 계약 테스트(두 벌 금지) · 카세트 녹화 필터와 동일 케이스 세트 통과 | 05 §3.7, 03 §7.3 | ☐ | |
| **S09-5** | brokers 자기 제약 아키텍처 테스트 | `tests/arch/test_boundaries.py`(brokers 절) | `brokers`가 import하는 1차 패키지가 `core`·`config`·`audit`·`persistence.repos.tokens`·`persistence.session`·`calendar`뿐임을 단정 · `ws/events.py`가 `client.py`·`auth.py`를 import하지 않음 · `asyncio.sleep` 제외 목록 선언 | 05 §2, 01 §8.2 C02 [DD-01-8] | ☐ | |

### S10 — KIS 인증·레이트리밋·TR 맵

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S10-1** | TR 매핑 로더 `tr_map` | `src/omra/brokers/kis/tr_map.py`, `config/tr_ids.kis.yaml`(확장), `tests/unit/brokers/test_tr_map.py` | `TrSpec` 모델 · `rest.{live_prefix: T, paper_prefix: V}` 규칙 치환 · **`ws`는 prefix 규칙이 불성립하므로 env별 명시 테이블**(계획 01 §2) · 미등록 TR 조회 시 `ConfigError` | 05 §7.1, 계획 01 §2·§3.2 | ☐ | |
| **S10-2** | 우선순위 토큰버킷 `ratelimit` | `src/omra/brokers/kis/ratelimit.py`, `tests/unit/brokers/test_ratelimit.py`, `tests/arch/test_at_protocol.py`(AT-6) | `PriorityTokenBucket` · 실전 15 RPS·모의 2 RPS 프로파일 · **불변식 4종**을 AT-6 아키텍처 테스트로 강제 · 우선순위 역전 없음(property) | 05 §6, 계획 01 §5.2 | ☐ | |
| **S10-3** | TokenManager 접근토큰 | `src/omra/brokers/kis/auth.py`(1차), `src/omra/persistence/repos/tokens.py`(연결), `tests/unit/brokers/test_token.py` | SQLite `broker_tokens` 영속(재시작에 재발급하지 않음) · **프로세스 간 파일락** `var/db/.token.lock` · in-process `token_lock` 1회 재발급 · EGW00133 수신 시 70초 백오프 1회 · 선제 갱신(만료 전) | 05 §5, 계획 01 §5.1 | ☐ | |
| **S10-4** | approval_key 발급·캐시 | `src/omra/brokers/kis/auth.py`(2차), `tests/unit/brokers/test_approval_key.py` | `approval_key`도 `broker_tokens` 동일 저장소 관리 · 유효기간·재발급이 기존 세션에 미치는 영향은 **M1 W7 검증 항목**(S17-5)과 결선 | 05 §5, 계획 01 §5.1·04 §5.2 | ☐ | |
| **S10-5** | credential_id 단위 조립 팩토리 (SP-C5) | `src/omra/brokers/kis/__init__.py`, `tests/unit/brokers/test_credential.py` | 앱키 1개로 복수 CANO 접근이 **불가**로 판명될 경우 TokenManager·RateLimiter를 앱키 단위로 다중화할 수 있도록 `credential_id` 축을 미리 도입 · SP-C5 결과에 따라 값만 분기 | 05 §5, 01 §11-4, 계획 04 SP-C5 | ☐ | |

### S11 — KIS REST read-only

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S11-1** | `KisRestClient.call()` 단일 파이프라인 | `src/omra/brokers/kis/client.py`(1차), `tests/unit/brokers/test_kis_call.py` | 레이트리밋 → 토큰 주입 → 요청 → 오류 분류 → 재시도(tenacity) → 마스킹 감사 순서 고정 · **모든 TR이 이 함수 하나를 통과**함을 아키텍처 테스트로 고정 | 05 §7.2 | ☐ | |
| **S11-2** | 잔고 조회 TR (국내·해외) | `src/omra/brokers/kis/client.py`(2차), `tests/contract/kis/test_balance.py` | 국내·해외 잔고 TR 파싱 → 도메인 `Position` 매핑 · 계좌상품코드 분기 · 카세트 재생으로 계약 고정 | 05 §7.3, 계획 04 §2 M1 | ☐ | |
| **S11-3** | 시세·기간시세·매수가능금액 TR | `src/omra/brokers/kis/client.py`(3차), `tests/contract/kis/test_quote.py` | 현재가·기간시세·매수가능금액 TR · `intstock-multprice`(1콜 30종목) 활용 · 카세트 재생 | 05 §7.3, 계획 01 §0.1 | ☐ | |
| **S11-4** | 휴장일 TR `CTCA0903R` | `src/omra/data/providers/kis.py`(`KisHolidayFetcher`), `tests/contract/kis/test_holiday.py` | 휴장일 TR 조회 → `market_holidays` 캐시 적재 · 카세트 재생 | 06 §4.1·§10.2 | ☐ | |
| **S11-5** | `MarketDataPort` 구현·주입 | `src/omra/data/ports.py`, `src/omra/brokers/kis/client.py`(4차), `tests/unit/data/test_ports.py` | `KisMarketDataPort` Protocol 구현 · `data → brokers`가 Port로만 좁혀짐(C08 계약과 정합) | 06 §4.4, 01 §8.2 C08 | ☐ | |

### S12 — `data/` TET Fetcher 계층

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S12-1** | 표준 데이터모델 7종 | `src/omra/data/models.py`, `tests/unit/data/test_models.py` | OHLCV·Quote·FxRate·EtfNav·MasterRow·Holiday·StockInfo 등 표준 모델(Pydantic) · 전 provider가 같은 모델로 수렴 | 06 §3.2 | ☐ | |
| **S12-2** | Fetcher ABC·FetchResult·예외 | `src/omra/data/fetcher.py`, `tests/unit/data/test_fetcher.py` | TET(Transform-Extract-Transform) 3단 · `FetchResult` 응답 봉투(results/provider/warnings) · `ProviderError`·`StaleDataError`가 `DataError` 하위 | 06 §3, 02 §10.1 | ☐ | |
| **S12-3** | ProviderRegistry·헬스·라우팅 | `src/omra/data/registry.py`, `tests/unit/data/test_registry.py` | 선언적 provider 매핑 + 시장 인지형 라우팅 · 폴백 사다리 · `ProviderHealth` · 라우팅 테이블 커버리지를 기동 셀프체크가 검사 | 06 §4~§4.3 | ☐ | |
| **S12-4** | FDR·pykrx 일봉 fetcher | `src/omra/data/providers/fdr.py`, `.../pykrx_provider.py`, `tests/contract/data/test_ohlcv.py` | KRX·US 일봉 · **pykrx는 야간 저빈도 전용, 요청당 1초 지연** · 카세트 재생 | 06 §4.1, 계획 01 §1.5 | ☐ | |
| **S12-5** | KIS 시세·ETF NAV fetcher | `src/omra/data/providers/kis.py`, `tests/contract/data/test_kis_quote.py` | `KisQuoteFetcher`·`KisOverseasQuoteFetcher`·`KisFxFetcher` · `KisEtfNavFetcher`는 **[확인 필요]** — REST 스냅샷 경로 기본 | 06 §4.1 | ☐ | |
| **S12-6** | `QuoteService` — realtime의 유일한 REST 경유로 | `src/omra/data/quote.py`, `tests/unit/data/test_quote.py` | 호가 나이(`quote.max_age_ms`) 검사 · `realtime → data.quote`만 허용(C06a 계약과 정합)임을 아키텍처 테스트로 고정 | 06 §6, 01 §8.2 C06a | ☐ | |
| **S12-7** | `ParquetStore` 원자적 쓰기·PIT 읽기 | `src/omra/data/store.py`, `tests/unit/data/test_store.py` | 연도·시장 파티션 · 임시파일 → rename 원자적 쓰기 · point-in-time 읽기(`as_of` 이후 데이터 미반환) | 06 §7, 03 §5 | ☐ | |
| **S12-8** | 데이터 품질 체크 3판정 | `src/omra/data/store.py`(2차), `tests/unit/data/test_quality.py` | 결측·중복·수정주가 점프 3판정 · 실패해도 **거래를 차단하지 않고 전일 캐시 사용** | 06 §7, 계획 01 §4.2 | ☐ | |

### S13 — `calendar/` 거래 캘린더·세션·결제일

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S13-1** | `TradingCalendar` — XKRX/XNYS·거래일 산술 | `src/omra/calendar/trading.py`, `tests/unit/calendar/test_trading.py` | `exchange_calendars` 기반 · 거래일 가감산·`run_date`(venue 현지 거래일) 산출 · 미국 잡은 **고정 cron이 아니라 캘린더가 계산한 UTC 시각으로 매일 동적 등록** | 06 §10, 계획 01 §4.1 | ☐ | |
| **S13-2** | 휴장일 캐시·KIS 교차검증 | `src/omra/calendar/crosscheck.py`, `src/omra/persistence/repos/holidays.py`(연결), `tests/unit/calendar/test_crosscheck.py` | XKRX 1차 + `CTCA0903R` 교차검증 · **불일치 시 그날 국내 집행 중단 + critical**(fail-safe) · 미국은 XNYS 단독(잔여 리스크 브리핑 표기) | 06 §10.2, 계획 01 §4.1 | ☐ | |
| **S13-3** | 세션 상태머신·`execution_blocked` | `src/omra/calendar/sessions.py`, `tests/unit/calendar/test_sessions.py` | 세션 상태 전이(PRE/OPEN/CLOSE/POST/CLOSED) · 집행 창 판정 · 반일장은 XNYS 세션 시각을 그대로 따름 | 06 §11 | ☐ | |
| **S13-4** | `SettlementCalculator` 결제일·D\* 역산 | `src/omra/calendar/settlement.py`, `tests/unit/calendar/test_settlement.py` | 국내 T+2 예수금·미국 T+1(+국내 휴장일) · 연말 세금 마감일 D\* 역산 · 하베스팅 D\*−2 산출 | 06 §12, 계획 01 §4.1 | ☐ | |

### S14 — 야간 배치·종목마스터

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S14-1** | `KisMasterFetcher` — `.mst.zip` 파싱 | `src/omra/data/master.py`(1차), `tests/contract/data/test_master.py` | `kospi/kosdaq/konex_code.mst.zip` **무인증** 다운로드 · 고정폭 파싱 → 전종목 플래그(거래정지·관리종목·시장경고·불성실공시·정리매매·단기과열·공매도과열·ETP 유형) · 플래그 인코딩은 **SP-A2 [확인 필요]** — 미관측 필드는 `unknown` | 06 §8, 계획 04 §2 M1 추가① | ☐ | |
| **S14-2** | `MasterService` PIT 스냅샷 | `src/omra/data/master.py`(2차), `tests/unit/data/test_master_pit.py` | 일자별 스냅샷을 Parquet에 적재 · `as_of` 조회가 미래 스냅샷을 반환하지 않음 · `max_age`(잠정 2거래일) 유예 | 06 §8, 03 §5 | ☐ | |
| **S14-3** | `MasterDiff` — corporate action 감지 | `src/omra/data/master.py`(3차), `tests/unit/data/test_master_diff.py` | 전일 대비 diff로 분할/병합·코드 변경 감지 → 대사 화이트리스트 등록 입력 산출(등록은 M4 S37) | 06 §8, 계획 01 §4.2 | ☐ | |
| **S14-4** | `nightly_data_batch` 잡 본체 | `src/omra/data/jobs.py` 또는 `src/omra/scheduler/`(잡 등록은 M3), `tests/integration/test_nightly_batch.py` | 02:00 배치: 일봉·시총·종목마스터 → Parquet · 실패해도 거래 차단 없음(전일 캐시) · **7일 연속 무인 성공**이 M1 DoD | 계획 01 §4.2, 04 §2 M1 DoD | ☐ | |

### S15 — 감시 데이터층 (착수 순서 1위의 전반부)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S15-1** | `collectors/` 중립 수집 프레임워크 | `src/omra/collectors/http.py`, `.../robots.py`, `.../dedup.py`, `tests/unit/collectors/test_http.py` | 조건부 요청(ETag/If-Modified-Since)·캐시·백오프 · `robots.txt` Disallow **하드 차단** · `payload_hash` dedup · **C03 계약**(core·audit 외 전부 금지) green | 14 §2.1, 01 §8.2 C03 | ☐ | |
| **S15-2** | 감시 모델·예외·포트 골격 | `src/omra/surveillance/models.py`, `.../errors.py`, `.../ports.py`, `tests/unit/surveillance/test_models.py` | `FlagObservation`·`SourceResult`·`Reason`·`EscalationProposal` · `TradabilityBlocked`(`DomainError` 하위) · 금지 패키지(`calendar`·`tax`·`protections`)를 `ports.py` Protocol 주입으로 대체 | 11 §2.1·§8.2 [DD-11-13·18] | ☐ | |
| **S15-3** | 감시 소비 REST fetcher (국내 3종) | `src/omra/data/providers/kis_surv.py`, `tests/contract/data/test_kis_surv.py` | `KisStockInfoFetcher`(CTPF1002R — `tr_stop_yn`·`admn_item_yn`·`etf_etn_ivst_heed_item_yn`·`lstg_abol_dt`·`etf_txtn_type_cd`) · `KisKsdInfoFetcher`(`ksdinfo_*` 예탁원 사전 캘린더) · 카세트 재생 · **SP-A1 [확인 필요]** — ETF에 플래그가 실제로 채워지는가 | 06 §4.1, 11 [DD-11-10], 계획 04 §2 M1 | ☐ | |
| **S15-4** | 감시 소스 어댑터 3종 | `src/omra/surveillance/sources/kis_master.py`, `.../kis_stock_info.py`, `.../kis_ksdinfo.py`, `tests/unit/surveillance/test_sources.py` | KR-01(거래정지)·KR-02(관리종목)·KR-03(ETF/ETN 투자유의)·KR-04(상장폐지 예정)·KR-12(CA 매매거래정지 예정) 5항목 산출 · **결정론 구조 파서만**(정규식 + Pydantic, LLM 금지) | 11 §2.1, 계획 04 §2 M1 감시 카탈로그 | ☐ | |
| **S15-5** | `poll.py` — 감시 폴 진입점·합산 예산 | `src/omra/surveillance/poll.py`, `tests/unit/surveillance/test_poll.py` | 폴 진입점 5종 · `surv_daily_poll`+`surv_overseas_poll`+`surv_ksdinfo` **3개 합산 타임아웃 300초** · 0건 의심 판정 · 미완료 종목은 `unknown` | 11 §8.4·§13.2 [DD-11-19], 계획 01 §4.3 | ☐ | |

### S16 — record-replay 카세트 인프라

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S16-1** | 카세트 포맷·매칭기 | `tests/contract/cassette.py`, `tests/unit/core/test_cassette_format.py` | 포맷·직렬화·요청 매칭 규칙 확정 · 카세트 파일이 git 관리 대상 | 16 §5.1 | ☐ | |
| **S16-2** | 녹화기 `RecordingTransport` | `tests/contract/record.py` | `record` 마커 + `OMRA_TEST_LIVE=1` 없으면 **무조건 skip**(V16-03) · 녹화 시 마스킹 필터 적용 | 16 §5.2·§5.7 | ☐ | |
| **S16-3** | 재생기 `ReplayTransport`·`ReplaySocket` | `tests/contract/replay.py` | httpx transport·WS 소켓 재생 · 카세트 미스 시 명시적 실패(네트워크 폴백 금지) | 16 §5.3 | ☐ | |
| **S16-4** | 카세트 비밀 유출 방어·최초 세트 녹화 | `tests/cassettes/**`, `.github/workflows/ci.yml`(J5·J10 시크릿 스캔) | 카세트에 실키·실계좌번호 패턴 0건(정적 스캔) · M1 대상 TR 카세트 세트 녹화 완료 · J5(contract) green | 16 §5.5·§5.7·§10.2 | ☐ | |

### S17 — 시크릿 만료 대응·런북·스파이크 8종

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S17-1** | 시크릿 만료 사다리 평가기 | `src/omra/monitoring/secrets_watch.py`, `tests/unit/monitoring/test_secrets_watch.py` | 알림 사다리 D-45/D-30/D-14/D-7/D-3/D-1 구현(**자동 조치는 M4**) · 만료 대장 스키마 소비 · 발급일 6개월 이상 분산 규칙 검증 | 12 §14, 04 §8.1~§8.2, 계획 01 §6.2 | ☐ | |
| **S17-2** | 로테이션 런북 | `docs/runbook/secret-rotation.md` | 포털 갱신 → 새 키 검증 호출 → `.env` 교체 → `docker compose up -d --force-recreate app` → 기동 셀프체크 통과 → 대장 갱신 · **소요 15분, 장 마감 후 수행** 명시 | 계획 04 §2 M1 추가② | ☐ | |
| **S17-3** | SP-C4 런북·실행 (최상 등급) | `docs/runbook/spike-c4.md`, `docs/spikes/sp-c4-result.md` | 실행 조건 4개(장중 수동 실행·60초 상한·MTS 수동 취소 폴백·예수금 최소화) 명시 · `ACNT_PRDT_CD` 22/29/ISA로 ①잔고조회 ②퇴직연금 매수가능조회 ③현재가 −30% 지정가 1주 → 미체결 확인 → **즉시 취소** · **결과로 M8 범위(3주/6주) 확정** | 계획 04 §2 M1 SP-C4·§5.1 | ☐ | |
| **S17-4** | 스파이크 SP-C1·C3·A1·A2 실행·문서화 | `docs/spikes/sp-c1.md`, `sp-c3.md`, `sp-a1.md`, `sp-a2.md` + 설계서 반영 diff | 각 스파이크 산출물이 **"설계 반영 문서 diff"**여야 한다 · SP-C3 LOC/MOO/LOO 지원 여부 → 미국 기본 경로 확정 · SP-A1·A2 둘 다 실패 시 감시 데이터층을 M3로 미루는 대체 경로 판정 | 계획 04 §2 M1 스파이크 표·§5.1 | ☐ | |
| **S17-5** | 스파이크 SP-C5·B14·E2 + M1 W7 T0 검증 2건 | `docs/spikes/sp-c5.md`, `sp-b14.md`, `sp-e2.md`, `sp-b3.md`, `approval-key-lifetime.md` | SP-C5(앱키당 복수 CANO) → TokenManager 다중화 여부 · SP-B14(앱키 만료일 API 조회) → 대장 수동/자동 확정 · SP-E2(`H0STNAV0`) → M9 게이트 절반 · `approval_key` 유효기간·재발급 영향 + SP-B3(앱키당 동시 WS 세션 수) | 계획 04 §2 M1·§5.2 | ☐ | |
| **S17-6** | 아키텍처 테스트 AT-2~AT-7 | `tests/arch/test_at_protocol.py`, `tests/arch/test_at_contract_sync.py`(확장) | AT-2 persist-then-submit 호출 순서 · AT-3 `guard.oneway` sides 축소만(property) · AT-4 `MarketStatus`가 `realtime.guards` 시그니처에서 배제 · AT-5 catch-up 커버리지 · AT-6 RateLimiter 불변식 · AT-7 계약 실차단 실증 | 01 §8.3, 16 §6.1 | ☐ | |
| **S17-7** | 백업·복구 절차·restore drill | `scripts/backup_restic.sh`, `scripts/restore_drill.sh`, `docs/runbook/restore-drill.md`, `src/omra/monitoring/backups.py` | Litestream 복제 관측 · restic 증분(감사로그 5분 / Parquet 일 1회) · 복구 리허설 스크립트가 **실제로 복원 성공**을 1회 실증 | 03 §8, 12 §16.4·§17.3, 계획 01 §6.5 | ☐ | |

---

## M2 — 포트폴리오 엔진 + 백테스트

> **진입 게이트**: M1 DoD
> **DoD** (계획 04 §2 M2): 기준 전략이 10년 백테스트에서 코어 게이트 통과 + lookahead 0건 + WF에서 in-sample 대비 붕괴 없음 + **EX-1 판정 완료** + config CI 게이트 green + 10년 백테스트 1회 실행 시간 VPS 실측 + 밴드 트리거 1회당 회전율 분포 산출 → P11 이월 상한 재설정 + 축소 유니버스(N=5)에서 레벨 5·6·7 제약 실행 가능성 확인
>
> ⚠ **이 로드맵 최대의 단일 리스크**(계획 04 §4.4-2). **범위를 지켜라** — 기준 전략 1개가 게이트를 통과하면 즉시 M3로 간다. 엔진 고도화(Gerber·vine copula·Schur)는 전부 M10 이후다.

### S18 — `engine/` 기반 계층

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S18-1** | 공개 타입·순수성 계약 | `src/omra/engine/types.py`, `tests/unit/engine/test_types.py`, `tests/arch/test_boundaries.py`(engine 절) | 입력 스냅샷·산출 타입이 이 패키지의 **유일한 공개 어휘** · 순수성 계약 5개(I/O 금지 / Clock 주입 금지·`as_of` 인자 / `numpy.random.Generator` 주입 / 같은 입력→같은 출력 / `core.errors`만 던짐)를 아키텍처 테스트로 강제 · `EngineError` 하위 9종 정의 | 07 §2.2~§3 [DD-07-1], 02 §10.1 [DD-02-20] | ☐ | |
| **S18-2** | Decimal↔float64 경계 `numerics` | `src/omra/engine/numerics.py`, `tests/unit/engine/test_numerics.py` | 경계 변환·양자화·`inputs_hash` 산출 · **내부 수치는 float64, 공개 산출은 Decimal**(mypy strict 섬 규율) · 같은 입력의 `inputs_hash` 결정론 | 07 §3.3, 16 §3.1 | ☐ | |
| **S18-3** | 외부 솔버 어댑터 `solvers` | `src/omra/engine/solvers.py`, `tests/unit/engine/test_solvers.py` | skfolio/CVXPY 격리 지점 · 솔버 결과가 도메인 타입으로 변환된 뒤 strict 섬으로 진입 · 솔버 결정론(시드·tolerance 고정) | 07 §6.5, 16 §3.1 | ☐ | |

### S19 — 기대수익·공분산

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S19-1** | Σ_strategic — Ledoit-Wolf | `src/omra/engine/covariance.py`, `tests/unit/engine/test_covariance.py` | 수익률행렬 구성(룩백 756영업일) + LW 상수상관 축소 · PSD 보장 · `NotPositiveSemiDefiniteError`·`SingularMatrixError`·`InsufficientDataError` 경로 | 07 §5.2, 계획 02 §3.2 | ☐ | |
| **S19-2** | Σ_monitor — EWMA (계약 C10 격리) | `src/omra/engine/covariance_monitor.py`, `tests/arch/test_boundaries.py`(C10) | EWMA(λ=0.94, 60일) 실현변동성 · **`optimizer`·`rebalancer`·`expected_returns`가 이 모듈을 import하면 CI 실패**(C10 실차단 실증) | 07 §5.3, 01 §8.2 C10 [DD-01-9], 계획 02 §3.2 | ☐ | |
| **S19-3** | 역최적화 균형수익률 Π | `src/omra/engine/expected_returns.py`(1차), `tests/unit/engine/test_equilibrium.py` | `market_weights` 기반 역최적화 Π 산출 · **표본평균 기대수익 경로를 만들지 않음**(계획 02 §3.1-5)을 아키텍처 테스트로 고정 | 07 §4, 계획 02 §3.1 | ☐ | |
| **S19-4** | Black-Litterman posterior | `src/omra/engine/expected_returns.py`(2차), `tests/unit/engine/test_bl.py` | BL posterior · view 개수·형식 검증(`ViewLimitError`·`ViewSpecError`) · view 부재 시 Π로 축퇴 | 07 §4, 계획 02 §3.1 | ☐ | |

### S20 — 최적화·정수 수량화

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S20-1** | 제약 MVO 연속 최적화 코어 | `src/omra/engine/optimizer.py`(1차), `tests/unit/engine/test_optimizer.py` | 제약(자산 상한 `mvo.asset_cap`·자산군 상한·`core.min_weight`) + 턴오버 L1 페널티 · `InfeasibleError` 경로 · **축소 유니버스 N=5에서 레벨 5·6·7 실행 가능성 확인**(M2 DoD) | 07 §6, 계획 02 §3.3 | ☐ | |
| **S20-2** | `lambda_risk` 캘리브레이션·폴백 사다리 | `src/omra/engine/optimizer.py`(2차), `tests/unit/engine/test_lambda.py` | 리스크 레벨 → `lambda_risk` 캘리브레이션 · 해 없음 시 폴백 사다리(제약 완화 순서 고정) · 완화 사실이 산출 메타에 남음 | 07 §6, 계획 02 §3.3 | ☐ | |
| **S20-3** | `quantize_full` 전체 정수화 | `src/omra/engine/quantize.py`(1차), `tests/unit/engine/test_quantize_full.py`, `tests/property/test_inv_quantize.py` | **순수 함수** — 백테스트·dry-run·실전 공유 · floor + `lot_step` 격자 + `fx_buffer` 0.005 + `T_min` · `cash.buffer` 준수 · property: 산출 수량 합의 평가액 ≤ 가용 현금 | 07 §7, 계획 02 §3.3 | ☐ | |
| **S20-4** | `quantize_partial` 부분 정수화·`plan_origins` | `src/omra/engine/quantize.py`(2차), `tests/unit/engine/test_quantize_partial.py` | 부분 정수화가 `origins=plan_origins`를 받아 **출처 태그를 draft까지 전달**(00 §4.2가 계약 테스트로 고정한 배선) · `TARGET_SHIFT` 태그 소실 없음 | 07 §7·§21.1, 00 §4.2, 02 §7.2 | ☐ | |

### S21 — sanity·축소·밴드·리밸런서

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S21-1** | HRP sanity check·Schur 진단 | `src/omra/engine/sanity.py`, `tests/unit/engine/test_sanity.py` | HRP 병렬 계산 → `hrp_gap_max = max |w_MVO,i/W_g − w_HRP,i/W_g|` · `SanityResult` 4필드 산출 · 임계 기본 20%p는 config에서 · Schur 진단은 **기록만** | 07 §9, 02 §7.4 [DD-02-16], 계획 02 §3.4 | ☐ | |
| **S21-2** | 소액 계좌 유니버스 축소·복원 (P4b) | `src/omra/engine/shrink.py`, `tests/unit/engine/test_shrink.py` | NAV < 3,000만 → 5종 / NAV ≥ 4,000만 → 복원 · 히스테리시스로 진동 방지 · 판정 월 1회 · **변경 예산 미소비** | 07 §8, 계획 02 §3.3.1, 00 §3.2 P4b | ☐ | |
| **S21-3** | 밴드 조회·복귀 규칙 스위치 | `src/omra/engine/bands.py`, `tests/unit/engine/test_bands.py` | `band_for(계좌, 모드, 슬리브)` 4행 + 크립토 행 조회 · 복귀 규칙(`fraction` 현행 50% / `destination` ρ 후보)을 **config 스위치로 양쪽 구현** — EX-1 판정 전 확정 금지 | 07 §10.4·§10.9, 계획 02 §4.3, 04 부록 B | ☐ | |
| **S21-4** | `plan_daily` 골격·재정규화·`frozen_reserve` | `src/omra/engine/rebalancer.py`(1차), `tests/unit/engine/test_plan_daily.py` | 진입부에서 tradability 마스크 **주입**(gate 직접 호출 금지 — C05a 계약) · `SV3` 자산을 분모에 남기되 조정 대상 제외 → 재정규화 · `frozen_reserve`는 **가상 예약(notional)이지 현금이 아님**을 타입으로 구분 | 07 §10·§10.5, 계획 02 §4.2, 03 §2.3 | ☐ | |
| **S21-5** | 개별 밴드 breach·쿨다운·`TARGET_SHIFT` | `src/omra/engine/rebalancer.py`(2차), `tests/unit/engine/test_band_breach.py` | 상대 25%·절대 5%p 판정 · 쿨다운 5거래일 · **`TARGET_SHIFT`를 밴드 복귀로 접지 않고 독립 보존**([DD-07-19]) — SAFE_MODE 매도 차단의 판별 기호 | 07 §10 [DD-07-19], 00 §4.2 | ☐ | |
| **S21-6** | 자산군 밴드·동결 우회 차단 | `src/omra/engine/rebalancer.py`(3차), `tests/unit/engine/test_class_band.py` | 자산군 합계 밴드 판정 → `CLASS_BAND` 레그 분해 · 동결 자산을 우회해 자산군 밴드를 억지로 맞추는 경로 차단 | 07 §10, 계획 02 §4.3 | ☐ | |
| **S21-7** | cash-flow first·계획 조립·불변식 I1~I8 | `src/omra/engine/rebalancer.py`(4차), `tests/unit/engine/test_cashflow.py`, `tests/property/test_inv_plan.py` | 배당·분배금·매도대금 물채우기 배분(목표비중 불변) · `RebalancePlan` 조립 + `plan_origins` · 불변식 I1~I8 property 테스트 · **`SV3` 자산에 대한 주문 0건** | 07 §10, 계획 02 §4.2 | ☐ | |

### S22 — 유니버스 필터

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S22-1** | hard 필터 0~2단계·HOLD 판정 | `src/omra/engine/universe.py`(1차), `tests/unit/engine/test_universe_hard.py` | `admn_item_yn=='N'` · `tr_stop_yn=='N'` · `etf_etn_ivst_heed_item_yn=='N'` · `lstg_abol_dt` 없음 · **`ptp_item_yn=='N'`(미국 hard)** · `|etp_chas_erng_rt_dbnb| ≤ 1`(레버리지·인버스 자동 배제) · 탈락 종목은 신규매수 금지하되 기존 보유는 HOLD | 07 §15, 계획 02 §2.3, 00 §7 | ☐ | |
| **S22-2** | as-of 재평가 (lookahead 방지) | `src/omra/engine/universe.py`(2차), `tests/unit/engine/test_universe_asof.py` | 백테스트에서 **현재 플래그를 과거에 적용하지 않고** 마스터 PIT 스냅샷으로 as-of 재평가 · 위반 시 C2 lookahead 탐지가 잡음 | 07 §15, 계획 02 §2.3, 15 §6 | ☐ | |
| **S22-3** | 랭킹 점수·교체 제안 | `src/omra/engine/universe.py`(3차), `tests/unit/engine/test_universe_rank.py` | soft 랭킹 점수(비용·유동성·추적오차 등) · 교체 제안은 **`approved_substitutes` 1:1 페어 안에서만**(P4 = A1) · 목록 밖 종목 제안 금지 | 07 §15, 계획 02 §2.2, 00 §3.2 P4·P5 | ☐ | |

### S23 — 백테스트 커널

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S23-1** | `BacktestSpec`·`CostModel`·`spec_hash` | `src/omra/backtest/spec.py`, `src/omra/backtest/costs.py`, `tests/unit/backtest/test_spec.py` | 사양 모델 + 결정론 `spec_hash` · 수수료·거래세·슬리피지·환전 스프레드 · **보수적 가정** 명시 · `RunKind`·`SimMode` enum | 15 §2·§5.2, 계획 02 §8.1 | ☐ | |
| **S23-2** | `BarView` 윈도우 접근자 | `src/omra/backtest/barview.py`, `tests/unit/backtest/test_barview.py`, `tests/property/test_inv_barview.py` | **전략이 미래를 볼 수 있는 API 자체를 만들지 않는** 구조적 lookahead 방지(zipline `BarData` 패턴) · `as_of` 이후 접근 시 예외 · property: 임의 시점에서 미래 데이터 노출 0 | 15 §6, 계획 00 §4 | ☐ | |
| **S23-3** | `SimLedger` in-memory 원장 | `src/omra/backtest/ledger.py`, `tests/unit/backtest/test_simledger.py` | `SimAccount`·`SimPosition` · **라이브 원장과 계산 로직 공유**(freqtrade 이중 원장 패턴) · 이동평균단가 계산이 `tax` 규약과 동일 | 15 §4, 계획 00 §4, 02 §5.1 | ☐ | |
| **S23-4** | 체결 시뮬·자산 생애주기 | `src/omra/backtest/broker_sim.py`, `src/omra/backtest/corporate.py`, `tests/unit/backtest/test_fill_sim.py` | `CloseFillSimulator` t+1 종가 체결·수량/틱 라운딩·거부 사유 · 자산 생애주기(`start_date`/`end_date`/`auto_close_date`) 청산 · CA 비율 조정·배당/분배금 | 15 §5.1·§5.3·§5.6, 계획 00 §4 zipline | ☐ | |
| **S23-5** | 일간 시뮬 커널 `engine_loop` | `src/omra/backtest/engine_loop.py`, `tests/integration/test_engine_loop.py` | 하루 = 8단계 고정 순서 · `SimClock` 주입 · 10년 시뮬이 결정론(동일 seed → 동일 결과) | 15 §3 | ☐ | |
| **S23-6** | `BacktestRunner`·결과 파일·`backtest` CLI | `src/omra/backtest/runner.py`, `src/omra/backtest/result.py`, `src/omra/cli/`(backtest 명령), `tests/integration/test_backtest_cli.py` | 사양 → 시뮬 → 지표 → 게이트 → 결과 파일 · `tools` 컨테이너에서만 실행(app에서 호출 시 거부) · 스냅샷 나이 임계(`tools.snapshot_max_age_h`) 초과 시 실행 거부 · **10년 1회 실행 시간 VPS 실측** | 15 §2·§14.3, 01 §7.3 [DD-01-12] | ☐ | |

### S24 — 백테스트 게이트·lookahead·Walk-Forward

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S24-1** | lookahead 자동탐지 (C2) | `src/omra/backtest/lookahead.py`, `tests/unit/backtest/test_lookahead.py` | 날짜 필터 위반·미래 데이터 접근 자동 탐지 · **C2는 완화 대상이 아님**(계획 04 §2 M2 게이트 미통과 절차 ③) · 의도적 위반 픽스처를 100% 검출 | 15 §9, 계획 02 §8.2 | ☐ | |
| **S24-2** | 게이트 레지스트리·C1·C3 스냅샷 회귀 | `src/omra/backtest/gates/base.py`, `.../core.py`, `src/omra/backtest/snapshot.py`, `tests/snapshots/**`, `tests/unit/backtest/test_gates_core.py` | `Gate` ABC·`GateResult`·`GateRegistry` · C1(성과)·C2(lookahead)·C3(스냅샷 회귀) · 스냅샷 갱신 프로토콜(사람 검토 필수) · 종료 코드 0/1/2/3 분기 | 15 §10.1~§10.3, 계획 02 §8.2 | ☐ | |
| **S24-3** | Walk-Forward·CPCV 분할 러너 | `src/omra/backtest/walkforward.py`, `tests/unit/backtest/test_wf.py` | WF 분할·in-sample 대비 붕괴 판정 · CPCV 분할(위성 게이트 S1의 전제, M7에서 소비) | 15 §8 | ☐ | |
| **S24-4** | 성과지표·tear sheet | `src/omra/backtest/stats/metrics.py`, `.../report.py`, `.../bootstrap.py`, `tests/unit/backtest/test_metrics.py` | **자체 지표가 게이트 판정의 정본**이고 QuantStats tear sheet는 사람용 전용 · stationary block bootstrap 유틸(MC 공용) | 15 §11~§12 | ☐ | |
| **S24-5** | 가드 A/B 게이트 (`clean` vs `with_guards`) | `src/omra/backtest/modes.py`, `src/omra/backtest/gates/guard_ab.py`, `tests/unit/backtest/test_guard_ab.py` | `sim_mode` 2종 조립 · 가드·감시 개입 on/off 비교 · **필수 포함 구간 2020-02~04 / 2022 전년 / 2024-08** · CI 병합 조건(J8) | 15 §7·§10.5, 계획 03 §4.4, 04 §2 M2 추가5 | ☐ | |
| **S24-6** | J8 백테스트 게이트 CI·config 변경 트리거 | `.github/workflows/ci.yml`(J8), `tests/unit/backtest/test_ci_trigger.py` | `config/*.yaml` 변경이 스냅샷 회귀를 트리거(잡 산출물 `var/policy/`는 제외) · J8이 `tools` 이미지에서 실행 · 경로 필터 누락이 곧 미검증임을 테스트로 고정 | 16 §9.3·§10.2, 계획 04 §2 M2 추가3 | ☐ | |

### S25 — 실험 원장·EX-1 밴드 복귀 실험

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S25-1** | 실험 원장 L1·`experiment ingest` | `src/omra/labs/models.py`, `src/omra/labs/experiments.py`(1차), `src/omra/cli/`(experiment ingest), `tests/unit/labs/test_experiments.py` | `experiments`·`experiment_events` append-only 적재 · 사양 해시·기간·결과 기록 · `distinct_spec_count()`가 **DSR의 N**을 산출 · tools 산출 JSON → app CLI 적재 단방향 경로 | 14 §13, 03 §3.3.11, 01 §7.3, 계획 07 §13 | ☐ | |
| **S25-2** | EX-1 밴드 복귀 실험 실행·판정 | `docs/experiments/ex-1.md`, `config/config.yaml`(`band.restore_fraction` 확정) | 현행 `0.5d`(부분 복귀 50%) vs `ρ·b`(ρ ∈ {0.75, 0.875, 1.0}) 비교 · **`single` 계좌 모델로 수행** · 각 시도를 실험 원장에 기록 · **결과가 애매하면 현행 50% 유지하고 M10 이후로 넘긴다** | 계획 04 §2 M2 추가1·§4.4-2, 02 §4.3 | ☐ | |
| **S25-3** | 회전율 분포 산출·P11 이월 상한 재설정 | `docs/experiments/turnover-distribution.md`, `config/config.yaml`(`protections.p11.*`) | 밴드 트리거 1회당 회전율 분포 산출 → **P11 이월 상한을 95백분위 × 1.5로 재설정** · 실제 연간 밴드 트리거 횟수를 부산물로 얻어 계획 07의 관측 기간 가정 재산정 | 계획 04 §2 M2 DoD, 03 §1.2 | ☐ | |
| **S25-4** | 아키텍처 테스트 AT-8~AT-17 | `tests/arch/test_code_rules.py`(확장), `tests/arch/test_boundaries.py`(확장) | AT-8 strict 섬 시그니처 · AT-9 float 금지 · AT-10 CANO 부재 · AT-11 `write_session` 안 `await` 금지 · AT-12 상태 문자열 리터럴 비교 금지 · AT-13 문서↔설정 대조 · AT-14~AT-17 scheduler 역방향·LLM 격리·backtest 규율 | 16 §6.3 | ☐ | |

---

## M3 — dry-run 라이브 루프 + 감시 정책층

> **진입 게이트**: M2 게이트 최초 통과
> **DoD** (계획 04 §2 M3): VPS 2주 연속 무인 구동(크래시 0, 재시작 복원 검증 1회) · 감사로그에 전 결정 기록 · **`SV3` 자산 주문 0건 property 테스트 통과** · 소스 전면 장애 하루를 주입해도 계획이 변하지 않음을 dry-run으로 실증(스냅샷 유예)

### S26 — 상태 3평면·제약 결합

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S26-1** | 상태 벡터 테이블·축별 결합 | `src/omra/protections/state/vectors.py`, `.../combine.py`, `tests/unit/protections/test_combine.py` | 상태 → `ConstraintVector` 테이블(03 §2.1 5축 표 전재) · 축별 결합(`min`/`min`/`AND`/`max`/`min`) · **매도 축은 AND가 아니다**를 property로 고정 · 3평면(전역·슬리브·부재) 결합 | 09 §7.1~§7.2, 계획 03 §2.1 | ☐ | |
| **S26-2** | `StateView` 읽기 표면 | `src/omra/protections/state/view.py`, `tests/unit/protections/test_stateview.py` | 소비자용 읽기 전용 값 객체 · `protections` 내부 심볼 직접 import 금지 규율에서 **유일한 예외** · 3평면 스냅샷 + `safe_mode_reasons` | 09 §7.3 [DD-09-1] | ☐ | |
| **S26-3** | `SafetyFacade` 단일 표면 | `src/omra/protections/__init__.py`, `src/omra/protections/base.py`, `tests/unit/protections/test_facade.py` | 외부(execution·scheduler·rpc)가 보는 유일한 표면 · `Protection` ABC·`ProtectionContext`·`ProtectionResult`·`BreakerGrade`·`Action` 타입 · **C09 계약**(protections → execution·engine.optimizer/rebalancer 금지) green | 09 §2.1~§2.3 [DD-09-1·2], 01 §8.2 C09 | ☐ | |
| **S26-4** | 상태 전이 엔진 골격 | `src/omra/protections/state/machine.py`(1차), `src/omra/persistence/repos/state.py`(연결), `tests/unit/protections/test_machine.py` | 전이표·`assert_transition`(표 밖 전이 전부 금지) · `bot_state`·`sleeve_state`·`presence` 영속 · `prev_state` 갱신 규칙(진입 시 `prev_state ← cur`) · **전이는 발생 시점에 즉시 커밋** | 09 §7.4~§7.5, 03 §3.2.1 [DD-03-27] | ☐ | |
| **S26-5** | 상태 enum 자리 확보 (M3 범위) | `tests/unit/protections/test_state_enum.py` | `SAFE_MODE`의 **전이 규칙 구현은 M4**지만 열거형에는 M3에서 자리를 만든다(나중에 상태를 추가하면 persistence 마이그레이션이 필요) · 6값 전부 DB에 저장 가능함을 실증 | 계획 04 §2 M3 | ☐ | |

### S27 — 감시 정책층 (착수 순서 1위의 후반부)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S27-1** | `catalog.py` — SV 등급 매핑 | `src/omra/surveillance/catalog.py`, `config/surveillance.yaml`, `tests/unit/surveillance/test_catalog.py` | `risk_type → SV 등급` 매핑을 config로 외부화 · 순수 조회기(부수효과 없음) · `SV0` 기록 / `SV1` 알림 / `SV2` 신규매수 금지 / `SV3` 거래 동결 · **청산은 등급이 아니라 별도 타입 `ESC_REPLACE`/`ESC_LIQUIDATE`** | 11 §8.1·§11.1, 04 §5.7, 계획 00 §5.1 | ☐ | |
| **S27-2** | `flags.apply` — 파생 상태 재도출 | `src/omra/surveillance/flags.py`(1차), `tests/unit/surveillance/test_flags_apply.py` | 일 1회 전수 폴에서 재도출 · **`override_*` 4컬럼 보존** · 음성 관측 행 기록 · 종목 판정은 `instrument_key` **exact match만**(이름 매칭·유사도 금지) · 미해결은 `"UNRESOLVED:{payload_hash}"` | 11 §9, 06 §7.1·§9.1 | ☐ | |
| **S27-3** | `flags.level_of` — 신선도 우선·`unknown` 유예 | `src/omra/surveillance/flags.py`(2차), `tests/unit/surveillance/test_level_of.py` | 각 소스 `max_age`(잠정 2거래일) · **전일 성공 스냅샷이 `max_age` 이내면 그것을 사용** · `unknown`은 "한 번도 관측 안 됨 또는 스냅샷 초과"일 때만 · **`unknown = SV2`**(매수만 차단, 전체 HALT 아님) · **소스 장애 하루는 아무것도 바꾸지 않는다** | 11 §9, 계획 04 §2 M3 | ☐ | |
| **S27-4** | `gate.py` — 소비자 API 6종 | `src/omra/surveillance/gate.py`, `tests/unit/surveillance/test_gate.py` | `level_of` · `reasons` · `partition_by_tradability` · `blocked_for_buy` · `assert_tradable` · `frozen_nav_ratio` · pull 방식만(감시가 주문을 만들지 않음) | 11 §10, 계획 01 §3.6 | ☐ | |
| **S27-5** | `partition_by_tradability` 결선·불변식 | `src/omra/engine/rebalancer.py`(마스크 주입), `tests/property/test_inv_tradability.py` | `daily_rebalance_check` 진입부 결선 · `SV3` 자산은 드리프트 계산에서 **고정 비중**(분모에 남되 조정 대상 제외) → 재정규화 → 정수화 → 주문 · **불변식: `SV3` 자산에 대한 주문 0건**(property-based, M3 DoD) | 11 §10, 계획 04 §2 M3 | ☐ | |
| **S27-6** | 감시 전용 repos 결선·소스 장애 실증 | `src/omra/persistence/repos/surveillance_flags.py`(결선), `tests/integration/test_surv_outage.py` | 소스 전면 장애 하루를 주입해도 **계획이 변하지 않음**을 dry-run으로 실증(M3 DoD) · `pending_transfers` 쓰기가 감시에서 차단됨(C05b 계약, E7 불변식 1의 기계화) | 03 §4.3, 01 §8.2 C05b, 계획 04 §2 M3 DoD | ☐ | |

### S28 — `scheduler/`·`monitoring/` 오케스트레이션

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S28-1** | 잡 선언 모델·시간 예산 타입 | `src/omra/scheduler/spec.py`, `src/omra/scheduler/budget.py`, `tests/unit/scheduler/test_spec.py` | `JobSpec`·`CatchUpClass`·`LedgerMode`·`TriggerSpec`·`BudgetSpec` · 시간 예산은 취소가 아니라 **협조적 체크포인트** · `BudgetExhausted` | 12 §3·§6, 계획 01 §1.4-3 | ☐ | |
| **S28-2** | run ledger 도메인 API | `src/omra/scheduler/ledger.py`, `tests/unit/scheduler/test_ledger.py` | `(run_date, venue, task_name)` PK · status 5값 · **동일 `run_date`에 `done`인 잡은 어떤 경우에도 재실행하지 않는다** · `venue='SYS'` 네임스페이스 | 12 §7, 03 §3.2.1, 계획 01 §4.2.1 | ☐ | |
| **S28-3** | `JobRegistry`·커버리지 불변식 (SC-10) | `src/omra/scheduler/registry.py`, `tests/unit/scheduler/test_registry.py` | 선언적 재등록 · **§4.2의 모든 잡이 catch-up 3분류 표의 한 행에 속함**을 기동 셀프체크 SC-10과 CI가 함께 단정 · 동적 등록(미국 잡) 경로 | 12 §3.3·§4.2, 계획 01 §4.2.1 | ☐ | |
| **S28-4** | 잡 카탈로그 리터럴 전개 | `src/omra/scheduler/catalog.py`, `tests/unit/scheduler/test_catalog.py` | 계획 01 §4.2 시각표의 **코드 대응물** — 전 잡의 `JobSpec` 리터럴 · 기본값 `max_instances=1`·`coalesce=True`·`misfire_grace_time=<시간 예산>` · 미구현 잡은 명시적 스텁 | 12 §4, 계획 01 §1.4·§4.2 | ☐ | |
| **S28-5** | `SchedulerService` — APScheduler 래핑 | `src/omra/scheduler/service.py`, `tests/unit/scheduler/test_service.py` | `AsyncIOScheduler` 임베드(T-01) · 수명 관리·수동 트리거 · **모든 잡 발화 직전 `data/KILL` 검사** · CPU-bound 단계는 `asyncio.to_thread` 오프로드 | 12 §3.4, 01 §4.4 [DD-01-4]·§6.4 | ☐ | |
| **S28-6** | catch-up 3분류 판정기 | `src/omra/scheduler/catchup.py`, `tests/unit/scheduler/test_catchup.py` | `none`(재실행 안 함) / `until HH:MM`(창 안이면 catch-up, 밖이면 skip+알림) / `always`(즉시 catch-up) · 집행 계열은 **대사 통과 전 주문 금지**를 그대로 따름 | 12 §8, 계획 01 §4.2.1 | ☐ | |
| **S28-7** | `DailyPlanner` 07:00 잡·서브스텝 | `src/omra/scheduler/planner.py`, `tests/integration/test_daily_planner.py` | **하드 예산 10분**(07:00~07:10) · 서브스텝(토큰 선제 갱신·휴장일 교차검증·동적 잡 등록·환율 스냅샷·헬스체크·시크릿 만료 점검·부재 사다리 평가) + 감시 폴 3종 합산 300초 · **`signal_and_plan`(07:30)은 감시 폴 완료를 기다리지 않는다** | 12 §5, 계획 01 §4.2~§4.3 | ☐ | |
| **S28-8** | heartbeat·loop lag·`HealthReport` | `src/omra/monitoring/heartbeat.py`(확장), `src/omra/monitoring/health.py`(확장), `tests/unit/monitoring/test_health.py` | heartbeat 잡 · loop lag 계측 · `/healthz` 항목 카탈로그(heartbeat 나이·DB 쓰기·토큰·loop lag·WS 상태·감시 신선도)의 M3 범위분 · `collect()` | 12 §11~§12, 계획 01 §6.4 | ☐ | |

### S29 — `realtime/` 집행 가드 (축소 방향 전용)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S29-1** | 판정 객체·입력 DTO·틱 저장소 | `src/omra/realtime/verdict.py`, `.../context.py`, `.../ticks.py`, `tests/unit/realtime/test_verdict.py` | `Verdict` 4값(`PROCEED`/`DEFER`/`SHRINK`/`ABORT`)·`GuardOutput`(frozen)·`Counterfactual` · `GuardContext`·`GuardBudgets`·`BasketWeights` · `LatestTickStore`(최신값 슬롯)·`MinuteBucketSeries`(60초 버킷) · **C06b 계약**(realtime → persistence 전체 금지) green | 11 §3~§4.2 [DD-11-2], 01 §8.2 C06b | ☐ | |
| **S29-2** | 일방향 밸브 합성 규칙 | `src/omra/realtime/verdict.py`(2차), `tests/property/test_inv_oneway.py` | 산출이 `{PROCEED, DEFER, SHRINK, ABORT}` + 가격 힌트로 **제한**됨 · `sides`는 축소만 가능(AT-3 property) · **수량·방향·목표비중을 생성할 수 없음**을 타입과 아키텍처 테스트로 고정 | 11 §3, 01 §8.3 AT-3, 계획 00 §5 원칙 9 | ☐ | |
| **S29-3** | 3-AND 발동 조건 `ArmingTracker` | `src/omra/realtime/arming.py`, `tests/unit/realtime/test_arming.py` | 3-AND 발동 조건 구현 · 오발동 방지 · 발동/해제 히스테리시스 | 11 §4.3 | ☐ | |
| **S29-4** | `PriceGuard`·`MoveGuard` | `src/omra/realtime/guards.py`(1차), `tests/unit/realtime/test_guards.py` | 가격 이상치·급변 가드 · `MoveGuard.min_symbols: 2`는 **보수 해석 채택**(11 §20.4 이견 기록) · 거래정지·VI 판정은 소유하지 않음(surveillance 단독) | 11 §4, 계획 01 §2.3 | ☐ | |
| **S29-5** | `GuardChain` 오케스트레이션·오류 경로 | `src/omra/realtime/guards.py`(2차), `tests/unit/realtime/test_guard_chain.py` | 가드 체인 합성 · 핸들러 예외 격리(warning + 감사로그, **3회 연속 시 해당 가드 비활성 + critical**) · 연속 실패 카운터는 `execution_state`에 영속(복원은 M4 SC-9) | 11 §4, 계획 01 §2.4·§3.5 | ☐ | |
| **S29-6** | `guard_monitor` 매시 잡 결선 | `src/omra/scheduler/catalog.py`(결선), `tests/integration/test_guard_monitor.py` | `drift_monitor` → `guard_monitor` 개칭 · "알림 전용" → "알림 + **축소 방향** 가드 발동 가능" · **드리프트 밴드 재판정은 하지 않는다** · 집행 창 밖에서는 T0 채널과 REST 스냅샷만 사용 | 계획 04 §2 M3, 01 §4.2 | ☐ | |

### S30 — `execution/` 골격 + DryRun E2E

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S30-1** | `order_lock`·`ExecutionContext` | `src/omra/execution/locks.py`, `src/omra/execution/context.py`, `tests/unit/execution/test_locks.py` | 프로세스 전역 단일 `asyncio.Lock` · **`order_lock`을 잡은 채 다른 락을 기다리는 코드 금지**(순서는 언제나 `order_lock` → `token_lock`) 아키텍처 테스트 · 의존성 주입 컨테이너 | 08 §2, 01 §4.3, 계획 01 §1.4-2 | ☐ | |
| **S30-2** | 주문 조립 `assembler`·`OrderDraft` | `src/omra/execution/assembler.py`, `tests/unit/execution/test_assembler.py` | plan(비중 dict) + 레그 목록 → `Order` 조립 · **`LegKind` 폐지, `OrderDraft.origin: OrderIntent` 직접 사용**([DD-08-2]) · `mandatory_orders` 병합 지점 · `PlannedLeg.origin → OrderDraft.origin → Order.intent` **전 구간 항등 사상**을 계약 테스트로 고정 | 08 §4.1~§4.2, 00 §4.2, 02 §7.2 [DD-02-17] | ☐ | |
| **S30-3** | `router.py` — `AccountMode` 분기의 유일한 지점 | `src/omra/execution/router.py`, `tests/unit/execution/test_router.py` | `AUTO`/`BROKER_SCHEDULED`/`INSTRUCTION` 분기 · **상위 리밸런서는 분기를 모른다**를 아키텍처 테스트로 고정 · SP-C4 결과가 config 값 전환으로 흡수됨 | 08 §2·router, 계획 00 §5-2, 02 §1.2 | ☐ | |
| **S30-4** | pre-trade 체인 — 단계 정의·러너 | `src/omra/protections/pretrade_spec.py`, `src/omra/execution/pretrade.py`, `tests/unit/execution/test_pretrade.py` | **단계 정의·순서의 정본은 09**, 08은 시그니처·호출 지점·오류 매핑 · `PretradeRejection`을 러너 경계에서 전부 잡아 **판정 객체 1개로 변환** · 러너 밖 전파 0(누출 테스트) · 단계 2.5 `tax.assert_not_blocked`는 M4 스텁 | 09 §6, 08 §5.1, 02 §10.2 규칙 1 [DD-02-20] | ☐ | |
| **S30-5** | 주문 제출 프로토콜 `submitter` | `src/omra/execution/submitter.py`, `tests/unit/execution/test_submitter.py` | **persist-then-submit**(orders 레코드 커밋 → 제출) · AT-2 호출 순서 아키텍처 테스트 · `AmbiguousOrderState` 시 신규 주문 금지 + `SUBMITTING` 유지 · 고아 판정·`EXPIRED_UNKNOWN` 경로(해소는 M4) | 08 §5, 계획 01 §3.2 | ☐ | |
| **S30-6** | `DryRunBroker`·`PaperExecutionEngine` | `src/omra/brokers/paper.py`, `tests/unit/brokers/test_paper.py` | 체결 시뮬레이터 — **분기는 이 클래스 선택 하나뿐** · 지정가 매수가 한도 위로 체결되지 않음(V5-07) · 부분 체결·거부 시뮬 | 05 §4, 계획 04 §2 M3 | ☐ | |
| **S30-7** | 집행 창 공통 루프·KRX 창 | `src/omra/execution/windows/base.py`, `.../krx.py`, `tests/integration/test_krx_window.py` | 승인 전제 확인 · 시간 예산 체크포인트 · **매도 선행** · `krx_execute` 10:00–14:30(개장·폐장 30분 회피) · 미체결 잔량 이월 없음 | 08 §windows, 계획 01 §4.2, 02 §4.1 | ☐ | |
| **S30-8** | 미집행 주문 감사로그 결선 | `src/omra/execution/guards_client.py`, `src/omra/backtest/unexecuted.py`, `tests/unit/execution/test_unexecuted.py` | `Verdict != PROCEED`인 **모든 판정**에 `counterfactual`(가상 체결가·수량) 기록 · `blocked_by` 8값 · **여기서 안 만들면 M5 이후 소급 계산이 불가능**하므로 M5보다 반드시 앞선다 | 03 §7.2 [DD-03-25·34], 15 §7.3, 계획 04 §2 M3 | ☐ | |

### S31 — `rpc/` 알림·브리핑·Telegram

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S31-1** | rpc 포트 Protocol·import 계약 | `src/omra/rpc/ports.py`, `tests/arch/test_boundaries.py`(rpc 절) | `StateControl`·기타 포트 Protocol 선언 · 구현체는 조립 시 주입 · **`rpc`는 다른 패키지를 런타임 import 하지 않는다** · **C13 계약**(rpc → web 금지) green | 13 §2.2·§2.4 [DD-13-2], 01 §8.2 C13 | ☐ | |
| **S31-2** | 알림 타입·채널 ABC·Telegram 채널 | `src/omra/rpc/message.py`, `src/omra/rpc/channels/base.py`, `.../telegram.py`, `.../logch.py`, `tests/unit/rpc/test_channels.py` | `Notification`·`NotificationKind`·`AlertGrade`·`DedupKey`·`Rendered` · `RPCChannel` ABC는 `send()`만 · `TelegramChannel`(발송) + `TelegramApp`(폴링 수신) · `LogChannel` 항상 on | 13 §3.1, 계획 01 §1.5 | ☐ | |
| **S31-3** | `RPCManager` 브로드캐스트 파이프라인 | `src/omra/rpc/manager.py`, `tests/unit/rpc/test_manager.py` | 멀티채널 브로드캐스트 · 등급 라우팅 · **집행 전제 기록**(브리핑 발송 성공이 당일 자동 집행의 전제) | 13 §3.2, 계획 03 §3 | ☐ | |
| **S31-4** | 일일 브리핑 조립 | `src/omra/rpc/briefing.py`, `tests/unit/rpc/test_briefing.py` | 08:30 브리핑 1건 통합: 전일 성과 + 오늘 계획 + 당일 확인코드 + "10:00 자동 집행 예정, /reject로 취소" + 전일 가드 개입 N건 1줄 집계 | 13 §4, 계획 01 §4.2 | ☐ | |
| **S31-5** | Telegram 명령 카탈로그·인증·파서 (M3 범위) | `src/omra/rpc/commands/catalog.py`, `.../auth.py`, `.../parser.py`, `.../handlers/`, `tests/unit/rpc/test_commands.py` | `/status /balance /pause /resume /stop` · `chat_id` allowlist · 시도 제한 · 인자 파서·오류 응답 · 나머지 명령은 M4 | 13 §6.1~§6.5, 계획 04 §2 M3 | ☐ | |

### S32 — dry-run E2E·부재 감지·property 불변식

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S32-1** | 일일 사이클 E2E (dry-run) | `tests/integration/harness.py`, `tests/integration/test_daily_cycle.py` | 셀프체크 → 판정 → 계획 → 브리핑 → 시뮬 체결 → 장부 → EOD 전 구간 · 재시작 복원 검증 1회 · **감사로그에 전 결정 기록** | 계획 04 §2 M3 DoD, 01 §4.2 | ☐ | |
| **S32-2** | 부재 감지 골격 `presence` | `src/omra/protections/presence.py`(1차), `tests/unit/protections/test_presence.py` | `last_seen` 추적(Telegram 명령 / 대시보드 로그인 / 브리핑 읽음) · `PresenceState` 4값 전이 · **M4의 `SAFE_MODE` 사다리가 이 위에 올라간다** | 09 §11, 계획 04 §2 M3 | ☐ | |
| **S32-3** | property 전략·불변식 INV-01~INV-14 | `tests/property/strategies.py`(확장), `tests/property/test_inv_*.py` | 공용 전략(Instrument·가격·현금·포지션·계획) · 불변식 14종 · `SV3` 주문 0건·`guard.oneway`·quantize 예산 준수 등 | 16 §4.2 | ☐ | |
| **S32-4** | `with_guards` 백테스트 모드 결선 | `src/omra/backtest/modes.py`(확장), `tests/unit/backtest/test_with_guards.py` | 가드·감시 개입이 백테스트에서 재현됨 · 미집행 주문이 `UnexecutedOrder` → `GuardVerdictPayload`로 매핑 | 15 §7·§7.3 | ☐ | |
| **S32-5** | 통합 하네스·`FaultInjector` 골격 | `tests/integration/faults.py` | `Fault`·`FaultPoint` 프리미티브 · in-memory SQLite · `SimClock` 시간 압축 재생(monkeypatch 없이) | 16 §7.1~§7.2 | ☐ | |

---

## M4 — KIS 모의 E2E + 안전장치·무인성 완성

> **진입 게이트**: dry-run 2주 무사고
> **DoD 겸 M5 진입 게이트 10항목** (계획 04 §2 M4): ①모의계좌 4주 연속 무사고 ②그 4주간 실제 리밸런싱 ≥2회 + SP-E3 계측 주문 누적 30건 ③백테스트 게이트 CI green 유지 ④kill switch 실사격 ⑤전환 체크리스트 전 항목 서명 ⑥부재 시뮬레이션 통과(12월 3중 충돌 판정 포함) ⑦알림 이중화 실사격 ⑧자가치유 실사격 ⑨장애주입 F1~F22 전 항목 green ⑩dead-man's switch ping 실패 주입 1회
>
> ⚠ **이 마일스톤이 [R1]("별다른 앱 조작 없이")의 실질 구현부다.** 상태 모델을 실전 이후에 바꾸는 것은 실전 이전에 바꾸는 것보다 훨씬 비싸고 위험하다(계획 04 원칙 ④·⑥).

### S33 — KIS 주문 TR + T0 실시간 채널

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S33-1** | KIS 주문·취소·체결조회 TR | `src/omra/brokers/kis/client.py`(5차), `tests/contract/kis/test_order.py` | 주문(`TTTC0802U`/`TTTC0801U`)·취소·체결조회 TR · **client order id 필드 유무 확인**(있으면 `Order.id` 탑재, 없으면 튜플 매칭) · 모의 도메인 카세트 | 05 §7.4, 계획 01 §3.2, 04 §5.2 | ☐ | |
| **S33-2** | 정정 TR `_replace_live` | `src/omra/brokers/kis/client.py`(6차), `tests/contract/kis/test_replace.py` | 정정 TR + `broker_order_org_no` 필수 처리 · replace 규약 3항(어느 단계에서 실패해도 REST 재조회로 확정) | 05 §7.4, 계획 01 §3.2 | ☐ | |
| **S33-3** | P9 통지 배선·거부 사유코드 매핑 | `src/omra/brokers/kis/client.py`(7차), `src/omra/protections/breakers/p9_errors.py`(연결), `tests/unit/brokers/test_p9_tagging.py` | 거부 사유코드 → **VI·거래정지 유래는 P9 카운트 제외** · P9-order·P9-quote 분리 · venue 분리 | 05 §7.4, 09 §breakers, 계획 04 §2 M4 추가① | ☐ | |
| **S33-4** | `KisWsSession` 생명주기·재연결 | `src/omra/brokers/kis/ws/session.py`, `tests/unit/brokers/test_ws_session.py` | 백오프 1→2→…→60s full jitter · 10회 연속 실패 시 당일 REST 폴백 모드 · **장중 30초 무메시지 → 강제 재연결**(장중 여부 술어를 생성 인자로 주입) · `start_delay` 인자 · PINGPONG | 05 §7.5 [DD-05-1], 계획 01 §5.3 | ☐ | |
| **S33-5** | 구독 레지스트리·예산 분기 | `src/omra/brokers/kis/ws/registry.py`, `tests/unit/brokers/test_ws_registry.py` | 예산 41/38/9 · **`used + requested > 38`이면 등록 거부 + 해당 종목 REST 폴백 + warning**(어서션이 아니라 명시적 분기) · 종목 상한 9개 하드캡 · **축약 사다리 L0/L1/L2는 만들지 않는다** | 05 §7.6, 계획 00 §6.3, 06 §1.3 | ☐ | |
| **S33-6** | WS decoder — 프레임 파싱·AES256·체결통보 | `src/omra/brokers/kis/ws/decoder.py`, `src/omra/brokers/kis/ws/events.py`, `tests/contract/kis/test_ws_decode.py` | 프레임 파싱·AES256-CBC 복호 · 체결통보 2건(`H0STCNI0`/`H0GSCNI0`) → `Fill` · **핸들러 주입**(brokers가 surveillance·realtime을 import하지 않음) · 예외 격리 3연속 시 가드 비활성 + critical | 05 §7.7 [DD-05-1], 계획 01 §2.4 | ☐ | |
| **S33-7** | `fill_queue`·T-07 `fill_consumer` 배선 | `src/omra/runtime/bot.py`(phase C 확장), `src/omra/execution/tracker.py`(1차), `tests/integration/test_fill_queue.py` | `fill_queue` 무제한(maxsize=0) · **Fill 절대 drop 금지** — 인위적 소비 지연 하에 1만 건 주입 → 전량 소비 단정 · 1,000건 초과 warning · 예외 시 이벤트를 큐에 되돌리고 재시작 | 01 §4.1 T-07·§4.3 [DD-01-3], 계획 01 §2.4 | ☐ | |
| **S33-8** | `approval_key` 발급·07:00 세션 재수립 | `src/omra/brokers/kis/auth.py`(3차), `src/omra/scheduler/planner.py`(결선), `tests/integration/test_ws_reestablish.py` | `daily_planner` 07:00에 approval_key 재발급 + T0 세션 재수립 · WS 3소켓 **3초 간격 순차 재수립**(`start_delay` 0/3/6초) · 재발급이 기존 세션에 미치는 영향은 S17-5 실측값 반영 | 05 §5, 01 §4.3, 계획 01 §5.3 | ☐ | |

### S34 — 서킷브레이커 P1~P11

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S34-1** | 브레이커 레지스트리·체인 실행기 | `src/omra/protections/registry.py`, `src/omra/protections/chain.py`, `tests/unit/protections/test_chain.py` | 선언 순서 로딩·스코프 분류(PLAN/ORDER)·체인 평가·결과 합성 · 등급 3분류(A 무결성 / B 시장 / **B\*** / C 자기 행위) | 09 §3.3~§3.4, 계획 03 §1.1 | ☐ | |
| **S34-2** | P1·P1b — 계좌 MDD·TWR 지수 | `src/omra/protections/breakers/p1_mdd.py`, `tests/unit/protections/test_p1.py` | MDD −15% → **비대칭 해제**(매도 계속 차단, 매수는 사람 승인 하 허용) · −25%(P1b) → 전면 `HALTED`(등급 B\*, 부재 사다리 자동 강등 비적용) · TWR 지수 산출 | 09 §breakers, 계획 03 §1.1~§1.2, 00 §3.2 S2 | ☐ | |
| **S34-3** | P2·P3·P4·P5·P6 — ORDER 스코프 | `src/omra/protections/breakers/p2_p3_daily.py`, `.../p4_cooldown.py`, `.../p5_p6_quote.py`, `tests/unit/protections/test_order_scope.py` | P2 일일 건수·P3 일일 금액(등급 C — 날짜 경과 시 자동 해제, **2일 연속 시 등급 A 격상**) · P4 종목 쿨다운 · P5 가격 이상치 · P6 스프레드 | 09 §breakers, 계획 03 §1.1~§1.2 | ☐ | |
| **S34-4** | P7·P7-cond·P10·P11 — 계획 품질·회전율 | `src/omra/protections/breakers/p7_sanity.py`, `.../p10_p11_turnover.py`, `tests/unit/protections/test_plan_scope.py` | P7 MVO-HRP 괴리(임계 20%p, `SanityResult` 소비) · P7-cond 공분산 조건수 · P10 월 회전율 상한 · **P11 일일 회전율 예산**(이월 상한은 S25-3 실측값) | 09 §breakers, 계획 03 §1.2, 07 §9 | ☐ | |
| **S34-5** | P9-order·P9-quote 분리·점검 신호 소비 | `src/omra/protections/breakers/p9_errors.py`, `tests/unit/protections/test_p9.py` | **VI·거래정지로 인한 주문 거부는 P9 연속 오류 카운트에서 제외**(착수 순서 1위와 짝을 이루는 나머지 절반) · venue 분리 · 업비트 점검성 응답(503)은 P9 미소비 | 09 §breakers, 계획 04 §2 M4 추가① | ☐ | |

### S35 — `SAFE_MODE`·순매수 회계·부재 사다리

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S35-1** | `SAFE_MODE` 전이·`safe_mode_reasons` refcount | `src/omra/protections/state/machine.py`(2차), `tests/unit/protections/test_safe_mode.py` | 정의는 "매도 금지"가 아니라 **"목표비중 하향 방향의 매도 금지"** · `safe_mode_reasons` JSON 배열(복수 사유 refcount — **전부 해소되어야 복귀**) · 밴드 2배 확대 · cash-flow first 계속 | 09 §7.4~§7.5, 계획 03 §2.1, 04 §2 M4 추가① | ☐ | |
| **S35-2** | `safemode_filter`·`SAFE_MODE_SELL_DROP` | `src/omra/execution/assembler.py`(2차), `tests/unit/execution/test_safemode_filter.py` | 금지 4종(목표 하향 매도·하베스팅 자동 매도·위성 축소 매도·기타) 제거 · `SAFE_MODE_SELL_DROP`에 **`TARGET_SHIFT` 편입**(08 §4.4) · **`order.intent in SAFE_MODE_SELL_DROP`** 단일 판별 키 · 07→08 배선이 빠지면 판별 불가임을 계약 테스트로 고정 | 08 §4.4, 00 §4.2, 09 §6.3 | ☐ | |
| **S35-3** | 순매수 회계 `netbuy.py` | `src/omra/protections/netbuy.py`, `tests/unit/protections/test_netbuy.py`, `tests/property/test_inv_netbuy.py` | committed/settled 2계 회계 · 상한 **일 NAV 3% / rolling 30일 NAV 10%** · 도달/초과 판정 · `order_lock` 안에서 원자적 갱신 · **순매수 상한 초과는 등급 B\***(HALTED, 자동 강등 비적용) | 09 §9, 계획 03 §2.1~§2.4 | ☐ | |
| **S35-4** | 순매수 상한 사전 투영 | `src/omra/execution/assembler.py`(3차), `tests/unit/execution/test_netbuy_projection.py` | 조립 단계에서 상한을 **사전 투영**해 제출 전 축소 · 초과 예상 레그를 미집행 감사로그에 기록(`blocked_by=SAFE_MODE_CAP`) | 08 §4, 03 §7.2 | ☐ | |
| **S35-5** | 부재 사다리·실효 grace 클램프 | `src/omra/protections/presence.py`(2차), `tests/unit/protections/test_presence_ladder.py` | HALT + 무응답 24h + 등급 B/C → `SAFE_MODE` 자동 강등 · 무응답 72h + 등급 A → 자동 재개 없음, 일 1회 자가진단 재시도 · **어떤 경우에도 자동으로 평시 `RUNNING` 복귀는 없다** · `/away 30d` 제공하되 **선언 없이도 무응답 감지로 같은 상태에 수렴** · 등급 B\*는 강등 비대상 | 09 §11, 계획 03 §5.3.2, 04 §2 M4 추가① | ☐ | |
| **S35-6** | Kill Switch·확인코드·`/panic` | `src/omra/protections/killswitch.py`, `src/omra/rpc/confirmcode.py`, `tests/integration/test_killswitch.py` | `data/KILL` 워처 · 당일 확인코드 생성·검증 · `/panic` → 미체결 전량 취소 → `STOPPED` 영속 → critical(프로세스는 종료하지 않음) · `STOPPED` 탈출은 KILL 제거 선행 → `/resume <확인코드>` → 목적지 `SAFE_MODE` · **실사격 1회** | 09 §10, 계획 03 §2.6, 04 §2 M4 DoD④ | ☐ | |
| **S35-7** | `failsafe.py` 기본값 실행기 | `src/omra/protections/failsafe.py`, `tests/unit/protections/test_failsafe.py` | fail-safe 기본값 표의 실행기 · **기본 목적지는 `STOPPED`가 아니라 `SAFE_MODE`**(계획 00 §5 원칙 10) · 장부 무결성 의심(등급 A)에만 `HALTED` | 09 §12, 계획 03 §3, 00 §5 원칙 10 | ☐ | |

### S36 — P12~P15 · 감시 결합 · 세금 오버레이 스텁

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S36-1** | P12~P15 감시 유래 브레이커 | `src/omra/protections/breakers/p12_p15_surv.py`, `tests/unit/protections/test_p12_p15.py` | P12 감시 소스 침묵(복구 시 `prev_state` 복귀) · P13 동결 자산 비중 >NAV 20% → `SAFE_MODE`, 40% 초과 시에만 HALT(등급 B\*) · P14 기한부 미승인 · **P15 감시 이벤트 폭증 `max(4건, 30%)` — 등급 C이나 해제는 A5(수동)** | 09 §breakers, 계획 03 §1.1~§1.2, 04 §2 M4 추가① | ☐ | |
| **S36-2** | 이벤트 폭증 판정·소스 신선도·주간 헬스 리뷰 | `src/omra/surveillance/flags.py`(3차), `tests/unit/surveillance/test_health.py` | `source_freshness()`·`health_review()` — P12·healthcheck 입력 · 0건 의심 판정 · 주간 감시 소스 헬스 리뷰 | 11 §8.4.3·§13.2 | ☐ | |
| **S36-3** | `SAFE_MODE` × `SV3` 상호작용·`frozen_reserve` | `src/omra/engine/rebalancer.py`(5차), `tests/unit/engine/test_frozen_reserve.py` | 감시 동결로 인한 **비대칭 재정규화(축소 방향)는 `SAFE_MODE`에서 허용** · `frozen_reserve`가 **매수 레그 재원**과 `cash.buffer` 판정에서 제외됨 · **현금이 아니라 가상 예약**임을 타입으로 강제 | 계획 04 §2 M4 추가①, 02 §4.2, 03 §2.3 | ☐ | |
| **S36-4** | 감시 gate pre-trade 통합·오발동 튜닝 | `src/omra/execution/pretrade.py`(2차), `docs/experiments/surv-false-positive.md` | 주문 직전 `surveillance.gate.assert_tradable(order)`를 **pull**로 호출 · 모의 4주간 오발동률 기록·임계 재캘리브레이션 · **오발동 정의**: `SV2`/`SV3` 부여 (종목, 사유) 중 동일 영업일 재확인으로 사유 부재 확인된 건 · **`unknown → SV2`는 오발동이 아니라 별도 `unknown_rate`** | 계획 04 §2 M4 추가②, 11 §10 | ☐ | |
| **S36-5** | `TaxOverlayPort` 프로토콜·M4 스텁 | `src/omra/execution/context.py`(2차), `src/omra/tax/__init__.py`(스텁), `tests/unit/execution/test_tax_stub.py` | M4는 **판정만** 검증 — `tax_overlay` 스텁이 12월 3중 충돌 우선순위 ①상폐 D−10 > ②하베스팅 D\*−2 > ③밴드 리밸런싱을 올바르게 반환 · `SAFE_MODE` 예외 판정(E7은 실행, 하베스팅은 금지) · **주문 생성 없음** | 10 §2.2, 계획 04 §2 M4 부재 시뮬레이션 | ☐ | |
| **S36-6** | `ESC_*` 제안·기한부 이벤트·수동 오버라이드 | `src/omra/surveillance/flags.py`(4차), `tests/unit/surveillance/test_escalation.py` | `ESC_REPLACE`/`ESC_LIQUIDATE` **제안만**(A3 30일 → 무행동, **영구**) · `deadline_at` → P14 입력 · MANUAL 행 `override_level` 하향 · **자동 청산 경로 부재**를 아키텍처 테스트로 고정 | 11 §9, 계획 00 §3.2 S5·§6.1 | ☐ | |

### S37 — 대사·자가치유·체결 추적

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S37-1** | 체결 추적 `tracker`·미매칭 보류 | `src/omra/execution/tracker.py`(2차), `tests/unit/execution/test_tracker.py` | `broker_exec_id` dedup(체결통보·REST 중복 반영 방지) · 타이머 취소 · 순매수 회계 갱신 호출 · 쿨다운 카운터 갱신 · 매칭 실패 체결은 `unmatched_fills`로 보류 + `unmatched_fill` 감사 이벤트 | 08 §7, 03 §3.3.16 [DD-08-11] | ☐ | |
| **S37-2** | 재호가 `repricer` — 상한 3회 | `src/omra/execution/repricer.py`, `tests/unit/execution/test_repricer.py` | 5분×3(KRX·미국 대안) · **3분기 판정**: ①지정가가 최우선 반대호가 밖 → 재호가(카운트 +1) ②marketable AND 부분체결 → SKIP(카운트 미소비) ③marketable이나 체결 0 → 재호가 · `next_up`/`next_down` 1틱씩 · **시장가 폴백 없음** · 행 단위 체인 추적 | 08 §repricer, 계획 02 §4.1.1, 04 §2 M9 | ☐ | |
| **S37-3** | 주문 품질 게이트 `quality` | `src/omra/execution/quality.py`, `tests/unit/execution/test_quality.py` | 호가단위 정규화 호출 · iNAV·LP 스프레드 게이트(**REST 스냅샷 30분×3 경로가 기본**) · 스프레드 3틱 판정(`ticks_between`) · 대량 분할 TWAP · 1회 주문 상한 | 08 §quality, 계획 02 §4.4 | ☐ | |
| **S37-4** | 고아 주문 해소·`EXPIRED_UNKNOWN` 종결 | `src/omra/execution/submitter.py`(2차), `tests/integration/test_orphan.py` | 재기동 후 튜플 매칭 ±5분 → `kind=orphan_order` 화이트리스트 · 3영업일 무관측 시 `CANCELLED`(`unknown_expired`) 종결 · **F21**(제출 직후 SIGKILL → 고아 흡수, P8 미발동) green | 08 §7.4 [DD-08-8], 02 §7.1 [DD-02-18], 계획 01 §3.2 | ☐ | |
| **S37-5** | 대사 화이트리스트 매칭 엔진 | `src/omra/protections/whitelist.py`, `src/omra/persistence/repos/reconcile.py`(결선), `tests/unit/protections/test_whitelist.py` | 매칭 규칙 AND 5개 · `scheduled_fill`의 금액 1급 키 · `orphan_order` 시스템 자동 등록 · 멱등 유니크 인덱스 준수 · `amount_tolerance > 0` 강제 | 09 §5.2, 03 §3.2.2 [DD-03-3] | ☐ | |
| **S37-6** | `external_expectations_sync` 잡 | `src/omra/scheduler/catalog.py`(결선), `config/external_schedules.yaml`, `tests/integration/test_expectations_sync.py` | **트리거 3개**(매월 1일 02:20 + 기동 셀프체크 SC-8 + YAML 해시 변경) · 당월+익월 30일분 전개 · 멱등 키 `(source, account_id, kind, instrument_key, expected_date_from)` · **이 잡이 없으면 매월 지정일마다 P8(등급 A HALTED)이 발동** | 계획 01 §4.2, 03 §1.3.1 | ☐ | |
| **S37-7** | P8 트리거·자가치유 사다리 | `src/omra/protections/breakers/p8_reconcile.py`, `src/omra/protections/healing.py`, `tests/integration/test_healing.py` | 자가치유 조건 4개: ①체결내역 재조회 3회(10분 간격) 동일 ②불일치가 특정 종목·수량으로 국소화되고 **CA 비율로 정확히 재현** ③현금 불일치 부재 ④목적지는 `RUNNING`이 아니라 `SAFE_MODE` · **금액 임계(NAV 0.5%)를 쓰지 않는다** · 재현 실패 시 HALT 유지 · **실사격 1회**(액면분할 시뮬) | 09 §5.3, 계획 03 §1.3, 04 §2 M4 DoD⑧ | ☐ | |
| **S37-8** | EOD 대사 오케스트레이션 | `src/omra/execution/reconcile.py`, `tests/integration/test_eod_reconcile.py` | `krx_eod`(15:40)·`us_reconcile` 서브스텝 · expectation 소비 · 미체결 종결 · `EXPIRED_UNKNOWN` 재판정 · **환전 재정산 확정분 → `kind=fx_resettle` 화이트리스트 등록**(이 서브스텝이 없으면 미국 결제일마다 P8 발동) | 08 §reconcile, 계획 01 §4.2, 03 §1.3.1 | ☐ | |
| **S37-9** | 가드 예산 영속화·Verdict 소비 | `src/omra/execution/exec_state.py`, `src/omra/execution/guards_client.py`(2차), `tests/integration/test_guard_budget.py` | `(run_date, venue, instrument_key, counter_kind, value)` 영속 · 기동 복원 SC-9 · **복원 실패 시 카운터를 0이 아니라 상한 소진 상태로 가정**(보수 방향) · **F22**(집행 창 도중 재시작 후 당일 가드 예산 누적 유지) green | 08 §exec_state, 01 §5.3-b, 계획 01 §3.5 | ☐ | |

### S38 — 알림 이중화·승인 흐름·웹 대시보드

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S38-1** | 등급 레지스트리·중복 억제·묶음 | `src/omra/rpc/registry.py`, `src/omra/persistence/repos/notifications.py`(결선), `tests/unit/rpc/test_grade_registry.py` | `kind → grade·채널·묶음 정책` 레지스트리 + **CI 완전성 게이트**(등급 미정의 kind 0건) · `Verdict != PROCEED` 기본 등급 **silent** · info는 감시 등급 진입 1회만(동일 종목·사유 재알림 금지) · critical은 계획 03 §7.2 표 ①~⑩ | 13 §3.3, 계획 03 §7.2, 04 §2 M4 추가① | ☐ | |
| **S38-2** | SMTP·Webhook 채널·발송 실패 사다리 | `src/omra/rpc/channels/smtp.py`, `.../webhook.py`, `src/omra/monitoring/notify_watch.py`, `tests/integration/test_notify_dual.py` | SMTP는 **발송 전용, 수신 코드 없음** · **양쪽 모두 실패**할 때만 집행 보류 · **양쪽 실패 2영업일 연속이면 `SAFE_MODE` 전이** · **실사격**: Telegram 차단 상태에서 이메일 폴백으로 브리핑 발송 성공 → 집행 진행 확인 | 13 §2.1, 12 §15, 계획 03 §3, 04 §2 M4 DoD⑦ | ☐ | |
| **S38-3** | 당일 확인코드·2단계 확인·L2/L3 명령 | `src/omra/rpc/commands/confirm.py`, `.../catalog.py`(확장), `tests/unit/rpc/test_confirm.py` | 인라인 2단계 확인 토큰 · L2/L3 등급 명령(`/panic`·`/resume`·`/away`·`/revert`) · 확인코드 검증·시도 제한 | 13 §6.3~§6.4, 계획 03 §2.6 | ☐ | |
| **S38-4** | `ApprovalService` — plan gate·`/reject` | `src/omra/rpc/approvals.py`(1차), `tests/integration/test_plan_gate.py` | 브리핑 → grace 30분(부재 시 최대 12h) → 자동 집행(A2 negative-option) · `/reject`로 당일 취소 · 실효 grace 클램프가 부재 상태를 반영 | 13 §5, 계획 00 §3.2 E1 | ☐ | |
| **S38-5** | A3 승인 큐·타임아웃 스윕·72h 거부권 | `src/omra/rpc/approvals.py`(2차), `src/omra/persistence/repos/approvals.py`(결선), `tests/unit/rpc/test_approval_queue.py` | A3 큐(`approval_requests`) · 타임아웃 기본 동작 = **무행동**(직전 상태 유지) · **2회 연속 미승인 시 critical 격상** · A1 72시간 사후 거부권(`/revert <change_id>`) | 13 §5, 계획 00 §3.1~§3.2 | ☐ | |
| **S38-6** | 웹 인증·세션·CSRF·읽기 경로 | `src/omra/web/security.py`, `src/omra/web/deps.py`, `src/omra/web/routers/auth.py`, `tests/unit/web/test_security.py` | argon2 로그인·세션 쿠키·CSRF · `run_ro` 읽기 헬퍼 · Tailscale 인터페이스 바인딩 · **C12 계약**(web → execution·brokers·engine·tax·protections 금지) green | 13 §7.3·§7.5 [DD-13-2], 01 §8.2 C12 | ☐ | |
| **S38-7** | 대시보드 화면·htmx 조각·차트 | `src/omra/web/routers/pages.py`, `.../fragments.py`, `.../charts.py`, `src/omra/web/templates/**`, `src/omra/web/static/**`, `tests/unit/web/test_pages.py` | 화면(개요·드리프트·주문이력·안전장치 패널) · htmx polling 5~10초 · **Chart.js·htmx 번들 동봉(CDN 금지)** · 시뮬-실전 괴리 건별 기록 화면 | 13 §8.1~§8.3, 계획 01 §1.2, 04 §2 M4 | ☐ | |
| **S38-8** | `/actions` 라우터·`/realtime` 격리 탭 | `src/omra/web/routers/actions.py`, `.../realtime.py`, `tests/unit/web/test_ui_isolation.py` | 상태 변경은 `rpc.commands.handlers` 재사용(웹이 직접 주문 경로를 갖지 않음) · **"지금 매매" 버튼이 존재하지 않음**을 폼 검사 테스트 + C12 계약으로 이중 강제 · 실시간 데이터는 별도 탭에만, Telegram 실시간 가격 알림 기본 off | 13 §8.4·§9.1~§9.2, 계획 01 §1.2 | ☐ | |

### S39 — 운영 자가관리·장애주입·시나리오

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S39-1** | `JobRunner`·실패 정책·알림 등급 | `src/omra/scheduler/runner.py`, `tests/unit/scheduler/test_runner.py` | 원장 전이·예산·락·실패 처리·알림 등급 결선 · `InvariantViolation`은 재시도·삼킴 금지(즉시 `failed` + warning) | 12 §10, 02 §10.2 규칙 2 | ☐ | |
| **S39-2** | 디스크 사다리·dead-man's switch | `src/omra/monitoring/disk.py`, `src/omra/monitoring/dms.py`, `tests/integration/test_dms.py` | 디스크 80% → 로테이션 강화, **90% → 데이터 적재만 중단하고 거래는 유지**(순서 반대 금지) · DMS ping 조건 4가지(브리핑 산출물 / **드리프트 판정 실행 성공** / 대사 / 감시 소스 신선도) · **각각 하나씩 끊어 ping 중단 감지 실증**(M4 DoD⑩) | 12 §12.4·§13, 계획 04 §2 M4 DoD⑩ | ☐ | |
| **S39-3** | 시크릿 자동 조치·부재 겹침 점검 | `src/omra/monitoring/secrets_watch.py`(2차), `tests/integration/test_secret_auto.py` | D-7 → 해당 브로커 슬리브 **`PAUSED_ALL`**(양방향 정지 — `PAUSED`는 매도·정정·취소를 허용해 P9-order 폭주를 막지 못한다) · D-3 → 전체 `SAFE_MODE` · `/away` 선언 시 부재 기간과 겹치는 만료 시크릿 즉시 경고 · **F15 주입 테스트**(DryRun, 만료일 주입) | 12 §14, 04 §8.3, 계획 03 §2.1, 04 §2 M4 | ☐ | |
| **S39-4** | `weekly_maintenance`·백업 관측 | `src/omra/scheduler/catalog.py`(결선), `src/omra/monitoring/backups.py`(2차), `tests/integration/test_weekly.py` | 일요일 03:00 10단계(DB VACUUM·백업 검증·Parquet 무결성·로그 로테이션·카세트 스모크·감시 소스 헬스 리뷰·RO 스냅샷 생성 등) · 분기 복구 리허설 자동 실행, **실패 시에만 알림** | 12 §16~§17, 계획 00 §3.2 O3 | ☐ | |
| **S39-5** | 장애 주입 F1~F11 | `tests/integration/test_f01.py` … `test_f11.py`, `tests/integration/faults.py`(확장) | F1~F11 전 항목 green · 토큰 강제 만료·네트워크 차단·프로세스 kill 후 복구 각 1회 통과 | 16 §7.3, 계획 03 §4.3 | ☐ | |
| **S39-6** | 장애 주입 F12~F22 | `tests/integration/test_f12.py` … `test_f22.py` | F14(폴백 등가성)·F15(시크릿 만료)·F17(`/panic`)·**F18**(환전 재정산 현금 불일치 → 화이트리스트 통과)·**F19**(업비트 점검 503 → P9 미소비, KIS 코어 정상)·**F20**(부재 `AWAY` 중 밴드 breach가 실효 grace 클램프로 당일 집행)·**F21**(SIGKILL → 고아 흡수)·**F22**(재시작 후 가드 예산 누적 유지) green | 16 §7.3, 계획 03 §4.3, 04 §2 M4 DoD⑨ | ☐ | |
| **S39-7** | 시나리오 DSL·L6 케이스 | `tests/scenario/dsl.py`, `.../runner.py`, `.../asserts.py`, `tests/scenario/cases/away_30d.yaml`, `.../dec_triple_conflict.yaml` | 시계열 시나리오 DSL · **30일 부재 시뮬레이션**(등급 B/C HALTED → 무응답 24h → `SAFE_MODE` 자동 강등 → 축소 운용 → 복귀 사다리 1회 실사격, **등급 B\*는 강등되지 않음**도 단정) · **12월 3중 충돌 판정 케이스**(M4는 판정만) | 16 §8.1~§8.3, 계획 04 §2 M4 DoD⑥ | ☐ | |
| **S39-8** | RTM 수거 대장·게이트 증빙 수집기 | `tests/rtm/test_rtm_coverage.py`, `tests/rtm/waivers.yaml`, `tests/gates/gate_report.py` | 설계서 검증 항목 ID(`V<문서>-<일련>`)를 `verifies()` 마커로 수거 · 미커버 항목은 `waivers.yaml`에 사유와 함께 등재해야 통과 · 게이트 증빙 수집기가 무사고 카운터 리셋 판정을 자동화 | 16 §12.2·§13 | ☐ | |
| **S39-9** | 카세트 drift·스모크·폴백 등가성 이중 재생 | `tests/contract/replay.py`(확장), `tests/contract/test_smoke.py` | 주 1회 카세트 스모크 + drift 판정 · **WS 카세트와 REST 카세트를 같은 시나리오로 이중 재생해 판정 결과가 동일함**을 단정(폴백 등가성 — F14와 짝) | 16 §5.4·§5.6 | ☐ | |

### S40 — SP-E3 섀도 계측 하네스 (M9 게이트의 유일한 입력)

> 순환처럼 보이지만 **"구독은 하되 결선하지 않는다"는 섀도 배치**다. M9 취소 여부와 무관하게 지불하는 고정비(+1주)임을 계획 04 §2 M4가 명시한다.

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S40-1** | 섀도 구독·이중 판정 로거 | `src/omra/monitoring/shadow_gate.py`, `tests/integration/test_shadow_gate.py` | 집행 창 한정으로 `H0STNAV0`·`H0STASP0`를 **섀도 용도로만** 구독 · **집행 경로에 결선하지 않음**을 아키텍처 테스트로 고정 · 도메인 분리(시세·NAV = 실전 approval_key, 주문 = 모의 도메인) | 계획 04 §2 M4 추가③ | ☐ | |
| **S40-2** | 게이트 판정 불일치율 계측 (지표 ①) | `src/omra/monitoring/shadow_gate.py`(2차), `docs/spikes/sp-e3-metrics.md` | "REST 스냅샷 1회 판정" vs "실시간 NAV·호가 판정"이 다른 주문의 비율 · **계측 주문 누적 30건 도달까지 의도적 불균형 트리거 반복**(밴드 파라미터는 조작하지 않는다) · 미달 시 M5 실전 4주 관측 합산 | 계획 04 §2 M4 DoD②·M9 게이트 | ☐ | |

---

## M5 — 실전 소액 (국내상장 ETF)

> **진입 게이트**: 모의 4주 무사고 + 전환 체크리스트 전 항목 서명
> **DoD** (계획 04 §2 M5): 실전 4주 무사고 + 리밸런싱 ≥2회 + **tracking error ⑤ 잔차** 정상 + SP-E3 계측 주문 누적 30건 도달
>
> M5는 "사람이 매일 보는 실전"이 아니라 **"한 달 부재해도 죽지 않는 실전"**이다.

### S41 — 실전 전환

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S41-1** | live 3중 일치 검증·전환 체크리스트 | `src/omra/config/constraints.py`(확장), `docs/runbook/live-transition.md`, `tests/unit/config/test_live_confirm.py` | `env: live`면 `live_confirmation` **"<계좌 뒤 4자리>-I-UNDERSTAND" 3중 일치** 검사, 불일치 시 기동 거부(상태 기록 없음) · 최초 기동은 `SAFE_MODE`([DD-01-11]) · 체크리스트 전 항목 서명 | 01 §5.1 A2, 04 §9, 계획 03 §5.1 | ☐ | |
| **S41-2** | `manual_approve` 첫 1주 모드 | `src/omra/config/schema/run.py`(확장), `tests/integration/test_manual_approve.py` | 첫 1주 `manual_approve: true` → 사람 승인 후 집행 · 이후 자동 전환 · 승인 없이 주문 0건 | 계획 03 §5.1-4, 04 §2 M5 | ☐ | |
| **S41-3** | tracking error 5항목 분해 | `src/omra/backtest/tracking.py`, `tests/unit/backtest/test_te_decompose.py` | ①비용 ②체결 시점 ③가드·감시 개입 ④`SAFE_MODE` 제약 ⑤잔차 · `blocked_by` 8값 → TE 항목 전수 매핑(감사로그와 같은 표) · **조사 임계·롤백 트리거 R1은 ⑤ 잔차에만** 적용 | 15 §7.4, 03 §7.2·§7.5, 계획 03 §4.6, 04 §2 M5 | ☐ | |
| **S41-4** | 주간 tracking error 리포트 | `src/omra/web/routers/pages.py`(확장), `src/omra/rpc/briefing.py`(확장), `tests/unit/web/test_te_report.py` | 주간 TE 리포트가 5항목으로 분해되어 표시 · **첫 주부터 가동** | 계획 04 §2 M5 | ☐ | |
| **S41-5** | 증액 스케줄·자금 상한 게이트 | `src/omra/protections/breakers/`(자금 상한 결선), `docs/runbook/scale-up.md`, `tests/unit/protections/test_max_account_value.md` | 초기 자금 300~500만원 · 유니버스는 축소 규칙 N=5 · `max_account_value` hard rail · **배포된 변경이 무사고 카운터를 리셋**하는 규칙(예외: 봇이 import하지 않는 코드·안전장치 hotfix)을 증빙 수집기가 판정 | 계획 03 §5.2, 04 §2 M5·로드맵 원칙 ② | ☐ | |

---

## M6 — 미국 확장 + 세금 엔진 + FX 파이프라인

> **진입 게이트**: 실전 4주 무사고 + **해외 소액 왕복 거래로 정산 방식 실증**(M5 국내 ETF 유니버스 제한의 명시적 예외, M5 DoD 판정에서 제외)
> **DoD** (계획 04 §2 M6): ①미국 모의 2주 + 실전 미국 2주 무사고 ②**12월 3중 충돌 실집행 검증 1회 통과** ③`해외주식 기간손익`(032) vs 자체 이동평균 대사 일치(+국내상장 ETF 첫 매도 시 1회 대사) ④US-01·US-02 감시 플래그 7일 연속 파싱 성공 ⑤FX 스냅샷 3용도가 감사로그에 기록 ⑥`waterfall_gap_check` 드라이런 1회 ⑦`ptp_item_yn` 필터 통과·탈락 종목 목록 문서화 ⑧`HDFSCNT0`·`HDFSASP0` 실지연 실측값 문서화

### S42 — 미국 집행·FX 파이프라인

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S42-1** | 해외 주문 TR·통합증거금 체크 | `src/omra/brokers/kis/client.py`(8차), `tests/contract/kis/test_us_order.py` | 해외 주문/정정/취소/체결조회 TR · 통합증거금 원화 증거금 체크(버퍼 0.5%) · **Blue Ocean 주간거래는 코드 레벨 금지** | 05 §7.4, 계획 00 §6.3, 02 §4.1 | ☐ | |
| **S42-2** | 미국 집행 창 — LOC 기본·장중 지정가 대안 | `src/omra/execution/windows/us.py`, `tests/integration/test_us_window.py` | `us_submit_close`(22:20/23:20 동적, **LOC 기본**) · `us_execute_limit`(config 대안, 장중 지정가 + 재호가 5분×3) · **SP-C3 결과에 따라 기본 경로 확정** · LOC 경로에서는 T1 WS 미구독 | 08 §windows/us, 계획 02 §4.1·§4.5, 04 SP-C3 | ☐ | |
| **S42-3** | FX fetcher·`fx_rate` 라우트 | `src/omra/data/providers/fdr.py`(확장), `src/omra/data/providers/kis.py`(확장), `tests/contract/data/test_fx.py` | `("fx_rate","USDKRW")` fetcher 2종 + 폴백 · Parquet 적재 | 06 §9, 계획 02 §4.7 | ☐ | |
| **S42-4** | `FxService` — 용도별 스냅샷·괴리·절사 | `src/omra/data/fx.py`, `tests/unit/data/test_fx_service.py` | 용도별 스냅샷 시각 3종(판정·주문·세금) · 소스 간 0.5% 괴리 판정 · `krw_floor` 원 단위 절사 · **감사로그 `fx_snapshot_applied` 기록** | 06 §9, 03 §7.2, 계획 02 §4.7 | ☐ | |
| **S42-5** | FX stale 규칙·planning 실패 폴백 | `src/omra/data/fx.py`(2차), `tests/unit/data/test_fx_stale.py` | `StaleDataError` 시 판정 폴백(전일 환율 + 브리핑 표기) · 주문 경로에서는 stale 환율로 제출하지 않음 | 06 §9 | ☐ | |
| **S42-6** | `HDFSCNT0`·`HDFSASP0` 실지연 실측 | `docs/spikes/hdfs-latency.md`, `config/config.yaml`(대안 경로 가격 산정 규칙 확정) | 실지연 실측값 문서화 → **미국 장중 대안 경로의 가격 산정 규칙 확정**(계획 02 §4.1이 이 값에 의존) | 계획 04 §2 M6 DoD⑧·§5.2 | ☐ | |

### S43 — 세금 엔진 코어

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S43-1** | `TaxParamStore` — `tax.yaml` effective-date | `src/omra/tax/params.py`, `tests/unit/tax/test_params.py` | effective-date 버전 선택 · **집행 경로와 집계 경로 분리**([DD-10-13] — 연말 경계 12/30 체결·1/2 결제에서 귀속 연도와 적용 버전이 어긋나지 않게) | 10 §3 [DD-10-13], 04 §5.8 | ☐ | |
| **S43-2** | 원가 산정기·세금 원장 | `src/omra/tax/cost_basis.py`, `src/omra/tax/ledger.py`, `tests/unit/tax/test_ledger.py` | `CostBasisCalculator` ABC + **이동평균단가**(로트 단위 아님) · **결제일 귀속** 단일 원장 · 증권사 실현손익 명세와 1회 대사 | 10 §4, 계획 02 §5.1~§5.2 | ☐ | |
| **S43-3** | 금소세·건보 누적기·과표기준가 스위치 | `src/omra/tax/income.py`, `src/omra/tax/basis_price.py`, `tests/unit/tax/test_income.py` | 연중 손익·배당·분배금·원천징수 집계 · 금소세·건보 임계 추적 · 과표기준가 소스 스위치 `api|fallback` — **SP-C1 결과상 `fallback`이 기본 경로일 가능성이 높음**(실차익 과대추정) | 10 §8·§10, 계획 02 §5.3, 04 부록 B | ☐ | |
| **S43-4** | ISA 소진률 추적기 | `src/omra/tax/isa.py`, `tests/unit/tax/test_isa.py` | **계약기간 누적(contract-to-date)** 소진률(연초 리셋 없음) · 70% 초과 시 ISA 내 매도에 확인 요구 · **`unknown`(개시 잔액 미입력)이면 E7이 A3로 강등** | 10 §9, 계획 02 §5.2, 00 §3.2 E7 | ☐ | |
| **S43-5** | 매도 차단 마스크·`assert_not_blocked` | `src/omra/tax/overlay.py`(1차), `tests/unit/tax/test_blocked.py` | `blocked_for_sell` · `assert_not_blocked`가 `TaxSellBlockedError`(`PretradeRejection` 하위)를 던짐 · **E7 유래 주문(`order.intent is OrderIntent.E7_TRANSFER`)은 면제** — 판별 키가 전 문서 동일함을 계약 테스트로 고정 | 10 §13.2, 02 §10.1·§7.2 [DD-02-17], 계획 02 §5.6-(c) | ☐ | |
| **S43-6** | `tax_overlay`·매도 우선순위 | `src/omra/tax/overlay.py`(2차), `tests/unit/tax/test_overlay.py` | `tax_overlay`가 그날 계획에 세금 유래 레그를 얹음 · 매도 우선순위(현금 조달형 매도의 종목·수량 재배열) · 12월 3중 충돌 우선순위 ①>②>③ | 10 §13, 계획 02 §4.3·§5.6 | ☐ | |
| **S43-7** | `TaxEngine` 파사드·import 규율 | `src/omra/tax/engine.py`, `src/omra/tax/__init__.py`, `tests/arch/test_boundaries.py`(tax 절) | 소비자 계약 4종(`blocked_for_sell`·`mandatory_orders`·`tax_overlay`·`assert_not_blocked`)만 노출 · **C15 계약**(tax → execution·brokers·engine 등 금지) green · `OrderDraft`는 `TYPE_CHECKING` 하에서만 참조 | 10 §2.1~§2.2 [DD-10-2], 01 §8.2 C15 | ☐ | |

### S44 — 세금 엔진 확장 (하베스팅·양도세·E7·T9)

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S44-1** | 하베스팅 시즌·후보·수량 산정 | `src/omra/tax/harvest.py`(1차), `tests/unit/tax/test_harvest.py` | 11/25~12월 평일 · **(종목 × 이동평균단가) 단위** 후보 선정 · 게이트 4종(왕복비용 < 절세액×0.5 / 밴드 위반 없음 / 연 하베스팅 주문금액 ≤ NAV 20% / D\*−2 준수) · `harvest_ledger` 누적 | 10 §11, 계획 02 §5.1.2, 00 §3.2 T3 | ☐ | |
| **S44-2** | 하베스팅 승인 사다리·12월 충돌 조정 | `src/omra/tax/harvest.py`(2차), `tests/integration/test_dec_conflict.py` | **첫 해는 "계산 + 지시서 + 수동 승인"만**(A3), 이듬해부터 A1 · **`SAFE_MODE` 중 자동 실행 금지** · ①E7 > ②하베스팅 > ③밴드 우선순위, ①과 ②가 같은 종목이면 ①이 ②를 흡수 · **12월 3중 충돌 실집행 검증 1회 통과**(M6 DoD②) | 10 §11, 계획 03 §4.7, 04 §2 M6 DoD② | ☐ | |
| **S44-3** | E7 세금 측 절차 `TransferPlanner` | `src/omra/tax/transfers.py`, `tests/unit/tax/test_transfers.py` | `pending_transfers` **행 생성 주체는 tax** · 균등 분할 공식(D−10~D−3) · **상한 4개 전부 AND**(승인 페어 1:1 / 분할 / 2소스 교차 확인 / 과세 이득 계좌 한정) · 불변식 5개 · `SAFE_MODE`에서 실행, `HALTED`·`PAUSED_ALL`·`STOPPED`에서 미실행 | 10 §14, 계획 02 §5.6, 00 §3.2 E7 | ☐ | |
| **S44-4** | E7 집행 측 `transfers.py` | `src/omra/execution/transfers.py`, `tests/integration/test_e7.py` | 상태 전이(`PENDING`→`RUNNING`→`DONE`/`ABORTED`)·`slices_done` 진행 · 기집행 수량은 **컬럼이 아니라 `fills ⨝ orders(intent='e7_transfer')` 파생**([DD-03-36]) · `PlanReason.E7_TRANSFER` 단독 계획 경로 | 08 §14.1, 03 §3.5 [DD-03-36·37] | ☐ | |
| **S44-5** | 양도세 집계·판정·신고서 초안 (T4~T6) | `src/omra/tax/capital_gains.py`, `tests/unit/tax/test_capital_gains.py` | `해외주식 기간손익`(032)으로 연간 실현손익 자동 집계 → **250만원 공제 초과 여부 자동 판정, 미초과 시 개입 0회** · 4월 1일 자동 알림 + 대행신고 딥링크 + 예상세액 + 마감 카운트다운 · 증권사 산출 손익 대사표 · **"이 초안은 참고용이며 증권사 대행신고 산출액이 정본" 문구 삽입 필수** | 10 §12, 계획 00 §3.2 T4~T6, 04 §2 M6 | ☐ | |
| **S44-6** | `waterfall_gap_check` 잡 (T9) | `src/omra/tax/gap_check.py`, `src/omra/scheduler/catalog.py`(결선), `tests/integration/test_gap_check.py` | 11/1 + 12/8·12/15·12/19 09:00 · 연금·IRP·ISA YTD 납입액을 잔고·입금 내역에서 집계 → 공제 한도 잔여 산출 → 잔여 시 **critical** + D-12/D-5/D-1 재알림 · catch-up 창을 12/19까지 확장 · **드라이런 1회**(11/1 이전이면 날짜 주입) | 10 §7, 계획 01 §4.2·§4.2.1, 00 §3.2 T9 | ☐ | |

### S45 — 미국 감시·PTP 검증

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S45-1** | 해외 감시 fetcher·소스 | `src/omra/data/providers/kis_surv.py`(확장), `src/omra/surveillance/sources/kis_overseas.py`, `tests/contract/data/test_overseas_info.py` | 해외 `search_info` — `ovrs_stck_tr_stop_dvsn_cd`·`lstg_abol_item_yn`·**`ptp_item_yn`** · US-01(거래정지)·US-02(상장폐지) · `surv_overseas_poll` 편입 · **7일 연속 파싱 성공**(M6 DoD④) · **Nasdaq halt RSS·EDGAR 8-K는 짓지 않는다** | 11 §2.1, 06 §4.1, 계획 04 §2 M6·부록 A | ☐ | |
| **S45-2** | KR-04 → `pending_tax_events` 결선 | `src/omra/surveillance/sources/kis_stock_info.py`(확장), `src/omra/persistence/repos/pending_tax_events.py`(결선), `tests/integration/test_kr04.py` | KR-04 상폐 확정 감지 → `pending_tax_events` 기록(사실 필드만, 세금 계산 필드 없음) · **2개 소스 교차 확인**(종목마스터 + `CTPF1002R`), 불일치 시 A3 강등 · **`surveillance`는 주문을 생성하지 않는다**(원칙 9) | 11 §8.4, 06 §8.4, 계획 00 §3.2 E7 | ☐ | |
| **S45-3** | `ptp_item_yn` hard 필터 실집행 검증 | `docs/experiments/ptp-filter.md`, `tests/unit/engine/test_ptp.py` | 실제 미국 유니버스에 적용해 **통과·탈락 종목 목록 문서화**(M6 DoD⑦) · IRS §1446(f) 10% 원천징수 회피 근거 명시 | 계획 00 §7, 02 §2.3, 04 §2 M6 DoD⑦ | ☐ | |
| **S45-4** | 세금 원장 repos 결선·정산 대사 | `src/omra/persistence/repos/tax_events.py`(결선), `tests/integration/test_tax_reconcile.py` | `해외주식 기간손익`(032) vs 자체 이동평균 계산 **대사 일치**(M6 DoD③) · 국내상장 ETF도 첫 매도 발생 시 증권사 실현손익 명세와 1회 대사 | 계획 04 §2 M6 DoD③, 02 §5.2 | ☐ | |

---

## M9 — T1 실시간 집행 계층 (**조건부 · 취소 가능**)

> **진입 게이트 — OR 2조건**(하나만 통과해도 착수, **둘 다 실패하면 취소**):
> ① M5 실전 REST 집행의 실체결가 vs 동시각 WS 스냅샷 기준 기대체결가의 implementation shortfall 차이 ≥ 5bp (모의 가상체결가는 산출에 쓰지 않는다)
> ② "REST 스냅샷 1회 판정" vs "실시간 NAV·호가 판정"이 불일치한 주문 ≥ 5%
> ★ **관측 하한**: 조건 ② 판정은 SP-E3 계측 대상 주문이 **30건 이상**일 때만 유효. 미달이면 **판정 불가 = 취소와 동일 처리**
> 전제 조건(AND): SP-E2에서 `H0STNAV0` 수신 가능 + M5 실전 4주 무사고 + 과매매 방지 장치 설계 완료
>
> ⚠ **둘 다 실패하는 시나리오가 기본 시나리오다**(계획 04 부록 B). 취소되면 iNAV 게이트는 REST 스냅샷 경로(30분×3)로 확정되고 T1 설계는 폐기된다. **이것은 실패가 아니라 게이트가 정상 작동한 결과다.**

### S46 — T1 실시간 집행 계층

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S46-0** | **게이트 판정**(코드 아님) | `docs/spikes/m9-gate-decision.md` | 조건 ①②와 관측 하한 30건을 실측값으로 판정하고 **착수/취소를 확정**한다. 취소 시 S46-1~4를 `⊘`로 마감하고 사유를 기록 | 계획 04 §2 M9 진입 게이트 | ☐ | |
| **S46-1** | T1 구독 계획·종목 절단 순서 | `src/omra/brokers/kis/ws/registry.py`(확장), `tests/unit/brokers/test_t1_subscribe.py` | 집행 창 진입 시 당일 `RebalancePlan` 대상 종목만 구독(통상 2~5개) · 창 종료 시 전체 해제 · 절단 순서 `활성 주문 → DEFER 유지 → 다음 슬라이스 후보` · **종목 상한 9개 하드캡** | 05 §7.6, 계획 04 §2 M9 범위 | ☐ | |
| **S46-2** | `kis_ws_market` 감시 소스 | `src/omra/surveillance/sources/kis_ws_market.py`, `tests/unit/surveillance/test_ws_market.py` | `H0STMKO0` → KR-01P·KR-09 · `surveillance.sources.kis_ws_market.enabled` 플래그 전환만으로 활성(**스키마 변경 없음**) | 11 §2.1, 04 [DD-04-14] | ☐ | |
| **S46-3** | iNAV 게이트 실시간 경로·`PremiumGate` | `src/omra/realtime/guards.py`(3차), `tests/unit/realtime/test_premium_gate.py` | 해제 조건 = 게이트 해소 AND 최소 300초 경과 · 연기 3회 상한 · **당일 총 연기 90분 상한** · **REST 경로와 판정 결과가 동일해야 하며 차이는 지연뿐**(폴백 등가성 통합 테스트로 강제) | 11 §4, 계획 04 §2 M9, 02 §4.4 | ☐ | |
| **S46-4** | T1 재호가 3분기·`BookTop` 힌트·불변식 | `src/omra/execution/repricer.py`(2차), `src/omra/realtime/execution_hint.py`, `tests/arch/test_boundaries.py`(realtime 절) | 실시간 정보는 재호가를 **줄이는 데만** 사용 · `marketable limit` 산정 + 호가 나이 검사 · 불변식 CI 강제: `realtime -/-> engine.optimizer`·`engine.rebalancer`·`tax` · **WS는 최적화이지 의존성이 아니다**(전면 장애 시 REST 폴백으로 집행 계속, 정확성 차이 없이 성능 차이만) | 11 §5, 01 §8.2 C06a, 계획 04 §2 M9 불변식 | ☐ | |
| **S46-5** | 사후 철회 경로 | `docs/runbook/m9-rollback.md`, `config/config.yaml`(플래그) | **착수 후에도 조건 ②의 불일치율이 5% 미만으로 떨어지면 T1 구독을 해제하고 REST 경로로 되돌린다** · loop lag 500ms 초과 0회 2주 관측 · 예산 초과 시 REST 폴백 실사격 1회 | 계획 04 §2 M9 DoD | ☐ | |

---

## M7 — 암호화폐 + 모멘텀 위성 (조건부)

> **진입 게이트**: **M6 DoD 전 항목 통과**. 코어 실전이 흔들리면 연기한다.
> **DoD** (계획 04 §2 M7): 업비트 실계좌 소액 4주 무사고 + 김치프리미엄 가드 발동 또는 주입 검증 1회 + `VEA` 도입 시 hard 필터 통과 확인 + **F15 실사격**(실키 만료일 기준 D-7 `PAUSED_ALL` / D-3 `SAFE_MODE`) + **F19 실사격** + 위성 게이트 S1~S4 판정 완료

### S47 — 업비트 어댑터·크립토 슬리브

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S47-1** | `UpbitAuth`·`UpbitBroker` REST 골격 | `src/omra/brokers/upbit/auth.py`, `.../client.py`(1차), `tests/contract/upbit/test_auth.py` | 요청 서명 · 잔고·시세 조회 · **인증 방식은 [확인 필요]로 남아 있던 항목** — 공식 문서 실측 후 확정 · **출금 권한은 절대 활성화하지 않는다**(키 유출 = 자산 유출) | 05 §8.1, 계획 00 §6.4 | ☐ | |
| **S47-2** | 업비트 그룹별 레이트리미터 | `src/omra/brokers/upbit/ratelimit.py`, `tests/unit/brokers/test_upbit_rl.py` | `GroupRateLimiter` + `remaining-req` 헤더 반영 · 그룹별 독립 버킷 | 05 §8.2 | ☐ | |
| **S47-3** | 업비트 주문·3단계 replace·`upbit` 틱 표 | `src/omra/brokers/upbit/client.py`(2차), `src/omra/core/tick.py`(upbit 표 확정), `tests/contract/upbit/test_order.py` | 주문/취소 · 3단계 replace · **`upbit` KRW 마켓 호가단위 구간표 확정**(공식 문서 + 주문 거부 실측 교차 확인) → S02-5의 xfail 테스트 활성화 · `lot_step = 1e-8` · 거래소 최소 주문금액 확인 | 05 §8.3, 02 §6.1·§13 | ☐ | |
| **S47-4** | 업비트 WS public·private (T0 채널) | `src/omra/brokers/upbit/ws/public.py`, `.../private.py`, `.../decoder.py`, `.../events.py`, `tests/contract/upbit/test_ws.py` | public `ticker`(BTC·ETH) + private `myOrder`·`myAsset` · **24/7이라 사람이 자는 동안 사고가 나는 유일한 시장** · **M9를 짓지 않았더라도 별개로 채택** · T-05·T-06 태스크 배선 | 05 §8.4, 계획 04 §1.1 순위 3·§2 M7 | ☐ | |
| **S47-5** | 점검 감지 스트릭·`CryptoCalendar` | `src/omra/brokers/upbit/client.py`(3차), `src/omra/calendar/crypto.py`, `tests/unit/calendar/test_crypto.py` | **업비트에는 점검 상태 API가 없다** — 응답 기반 감지(연속 3회 점검성 응답 503/타임아웃 → 크립토 슬리브 당일 집행 보류, 정상 응답 3회 연속 시 자동 해제) · 그 구간을 `MAINT`로 취급 · **P9 미소비**(F19) | 05 §8.5, 06 §10.4, 계획 01 §4.1, 06 §10 | ☐ | |
| **S47-6** | 크립토 슬리브 vol 스케일·판정·집행 | `src/omra/engine/overlay/crypto.py`, `src/omra/execution/windows/upbit.py`, `src/omra/scheduler/catalog.py`(결선), `tests/integration/test_crypto_execute.py` | `crypto_execute` 09:00이 **슬리브 밴드 판정의 유일한 소유자** · σ_realized EWMA(λ=0.94, 60일) **주 1회 고정 갱신**(일중·일간 갱신 금지) · **BTC 70 : ETH 30 고정, 알트 없음** · 밴드 1%p/30% · marketable limit·3분 재호가 | 07 §11, 계획 02 §7·§3.6, 01 §4.2 | ☐ | |
| **S47-7** | `KimchiGuard`·`CryptoDropGuard`·업비트 감시 | `src/omra/realtime/guards.py`(4차), `src/omra/surveillance/sources/upbit_market.py`, `tests/integration/test_kimchi.py` | 김치프리미엄 가드(분모 = 환율, 분자 상대편 = **글로벌 BTC 시세 소스 확정**) · 급락 가드 · `/v1/market/all?isDetails=true`의 `market_warning`·`market_event`(UP-01·UP-05) · **업비트 공지 파싱은 하지 않는다** · **발동 또는 주입 검증 1회**(M7 DoD) | 11 §4, 계획 02 §7, 06 §10, 04 §2 M7 | ☐ | |

### S48 — 듀얼 모멘텀 위성·위성 게이트

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S48-1** | 듀얼 모멘텀 신호·앙상블 | `src/omra/engine/overlay/momentum.py`(1차), `tests/unit/engine/test_momentum.py` | 듀얼 모멘텀 신호 + 앙상블 · **기본 OFF** · 기본 페어는 `VOO`/`VXUS`(둘 다 계획 02 §2.2 1순위) — **유니버스 밖 종목을 위성이 직접 지명하지 않는다** | 07 §12, 계획 02 §6.1 | ☐ | |
| **S48-2** | 위성 DD 규칙·턴오버·상태 전이 | `src/omra/engine/overlay/momentum.py`(2차), `src/omra/persistence/repos/satellite.py`(결선), `tests/unit/engine/test_satellite_dd.py` | 위성 슬리브 DD −25% 코어 회수는 **"청산"이 아니라 코어로의 이전** · **SAFE_MODE·P1 발동 중에는 `safemode_filter`가 제거** · 슬리브 상한 10%의 손실 봉인 · `satellite_state` 영속 | 07 §12, 계획 00 §6.1, 02 §6 | ☐ | |
| **S48-3** | DSR·시도 수 N·위성 게이트 S1~S4 | `src/omra/backtest/stats/dsr.py`, `src/omra/backtest/gates/satellite.py`, `tests/unit/backtest/test_satellite_gates.py` | S1 CPCV · S2 이웃 안정성 · S3 **DSR**(`N` = `experiments.distinct_spec_count()`) · S4 부트스트랩 + 슬리브 on/off A/B · **게이트 통과 후에만 활성화** | 15 §10.4·§11, 계획 02 §8.2, 05 §6.2 | ☐ | |
| **S48-4** | M7 스파이크·실키 실사격 | `docs/spikes/sp-a8-a9.md`, `docs/spikes/global-btc-source.md`, `tests/integration/test_f15_live.py` | SP-A8/A9(업비트 `market_warning`·`market_event` 실측) · 글로벌 BTC 시세 소스 확정 · **F15 실사격**(실키 만료일 기준 D-7 `PAUSED_ALL` / D-3 `SAFE_MODE` — M4에서는 주입 테스트만) · **업비트 키는 M7 착수 시점에 발급**(KIS와 6개월 이상 분산) | 계획 04 §2 M7, §5.2, 00 §3.2 O1 | ☐ | |

---

## M8 — 목표기반 + 리포팅 + 계좌 자동화

> **진입 게이트**: M5 이후 병행 가능
> **범위 분기**: SP-C4 성공 → **3주**(지시서 UX 사실상 삭제) / 실패 → **6주**(지시서 UX 정식 구현 + 적립식 예약 + 자동이체 폴백)
> **DoD**: 계좌별 sub-target 분해가 IRP 위험자산 ≤70%를 만족하는 property 테스트 통과 · 밴드 표 4행 + 크립토 행이 `band_for`로 실제 조회됨 · 몬테카를로 분기 1회 산출 · LLM 월간 리포트 수치 불변 검증 통과

### S49 — 목표기반 운용

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S49-1** | `goals.yaml` 스키마·glide path | `src/omra/config/files/goals.py`(확장), `src/omra/engine/glide.py`, `tests/unit/engine/test_glide.py` | **전체 HR**(시스템이 자동 변경 불가) · glide 구간 규칙 · **복수 goal 결합 규칙 부재이므로 primary 1개로 좁힘**(07 §21.4 이견) | 07 §13, 04 §5.3, 계획 00 §3.2 P7 | ☐ | |
| **S49-2** | 몬테카를로 블록 부트스트랩 코어 | `src/omra/engine/montecarlo.py`, `tests/unit/engine/test_mc.py` | stationary block bootstrap **단일 엔진** · `numpy.random.Generator` 주입(전역 시드 금지) · 5,000경로 · **매매 경로와 완전 분리 — 모니터링 전용** | 07 §14, 계획 02 §9 | ☐ | |
| **S49-3** | MC 성공확률·팬차트·처방 역산·GK | `src/omra/engine/montecarlo.py`(2차), `src/omra/backtest/mc_runner.py`, `tests/unit/backtest/test_mc_runner.py` | 목표 확률 모니터 · 팬차트 데이터 · Guyton-Klinger ±10% 조정(통보만, **2회 연속 삭감 방향 발동 시에만 재승인**) · `mc_projection` 분기 잡 결선 | 07 §14, 15 §13, 계획 00 §3.2 T8, 02 §9 | ☐ | |
| **S49-4** | 밴드 표 4행 + 크립토 행 결선 | `src/omra/engine/bands.py`(2차), `config/config.yaml`(밴드 표), `tests/unit/engine/test_band_table.py` | 일반위탁 5%p/25% · 연금·IRP(AUTO) 5%p/25% · 연금·IRP(지시서·예약) 7%p/35% · **ISA는 모드 무관 7%p/35%**(비과세 한도를 리밸런싱 실현손익으로 소진하지 않기 위함) · 업비트 1%p/30% · `band_for` 조회 실증 | 계획 02 §4.3, 04 §2 M8 | ☐ | |

### S50 — asset location·워터폴·계좌 자동화

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S50-1** | asset location — `decompose_to_accounts` | `src/omra/tax/asset_location.py`, `src/omra/persistence/repos/decomposition.py`(결선), `tests/property/test_inv_decompose.py` | 계좌별 sub-target 분해 · 계좌 유형별 hard 제약 선형 반영 · **IRP 위험자산 ≤70% property 테스트 통과** · `portfolio_decomposition`(+`_meta`) 영속 | 10 §5, 07 [DD-07-10], 계획 02 §4.3.0 | ☐ | |
| **S50-2** | 워터폴 계산·신규자금 유입 분류 | `src/omra/tax/waterfall.py`(1차), `tests/unit/tax/test_waterfall.py` | 유입 감지 → 워터폴 우선순위 계산 · 일반위탁 내 배분은 자동(A2), 절세계좌 송금은 사람(A3) · **워터폴 계산 자체는 런타임에서 계속 수행**(자동이체는 정기분만 대체) | 10 §6, 계획 00 §3.2 E4·E5 | ☐ | |
| **S50-3** | 이체 지시·`pending_transfer_reserve` | `src/omra/tax/waterfall.py`(2차), `tests/unit/tax/test_transfer_reserve.py` | 이체 지시 생성 · 예약분이 배분 대상에서 제외됨 | 10 §6 | ☐ | |
| **S50-4** | 계좌 hard 제약 시정·legacy 처분 | `src/omra/engine/rebalancer.py`(6차), `tests/unit/engine/test_constraint_cure.py` | 제약 위반 시정 주문에 **`OrderIntent.CONSTRAINT_CURE`** 태그 · legacy 보유(유니버스 밖) 처분 규칙 | 07 §10, 계획 02 §4.3.0-(g) | ☐ | |
| **S50-5** | **[SP-C4 성공 분기]** 절세계좌 직접 주문 | `src/omra/execution/router.py`(확장), `config/config.yaml`(`accounts[].mode: AUTO`), `tests/integration/test_tax_account_auto.py` | `ACNT_PRDT_CD` 22/29/ISA 직접 주문 · **절세계좌 3종에서 실주문 → 체결 → 대사가 2주 무사고** · 상위 리밸런서는 분기를 모름 | 08 §router, 계획 00 §3.2 E2, 04 §2 M8 | ☐ | |
| **S50-6** | **[SP-C4 실패 분기]** 지시서 UX·적립식 예약 | `src/omra/execution/instruction.py`, `config/external_schedules.yaml`(확장), `tests/integration/test_instruction.py` | 지시서 생성·라이프사이클·리마인더 · `source='instruction'` 대사 기대값(발행일~+7일) · ETF 적립식 자동매수 예약 + 은행→증권 월정액 자동이체 폴백 · **지시서 생성 → 사람 이행 → 대사 화이트리스트 통과가 1사이클 완주** · 예약매수 등록분이 `external_expectations_sync`로 전개되어 P8 미발동 확인 | 08 §instruction [DD-08-7], 03 [DD-03-3], 계획 04 §2 M8 | ☐ | |
| **S50-7** | 외부 금융소득 등록·귀속 계산 (T2) | `src/omra/tax/income.py`(2차), `config/external_income.yaml`, `tests/unit/tax/test_external_income.py` | `{원금·이율·만기·지급주기}` 등록 → 매년 자동 계산 · **임계 70% 도달 시에만** 확인 질의, 미응답 시 보수적(과대) 가정 유지 | 10 §8, 04 §5.6, 계획 00 §3.2 T2 | ☐ | |

### S51 — 리포팅·`market_weights` 자동화

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S51-1** | `market_weights` 자동화 (P6) | `src/omra/data/providers/`(holdings CSV), `config/market_weights.yaml`, `tests/unit/data/test_holdings.py` | ETF holdings CSV 파싱으로 **주식 지역 비중만** 월 1회 · 자산군당 5%p 초과 이동 시 자동 적용 금지 + 검토 플래그(A3) · **상위 배분(주식45:채권45:대체10)은 상수로 확정 — 갱신 자체를 폐지** | 계획 00 §3.2 P6, 04 §2 M8 | ☐ | |
| **S51-2** | LLM 월간 리포트 파이프라인 | `src/omra/research/citation.py`(공유), `src/omra/research/`(리포트), `tests/unit/research/test_report.py` | **고정 DAG**(Data-CoT → Concept-CoT → Thesis-CoT) · **숫자는 코드, 글은 LLM** — 수치 provenance 주입 + 사후 수치 불변 검증 · **수치 불변 검증 통과**가 DoD · LLM은 주문 경로 import 불가(C04a) | 14 §citation, 계획 01 §8.1, 00 §4 | ☐ | |
| **S51-3** | 분기 자동 결정 감사 리포트 | `src/omra/labs/reports.py`, `tests/unit/labs/test_reports.py` | 분기별 자동 결정(A0·A1·A2)의 감사 리포트 렌더러 · 사람이 사후 검토할 수 있는 형태 | 14 [DD-14-16], 12 §17.3 | ☐ | |

---

## M10a — 자가 개선: 지식 수집

> **진입 게이트**: **M5 실전 6개월 무사고**. 이 지연은 일정 문제가 아니라 설계 결정이다(계획 04 원칙 ⑧·§4.4-7).
> **DoD** (계획 07 §14.2 6항목): `P0` 소스 4주 연속 수집 · 인용 검증기 오염 100% 검출 · 룰 엔진 HR-1~HR-10 양성/음성 회귀 테스트 · import-linter 실차단 확인 · 다이제스트 1회 LLM 비용 실측·상한 설정 · **읽는 데 10분 이내**
>
> **성공 지표는 "채택한 개선의 수"가 아니라 "놓친 부패의 수 = 0"이다.** 산출물은 읽을거리뿐이며 자동으로 바뀌는 것은 없다.

### S52 — `research/` 지식 수집 파이프라인

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S52-1** | research 모델·설정·`SourceAdapter` ABC | `src/omra/research/models.py`, `.../settings.py`, `.../sources/base.py`, `.../sources/registry.py`, `tests/unit/research/test_models.py` | `RawItem`·`KnowledgeItem`·`ExtractionResult`·`RuleVerdict` · `SourceSpec`·`SourceAdapter`·`SourceState/Health` · 레지스트리 이름이 config 키와 문자 일치 단정 · **C04a 계약**(research → surveillance 등 금지) green | 14 §2.1 [DD-14-1], 01 §8.2 C04a | ☐ | |
| **S52-2** | `P0` 소스 어댑터 4종·상태 영속 | `src/omra/research/sources/github_releases.py`, `.../pypi_json.py`, `.../kis_repo.py`, `.../kr_tax_notice.py`, `tests/contract/research/test_p0_sources.py` | **릴리스노트를 arXiv보다 우선**(우리를 깨뜨리는 것은 논문이 아니라 의존성 변경) · `research_extractions` 적재 · **4주 연속 수집**이 DoD | 14 §3.2, 계획 04 §2 M10a, 07 §14.2 | ☐ | |
| **S52-3** | `P1`·`P2` 소스 어댑터 4종·SP-R1 러너 | `src/omra/research/sources/upbit_docs.py`, `.../arxiv_qfin.py`, `.../practitioner_rss.py`, `.../skfolio_docs.py`, `src/omra/cli/`(research probe), `docs/spikes/sp-r1.md` | arXiv q-fin.PM·블로그 3~5개·제도 공지 · **SP-R1**: 소스 도달성 1주 실측(tools 전용, DB 미기록) | 14 §3.2, 01 §2.3 [DD-01-16], 계획 04 §5.2 | ☐ | |
| **S52-4** | 사전필터·LLM 구조화 추출·비용 원장 | `src/omra/research/prefilter.py`, `.../extract.py`, `tests/unit/research/test_extract.py` | **사전필터를 `extract.py`에서 분리**(LLM은 2단에만) · `KnowledgeItem` 스키마 강제 · `llm_call` 감사 이벤트 + 비용 원장 · **다이제스트 1회 LLM 비용 실측·상한 설정** | 14 §4 [DD-14-1], 계획 07 §4 | ☐ | |
| **S52-5** | 인용 검증기 `citation.py` | `src/omra/research/citation.py`, `tests/unit/research/test_citation.py` | **원문에 없는 수치 생성 차단** · 오염 주입 시 **100% 검출**(DoD) · 월간 리포트와 코드 공유 | 14 §4, 계획 07 §4, 00 §4 FinRobot | ☐ | |
| **S52-6** | 룰 엔진 HR-1~HR-10 | `src/omra/research/rules.py`, `tests/unit/research/test_rules.py` | **결정론, LLM 없음** · HR-1~HR-10 양성/음성 회귀 테스트 통과 | 14 §4.4, 계획 07 §4.4 | ☐ | |
| **S52-7** | 월간 다이제스트·잡 본체·D4 레지스트리 | `src/omra/research/digest.py`, `.../jobs.py`, `config/research_open_questions.yaml`, `tests/integration/test_digest.py` | 결정론 렌더러 · `research_collect`(일 04:00)·`research_rank`(월 1일 05:00)·`research_batch_poll` 잡 · **읽는 데 10분 이내** · `research_open_questions.yaml` D4 소비 · **감시 파이프라인 안에서는 LLM 파싱을 하지 않는다**(`research -/-> surveillance` 실차단 확인) | 14 §5·§10.3, 04 §5.12, 계획 04 §2 M10a | ☐ | |

---

## (보류) — `labs/` 파라미터 챌린저층

> 계획 04 부록 A.1이 **"첫 챌린저 후보가 나오기 전까지 사용처가 없다"**로 보류한 영역이다. 마일스톤 번호를 부여하지 않는 이유는 착수 자체가 조건부이기 때문이다.

### S53 — `labs/` 챌린저·카나리·롤백 (착수 조건 충족 시에만)

> **착수 조건**(계획 04 부록 A.1): M10a 3개월 운영 + 챌린저 후보 1개 이상. **밴드 파라미터는 hard rail이라 챌린저 대상이 될 수 없다** — `rebalance.cooldown_days`를 첫 챌린저로 지정.
> 조건 미충족 시 이 스테이지 전체가 `⏸`이며, 그것이 정상이다.

| 단위 | 제목 | 산출 파일 | 완료 판정(DoD) | 근거 | 상태 | 커밋 |
|---|---|---|---|---|:--:|---|
| **S53-1** | 카나리 α 블렌딩·재시작 복원 | `src/omra/labs/canary.py`, `src/omra/persistence/repos/budget.py`(결선), `tests/integration/test_canary_restore.py` | 대상별 파라미터화(단일 코드) · 사다리 1/3→2/3→1 × 5거래일 · **재시작 전후 α 단계·잔여 거래일 동일**(SC-6) · 경과 거래일은 `step_started_on` 기준(재시작이 단계 시계를 되돌리지 않는다) | 14 §canary, 01 §5.3-a SC-6, 계획 07 §8 | ⏸ | |
| **S53-2** | 변경 예산 `budget.py`·상위 캡 지배 | `src/omra/labs/budget.py`, `tests/unit/labs/test_budget.py` | `policy.change_budget.total_per_year: 6`이 하위 예산(targets 4 / params 4 / logic 2)을 **지배** · 소진 시 모든 자동 변경이 **A3로 강등** · 연 1회(1/1) 리셋 · **P1 3%p 이하·P4b는 예산 미소비** | 14 §budget, 계획 00 §3.2, 07 §9 | ⏸ | |
| **S53-3** | `G0` 사전등록·90일 동결 | `src/omra/labs/experiments.py`(2차), `src/omra/labs/gates.py`(1차), `tests/unit/labs/test_g0.py` | 사전등록 검증 · 90일 동결 · append-only 원장 | 14 §gates, 계획 07 §7.2 | ⏸ | |
| **S53-4** | 게이트 파이프라인 G0~G3·챌린저·섀도 | `src/omra/labs/gates.py`(2차), `.../challenger.py`, `.../shadow.py`, `tests/unit/labs/test_gates.py` | G2는 **별도 프로세스**(`docker compose run --rm tools python -m omra.cli backtest --challenger`) 호출만, 봇은 결과 파일만 읽음 · G3 섀도 결정 차이 4지표 · **자동 승격 상한 = 섀도 단계**, 그 위는 예외 없이 사람 | 14 §challenger·§shadow, 01 §7.3, 계획 07 §7.3 | ⏸ | |
| **S53-5** | 롤백 R1~R5·기동 R5 수신 | `src/omra/labs/rollback.py`, `src/omra/runtime/selfcheck.py`(SC-12 결선), `tests/unit/labs/test_rollback.py` | **프로세스 지표 전용** 롤백 트리거 R1~R5 · R1은 TE ⑤ 잔차에만 반응 · SC-12가 직전 세션의 섀도 불일치·스냅샷 회귀 실패 플래그를 R5로 통지(DEGRADE) | 14 §rollback, 01 §5.2 SC-12, 계획 07 §10 | ⏸ | |
| **S53-6** | C07a/C07b 계약 활성화 확인 | `tests/arch/test_boundaries.py`(labs 절) | `labs` 관련 계약이 실제 코드에서 차단 실증 · `labs → engine` 순수함수 호출은 허용, `labs → execution·brokers·rpc·research` 금지 | 01 §8.2 C07a/b·§8.4, 계획 04 §2 M1 | ⏸ | |

---

## 4. 이 문서의 갱신 이력

| 일자 | 변경 | 커밋 |
|---|---|---|
| 2026-08-05 | 최초 작성 — 53개 스테이지 · 307개 단위 등재 | — |
